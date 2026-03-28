import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class PaymentInfo(BaseModel):
    protocol: str = "x402"
    address: str
    currency: str = "USDC"
    network: str
    price_per_query: str


class VendorManifest(BaseModel):
    vendor_id: str
    name: str
    description: Optional[str] = None
    category: list[str]
    mcp_endpoint: str
    payment: PaymentInfo
    ships_to: Optional[list[str]] = None
    verified: bool = False
    schema_version: str

    @field_validator("vendor_id")
    @classmethod
    def vendor_id_format(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", v):
            raise ValueError("vendor_id must be lowercase-hyphenated, e.g. 'my-store'")
        return v

    @field_validator("category")
    @classmethod
    def category_nonempty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("category must contain at least one entry")
        return v

    @field_validator("schema_version")
    @classmethod
    def schema_version_supported(cls, v: str) -> str:
        if v != "0.1.0":
            raise ValueError(f"Unsupported schema_version {v!r}. Only '0.1.0' is accepted.")
        return v


class VendorRegistration(BaseModel):
    """Manifest plus registry-added metadata."""
    manifest: VendorManifest
    registered_at: datetime


class HealthStatus(BaseModel):
    vendor_id: str
    status: str          # "healthy" | "degraded" | "unreachable"
    latency_ms: Optional[float] = None
    checked_at: datetime
    detail: Optional[str] = None


class DiscoverResponse(BaseModel):
    count: int
    vendors: list[VendorRegistration]
