import pytest
from fastapi.testclient import TestClient
from src.vendor_server.main import app

client = TestClient(app)


def _get_token() -> str:
    resp = client.post("/pay", json={
        "tx_hash": "0xdeadbeef",
        "amount": "0.05",
        "payer_address": "0xAgentWallet",
    })
    assert resp.status_code == 200
    return resp.json()["token"]


# --- /catalog ---

def test_catalog_without_token_returns_402():
    resp = client.get("/catalog")
    assert resp.status_code == 402
    body = resp.json()
    assert body["x402_version"] == 1
    assert body["error"] == "Payment Required"
    assert len(body["accepts"]) == 1
    assert body["accepts"][0]["currency"] == "USDC"


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
    assert "price_usdc" in product


# --- /pay ---

def test_pay_with_valid_tx_issues_token():
    resp = client.post("/pay", json={
        "tx_hash": "0xabc123",
        "amount": "0.05",
        "payer_address": "0xSomeAgent",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["expires_in"] == 3600


def test_pay_with_empty_tx_hash_rejected():
    resp = client.post("/pay", json={
        "tx_hash": "",
        "amount": "0.05",
        "payer_address": "0xSomeAgent",
    })
    assert resp.status_code == 400


def test_pay_with_insufficient_amount_rejected():
    resp = client.post("/pay", json={
        "tx_hash": "0xabc123",
        "amount": "0.01",
        "payer_address": "0xSomeAgent",
    })
    assert resp.status_code == 400


# --- /buy ---

def test_buy_without_token_returns_402():
    resp = client.post("/buy", json={
        "product_id": "hms-tee-001",
        "quantity": 1,
        "shipping_address": "Mannerheimintie 1, Helsinki",
        "payer_address": "0xAgent",
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
            "payer_address": "0xAgent",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["product_id"] == "hms-tee-001"
    assert body["quantity"] == 2
    assert body["total_usdc"] == "36.00"
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
            "payer_address": "0xAgent",
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
            "payer_address": "0xAgent",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
