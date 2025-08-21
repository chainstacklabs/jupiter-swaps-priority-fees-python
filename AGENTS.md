# AGENTS Guidelines for This Repository

This repository contains a Python script for executing Jupiter swaps on Solana with dynamic priority fees. When working on the project interactively with an agent (e.g. the Codex CLI) please follow the guidelines below for safe development and testing.

## 1. Use Test Amounts for Development

* **Always use minimal amounts** (e.g., 0.001 SOL) for testing.
* **Test on devnet first** if possible.
* **Do _not_ execute large swaps** during agent development sessions.
* **Monitor priority fees** to avoid wallet drainage.

## 2. Keep Dependencies in Sync

If you update dependencies:

1. Install with pip: `pip install solana aiohttp solders`.
2. Use specific versions for consistency.
3. Test with latest Jupiter API endpoints.
4. Verify compatibility with async Solana client.

## 3. Environment Configuration

Set up critical parameters in the script:

```python
PRIVATE_KEY = "YOUR_TEST_WALLET_KEY"  # Use test wallet only
RPC_ENDPOINT = "YOUR_CHAINSTACK_NODE"  # Trader node recommended
AMOUNT = 1000000  # 0.001 SOL (minimal test amount)
AUTO_MULTIPLIER = 1.1  # 10% bump to median fee
SLIPPAGE_BPS = 1000  # 10% slippage
```

Never commit private keys to version control.

## 4. Priority Fee Management

The script calculates priority fees dynamically:

* Fetches fees from last 150 blocks.
* Uses median to avoid outliers.
* Applies multiplier for better inclusion.
* Adds ComputeBudget instruction.

Monitor fee calculations to avoid excessive costs.

## 5. RPC Node Selection

Choose appropriate node type:

| Node Type | Use Case | Benefits |
| --------- | -------- | -------- |
| Trader Node | Production swaps | Lower latency |
| Regular Node | Development | Cost-effective |

## 6. Testing Workflow

Follow this safe testing sequence:

1. **Configure test parameters**: Use minimal amounts
2. **Check wallet balance**: Ensure sufficient SOL
3. **Verify token addresses**: Confirm correct mints
4. **Test fee calculation**: Review priority fee logic
5. **Execute small swap**: Start with 0.001 SOL
6. **Monitor transaction**: Check Solscan for confirmation

## 7. Token Configuration

Common token mints:
* **SOL**: `So11111111111111111111111111111111111111112`
* **USDC**: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
* **USDT**: `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`

Always verify addresses from official sources.

## 8. Error Handling

The script handles various errors:

* Network timeouts (10 second default)
* API failures
* Transaction signing errors
* Confirmation timeouts (60 seconds)

Add additional error handling as needed.

## 9. Safety Checklist

Before running swaps:

- [ ] Using test wallet
- [ ] Minimal swap amount
- [ ] Correct token addresses
- [ ] RPC endpoint working
- [ ] Priority fee reasonable
- [ ] Slippage appropriate

## 10. Common Issues

**"Insufficient lamports"**
- Top up SOL for fees
- Reduce swap amount
- Check priority fee calculation

**"Transaction simulation failed"**
- Verify wallet balance
- Check token liquidity
- Adjust slippage

**"RPC timeout"**
- Use different endpoint
- Increase timeout values
- Check network status

## 11. Monitoring Tools

Track transactions:
* **Solscan**: `https://solscan.io/tx/{signature}`
* **Explorer**: Verify transaction details
* **RPC logs**: Monitor client responses

## 12. Performance Optimization

* Use async operations for efficiency.
* Cache recent blockhash when possible.
* Batch RPC calls if needed.
* Monitor rate limits.

## 13. Development Best Practices

* Start with SOL→USDC swaps (most liquid).
* Test priority fee logic separately.
* Log all transaction details.
* Handle edge cases gracefully.
* Keep swap amounts minimal during testing.

## 14. Quick Test Commands

```bash
# Run the swap
python jupiter_swap.py

# Test with different parameters
# Edit script constants first
python jupiter_swap.py
```

## 15. Security Reminders

* **Never share private keys**.
* **Use dedicated test wallets**.
* **Monitor all transactions**.
* **Verify fee calculations**.
* **Check slippage settings**.
* **Confirm token addresses**.

---

Following these practices ensures safe Jupiter swap execution, prevents excessive fees, and maintains wallet security. Always test with minimal amounts and monitor priority fees carefully during development.