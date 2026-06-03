import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from src.vendor_server.main import create_vendor_app, app

client = TestClient(app)

# Chennai Threads client for new-vendor tests
chennai_app = create_vendor_app("chennai-threads")
chennai_client = TestClient(chennai_app)


def _get_token() -> str:
    resp = client.post("/pay", json={
        "payment_id": "pay-test-001",
        "amount": "0.05",
        "payer_id": "test-agent",
    })
    assert resp.status_code == 200
    return resp.json()["token"]


# --- /catalog ---

def test_catalog_without_token_returns_402():
    resp = client.get("/catalog")
    assert resp.status_code == 402
    body = resp.json()
    assert body["error"] == "Payment Required"
    assert len(body["accepts"]) == 1
    assert body["accepts"][0]["currency"] == "USD"


def test_catalog_with_invalid_token_returns_402():
    resp = client.get("/catalog", headers={"Authorization": "Bearer bogus-token"})
    assert resp.status_code == 402


def test_catalog_with_valid_token_returns_products():
    token = _get_token()
    resp = client.get("/catalog", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["vendor_id"] == "helsinki-maker-store"
    assert len(body["products"]) > 0
    product = body["products"][0]
    assert "id" in product
    assert "price" in product


# --- /pay ---

def test_pay_with_valid_payment_issues_token():
    resp = client.post("/pay", json={
        "payment_id": "pay-abc123",
        "amount": "0.05",
        "payer_id": "test-agent",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["expires_in"] == 3600


def test_pay_with_empty_payment_id_rejected():
    resp = client.post("/pay", json={
        "payment_id": "",
        "amount": "0.05",
        "payer_id": "test-agent",
    })
    assert resp.status_code == 400


def test_pay_with_insufficient_amount_rejected():
    resp = client.post("/pay", json={
        "payment_id": "pay-abc123",
        "amount": "0.01",
        "payer_id": "test-agent",
    })
    assert resp.status_code == 400


# --- /buy ---

def test_buy_without_token_returns_402():
    resp = client.post("/buy", json={
        "product_id": "hms-tee-001",
        "quantity": 1,
        "shipping_address": "Mannerheimintie 1, Helsinki",
        "payer_id": "test-agent",
    })
    assert resp.status_code == 402


def test_buy_valid_product():
    token = _get_token()
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-tee-001",
            "quantity": 2,
            "shipping_address": "Mannerheimintie 1, Helsinki",
            "payer_id": "test-agent",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["product_id"] == "hms-tee-001"
    assert body["quantity"] == 2
    assert body["total"] == "36.00"
    assert body["status"] == "confirmed"
    assert "order_id" in body


def test_buy_nonexistent_product_returns_404():
    token = _get_token()
    resp = client.post(
        "/buy",
        json={
            "product_id": "does-not-exist",
            "quantity": 1,
            "shipping_address": "somewhere",
            "payer_id": "test-agent",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_buy_out_of_stock_returns_409():
    token = _get_token()
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-mug-001",  # in_stock=False
            "quantity": 1,
            "shipping_address": "somewhere",
            "payer_id": "test-agent",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


# --- Chennai Threads vendor ---

def _get_chennai_token() -> str:
    resp = chennai_client.post("/pay", json={
        "payment_id": "pay-chennai-001",
        "amount": "0.02",
        "payer_id": "test-agent",
    })
    assert resp.status_code == 200
    return resp.json()["token"]


def test_chennai_catalog_returns_5_products():
    token = _get_chennai_token()
    resp = chennai_client.get("/catalog", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["vendor_id"] == "chennai-threads"
    assert body["vendor_name"] == "Chennai Threads"
    assert len(body["products"]) == 5


def test_chennai_has_blue_tee():
    token = _get_chennai_token()
    resp = chennai_client.get("/catalog", headers={"Authorization": f"Bearer {token}"})
    products = resp.json()["products"]
    blue_tee = [p for p in products if p["id"] == "ct-tee-blue-001"]
    assert len(blue_tee) == 1
    assert blue_tee[0]["price"] == "25.00"
    assert "IN" in blue_tee[0]["ships_to"]


def test_chennai_out_of_stock_tote():
    token = _get_chennai_token()
    resp = chennai_client.post(
        "/buy",
        json={
            "product_id": "ct-tote-001",
            "quantity": 1,
            "shipping_address": "T Nagar, Chennai",
            "payer_id": "test-agent",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


# --- /reserve ---

def test_reserve_without_token_returns_402():
    resp = client.post("/reserve", json={
        "product_id": "hms-tee-001",
        "quantity": 1,
    })
    assert resp.status_code == 402


def test_reserve_valid_product():
    token = _get_token()
    resp = client.post(
        "/reserve",
        json={"product_id": "hms-tee-001", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["product_id"] == "hms-tee-001"
    assert body["quantity"] == 1
    assert body["status"] == "held"
    assert "reservation_id" in body
    assert "held_until" in body


def test_reserve_nonexistent_product_returns_404():
    token = _get_token()
    resp = client.post(
        "/reserve",
        json={"product_id": "nope", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_reserve_out_of_stock_returns_409():
    token = _get_token()
    resp = client.post(
        "/reserve",
        json={"product_id": "hms-mug-001", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


# --- /buy with reservation ---

def test_buy_with_valid_reservation():
    token = _get_token()
    # Reserve first
    res = client.post(
        "/reserve",
        json={"product_id": "hms-tee-001", "quantity": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    reservation_id = res.json()["reservation_id"]

    # Buy with reservation
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-tee-001",
            "quantity": 2,
            "shipping_address": "Helsinki",
            "payer_id": "test-agent",
            "reservation_id": reservation_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


def test_buy_with_invalid_reservation_returns_410():
    token = _get_token()
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-tee-001",
            "quantity": 1,
            "shipping_address": "Helsinki",
            "payer_id": "test-agent",
            "reservation_id": "bogus-reservation-id",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 410


def test_buy_with_mismatched_reservation_returns_410():
    token = _get_token()
    # Reserve product A
    res = client.post(
        "/reserve",
        json={"product_id": "hms-tee-001", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    reservation_id = res.json()["reservation_id"]

    # Try to buy product B with product A's reservation
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-hoodie-001",
            "quantity": 1,
            "shipping_address": "Helsinki",
            "payer_id": "test-agent",
            "reservation_id": reservation_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 410


def test_reservation_consumed_after_buy():
    token = _get_token()
    res = client.post(
        "/reserve",
        json={"product_id": "hms-tee-001", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    reservation_id = res.json()["reservation_id"]

    # First buy succeeds
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-tee-001",
            "quantity": 1,
            "shipping_address": "Helsinki",
            "payer_id": "test-agent",
            "reservation_id": reservation_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Second buy with same reservation fails
    resp2 = client.post(
        "/buy",
        json={
            "product_id": "hms-tee-001",
            "quantity": 1,
            "shipping_address": "Helsinki",
            "payer_id": "test-agent",
            "reservation_id": reservation_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 410


# --- /buy without reservation (backwards compatible) ---

def test_buy_without_reservation_still_works():
    token = _get_token()
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-tee-001",
            "quantity": 1,
            "shipping_address": "Helsinki",
            "payer_id": "test-agent",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


# --- callback_url ---

def test_buy_with_callback_url_returns_url_in_response():
    token = _get_token()
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-tee-001",
            "quantity": 1,
            "shipping_address": "Helsinki",
            "payer_id": "test-agent",
            "callback_url": "https://agent.example.com/order-updates",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["callback_url"] == "https://agent.example.com/order-updates"


def test_buy_without_callback_url_returns_null():
    token = _get_token()
    resp = client.post(
        "/buy",
        json={
            "product_id": "hms-tee-001",
            "quantity": 1,
            "shipping_address": "Helsinki",
            "payer_id": "test-agent",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["callback_url"] is None
