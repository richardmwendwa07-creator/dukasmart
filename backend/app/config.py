"""Application settings.

Everything tunable lives here so the forecasting / recommendation behaviour can be
adjusted without touching business logic. Values can be overridden with environment
variables (prefix ``DUKASMART_``) or a ``.env`` file next to the backend folder.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DUKASMART_",
        env_file=str(BACKEND_DIR / ".env"),
        extra="ignore",
    )

    # --- infrastructure -------------------------------------------------
    app_name: str = "DukaSmart"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'dukasmart.db').as_posix()}"
    # NOTE: for a real deployment this MUST be supplied via the environment.
    secret_key: str = "dev-only-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    # "*" for local/dev use — safe here because auth uses a Bearer token, not
    # cookies, so allow_credentials stays False and a wildcard origin is fine.
    cors_origins: str = "*"

    # --- forecasting ----------------------------------------------------
    # A product needs at least this many days with a non-zero sale before we are
    # willing to forecast it. Below this we return `insufficient_data` instead of
    # inventing a number (spec 4.6).
    min_nonzero_observations: int = 10
    # ...and the sales history must span at least this many calendar days.
    min_history_days: int = 28
    # Size of the time-ordered hold-out window used to score competing models.
    holdout_days: int = 14
    # Default forecast horizon when the caller does not specify one.
    default_horizon_days: int = 14
    # Horizons the UI offers.
    allowed_horizons: str = "7,14,30"

    # --- replenishment --------------------------------------------------
    # Safety margin applied on top of forecast (+ lead-time) demand, as a fraction.
    default_safety_margin_pct: float = 0.20

    # --- priority score weights (documented in docs/README.md) -----------
    # Must sum to 1.0; validated at import time below.
    weight_stockout_risk: float = 0.50
    weight_demand_velocity: float = 0.30
    weight_cost_efficiency: float = 0.20

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_horizon_list(self) -> list[int]:
        return [int(h.strip()) for h in self.allowed_horizons.split(",") if h.strip()]


settings = Settings()

_weight_sum = (
    settings.weight_stockout_risk
    + settings.weight_demand_velocity
    + settings.weight_cost_efficiency
)
if abs(_weight_sum - 1.0) > 1e-6:  # pragma: no cover - configuration guard
    raise ValueError(
        f"Priority score weights must sum to 1.0, got {_weight_sum:.4f}. "
        "Check DUKASMART_WEIGHT_* settings."
    )
