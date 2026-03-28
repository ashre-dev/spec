"""
On-chain USDC payment verification for Base Sepolia.

Used by the vendor's /pay endpoint when SEPOLIA_RPC_URL is set.
Falls back to mock_verify_payment when the env var is absent (dev/test mode).
"""

# Base Sepolia USDC (Circle's official deployment)
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
USDC_DECIMALS = 6

# Minimal ABI — only the Transfer event is needed for verification
_TRANSFER_EVENT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }
]


from web3 import Web3
from web3.logs import DISCARD


def verify_usdc_payment(
    tx_hash: str,
    recipient: str,
    amount_usdc: str,
    rpc_url: str,
) -> bool:
    """
    Verify that a Base Sepolia USDC transfer:
      - succeeded (transaction status == 1)
      - sent at least `amount_usdc` USDC
      - was directed to `recipient`

    Args:
        tx_hash:     0x-prefixed transaction hash.
        recipient:   Expected recipient wallet address (vendor).
        amount_usdc: Minimum required amount as a decimal string, e.g. "0.05".
        rpc_url:     HTTP(S) RPC endpoint for Base Sepolia.

    Returns:
        True if a qualifying transfer is found, False otherwise.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    raw_hash = bytes.fromhex(tx_hash.removeprefix("0x"))
    receipt = w3.eth.get_transaction_receipt(raw_hash)

    if receipt is None or receipt["status"] != 1:
        return False

    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_BASE_SEPOLIA),
        abi=_TRANSFER_EVENT_ABI,
    )

    # DISCARD suppresses errors from unrelated logs in the same tx
    events = usdc.events.Transfer().process_receipt(receipt, errors=DISCARD)
    required_units = int(float(amount_usdc) * 10**USDC_DECIMALS)

    for evt in events:
        to_addr: str = evt["args"]["to"]
        value: int = evt["args"]["value"]
        if to_addr.lower() == recipient.lower() and value >= required_units:
            return True

    return False
