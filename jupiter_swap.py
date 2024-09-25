import asyncio
import base58
import base64
import aiohttp
import statistics
import time
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.compute_budget import set_compute_unit_price

# Configuration
PRIVATE_KEY = "PRIVATE_KEY"

# trader node
RPC_ENDPOINT = "CHAINSTACK_NODE"

# regular node
# RPC_ENDPOINT = "CHAINSTACK_NODE"

INPUT_MINT = "So11111111111111111111111111111111111111112"  # SOL
OUTPUT_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC
AMOUNT = 1000000  # 0.001 SOL in lamports
AUTO_MULTIPLIER = 1.1 # a 10% bump to the median of getRecentPrioritizationFees over last 150 blocks
SLIPPAGE_BPS = 1000  # 10% slippage tolerance

async def get_recent_blockhash(client: AsyncClient):
    response = await client.get_latest_blockhash()
    return response.value.blockhash, response.value.last_valid_block_height

# Get the data on the priority fees over the last 150 blocks.
# Note that it calculates the priority fees median from the returned data.
# And if the majority of fees over the past 150 blocks are 0, you'll get a 0 here as well.
# I found the median approach more reliable and peace of mind over something like getting some
# fluke astronomical fee and using it. This can be easily drain your account.
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
                return statistics.median(fees)
    return 0

async def jupiter_swap(input_mint, output_mint, amount, auto_multiplier):
    print("Initializing Jupiter swap...")
    private_key = Keypair.from_bytes(base58.b58decode(PRIVATE_KEY))
    WALLET_ADDRESS = private_key.pubkey()
    print(f"Wallet address: {WALLET_ADDRESS}")

    async with AsyncClient(RPC_ENDPOINT) as client:
        print("Getting recent blockhash...")
        recent_blockhash, last_valid_block_height = await get_recent_blockhash(client)
        print(f"Recent blockhash: {recent_blockhash}")
        print(f"Last valid block height: {last_valid_block_height}")

        print("Getting recent prioritization fees...")
        prioritization_fee = await get_recent_prioritization_fees(client, input_mint)
        prioritization_fee *= auto_multiplier
        print(f"Prioritization fee: {prioritization_fee}")

    total_amount = int(amount + prioritization_fee)
    print(f"Total amount (including prioritization fee): {total_amount}")

    print("Getting quote from Jupiter...")
    quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={total_amount}&slippageBps={SLIPPAGE_BPS}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(quote_url, timeout=10) as response:
                response.raise_for_status()
                quote_response = await response.json()
                print(f"Quote response: {quote_response}")
    except aiohttp.ClientError as e:
        print(f"Error getting quote from Jupiter: {e}")
        return None

    print("Getting swap data from Jupiter...")
    swap_url = "https://quote-api.jup.ag/v6/swap"
    swap_data = {
        "quoteResponse": quote_response,
        "userPublicKey": str(WALLET_ADDRESS),
        "wrapUnwrapSOL": True
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(swap_url, json=swap_data, timeout=10) as response:
                response.raise_for_status()
                swap_response = await response.json()
                print(f"Swap response: {swap_response}")
    except aiohttp.ClientError as e:
        print(f"Error getting swap data from Jupiter: {e}")
        return None

    print("Creating and signing transaction...")
    async with AsyncClient(RPC_ENDPOINT) as client:
        try:
            swap_transaction = swap_response['swapTransaction']
            print(f"Swap transaction length: {len(swap_transaction)}")
            print(f"Swap transaction type: {type(swap_transaction)}")
            
            transaction_bytes = base64.b64decode(swap_transaction)
            print(f"Decoded transaction length: {len(transaction_bytes)}")
            
            unsigned_tx = VersionedTransaction.from_bytes(transaction_bytes)
            print(f"Deserialized transaction: {unsigned_tx}")

            # Add ComputeBudget instruction to do the prioritization fee as implemented in solders
            compute_budget_ix = set_compute_unit_price(int(prioritization_fee))
            unsigned_tx.message.instructions.insert(0, compute_budget_ix)
            
            signed_tx = VersionedTransaction(unsigned_tx.message, [private_key])
            
            print(f"Final transaction to be sent: {signed_tx}")
            
            print("Sending transaction...")
            result = await client.send_transaction(signed_tx)
            print("Transaction sent.")
            tx_signature = result.value
            tx_details = await client.get_transaction(tx_signature)
            print(f"Confirmed transaction details: {tx_details}")
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
