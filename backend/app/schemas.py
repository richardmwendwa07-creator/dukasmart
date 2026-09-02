"""Pydantic request/response schemas.

Validation lives here so malformed input is rejected with a clear message before
it ever reaches the database (spec §3 "Rules to enforce").
"""

from __future__ import annotations

import json
from datetime import date, datetime

# Alias used where a *field* is called `date` — the assignment would otherwise
# shadow the `date` type inside that class body and break annotation evaluation.
DateType = date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import DataSufficiency, MovementSource, RecommendationStatus, UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: UserRole = UserRole.staff


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(ORMModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# --------------------------------------------------------------------------
# Suppliers
# --------------------------------------------------------------------------
class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact: str | None = Field(default=None, max_length=160)
    notes: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    contact: str | None = Field(default=None, max_length=160)
    notes: str | None = None


class SupplierOut(ORMModel):
    id: int
    name: str
    contact: str | None
    notes: str | None


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=80)
    selling_price: float = Field(gt=0, description="Price the shop sells one unit for")
    default_unit_cost: float = Field(ge=0, default=0, description="Usual cost to buy one unit")
    reorder_lead_time_days: int | None = Field(default=None, ge=0, le=365)
    supplier_ids: list[int] = Field(default_factory=list)
    preferred_supplier_id: int | None = None
    opening_stock: int = Field(default=0, ge=0, description="Units on the shelf right now")

    @field_validator("sku")
    @classmethod
    def _normalise_sku(cls, v: str) -> str:
        return v.strip().upper()


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    selling_price: float | None = Field(default=None, gt=0)
    default_unit_cost: float | None = Field(default=None, ge=0)
    reorder_lead_time_days: int | None = Field(default=None, ge=0, le=365)
    supplier_ids: list[int] | None = None
    preferred_supplier_id: int | None = None
    is_active: bool | None = None


class ProductOut(ORMModel):
    id: int
    name: str
    sku: str
    category: str | None
    selling_price: float
    default_unit_cost: float
    reorder_lead_time_days: int | None
    is_active: bool
    preferred_supplier_id: int | None
    suppliers: list[SupplierOut] = Field(default_factory=list)
    current_stock: int = 0


# --------------------------------------------------------------------------
# Sales
# --------------------------------------------------------------------------
class SaleItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, description="Units sold; must be a whole number above zero")
    # Optional override; defaults to the product's current selling price.
    unit_price_at_sale: float | None = Field(default=None, ge=0)


class SaleCreate(BaseModel):
    date: DateType | None = None
    note: str | None = Field(default=None, max_length=255)
    items: list[SaleItemIn] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def _no_duplicate_products(cls, v: list[SaleItemIn]) -> list[SaleItemIn]:
        ids = [i.product_id for i in v]
        if len(ids) != len(set(ids)):
            raise ValueError("The same product appears more than once. Combine it into one line.")
        return v


class SaleItemOut(ORMModel):
    id: int
    product_id: int
    product_name: str | None = None
    quantity: int
    unit_price_at_sale: float
    line_total: float = 0


class SaleOut(ORMModel):
    id: int
    date: DateType
    total_amount: float
    note: str | None
    user_id: int
    created_at: datetime
    items: list[SaleItemOut] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Purchases
# --------------------------------------------------------------------------
class PurchaseItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity_received: int = Field(gt=0)
    unit_cost: float = Field(ge=0)


class PurchaseCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    date_received: date | None = None
    note: str | None = Field(default=None, max_length=255)
    items: list[PurchaseItemIn] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def _no_duplicate_products(cls, v: list[PurchaseItemIn]) -> list[PurchaseItemIn]:
        ids = [i.product_id for i in v]
        if len(ids) != len(set(ids)):
            raise ValueError("The same product appears more than once. Combine it into one line.")
        return v


class PurchaseItemOut(ORMModel):
    id: int
    product_id: int
    product_name: str | None = None
    quantity_received: int
    unit_cost: float
    line_total: float = 0


class PurchaseOut(ORMModel):
    id: int
    supplier_id: int
    supplier_name: str | None = None
    date_received: date
    total_cost: float
    note: str | None
    user_id: int
    created_at: datetime
    items: list[PurchaseItemOut] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------
class AdjustmentCreate(BaseModel):
    product_id: int = Field(gt=0)
    change_qty: int = Field(description="Positive to add stock, negative to remove")
    note: str = Field(min_length=1, max_length=255, description="Why the count changed")

    @field_validator("change_qty")
    @classmethod
    def _non_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Adjustment cannot be zero. Enter how many units to add or remove.")
        return v


class MovementOut(ORMModel):
    id: int
    product_id: int
    change_qty: int
    source_type: MovementSource
    source_id: int | None
    resulting_stock: int
    note: str | None
    timestamp: datetime


class StockRow(BaseModel):
    product_id: int
    name: str
    sku: str
    category: str | None
    current_stock: int
    selling_price: float
    unit_cost: float
    stock_value_at_cost: float


# --------------------------------------------------------------------------
# Forecasts
# --------------------------------------------------------------------------
class ForecastRunRequest(BaseModel):
    horizon_days: int = Field(default=14, ge=1, le=90)
    product_ids: list[int] | None = None


