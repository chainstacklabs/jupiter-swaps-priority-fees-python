import asyncio
import base58
import base64
import aiohttp
import statistics
import time
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

# Configuration
PRIVATE_KEY = "PRIVATE_KEY"

# trader node
RPC_ENDPOINT = "CHAINSTACK_NODE"

# regular node
# RPC_ENDPOINT = "CHAINSTACK_NODE"

# Jupiter Swap API. lite-api.jup.ag is keyless (low rate); api.jup.ag takes an
# X-API-Key header for higher tiers (get a key at https://portal.jup.ag).
# The old quote-api.jup.ag/v6 endpoints were retired on 2025-10-01.
JUPITER_API = "https://api.jup.ag/swap/v1"

INPUT_MINT = "So11111111111111111111111111111111111111112"  # SOL
OUTPUT_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC
AMOUNT = 1000000  # 0.001 SOL in lamports
AUTO_MULTIPLIER = 1.1  # a 10% bump to the median of getRecentPrioritizationFees over last 150 blocks
SLIPPAGE_BPS = 1000  # 10% slippage tolerance


# Get the priority fee data over the last 150 blocks and return the median.
# Note: if the majority of fees over the past 150 blocks are 0, you'll get a 0 here too.
# The median is more reliable than chasing a fluke astronomical fee, which can drain your account.
async def get_recent_prioritization_fees(client: AsyncClient, input_mint: str):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getRecentPrioritizationFees",
        "params": [[input_mint]]
    }
    await client.is_connected()
    async with aiohttp.ClientSession() as session:
        async with session.post(client._provider.endpoint_uri, json=body) as response:
            json_response = await response.json()
            print(f"Prioritization fee response: {json_response}")
            if json_response and "result" in json_response:
                fees = [fee["prioritizationFee"] for fee in json_response["result"]]
                return statistics.median(fees) if fees else 0
    return 0


async def jupiter_swap(input_mint, output_mint, amount, auto_multiplier):
    print("Initializing Jupiter swap...")
    keypair = Keypair.from_bytes(base58.b58decode(PRIVATE_KEY))
    wallet_address = keypair.pubkey()
    print(f"Wallet address: {wallet_address}")

    # Estimate the priority fee (in micro-lamports per compute unit) from recent blocks.
    async with AsyncClient(RPC_ENDPOINT) as client:
        print("Getting recent prioritization fees...")
        median_fee = await get_recent_prioritization_fees(client, input_mint)
        compute_unit_price = int(median_fee * auto_multiplier)
        print(f"Median priority fee: {median_fee} micro-lamports/CU -> using {compute_unit_price}")

    # Get a quote from Jupiter for the swap amount (the priority fee is applied separately, below).
    print("Getting quote from Jupiter...")
    quote_url = (
        f"{JUPITER_API}/quote?inputMint={input_mint}&outputMint={output_mint}"
        f"&amount={amount}&slippageBps={SLIPPAGE_BPS}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(quote_url, timeout=10) as response:
                response.raise_for_status()
                quote_response = await response.json()
                print(f"Quote: {amount} -> {quote_response['outAmount']} (out)")
    except aiohttp.ClientError as e:
        print(f"Error getting quote from Jupiter: {e}")
        return None

    # Build the swap transaction. Jupiter adds the compute-budget instructions for us:
    # computeUnitPriceMicroLamports applies our priority fee, and dynamicComputeUnitLimit
    # simulates the swap to set an accurate compute-unit limit.
    print("Getting swap transaction from Jupiter...")
    swap_url = f"{JUPITER_API}/swap"
    swap_data = {
        "quoteResponse": quote_response,
        "userPublicKey": str(wallet_address),
        "wrapAndUnwrapSol": True,
        "computeUnitPriceMicroLamports": compute_unit_price,
        "dynamicComputeUnitLimit": True,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(swap_url, json=swap_data, timeout=10) as response:
                response.raise_for_status()
                swap_response = await response.json()
                print(f"Priority fee applied (lamports): {swap_response.get('prioritizationFeeLamports')}")
    except aiohttp.ClientError as e:
        print(f"Error getting swap data from Jupiter: {e}")
        return None

    # Sign the returned versioned transaction and send it through your node.
    print("Signing and sending transaction...")
    async with AsyncClient(RPC_ENDPOINT) as client:
        try:
            transaction_bytes = base64.b64decode(swap_response["swapTransaction"])
            unsigned_tx = VersionedTransaction.from_bytes(transaction_bytes)
            signed_tx = VersionedTransaction(unsigned_tx.message, [keypair])

            result = await client.send_transaction(signed_tx)
            print("Transaction sent.")
            return result
        except Exception as e:
            print(f"Error creating or sending transaction: {str(e)}")
            return None


async def wait_for_confirmation(client, signature, max_timeout=60):
    start_time = time.time()
    while time.time() - start_time < max_timeout:
        try:
            status = await client.get_signature_statuses([signature])
            if status.value[0] is not None:
                return status.value[0].confirmation_status
        except Exception as e:
            print(f"Error checking transaction status: {e}")
        await asyncio.sleep(1)
    return None


async def main():
    try:
        print("Starting Jupiter swap...")
        print(f"Input mint: {INPUT_MINT}")
        print(f"Output mint: {OUTPUT_MINT}")
        print(f"Amount: {AMOUNT} lamports")
        print(f"Auto multiplier: {AUTO_MULTIPLIER}")

        result = await jupiter_swap(INPUT_MINT, OUTPUT_MINT, AMOUNT, AUTO_MULTIPLIER)
        if result:
            tx_signature = result.value
            solscan_url = f"https://solscan.io/tx/{tx_signature}"
            print(f"Transaction signature: {tx_signature}")
            print(f"Solscan link: {solscan_url}")
            print("Waiting for transaction confirmation...")
            async with AsyncClient(RPC_ENDPOINT) as client:
                confirmation_status = await wait_for_confirmation(client, tx_signature)
                print(f"Transaction confirmation status: {confirmation_status}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
