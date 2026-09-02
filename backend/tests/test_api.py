"""API-level tests: auth, roles, validation messages, and the HTTP stock flows."""

from __future__ import annotations

from datetime import date, timedelta

from app.services.inventory import current_stock


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def test_password_is_hashed_and_never_returned(client, db):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Amina",
            "email": "amina@dukasmart.co.ke",
            "password": "supersecret1",
            "role": "owner",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]

    from sqlalchemy import select

    from app.models import User

    user = db.execute(select(User).where(User.email == "amina@dukasmart.co.ke")).scalar_one()
    assert user.password_hash != "supersecret1"
    assert user.password_hash.startswith("$2")  # bcrypt


def test_login_succeeds_and_wrong_password_fails(client, owner):
    good = client.post("/api/auth/login", json={"email": owner.email, "password": "duka1234"})
    assert good.status_code == 200
    assert good.json()["user"]["role"] == "owner"

    bad = client.post("/api/auth/login", json={"email": owner.email, "password": "wrong-one"})
    assert bad.status_code == 401
    # Same wording for both failure modes, so emails cannot be enumerated.
    unknown = client.post(
        "/api/auth/login", json={"email": "nobody@dukasmart.co.ke", "password": "whatever1"}
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == bad.json()["detail"]


def test_protected_endpoints_require_a_token(client):
    assert client.get("/api/products").status_code == 401
    assert client.get("/api/summary").status_code == 401
    assert client.get("/api/inventory/stock").status_code == 401


def test_short_password_is_rejected_with_a_clear_message(client):
    response = client.post(
        "/api/auth/register",
        json={"name": "Short", "email": "short@dukasmart.co.ke", "password": "abc", "role": "staff"},
    )
    assert response.status_code == 422
    assert "8" in response.json()["detail"]


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------
def test_staff_cannot_set_budgets_but_can_record_sales(client, db, staff, make_product):
    login = client.post("/api/auth/login", json={"email": staff.email, "password": "duka1234"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    product = make_product("Sugar", "SUGX", selling_price=165.0, opening_stock=20)

    # Staff CAN record a sale.
    sale = client.post(
        "/api/sales",
        headers=headers,
        json={"items": [{"product_id": product.id, "quantity": 3}]},
    )
    assert sale.status_code == 201, sale.text

    # Staff CANNOT create a budget or run recommendations.
    budget = client.post(
        "/api/budgets", headers=headers, json={"period": "Aug", "amount_available": 5000}
    )
    assert budget.status_code == 403
    assert "owner" in budget.json()["detail"].lower()

    assert client.get("/api/recommendations/runs", headers=headers).status_code == 403
    assert (
        client.post("/api/products", headers=headers, json={
            "name": "X", "sku": "XX1", "selling_price": 10
        }).status_code
        == 403
    )


# --------------------------------------------------------------------------
# Stock flows over HTTP
# --------------------------------------------------------------------------
def test_sale_endpoint_reduces_stock(client, db, auth_headers, make_product):
    product = make_product("Bread", "BRDX", selling_price=70.0, opening_stock=40)

    response = client.post(
        "/api/sales",
        headers=auth_headers,
        json={"items": [{"product_id": product.id, "quantity": 6}]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["total_amount"] == 420.0
    assert response.json()["items"][0]["product_name"] == "Bread"

    stock = client.get("/api/inventory/stock", headers=auth_headers).json()
    row = next(r for r in stock if r["product_id"] == product.id)
    assert row["current_stock"] == 34


def test_purchase_endpoint_increases_stock(client, db, auth_headers, supplier, make_product):
    product = make_product("Rice", "RICX", opening_stock=5)

    response = client.post(
        "/api/purchases",
        headers=auth_headers,
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": product.id, "quantity_received": 25, "unit_cost": 145.0}],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["total_cost"] == 3625.0
    assert current_stock(db, product.id) == 30


def test_overselling_returns_a_helpful_message(client, auth_headers, make_product):
    product = make_product("Tea", "TEAX", opening_stock=2)
    response = client.post(
        "/api/sales",
        headers=auth_headers,
        json={"items": [{"product_id": product.id, "quantity": 10}]},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Not enough Tea" in detail and "2" in detail


def test_invalid_quantities_are_rejected_before_reaching_the_database(
    client, auth_headers, make_product
):
    product = make_product("Salt", "SLTX", opening_stock=50)

    zero = client.post(
        "/api/sales", headers=auth_headers, json={"items": [{"product_id": product.id, "quantity": 0}]}
    )
    assert zero.status_code == 422

    negative = client.post(
        "/api/sales",
        headers=auth_headers,
        json={"items": [{"product_id": product.id, "quantity": -4}]},
    )
    assert negative.status_code == 422

    empty = client.post("/api/sales", headers=auth_headers, json={"items": []})
    assert empty.status_code == 422


def test_duplicate_product_lines_are_rejected(client, auth_headers, make_product):
    product = make_product("Soda", "SODX", opening_stock=50)
    response = client.post(
        "/api/sales",
        headers=auth_headers,
        json={
            "items": [
                {"product_id": product.id, "quantity": 2},
                {"product_id": product.id, "quantity": 3},
            ]
        },
    )
    assert response.status_code == 422
    assert "more than once" in response.json()["detail"]


def test_future_dated_transactions_are_rejected(client, auth_headers, make_product):
    product = make_product("Oil", "OILX", opening_stock=20)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/sales",
        headers=auth_headers,
        json={"date": tomorrow, "items": [{"product_id": product.id, "quantity": 1}]},
    )
    assert response.status_code == 400
    assert "future" in response.json()["detail"]


def test_movement_history_is_traceable_per_product(client, db, auth_headers, supplier, make_product):
    product = make_product("Traceable", "TRCX", opening_stock=10)
    client.post(
        "/api/purchases",
        headers=auth_headers,
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": product.id, "quantity_received": 20, "unit_cost": 50.0}],
        },
    )
    client.post(
        "/api/sales",
        headers=auth_headers,
        json={"items": [{"product_id": product.id, "quantity": 4}]},
    )

    movements = client.get(
        f"/api/inventory/movements?product_id={product.id}", headers=auth_headers
    ).json()

    assert len(movements) == 3  # opening + purchase + sale
    kinds = [m["source_type"] for m in movements]
    assert set(kinds) == {"adjustment", "purchase", "sale"}
    # Newest first, and the running total is right.
    assert movements[0]["resulting_stock"] == 26


def test_product_crud_and_stock_is_read_only_derived(client, auth_headers, supplier):
    created = client.post(
        "/api/products",
        headers=auth_headers,
        json={
            "name": "New Item",
            "sku": "new-1",
            "category": "Test",
            "selling_price": 120.0,
            "default_unit_cost": 80.0,
            "supplier_ids": [supplier.id],
            "opening_stock": 15,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["sku"] == "NEW-1"  # normalised to upper case
    assert body["current_stock"] == 15

    updated = client.put(
        f"/api/products/{body['id']}", headers=auth_headers, json={"selling_price": 135.0}
    )
    assert updated.status_code == 200
    assert updated.json()["selling_price"] == 135.0
    assert updated.json()["current_stock"] == 15  # unchanged by an edit

    duplicate = client.post(
        "/api/products",
        headers=auth_headers,
        json={"name": "Clash", "sku": "NEW-1", "selling_price": 10.0},
    )
    assert duplicate.status_code == 409


def test_negative_price_is_rejected(client, auth_headers):
    response = client.post(
        "/api/products",
        headers=auth_headers,
        json={"name": "Bad Price", "sku": "BAD1", "selling_price": -5.0},
    )
    assert response.status_code == 422


def test_health_and_forecast_config_endpoints(client, auth_headers):
    assert client.get("/api/health").json()["status"] == "ok"

    config = client.get("/api/forecasts/config", headers=auth_headers).json()
    weights = config["priority_weights"]
    assert sum(weights.values()) == 1.0
    assert weights["stockout_risk"] == 0.5
    assert config["min_nonzero_observations"] >= 8
