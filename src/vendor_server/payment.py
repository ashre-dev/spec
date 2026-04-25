"""
x402 payment handling.

Mock mode (default): accepts any non-empty tx_hash with the correct amount.
Real mode (set SEPOLIA_RPC_URL env var): verifies the USDC transfer on Base Sepolia.
"""

import os
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta

# token -> {expires_at, payer_address}
_active_tokens: dict[str, dict] = {}

TOKEN_TTL = 3600  # seconds

# reservation_id -> {product_id, quantity, expires_at}
_reservations: dict[str, dict] = {}

RESERVATION_TTL = 300  # 5 minutes


def issue_token(payer_address: str) -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    _active_tokens[token] = {
        "expires_at": time.time() + TOKEN_TTL,
        "payer_address": payer_address,
    }
    return token, TOKEN_TTL


def validate_token(token: str) -> bool:
    entry = _active_tokens.get(token)
    if not entry:
        return False
    if time.time() > entry["expires_at"]:
        del _active_tokens[token]
        return False
    return True


def create_reservation(product_id: str, quantity: int) -> tuple[str, str]:
    """Create a reservation hold. Returns (reservation_id, held_until ISO string)."""
    reservation_id = str(uuid.uuid4())
    expires_at = time.time() + RESERVATION_TTL
    held_until = datetime.now(timezone.utc) + timedelta(seconds=RESERVATION_TTL)
    _reservations[reservation_id] = {
        "product_id": product_id,
        "quantity": quantity,
        "expires_at": expires_at,
    }
    return reservation_id, held_until.isoformat()


def validate_reservation(reservation_id: str, product_id: str, quantity: int) -> bool:
    """Check reservation exists, matches product/quantity, and hasn't expired."""
    entry = _reservations.get(reservation_id)
    if not entry:
        return False
    if time.time() > entry["expires_at"]:
        del _reservations[reservation_id]
        return False
    return entry["product_id"] == product_id and entry["quantity"] == quantity


def consume_reservation(reservation_id: str) -> None:
    """Remove a reservation after successful purchase."""
    _reservations.pop(reservation_id, None)


def mock_verify_payment(tx_hash: str, amount: str, expected_amount: str) -> bool:
    """Stub — accepts any non-empty tx_hash with correct amount."""
    if not tx_hash:
        return False
    try:
        paid = float(amount)
        required = float(expected_amount)
        return paid >= required
    except ValueError:
        return False


def verify_payment(
    tx_hash: str,
    amount: str,
    expected_amount: str,
    recipient: str | None = None,
) -> bool:
    """
    Route to on-chain or mock verification based on env configuration.

    Real mode: SEPOLIA_RPC_URL must be set and `recipient` must be provided.
    Mock mode: falls back to mock_verify_payment (used in dev and tests).
    """
    rpc_url = os.getenv("SEPOLIA_RPC_URL")
    if rpc_url and recipient:
        from .x402_verifier import verify_usdc_payment
        return verify_usdc_payment(tx_hash, recipient, expected_amount, rpc_url)
    return mock_verify_payment(tx_hash, amount, expected_amount)
