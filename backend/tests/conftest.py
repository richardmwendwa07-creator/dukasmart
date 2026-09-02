"""Test fixtures: an isolated SQLite database per test, plus an API client."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Product, Supplier, User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------
# Convenience builders
# --------------------------------------------------------------------------
@pytest.fixture()
def owner(db) -> User:
    user = User(
        name="Test Owner",
        email="owner@dukasmart.co.ke",
        password_hash=hash_password("duka1234"),
        role=UserRole.owner,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def staff(db) -> User:
    user = User(
        name="Test Staff",
        email="staff@dukasmart.co.ke",
        password_hash=hash_password("duka1234"),
        role=UserRole.staff,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def supplier(db) -> Supplier:
    s = Supplier(name="Test Wholesaler", contact="0700 000 000")
    db.add(s)
    db.commit()
    return s


@pytest.fixture()
def make_product(db, supplier):
    def _make(
        name: str,
        sku: str,
        *,
        selling_price: float = 100.0,
        default_unit_cost: float = 70.0,
        lead_time: int | None = None,
        opening_stock: int = 0,
    ) -> Product:
        from app.services.inventory import set_opening_stock

        product = Product(
            name=name,
            sku=sku,
            category="Test",
            selling_price=selling_price,
            default_unit_cost=default_unit_cost,
            reorder_lead_time_days=lead_time,
            preferred_supplier_id=supplier.id,
            suppliers=[supplier],
        )
        db.add(product)
        db.flush()
        set_opening_stock(db, product, opening_stock)
        db.commit()
        return product

    return _make


@pytest.fixture()
def auth_headers(client, owner):
    response = client.post(
        "/api/auth/login", json={"email": owner.email, "password": "duka1234"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
