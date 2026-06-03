from pydantic import BaseModel
from typing import Optional


class PaymentDetails(BaseModel):
    protocol: str = "stripe"
    currency: str = "USD"
    price_per_query: str
    amount: str  # same as price_per_query, included for compatibility


class PaymentChallenge(BaseModel):
    """HTTP 402 response body — tells the agent what/where/how to pay."""
    error: str = "Payment Required"
    accepts: list[PaymentDetails]


class PayRequest(BaseModel):
    """Agent submits this to POST /pay to get a session token."""
    payment_id: str       # payment reference (e.g. Stripe payment intent ID)
    amount: str           # amount paid, e.g. "0.05"
    payer_id: str         # agent or buyer identifier


class PayResponse(BaseModel):
    token: str            # bearer token for subsequent /catalog calls
    expires_in: int = 3600


class Product(BaseModel):
    id: str
    name: str
    description: str
    price: str
    category: str
    in_stock: bool = True
    ships_to: list[str]


class CatalogResponse(BaseModel):
    vendor_id: str
    vendor_name: str
    products: list[Product]


class ReserveRequest(BaseModel):
    product_id: str
    quantity: int = 1


class ReserveResponse(BaseModel):
    reservation_id: str
    product_id: str
    quantity: int
    held_until: str  # ISO-8601 timestamp
    status: str = "held"


class BuyRequest(BaseModel):
    product_id: str
    quantity: int = 1
    shipping_address: str
    payer_id: str
    reservation_id: Optional[str] = None
    callback_url: Optional[str] = None


class BuyResponse(BaseModel):
    order_id: str
    product_id: str
    quantity: int
    total: str
    status: str = "confirmed"
    estimated_delivery: str
    message: Optional[str] = None
    callback_url: Optional[str] = None
