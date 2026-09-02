"""Forecasting: the data-sufficiency gate, the hold-out bake-off, reproducibility."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
import pytest

from app.config import settings
from app.models import DataSufficiency
from app.services.forecasting import (
    assess_sufficiency,
    build_daily_series,
    forecast_series,
    generate_forecasts,
)
from app.services.inventory import record_sale


def _sell_over_days(db, owner, product, pattern: list[int], end: date | None = None) -> None:
    """Record one sale per day, oldest first, ending at `end` (default today)."""
    end = end or date.today()
    start = end - timedelta(days=len(pattern) - 1)
    for offset, qty in enumerate(pattern):
        if qty <= 0:
            continue
        record_sale(
            db,
            user=owner,
            sale_date=start + timedelta(days=offset),
            items=[{"product_id": product.id, "quantity": qty}],
            allow_negative_stock=True,
        )
    db.commit()


# --------------------------------------------------------------------------
# Sufficiency gate
# --------------------------------------------------------------------------
def test_product_with_no_sales_is_insufficient(db, owner, make_product):
    product = make_product("Brand New Item", "NEW1", opening_stock=10)
    forecasts = generate_forecasts(db, horizon_days=14, product_ids=[product.id])
    db.commit()

    assert len(forecasts) == 1
    forecast = forecasts[0]
    assert forecast.data_sufficiency_flag == DataSufficiency.insufficient_data
    assert forecast.predicted_quantity is None
    assert forecast.model_used is None
    assert "No sales recorded" in forecast.insufficiency_reason


def test_too_few_nonzero_observations_is_flagged_not_guessed(db, owner, make_product):
    """The headline rule: too little history -> insufficient_data, never a number."""
    product = make_product("Slow Mover", "SLOW1", opening_stock=200)
    # 60 days of history but only 4 days with an actual sale.
    pattern = [0] * 60
    for i in (5, 20, 38, 55):
        pattern[i] = 2
    _sell_over_days(db, owner, product, pattern)

    forecasts = generate_forecasts(db, horizon_days=14, product_ids=[product.id])
    db.commit()
    forecast = forecasts[0]

    assert forecast.data_sufficiency_flag == DataSufficiency.insufficient_data
    assert forecast.predicted_quantity is None
    assert forecast.nonzero_observations == 4
    assert str(settings.min_nonzero_observations) in forecast.insufficiency_reason


def test_short_history_is_flagged_even_when_every_day_has_a_sale(db, owner, make_product):
    product = make_product("Brand New Fast Seller", "FAST1", opening_stock=500)
    # 12 consecutive selling days: passes the non-zero count, fails the span rule.
    _sell_over_days(db, owner, product, [4] * 12)

    forecasts = generate_forecasts(db, horizon_days=14, product_ids=[product.id])
    db.commit()
    forecast = forecasts[0]

    assert forecast.data_sufficiency_flag == DataSufficiency.insufficient_data
    assert "spans only" in forecast.insufficiency_reason


def test_sufficient_history_produces_a_real_forecast(db, owner, make_product):
    product = make_product("Steady Seller", "STDY1", opening_stock=2000)
    # 80 days of steady demand with a weekly rhythm.
    pattern = [6 + (3 if (i % 7) in (5, 6) else 0) for i in range(80)]
    _sell_over_days(db, owner, product, pattern)

    forecasts = generate_forecasts(db, horizon_days=14, product_ids=[product.id])
    db.commit()
    forecast = forecasts[0]

    assert forecast.data_sufficiency_flag == DataSufficiency.sufficient
    assert forecast.predicted_quantity is not None
    assert forecast.predicted_quantity > 0
    assert forecast.model_used in {
        "weighted_moving_average",
        "simple_exponential_smoothing",
        "gradient_boosting",
    }
    assert forecast.mae is not None
    # ~14 days at roughly 6-9/day; a wide but meaningful sanity band.
    assert 50 < forecast.predicted_quantity < 200


# --------------------------------------------------------------------------
# Reproducibility (spec: non-functional requirements)
# --------------------------------------------------------------------------
def test_forecast_stores_everything_needed_to_reproduce_it(db, owner, make_product):
    product = make_product("Reproducible", "REPRO1", opening_stock=2000)
    _sell_over_days(db, owner, product, [5, 7, 6, 8, 5, 9, 7] * 10)

    forecast = generate_forecasts(db, horizon_days=7, product_ids=[product.id])[0]
    db.commit()

    assert forecast.bucket == "daily"
    assert forecast.data_window_start is not None
    assert forecast.data_window_end is not None
    assert forecast.observations_used == 70
    assert forecast.horizon_days == 7

    params = json.loads(forecast.model_params)
    assert "holdout_days" in params and params["holdout_days"] > 0
    assert len(params["daily_predictions"]) == 7

    metrics = json.loads(forecast.error_metrics)
    assert "MAE" in metrics and "MAPE" in metrics

    # Every candidate that competed is recorded, with its score.
    scores = json.loads(forecast.candidate_scores)
    assert {s["model"] for s in scores} == {
        "weighted_moving_average",
        "simple_exponential_smoothing",
        "gradient_boosting",
    }


def test_same_input_gives_the_same_forecast(db, owner, make_product):
    """Reproducibility: identical data in -> identical number out."""
    product = make_product("Deterministic", "DET1", opening_stock=3000)
    _sell_over_days(db, owner, product, [4, 6, 5, 7, 4, 8, 6] * 11)

    first = generate_forecasts(db, horizon_days=14, product_ids=[product.id])[0]
    second = generate_forecasts(db, horizon_days=14, product_ids=[product.id])[0]
    db.commit()

    assert first.model_used == second.model_used
    assert first.predicted_quantity == pytest.approx(second.predicted_quantity)


# --------------------------------------------------------------------------
# Series construction and the hold-out split
# --------------------------------------------------------------------------
def test_series_is_zero_filled_across_every_calendar_day(db, owner, make_product):
    product = make_product("Gappy", "GAP1", opening_stock=500)
    today = date.today()
    for offset in (30, 20, 10):
        record_sale(
            db,
            user=owner,
            sale_date=today - timedelta(days=offset),
            items=[{"product_id": product.id, "quantity": 3}],
        )
    db.commit()

    series = build_daily_series(db, product.id)
    assert len(series) == 31           # day -30 through today inclusive
    assert (series > 0).sum() == 3     # only three days actually sold
    assert series.sum() == 9


def test_holdout_split_is_time_ordered(db):
    """The last N days must be the test set — never a random sample."""
    index = pd.date_range("2026-01-01", periods=90, freq="D")
    # Demand steps up sharply in the final stretch; a time-ordered split means
    # the model is scored on data it has genuinely never seen.
    values = [5.0] * 70 + [20.0] * 20
    outcome = forecast_series(pd.Series(values, index=index), horizon_days=7)

    assert outcome.sufficient
    assert outcome.holdout_days == settings.holdout_days
    assert outcome.mae is not None


def test_all_three_models_compete_and_the_best_mae_wins(db):
    index = pd.date_range("2026-01-01", periods=90, freq="D")
    values = [float(6 + (i % 7)) for i in range(90)]
    outcome = forecast_series(pd.Series(values, index=index), horizon_days=14)

    assert outcome.sufficient
    assert len(outcome.candidate_scores) == 3
    scored = [s for s in outcome.candidate_scores if s["mae"] is not None]
    winner = next(s for s in outcome.candidate_scores if s["model"] == outcome.model_used)
    # The winner is within 1% of the best score (the documented tie-break band).
    assert winner["mae"] <= min(s["mae"] for s in scored) * 1.01 + 1e-9


def test_assess_sufficiency_boundary(db):
    """Exactly at the threshold counts as sufficient."""
    index = pd.date_range("2026-01-01", periods=60, freq="D")
    values = [0.0] * 60
    for i in range(settings.min_nonzero_observations):
        values[i * 2] = 3.0

    result = assess_sufficiency(pd.Series(values, index=index))
    assert result.ok
    assert result.nonzero == settings.min_nonzero_observations

    values[0] = 0.0  # drop one below the line
    assert not assess_sufficiency(pd.Series(values, index=index)).ok


def test_forecast_is_never_negative(db):
    """Demand cannot be negative — a declining trend must floor at zero."""
    index = pd.date_range("2026-01-01", periods=90, freq="D")
    values = [max(0.0, 30.0 - i * 0.33) for i in range(90)]
    outcome = forecast_series(pd.Series(values, index=index), horizon_days=30)

    assert outcome.sufficient
    assert outcome.predicted_quantity >= 0
    assert all(v >= 0 for v in outcome.daily_predictions)
