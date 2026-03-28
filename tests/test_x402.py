"""
Phase 5 tests: on-chain USDC verification and wallet.

All web3 calls are mocked — no real network or blockchain interaction.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# ---------------------------------------------------------------------------
# Helpers: build a mock web3 stack
# ---------------------------------------------------------------------------

VENDOR_ADDR = "0xABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
AGENT_ADDR = "0xDEAD000000000000000000000000000000000001"
MOCK_TX_HASH = "0xabc123def456abc123def456abc123def456abc123def456abc123def456abc1"
AMOUNT_USDC = "0.05"
AMOUNT_UNITS = 50_000  # 0.05 * 10^6


def _make_transfer_event(to: str, value: int) -> dict:
    return {"args": {"from": AGENT_ADDR, "to": to, "value": value}}


def _mock_w3(receipt_status: int = 1, transfer_events: list | None = None):
    """Build a mock Web3 instance with a configurable receipt and Transfer events."""
    if transfer_events is None:
        transfer_events = [_make_transfer_event(VENDOR_ADDR, AMOUNT_UNITS)]

    # web3 receipts are dict-like; use a plain dict for simplicity
    mock_receipt = {"status": receipt_status}

    mock_contract = MagicMock()
    mock_contract.events.Transfer.return_value.process_receipt.return_value = transfer_events

    mock_eth = MagicMock()
    mock_eth.get_transaction_receipt.return_value = mock_receipt
    mock_eth.contract.return_value = mock_contract

    mock_w3_instance = MagicMock()
    mock_w3_instance.eth = mock_eth

    return mock_w3_instance


# ---------------------------------------------------------------------------
# verify_usdc_payment
# ---------------------------------------------------------------------------

class TestVerifyUsdcPayment:
    def _call(self, mock_w3_instance, **kwargs):
        from src.vendor_server.x402_verifier import verify_usdc_payment

        defaults = dict(
            tx_hash=MOCK_TX_HASH,
            recipient=VENDOR_ADDR,
            amount_usdc=AMOUNT_USDC,
            rpc_url="http://localhost:8545",
        )
        defaults.update(kwargs)

        with patch("src.vendor_server.x402_verifier.Web3") as MockWeb3:
            MockWeb3.return_value = mock_w3_instance
            MockWeb3.HTTPProvider.return_value = MagicMock()
            MockWeb3.to_checksum_address.side_effect = lambda a: a
            return verify_usdc_payment(**defaults)

    def test_valid_transfer_returns_true(self):
        assert self._call(_mock_w3()) is True

    def test_wrong_recipient_returns_false(self):
        events = [_make_transfer_event("0xSomeoneElse", AMOUNT_UNITS)]
        assert self._call(_mock_w3(transfer_events=events)) is False

    def test_insufficient_amount_returns_false(self):
        events = [_make_transfer_event(VENDOR_ADDR, 1_000)]  # only 0.001 USDC
        assert self._call(_mock_w3(transfer_events=events)) is False

    def test_exact_amount_passes(self):
        events = [_make_transfer_event(VENDOR_ADDR, AMOUNT_UNITS)]
        assert self._call(_mock_w3(transfer_events=events)) is True

    def test_overpayment_passes(self):
        events = [_make_transfer_event(VENDOR_ADDR, AMOUNT_UNITS * 2)]
        assert self._call(_mock_w3(transfer_events=events)) is True

    def test_no_transfer_events_returns_false(self):
        assert self._call(_mock_w3(transfer_events=[])) is False

    def test_failed_tx_returns_false(self):
        assert self._call(_mock_w3(receipt_status=0)) is False

    def test_missing_receipt_returns_false(self):
        w3 = _mock_w3()
        w3.eth.get_transaction_receipt.return_value = None
        assert self._call(w3) is False

    def test_address_comparison_is_case_insensitive(self):
        events = [_make_transfer_event(VENDOR_ADDR.lower(), AMOUNT_UNITS)]
        assert self._call(_mock_w3(transfer_events=events), recipient=VENDOR_ADDR.upper()) is True


# ---------------------------------------------------------------------------
# send_usdc (wallet)
# ---------------------------------------------------------------------------

class TestSendUsdc:
    def _call(self, mock_w3_instance, **kwargs):
        from src.agent.wallet import send_usdc

        defaults = dict(
            recipient=VENDOR_ADDR,
            amount_usdc=AMOUNT_USDC,
            private_key="0x" + "a" * 64,
            rpc_url="http://localhost:8545",
        )
        defaults.update(kwargs)

        with patch("src.agent.wallet.Web3") as MockWeb3:
            MockWeb3.return_value = mock_w3_instance
            MockWeb3.HTTPProvider.return_value = MagicMock()
            MockWeb3.to_checksum_address.side_effect = lambda a: a
            return send_usdc(**defaults)

    def _mock_send_w3(self, tx_hash_hex: str = MOCK_TX_HASH):
        w3 = MagicMock()
        account = MagicMock()
        account.address = AGENT_ADDR

        w3.eth.account.from_key.return_value = account
        w3.eth.get_transaction_count.return_value = 0

        mock_contract = MagicMock()
        mock_tx = {"from": AGENT_ADDR, "nonce": 0, "chainId": 84532}
        mock_contract.functions.transfer.return_value.build_transaction.return_value = mock_tx
        w3.eth.contract.return_value = mock_contract

        signed = MagicMock()
        signed.raw_transaction = b"\x00" * 32
        w3.eth.account.sign_transaction.return_value = signed

        raw_bytes = bytes.fromhex(tx_hash_hex.removeprefix("0x"))
        w3.eth.send_raw_transaction.return_value = raw_bytes
        w3.eth.wait_for_transaction_receipt.return_value = MagicMock()

        return w3

    def test_returns_0x_tx_hash(self):
        result = self._call(self._mock_send_w3())
        assert result.startswith("0x")
        assert len(result) == len(MOCK_TX_HASH)

    def test_correct_amount_sent(self):
        w3 = self._mock_send_w3()
        self._call(w3)
        transfer_call = w3.eth.contract.return_value.functions.transfer
        _, amount_arg = transfer_call.call_args[0]
        assert amount_arg == AMOUNT_UNITS

    def test_correct_recipient(self):
        w3 = self._mock_send_w3()
        self._call(w3)
        transfer_call = w3.eth.contract.return_value.functions.transfer
        recipient_arg, _ = transfer_call.call_args[0]
        assert recipient_arg == VENDOR_ADDR

    def test_chain_id_is_base_sepolia(self):
        from src.agent.wallet import BASE_SEPOLIA_CHAIN_ID
        assert BASE_SEPOLIA_CHAIN_ID == 84532


# ---------------------------------------------------------------------------
# verify_payment routing (payment.py)
# ---------------------------------------------------------------------------

class TestVerifyPaymentRouting:
    def test_routes_to_mock_when_no_rpc_url(self, monkeypatch):
        monkeypatch.delenv("SEPOLIA_RPC_URL", raising=False)
        from src.vendor_server.payment import verify_payment
        # mock tx_hash + correct amount → mock accepts it
        assert verify_payment("0xmockhash", "0.05", "0.05", recipient=VENDOR_ADDR) is True

    def test_mock_rejects_empty_tx_hash(self, monkeypatch):
        monkeypatch.delenv("SEPOLIA_RPC_URL", raising=False)
        from src.vendor_server.payment import verify_payment
        assert verify_payment("", "0.05", "0.05", recipient=VENDOR_ADDR) is False

    def test_routes_to_real_verifier_when_rpc_url_set(self, monkeypatch):
        monkeypatch.setenv("SEPOLIA_RPC_URL", "http://localhost:8545")
        from src.vendor_server import payment as payment_mod

        with patch.object(payment_mod, "verify_payment", wraps=payment_mod.verify_payment):
            with patch("src.vendor_server.x402_verifier.verify_usdc_payment") as mock_verify:
                mock_verify.return_value = True
                result = payment_mod.verify_payment(
                    MOCK_TX_HASH, AMOUNT_USDC, AMOUNT_USDC, recipient=VENDOR_ADDR
                )
        assert result is True
        mock_verify.assert_called_once_with(MOCK_TX_HASH, VENDOR_ADDR, AMOUNT_USDC, "http://localhost:8545")

    def test_falls_back_to_mock_when_recipient_missing(self, monkeypatch):
        monkeypatch.setenv("SEPOLIA_RPC_URL", "http://localhost:8545")
        from src.vendor_server.payment import verify_payment
        # No recipient → mock mode even if RPC URL is set
        assert verify_payment("0xmockhash", "0.05", "0.05", recipient=None) is True


# ---------------------------------------------------------------------------
# pay_vendor tool routing (tools.py)
# ---------------------------------------------------------------------------

class TestPayVendorToolRouting:
    def test_mock_mode_generates_tx_hash(self, monkeypatch):
        monkeypatch.delenv("SEPOLIA_RPC_URL", raising=False)
        monkeypatch.delenv("AGENT_PRIVATE_KEY", raising=False)
        from fastapi.testclient import TestClient
        from src.vendor_server.main import app

        tc = TestClient(app, raise_server_exceptions=False)

        import httpx
        from tests.test_agent import _StarletteTransport
        http = httpx.Client(transport=_StarletteTransport(app), base_url="http://testserver")

        from src.agent.tools import pay_vendor
        result = pay_vendor(
            vendor_url="http://testserver",
            recipient_address=VENDOR_ADDR,
            amount=AMOUNT_USDC,
            payer_address=AGENT_ADDR,
            http_client=http,
        )
        assert "token" in result

    def test_real_mode_calls_send_usdc(self, monkeypatch):
        monkeypatch.setenv("SEPOLIA_RPC_URL", "http://localhost:8545")
        monkeypatch.setenv("AGENT_PRIVATE_KEY", "0x" + "a" * 64)

        from src.agent import tools as tools_mod

        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"token": "real-token", "expires_in": 3600}
        mock_http.post.return_value = mock_resp

        with patch("src.agent.wallet.send_usdc", return_value=MOCK_TX_HASH) as mock_send:
            result = tools_mod.pay_vendor(
                vendor_url="http://vendor",
                recipient_address=VENDOR_ADDR,
                amount=AMOUNT_USDC,
                payer_address=AGENT_ADDR,
                http_client=mock_http,
            )

        mock_send.assert_called_once_with(VENDOR_ADDR, AMOUNT_USDC, "0x" + "a" * 64, "http://localhost:8545")
        assert result["token"] == "real-token"
