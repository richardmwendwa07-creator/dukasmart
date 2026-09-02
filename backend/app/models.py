"""SQLAlchemy models for DukaSmart.

Design notes
------------
* Money is stored as ``NUMERIC(12, 2)`` but surfaced to Python as ``float``
  (``asdecimal=False``) to keep the pandas/JSON layers simple. A production
  system handling real cash should switch to ``Decimal``.
* Quantities are whole units (packets, bottles, tins). See docs/README.md.
* ``InventoryMovement`` is the single source of truth for stock. Products
  deliberately have **no** mutable ``stock`` column: current stock is derived by
  summing movements (see ``services.inventory.current_stock``).
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

Money = Numeric(12, 2, asdecimal=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------
class UserRole(str, enum.Enum):
    owner = "owner"
    staff = "staff"


class MovementSource(str, enum.Enum):
    sale = "sale"
    purchase = "purchase"
    adjustment = "adjustment"


class DataSufficiency(str, enum.Enum):
    sufficient = "sufficient"
    insufficient_data = "insufficient_data"


class RecommendationStatus(str, enum.Enum):
    proposed = "proposed"
    accepted = "accepted"
    modified = "modified"
    rejected = "rejected"


def _enum(py_enum, name):
    """Store enums as plain VARCHAR + CHECK so SQLite/Postgres behave alike."""
    return Enum(py_enum, name=name, native_enum=False, values_callable=lambda e: [m.value for m in e])


# --------------------------------------------------------------------------
# Association: a product may be sourced from several suppliers
# --------------------------------------------------------------------------
product_suppliers = Table(
    "product_suppliers",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("supplier_id", ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True),
)


# --------------------------------------------------------------------------
# Core entities
# --------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "user_role"), nullable=False, default=UserRole.staff
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    sales: Mapped[list["Sale"]] = relationship(back_populates="user")
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="user")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="user")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    contact: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    products: Mapped[list["Product"]] = relationship(
        secondary=product_suppliers, back_populates="suppliers"
    )
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="supplier")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("selling_price >= 0", name="ck_product_selling_price_non_negative"),
        CheckConstraint("default_unit_cost >= 0", name="ck_product_unit_cost_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    selling_price: Mapped[float] = mapped_column(Money, nullable=False)
    # Fallback purchase cost. The recommendation engine prefers the most recent
    # actual PurchaseItem cost when one exists (see services/recommendation.py).
    default_unit_cost: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    reorder_lead_time_days: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    preferred_supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL")
    )
    preferred_supplier: Mapped["Supplier | None"] = relationship(foreign_keys=[preferred_supplier_id])

    suppliers: Mapped[list["Supplier"]] = relationship(
        secondary=product_suppliers, back_populates="products"
    )
    movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_amount: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="sales")
    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_item_qty_positive"),
        CheckConstraint("unit_price_at_sale >= 0", name="ck_sale_item_price_non_negative"),
        Index("ix_sale_items_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_at_sale: Mapped[float] = mapped_column(Money, nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    date_received: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_cost: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="purchases")
    supplier: Mapped["Supplier"] = relationship(back_populates="purchases")
    items: Mapped[list["PurchaseItem"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan"
    )


class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    __table_args__ = (
        CheckConstraint("quantity_received > 0", name="ck_purchase_item_qty_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_purchase_item_cost_non_negative"),
        Index("ix_purchase_items_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Money, nullable=False)

    purchase: Mapped["Purchase"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class InventoryMovement(Base):
    """Append-only audit trail. Current stock == SUM(change_qty) per product."""

    __tablename__ = "inventory_movements"
    __table_args__ = (
        CheckConstraint("change_qty <> 0", name="ck_movement_qty_nonzero"),
        Index("ix_movements_product_time", "product_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[MovementSource] = mapped_column(
        _enum(MovementSource, "movement_source"), nullable=False
    )
    source_id: Mapped[int | None] = mapped_column(Integer)
    resulting_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, index=True)

    product: Mapped["Product"] = relationship(back_populates="movements")


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (Index("ix_forecasts_product_time", "product_id", "generated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_quantity: Mapped[float | None] = mapped_column(Float)
    model_used: Mapped[str | None] = mapped_column(String(60))
    # JSON blobs kept as TEXT so the same code runs on SQLite and Postgres.
    model_params: Mapped[str | None] = mapped_column(Text)
    error_metrics: Mapped[str | None] = mapped_column(Text)
    mae: Mapped[float | None] = mapped_column(Float)
    mape: Mapped[float | None] = mapped_column(Float)
    data_sufficiency_flag: Mapped[DataSufficiency] = mapped_column(
        _enum(DataSufficiency, "data_sufficiency"), nullable=False
    )
    insufficiency_reason: Mapped[str | None] = mapped_column(String(255))

    # --- reproducibility: exactly which data went in ---------------------
    bucket: Mapped[str] = mapped_column(String(10), nullable=False, default="daily")
    data_window_start: Mapped[date | None] = mapped_column(Date)
    data_window_end: Mapped[date | None] = mapped_column(Date)
    observations_used: Mapped[int | None] = mapped_column(Integer)
    nonzero_observations: Mapped[int | None] = mapped_column(Integer)
    candidate_scores: Mapped[str | None] = mapped_column(Text)

    product: Mapped["Product"] = relationship()


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (CheckConstraint("amount_available >= 0", name="ck_budget_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(40), nullable=False)  # e.g. "2026-08" or "Week 34"
    amount_available: Mapped[float] = mapped_column(Money, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="budgets")


class RecommendationRun(Base):
    """Groups the line items produced by one 'what should I buy?' run."""

    __tablename__ = "recommendation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    safety_margin_pct: Mapped[float] = mapped_column(Float, nullable=False)
    budget_amount: Mapped[float] = mapped_column(Money, nullable=False)
    total_required_cost: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    total_recommended_cost: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    budget_constrained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weights_used: Mapped[str | None] = mapped_column(Text)
    products_considered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_skipped_no_forecast: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_skipped_no_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    budget: Mapped["Budget"] = relationship()
    user: Mapped["User"] = relationship()
    items: Mapped[list["Recommendation"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("run_id", "product_id", name="uq_recommendation_run_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    forecast_id: Mapped[int | None] = mapped_column(ForeignKey("forecasts.id"))

    current_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_demand: Mapped[float] = mapped_column(Float, nullable=False)
    safety_stock: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    lead_time_demand: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    estimated_shortage: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Money, nullable=False)
    required_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    required_cost: Mapped[float] = mapped_column(Money, nullable=False)
    recommended_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_cost: Mapped[float] = mapped_column(Money, nullable=False)

    # Transparent scoring inputs, persisted so the operator can be shown "why".
    stockout_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    demand_velocity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    cost_efficiency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

    status: Mapped[RecommendationStatus] = mapped_column(
        _enum(RecommendationStatus, "recommendation_status"),
        nullable=False,
        default=RecommendationStatus.proposed,
    )
    operator_quantity: Mapped[int | None] = mapped_column(Integer)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)

    run: Mapped["RecommendationRun"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
    forecast: Mapped["Forecast | None"] = relationship()
