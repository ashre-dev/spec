"""
Agent wallet — sends USDC on Base Sepolia.

Used by pay_vendor when SEPOLIA_RPC_URL + AGENT_PRIVATE_KEY are both set.
When those env vars are absent the agent runs in mock mode (no real transactions).
"""

# Base Sepolia USDC
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
USDC_DECIMALS = 6
BASE_SEPOLIA_CHAIN_ID = 84532  # eip155:84532

# Minimal ABI — just the transfer function
_ERC20_TRANSFER_ABI = [
    {
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


from web3 import Web3


def send_usdc(
    recipient: str,
    amount_usdc: str,
    private_key: str,
    rpc_url: str,
    timeout: int = 120,
) -> str:
    """
    Sign and broadcast a USDC ERC-20 transfer on Base Sepolia.

    Args:
        recipient:   Vendor wallet address (checksum or lower-case).
        amount_usdc: Amount as a decimal string, e.g. "0.05".
        private_key: Agent's hex private key (0x-prefixed or bare).
        rpc_url:     HTTP(S) RPC endpoint for Base Sepolia.
        timeout:     Seconds to wait for receipt.

    Returns:
        0x-prefixed transaction hash string.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = w3.eth.account.from_key(private_key)

    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_BASE_SEPOLIA),
        abi=_ERC20_TRANSFER_ABI,
    )

    amount_units = int(float(amount_usdc) * 10**USDC_DECIMALS)

    tx = usdc.functions.transfer(
        Web3.to_checksum_address(recipient),
        amount_units,
    ).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": BASE_SEPOLIA_CHAIN_ID,
        }
    )

    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash_bytes = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=timeout)

    return "0x" + tx_hash_bytes.hex()
