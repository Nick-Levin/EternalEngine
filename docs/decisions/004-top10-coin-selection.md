# ADR 004: TOP 10 Coin Selection for CORE-HODL

**Status:** Accepted  
**Date:** 2026-02-13  
**Deciders:** Development Team  
**Context:** Diversifying CORE-HODL beyond BTC/ETH

---

## Context and Problem Statement

Original CORE-HODL design specified only BTC (40%) and ETH (20%). However, this leaves 40% of the 60% target undeployed if we strictly follow the ratio. The decision was made to expand to a diversified basket of top cryptocurrencies.

## Decision Drivers

- Must deploy full 60% allocation
- Must maintain BTC/ETH as primary holdings
- Must include established, liquid altcoins
- Must be suitable for long-term holding (HODL)

## Coin Selection Criteria

1. **Market Cap:** Top 20 by market capitalization
2. **Liquidity:** High daily trading volume
3. **Longevity:** Established projects (2+ years)
4. **Availability:** Listed on Bybit spot market
5. **Diversity:** Different use cases (L1, DeFi, Meme, Infrastructure)

## Selected Coins

| Coin | Category | Rationale |
|------|----------|-----------|
| **BTC** | Store of Value | Primary holding (67% of crypto allocation) |
| **ETH** | Smart Contract Platform | Secondary holding (33% of crypto allocation) |
| **SOL** | L1 Blockchain | High-performance alternative to ETH |
| **XRP** | Payments | Cross-border payment solution |
| **BNB** | Exchange Token | Ecosystem utility token |
| **DOGE** | Meme | Cultural significance, liquidity |
| **ADA** | Smart Contract Platform | Academic approach, PoS |
| **TRX** | Infrastructure | Stablecoin transaction volume |
| **AVAX** | L1 Blockchain | Subnet architecture |
| **LINK** | Oracle | Infrastructure for DeFi |

## Allocation Strategy

### Within CORE-HODL (60% of portfolio):
- **BTC**: 40% of portfolio (67% of CORE-HODL)
- **ETH**: 20% of portfolio (33% of CORE-HODL)
- **Altcoins**: Equal weighting of remaining weekly deployment

### Weekly Deployment Example ($5,500/week):
- BTC: Higher weight (target 67% ratio)
- ETH: Medium weight (target 33% ratio)
- Altcoins: Equal split of remaining amount

## Implementation

```python
# Default symbols configuration
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
    "DOGEUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT", "LINKUSDT"
]

# BTC/ETH get special treatment for ratio maintenance
self.btc_symbol = "BTCUSDT"
self.eth_symbol = "ETHUSDT"
```

## Risk Considerations

### Benefits
- Diversification reduces single-asset risk
- Exposure to different crypto sectors
- Better capital utilization

### Risks
- More assets to monitor
- Some altcoins more volatile
- Rebalancing complexity

### Mitigations
- Position sizing limits (5% max per position)
- Stop-losses on all positions
- Weekly DCA reduces timing risk

## Future Considerations

- **Rebalancing:** Quarterly rebalancing to maintain target ratios
- **Delisting Risk:** Monitor exchange listings
- **Market Changes:** Review basket annually

## References
- [DEVLOG.md](../../DEVLOG.md)
- [AGENTS.md](../../AGENTS.md) - CORE-HODL specifications
- `src/core/config.py` - Default symbols configuration
