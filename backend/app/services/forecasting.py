"""Demand forecasting engine.

Approach (see docs/README.md for the narrative version)
-------------------------------------------------------
1. Build a **dense** daily demand series per product: every calendar day from the
   product's first recorded sale to "today" gets a row, with 0 on days nothing
   sold. Dense-with-zeros matters — sparse series make a slow seller look like a
   fast one.
2. **Data-sufficiency gate.** A product must have at least
   ``min_nonzero_observations`` days with a sale AND at least
   ``min_history_days`` of span. Otherwise we return ``insufficient_data`` and
   forecast nothing. Guessing from three data points would be worse than silence.
3. **Time-ordered hold-out.** The last ``holdout_days`` become the test window;
   everything before is training. Never a random split — that leaks the future
   into the past and flatters the model.
4. **Model bake-off.** Three candidates compete on the same hold-out:
     * ``weighted_moving_average`` - baseline, recent days weighted highest
     * ``simple_exponential_smoothing`` - baseline, statsmodels SES
     * ``gradient_boosting`` - scikit-learn HistGradientBoostingRegressor over
       lag / rolling / calendar features, forecast recursively
   Lowest hold-out MAE wins. Ties break toward the simpler model.
5. **Refit + forecast.** The winner is refit on the *full* history and used to
   predict each day of the horizon; ``predicted_quantity`` is the sum.
6. Everything needed to re-run the forecast (model name, parameters, data window,
   observation counts, every candidate's score) is persisted on the Forecast row.
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DataSufficiency, Forecast, Product, Sale, SaleItem

# statsmodels is chatty about short series; we handle the failure cases ourselves.
warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels")
warnings.filterwarnings("ignore", category=RuntimeWarning)

# MAPE is meaningless when the actual value is ~0 (division blows up), so we only
# average percentage error over days where at least this many units sold.
MAPE_MIN_ACTUAL = 1.0
MAPE_MIN_POINTS = 3


# --------------------------------------------------------------------------
# Series construction
# --------------------------------------------------------------------------
def build_daily_series(
    db: Session, product_id: int, as_of: date | None = None
) -> pd.Series:
    """Units sold per calendar day, zero-filled, indexed first-sale .. as_of."""
    as_of = as_of or date.today()
    rows = db.execute(
        select(Sale.date, SaleItem.quantity)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .where(SaleItem.product_id == product_id, Sale.date <= as_of)
        .order_by(Sale.date)
    ).all()

    if not rows:
        return pd.Series(dtype="float64", index=pd.DatetimeIndex([], name="date"))

    frame = pd.DataFrame(rows, columns=["date", "quantity"])
    frame["date"] = pd.to_datetime(frame["date"])
    daily = frame.groupby("date", as_index=True)["quantity"].sum().astype("float64")

    full_index = pd.date_range(daily.index.min(), pd.Timestamp(as_of), freq="D", name="date")
    return daily.reindex(full_index, fill_value=0.0)


def build_series_map(
    db: Session, product_ids: list[int], as_of: date | None = None
) -> dict[int, pd.Series]:
    """All products' daily series in a single query (avoids N+1 on a full run)."""
    as_of = as_of or date.today()
    if not product_ids:
        return {}

    rows = db.execute(
        select(SaleItem.product_id, Sale.date, SaleItem.quantity)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(SaleItem.product_id.in_(product_ids), Sale.date <= as_of)
    ).all()

    out: dict[int, pd.Series] = {}
    if not rows:
        return {pid: pd.Series(dtype="float64") for pid in product_ids}

    frame = pd.DataFrame(rows, columns=["product_id", "date", "quantity"])
    frame["date"] = pd.to_datetime(frame["date"])
    grouped = frame.groupby(["product_id", "date"], as_index=False)["quantity"].sum()

    for pid in product_ids:
        sub = grouped[grouped["product_id"] == pid]
        if sub.empty:
            out[pid] = pd.Series(dtype="float64")
            continue
        series = sub.set_index("date")["quantity"].astype("float64").sort_index()
        full_index = pd.date_range(series.index.min(), pd.Timestamp(as_of), freq="D", name="date")
        out[pid] = series.reindex(full_index, fill_value=0.0)
    return out


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def mean_absolute_error(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def mean_absolute_percentage_error(actual: np.ndarray, predicted: np.ndarray) -> float | None:
    """MAPE over days with meaningful sales only; None when not computable."""
    mask = np.abs(actual) >= MAPE_MIN_ACTUAL
    if int(mask.sum()) < MAPE_MIN_POINTS:
        return None
    pct = np.abs((actual[mask] - predicted[mask]) / actual[mask])
    return float(np.mean(pct) * 100.0)


# --------------------------------------------------------------------------
# Candidate models
# --------------------------------------------------------------------------
@dataclass
class ModelResult:
    """One candidate's hold-out score and its refit forecast."""

    name: str
    mae: float
    mape: float | None
    params: dict = field(default_factory=dict)
    # complexity is the tie-breaker: lower wins when MAE is effectively equal
    complexity: int = 0
    error: str | None = None


class Candidate:
    name = "base"
    complexity = 0

    def fit_predict(self, train: pd.Series, steps: int) -> np.ndarray:
        raise NotImplementedError

    def params(self) -> dict:
        return {}


class WeightedMovingAverage(Candidate):
    """Flat forecast = linearly weighted average of the last ``window`` days."""

    name = "weighted_moving_average"
    complexity = 1

    def __init__(self, window: int = 14):
        self.window = window

    def fit_predict(self, train: pd.Series, steps: int) -> np.ndarray:
        window = min(self.window, len(train))
        recent = train.to_numpy()[-window:]
        weights = np.arange(1, window + 1, dtype="float64")  # newest day weighted most
        value = float(np.sum(recent * weights) / np.sum(weights))
        return np.full(steps, max(value, 0.0))

    def params(self) -> dict:
        return {"window": self.window, "weighting": "linear (newest = highest)"}


class SimpleExpSmoothing(Candidate):
    """statsmodels SES; alpha estimated by MLE. Flat forecast at the final level."""

    name = "simple_exponential_smoothing"
    complexity = 2

    def __init__(self):
        self._alpha: float | None = None

    def fit_predict(self, train: pd.Series, steps: int) -> np.ndarray:
        from statsmodels.tsa.holtwinters import SimpleExpSmoothing as SES

        values = train.to_numpy(dtype="float64")
        model = SES(values, initialization_method="estimated").fit(optimized=True)
        self._alpha = float(model.params.get("smoothing_level", float("nan")))
        forecast = np.asarray(model.forecast(steps), dtype="float64")
        return np.clip(forecast, 0.0, None)

    def params(self) -> dict:
        return {"smoothing_level_alpha": None if self._alpha is None else round(self._alpha, 4)}


LAGS = (1, 2, 3, 7, 14)
ROLLING_WINDOWS = (7, 14, 28)


def _feature_frame(series: pd.Series) -> pd.DataFrame:
    """Lag + rolling + calendar features. Rolling windows are shifted by one day
    so a row never sees its own target (no leakage)."""
    df = pd.DataFrame({"y": series.astype("float64")})
    df.index = pd.DatetimeIndex(series.index)

    for lag in LAGS:
        df[f"lag_{lag}"] = df["y"].shift(lag)
    shifted = df["y"].shift(1)
    for window in ROLLING_WINDOWS:
        df[f"roll_mean_{window}"] = shifted.rolling(window, min_periods=1).mean()
    df["roll_std_7"] = shifted.rolling(7, min_periods=2).std()

    idx = df.index
    df["dayofweek"] = idx.dayofweek
    df["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    df["day"] = idx.day
    # Kenyan dukas see a payday bump around month-end / month-start.
    df["is_month_start"] = (idx.day <= 3).astype(int)
    df["is_month_end"] = (idx.day >= 27).astype(int)
    df["week_of_year"] = idx.isocalendar().week.to_numpy().astype(int)
    df["trend"] = np.arange(len(df))
    return df


FEATURE_COLUMNS = (
    [f"lag_{lag}" for lag in LAGS]
    + [f"roll_mean_{w}" for w in ROLLING_WINDOWS]
    + [
        "roll_std_7",
        "dayofweek",
        "is_weekend",
        "day",
        "is_month_start",
        "is_month_end",
        "week_of_year",
        "trend",
    ]
)


class GradientBoosting(Candidate):
    """HistGradientBoostingRegressor over lag/rolling/calendar features.

    Multi-step forecasting is recursive: predict day t+1, append it to the
    series, rebuild features, predict t+2, and so on.
    """

    name = "gradient_boosting"
    complexity = 3

    def __init__(self, max_iter: int = 200, learning_rate: float = 0.06, max_depth: int = 4):
        self.max_iter = max_iter
        self.learning_rate = learning_rate
        self.max_depth = max_depth

    def fit_predict(self, train: pd.Series, steps: int) -> np.ndarray:
        from sklearn.ensemble import HistGradientBoostingRegressor

        frame = _feature_frame(train)
        # Drop the warm-up rows where the longest lag is still undefined.
        usable = frame.dropna(subset=[f"lag_{max(LAGS)}"])
        if len(usable) < 10:
            raise ValueError("not enough rows after feature warm-up")

        model = HistGradientBoostingRegressor(
            max_iter=self.max_iter,
            learning_rate=self.learning_rate,
            max_depth=self.max_depth,
            min_samples_leaf=5,
            l2_regularization=1.0,
            random_state=42,  # reproducible: same data in, same forecast out
        )
        model.fit(usable[FEATURE_COLUMNS], usable["y"])

        history = train.copy()
        predictions: list[float] = []
        for _ in range(steps):
            next_day = history.index[-1] + pd.Timedelta(days=1)
            extended = pd.concat(
                [history, pd.Series([np.nan], index=pd.DatetimeIndex([next_day]))]
            )
            features = _feature_frame(extended).iloc[[-1]][FEATURE_COLUMNS]
            value = float(model.predict(features)[0])
            value = max(value, 0.0)
            predictions.append(value)
            history = pd.concat(
                [history, pd.Series([value], index=pd.DatetimeIndex([next_day]))]
            )
        return np.asarray(predictions, dtype="float64")

    def params(self) -> dict:
        return {
            "estimator": "HistGradientBoostingRegressor",
            "max_iter": self.max_iter,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "min_samples_leaf": 5,
            "l2_regularization": 1.0,
            "random_state": 42,
            "features": FEATURE_COLUMNS,
            "multi_step_strategy": "recursive",
        }


def _build_candidates() -> list[Candidate]:
    return [WeightedMovingAverage(window=14), SimpleExpSmoothing(), GradientBoosting()]


# --------------------------------------------------------------------------
# Sufficiency
# --------------------------------------------------------------------------
@dataclass
class Sufficiency:
    ok: bool
    reason: str | None
    observations: int
    nonzero: int
    span_days: int


def assess_sufficiency(series: pd.Series) -> Sufficiency:
    observations = int(len(series))
    if observations == 0:
        return Sufficiency(False, "No sales recorded yet for this product.", 0, 0, 0)

    nonzero = int((series > 0).sum())
    span_days = int((series.index.max() - series.index.min()).days) + 1

    if nonzero < settings.min_nonzero_observations:
        return Sufficiency(
            False,
            f"Only {nonzero} day(s) with a recorded sale; at least "
            f"{settings.min_nonzero_observations} are needed before a forecast is trustworthy.",
            observations,
            nonzero,
            span_days,
        )
    if span_days < settings.min_history_days:
        return Sufficiency(
            False,
            f"Sales history spans only {span_days} day(s); at least "
            f"{settings.min_history_days} are needed.",
            observations,
            nonzero,
            span_days,
        )
    return Sufficiency(True, None, observations, nonzero, span_days)


# --------------------------------------------------------------------------
# The bake-off
# --------------------------------------------------------------------------
@dataclass
class ForecastOutcome:
    sufficient: bool
    reason: str | None = None
    predicted_quantity: float | None = None
    daily_predictions: list[float] = field(default_factory=list)
    model_used: str | None = None
    model_params: dict = field(default_factory=dict)
    mae: float | None = None
    mape: float | None = None
    candidate_scores: list[dict] = field(default_factory=list)
    observations: int = 0
    nonzero: int = 0
    window_start: date | None = None
    window_end: date | None = None
    holdout_days: int = 0


def forecast_series(series: pd.Series, horizon_days: int) -> ForecastOutcome:
    """Run the full gate -> hold-out bake-off -> refit -> forecast pipeline."""
    sufficiency = assess_sufficiency(series)
    if not sufficiency.ok:
        return ForecastOutcome(
            sufficient=False,
            reason=sufficiency.reason,
            observations=sufficiency.observations,
            nonzero=sufficiency.nonzero,
            window_start=series.index.min().date() if len(series) else None,
            window_end=series.index.max().date() if len(series) else None,
        )

    n = len(series)
    # Hold out the configured window, but never more than 30% of history, and
    # always leave at least 21 training days behind.
    holdout = min(settings.holdout_days, max(1, int(n * 0.3)), max(1, n - 21))
    train, test = series.iloc[:-holdout], series.iloc[-holdout:]
    actual = test.to_numpy(dtype="float64")

    scores: list[ModelResult] = []
    for candidate in _build_candidates():
        try:
            predicted = candidate.fit_predict(train, len(test))
            scores.append(
                ModelResult(
                    name=candidate.name,
                    mae=mean_absolute_error(actual, predicted),
                    mape=mean_absolute_percentage_error(actual, predicted),
                    params=candidate.params(),
                    complexity=candidate.complexity,
                )
            )
        except Exception as exc:  # a candidate failing must not kill the run
            scores.append(
                ModelResult(
                    name=candidate.name,
                    mae=float("inf"),
                    mape=None,
                    complexity=candidate.complexity,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    usable = [s for s in scores if math.isfinite(s.mae)]
    if not usable:
        return ForecastOutcome(
            sufficient=False,
            reason="No forecasting model could be fitted to this sales pattern.",
            observations=sufficiency.observations,
            nonzero=sufficiency.nonzero,
            candidate_scores=[_score_dict(s) for s in scores],
            window_start=series.index.min().date(),
            window_end=series.index.max().date(),
        )

    # Winner = lowest MAE; ties (within 1%) go to the simpler model.
    best = min(usable, key=lambda s: (round(s.mae, 6), s.complexity))
    tolerance = best.mae * 1.01 + 1e-9
    best = min([s for s in usable if s.mae <= tolerance], key=lambda s: s.complexity)

    # Refit the winner on the FULL history and forecast the horizon.
    winner = next(c for c in _build_candidates() if c.name == best.name)
    try:
        daily = winner.fit_predict(series, horizon_days)
        final_params = winner.params()
    except Exception:
        # Extremely unlikely (it fitted on the shorter train set), but degrade to
        # the always-available baseline rather than failing the whole run.
        fallback = WeightedMovingAverage(window=14)
        daily = fallback.fit_predict(series, horizon_days)
        best = ModelResult(
            name=fallback.name, mae=best.mae, mape=best.mape, complexity=fallback.complexity
        )
        final_params = fallback.params()

    return ForecastOutcome(
        sufficient=True,
        predicted_quantity=float(np.sum(daily)),
        daily_predictions=[round(float(v), 3) for v in daily],
        model_used=best.name,
        model_params=final_params,
        mae=round(best.mae, 4),
        mape=None if best.mape is None else round(best.mape, 2),
        candidate_scores=[_score_dict(s) for s in scores],
        observations=sufficiency.observations,
        nonzero=sufficiency.nonzero,
        window_start=series.index.min().date(),
        window_end=series.index.max().date(),
        holdout_days=holdout,
    )


def _score_dict(score: ModelResult) -> dict:
    return {
        "model": score.name,
        "mae": None if not math.isfinite(score.mae) else round(score.mae, 4),
        "mape": score.mape if score.mape is None else round(score.mape, 2),
        "error": score.error,
    }


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------
def generate_forecasts(
    db: Session,
    *,
    horizon_days: int | None = None,
    product_ids: list[int] | None = None,
    as_of: date | None = None,
) -> list[Forecast]:
    """Forecast every active product (or the given subset) and persist the rows."""
    horizon_days = horizon_days or settings.default_horizon_days
    as_of = as_of or date.today()

    stmt = select(Product).where(Product.is_active.is_(True))
    if product_ids:
        stmt = stmt.where(Product.id.in_(product_ids))
    products = db.execute(stmt.order_by(Product.name)).scalars().all()
    if not products:
        return []

    series_map = build_series_map(db, [p.id for p in products], as_of=as_of)

    created: list[Forecast] = []
    for product in products:
        outcome = forecast_series(series_map.get(product.id, pd.Series(dtype="float64")), horizon_days)
        forecast = Forecast(
            product_id=product.id,
            horizon_days=horizon_days,
            bucket="daily",
            data_sufficiency_flag=(
                DataSufficiency.sufficient if outcome.sufficient else DataSufficiency.insufficient_data
            ),
            insufficiency_reason=outcome.reason,
            predicted_quantity=(
                None if outcome.predicted_quantity is None else round(outcome.predicted_quantity, 3)
            ),
            model_used=outcome.model_used,
            model_params=json.dumps(
                {
                    **outcome.model_params,
                    "holdout_days": outcome.holdout_days,
                    "bucket": "daily",
                    "as_of": as_of.isoformat(),
                    "daily_predictions": outcome.daily_predictions,
                }
            )
            if outcome.sufficient
            else None,
            error_metrics=json.dumps({"MAE": outcome.mae, "MAPE": outcome.mape})
            if outcome.sufficient
            else None,
            mae=outcome.mae,
            mape=outcome.mape,
            data_window_start=outcome.window_start,
            data_window_end=outcome.window_end,
            observations_used=outcome.observations,
            nonzero_observations=outcome.nonzero,
            candidate_scores=json.dumps(outcome.candidate_scores) if outcome.candidate_scores else None,
        )
        db.add(forecast)
        created.append(forecast)

    db.flush()
    return created


def latest_forecasts(
    db: Session, horizon_days: int | None = None, product_ids: list[int] | None = None
) -> dict[int, Forecast]:
    """Most recent forecast per product, optionally pinned to one horizon."""
    stmt = select(Forecast).order_by(Forecast.generated_at.asc(), Forecast.id.asc())
    if horizon_days is not None:
        stmt = stmt.where(Forecast.horizon_days == horizon_days)
    if product_ids:
        stmt = stmt.where(Forecast.product_id.in_(product_ids))
    out: dict[int, Forecast] = {}
    for forecast in db.execute(stmt).scalars():
        out[forecast.product_id] = forecast  # later (newer) rows win
    return out


def forecast_window(forecast: Forecast) -> tuple[date, date]:
    """The calendar days a stored forecast actually covers (used by the accuracy report)."""
    start = (forecast.data_window_end or forecast.generated_at.date()) + timedelta(days=1)
    return start, start + timedelta(days=forecast.horizon_days - 1)