class ForecastOut(ORMModel):
    id: int
    product_id: int
    product_name: str | None = None
    generated_at: datetime
    horizon_days: int
    predicted_quantity: float | None
    model_used: str | None
    mae: float | None
    mape: float | None
    data_sufficiency_flag: DataSufficiency
    insufficiency_reason: str | None
    bucket: str
    data_window_start: date | None
    data_window_end: date | None
    observations_used: int | None
    nonzero_observations: int | None
    model_params: dict | None = None
    error_metrics: dict | None = None
    candidate_scores: list[dict] | None = None

    # These three are stored as JSON text (so the same code runs on SQLite and
    # Postgres). Decode them on the way out rather than making callers do it.
    @field_validator("model_params", "error_metrics", "candidate_scores", mode="before")
    @classmethod
    def _parse_json_text(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except ValueError:
                return None
        return v


class StockRiskRow(BaseModel):
    product_id: int
    name: str
    sku: str
    current_stock: int
    horizon_days: int
    forecast_demand: float | None
    lead_time_demand: float
    safety_stock: float
    projected_need: float | None
    estimated_shortage: int
    at_risk: bool
    days_of_cover: float | None
    status: str  # plain-language label for the UI
    reason: str
    forecast_id: int | None = None
    model_used: str | None = None


# --------------------------------------------------------------------------
# Budgets
# --------------------------------------------------------------------------
class BudgetCreate(BaseModel):
    period: str = Field(min_length=1, max_length=40)
    amount_available: float = Field(gt=0, description="Money available to restock with")


class BudgetOut(ORMModel):
    id: int
    user_id: int
    period: str
    amount_available: float
    created_at: datetime


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------
class RecommendationRunRequest(BaseModel):
    budget_id: int = Field(gt=0)
    horizon_days: int = Field(default=14, ge=1, le=90)
    safety_margin_pct: float = Field(default=0.20, ge=0, le=2)
    refresh_forecasts: bool = Field(
        default=True, description="Regenerate forecasts before recommending"
    )


class RecommendationOut(ORMModel):
    id: int
    run_id: int
    product_id: int
    product_name: str | None = None
    sku: str | None = None
    supplier_name: str | None = None
    forecast_id: int | None
    current_stock: int
    forecast_demand: float
    safety_stock: float
    lead_time_demand: float
    estimated_shortage: int
    unit_cost: float
    required_quantity: int
    required_cost: float
    recommended_quantity: int
    recommended_cost: float
    stockout_risk_score: float
    demand_velocity_score: float
    cost_efficiency_score: float
    priority_score: float
    priority_rank: int
    reason: str | None
    status: RecommendationStatus
    operator_quantity: int | None
    decided_at: datetime | None
    unfunded_quantity: int = 0
    unfunded_cost: float = 0


class RecommendationRunOut(ORMModel):
    id: int
    generated_at: datetime
    budget_id: int
    budget_period: str | None = None
    horizon_days: int
    safety_margin_pct: float
    budget_amount: float
    total_required_cost: float
    total_recommended_cost: float
    budget_shortfall: float = 0
    budget_remaining: float = 0
    budget_constrained: bool
    products_considered: int
    products_skipped_no_forecast: int
    products_skipped_no_cost: int = 0
    weights_used: dict | None = None
    items: list[RecommendationOut] = Field(default_factory=list)

    @field_validator("weights_used", mode="before")
    @classmethod
    def _parse_weights(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except ValueError:
                return None
        return v


class RecommendationDecision(BaseModel):
    status: RecommendationStatus
    quantity: int | None = Field(
        default=None, ge=0, description="Required when status is 'modified'"
    )

    @field_validator("status")
    @classmethod
    def _not_proposed(cls, v: RecommendationStatus) -> RecommendationStatus:
        if v == RecommendationStatus.proposed:
            raise ValueError("Choose accept, modify, or reject.")
        return v


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------
class SalesReportRow(BaseModel):
    product_id: int
    name: str
    sku: str
    units_sold: int
    revenue: float
    unit_cost: float
    cost_of_goods_sold: float
    profit: float
    margin_pct: float | None = None


class SalesReport(BaseModel):
    start: date
    end: date
    total_revenue: float
    total_units: int
    sale_count: int
    total_cost_of_goods_sold: float
    total_profit: float
    overall_margin_pct: float | None = None
    by_product: list[SalesReportRow]
    by_day: list[dict]


class PurchasesReportRow(BaseModel):
    product_id: int
    name: str
    sku: str
    units_received: int
    spend: float


class PurchasesReport(BaseModel):
    start: date
    end: date
    total_spend: float
    total_units: int
    purchase_count: int
    by_product: list[PurchasesReportRow]
    by_supplier: list[dict]


class ForecastAccuracyRow(BaseModel):
    forecast_id: int
    product_id: int
    product_name: str
    generated_at: datetime
    horizon_days: int
    model_used: str | None
    predicted_quantity: float
    actual_quantity: int
    absolute_error: float
    percentage_error: float | None
    window_start: date
    window_end: date
    evaluable: bool


class ForecastAccuracyReport(BaseModel):
    rows: list[ForecastAccuracyRow]
    mae: float | None
    mape: float | None
    evaluated_count: int
    pending_count: int


class RecommendationFollowThroughRow(BaseModel):
    run_id: int
    generated_at: datetime
    product_id: int
    product_name: str
    recommended_quantity: int
    recommended_cost: float
    status: RecommendationStatus
    operator_quantity: int | None
    actually_purchased_quantity: int
    actually_purchased_cost: float
