import os
import uuid
import httpx
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional

from .models import (
    X402Challenge,
    PaymentDetails,
    PayRequest,
    PayResponse,
    CatalogResponse,
    BuyRequest,
    BuyResponse,
    ReserveRequest,
    ReserveResponse,
)
from .vendors import load_vendor
from .payment import (
    issue_token,
    validate_token,
    verify_payment,
    create_reservation,
    validate_reservation,
    consume_reservation,
)


def create_vendor_app(vendor_id: str) -> FastAPI:
    """
    Factory — creates a FastAPI app for the given vendor_id.
    Called at module level with VENDOR_ID env var for production,
    and directly in tests to spin up multiple vendor apps.
    """
    cfg = load_vendor(vendor_id)

    _app = FastAPI(title=f"ASHRE Vendor: {cfg['name']}", version="0.1.0")

    def _payment_required() -> JSONResponse:
        challenge = X402Challenge(
            accepts=[
                PaymentDetails(
                    address=cfg["wallet_address"],
                    price_per_query=cfg["price_per_query"],
                    amount=cfg["price_per_query"],
                )
            ]
        )
        return JSONResponse(status_code=402, content=challenge.model_dump())

    @_app.get("/catalog")
    def get_catalog(authorization: Optional[str] = Header(default=None)):
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
        if not token or not validate_token(token):
            return _payment_required()
        return CatalogResponse(
            vendor_id=cfg["vendor_id"],
            vendor_name=cfg["name"],
            products=cfg["products"],
        )

    @_app.post("/pay", response_model=PayResponse)
    def pay(req: PayRequest):
        if not verify_payment(req.tx_hash, req.amount, cfg["price_per_query"], recipient=cfg["wallet_address"]):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Payment rejected. Required {cfg['price_per_query']} USDC, "
                    f"got {req.amount!r} with tx_hash {req.tx_hash!r}"
                ),
            )
        token, expires_in = issue_token(req.payer_address)
        return PayResponse(token=token, expires_in=expires_in)

    @_app.post("/reserve", response_model=ReserveResponse)
    def reserve(req: ReserveRequest, authorization: Optional[str] = Header(default=None)):
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
        if not token or not validate_token(token):
            return _payment_required()

        product = cfg["products_by_id"].get(req.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{req.product_id}' not found")
        if not product.in_stock:
            raise HTTPException(status_code=409, detail=f"Product '{req.product_id}' is out of stock")

        reservation_id, held_until = create_reservation(req.product_id, req.quantity)
        return ReserveResponse(
            reservation_id=reservation_id,
            product_id=req.product_id,
            quantity=req.quantity,
            held_until=held_until,
        )

    @_app.post("/buy", response_model=BuyResponse)
    def buy(
        req: BuyRequest,
        background_tasks: BackgroundTasks,
        authorization: Optional[str] = Header(default=None),
    ):
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
        if not token or not validate_token(token):
            return _payment_required()

        product = cfg["products_by_id"].get(req.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{req.product_id}' not found")
        if not product.in_stock:
            raise HTTPException(status_code=409, detail=f"Product '{req.product_id}' is out of stock")

        # Validate reservation if provided
        if req.reservation_id:
            if not validate_reservation(req.reservation_id, req.product_id, req.quantity):
                raise HTTPException(
                    status_code=410,
                    detail="Reservation expired or invalid",
                )
            consume_reservation(req.reservation_id)

        total = float(product.price_usdc) * req.quantity
        order_id = str(uuid.uuid4())

        response = BuyResponse(
            order_id=order_id,
            product_id=req.product_id,
            quantity=req.quantity,
            total_usdc=f"{total:.2f}",
            status="confirmed",
            estimated_delivery="5-10 business days",
            callback_url=req.callback_url,
        )

        # Fire callback in background if agent provided a URL
        if req.callback_url:
            background_tasks.add_task(
                _send_callback,
                req.callback_url,
                {
                    "order_id": order_id,
                    "status": "confirmed",
                    "vendor_id": cfg["vendor_id"],
                    "product_id": req.product_id,
                    "quantity": req.quantity,
                    "total_usdc": f"{total:.2f}",
                    "estimated_delivery": "5-10 business days",
                },
            )

        return response

    return _app


async def _send_callback(url: str, payload: dict) -> None:
    """POST order status to the agent's callback URL. Fire-and-forget."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload)
    except httpx.HTTPError:
        pass  # best-effort — agent can always poll


# Default app — selected by VENDOR_ID env var (falls back to Helsinki)
app = create_vendor_app(os.getenv("VENDOR_ID", "helsinki-maker-store"))
