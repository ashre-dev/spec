from pydantic import BaseModel
from typing import Optional


class PaymentDetails(BaseModel):
    protocol: str = "x402"
    address: str
    currency: str = "USDC"
    network: str = "base-sepolia"
    price_per_query: str
    amount: str  # same as price_per_query, included for x402 compatibility


class X402Challenge(BaseModel):
    """HTTP 402 response body — tells the agent what/where/how to pay."""
    x402_version: int = 1
    error: str = "Payment Required"
    accepts: list[PaymentDetails]


class PayRequest(BaseModel):
    """Agent submits this to POST /pay to get a session token."""
    tx_hash: str          # mock transaction hash
    amount: str           # USDC amount paid, e.g. "0.05"
    payer_address: str    # agent wallet address


class PayResponse(BaseModel):
    token: str            # bearer token for subsequent /catalog calls
    expires_in: int = 3600


class Product(BaseModel):
    id: str
    name: str
    description: str
    price_usdc: str
    category: str
    in_stock: bool = True
    ships_to: list[str]


class CatalogResponse(BaseModel):
    vendor_id: str
    vendor_name: str
    products: list[Product]


class BuyRequest(BaseModel):
    product_id: str
    quantity: int = 1
    shipping_address: str
    payer_address: str


class BuyResponse(BaseModel):
    order_id: str
    product_id: str
    quantity: int
    total_usdc: str
    status: str = "confirmed"
    estimated_delivery: str
    message: Optional[str] = None
