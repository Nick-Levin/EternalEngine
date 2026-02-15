# ADR 003: Position Synchronization from Exchange

**Status:** Accepted  
**Date:** 2026-02-14  
**Deciders:** Development Team  
**Context:** Handling bot restarts with existing positions

---

## Context and Problem Statement

When the bot restarts, it needs to:
1. Know what positions exist on the exchange
2. Prevent immediate duplicate purchases
3. Distinguish between fresh start (no positions) and restart (positions exist)

Without proper sync, the bot would either:
- Buy immediately on restart (duplicate purchases)
- Not buy when it should (if database was cleared)

## Decision Drivers

- Must handle database cleared but positions exist on exchange
- Must handle bot restart after crash
- Must handle manual position creation
- Must not duplicate purchases
- Must allow fresh start (immediate first purchase)

## Considered Options

### Option 1: Database Only
**Approach:** Only trust database for position state.

**Pros:** Simple, single source of truth  
**Cons:** Database cleared = lost positions, bot buys again

### Option 2: Exchange Only
**Approach:** Always query exchange, ignore database.

**Pros:** Always accurate  
**Cons:** No local state tracking, complex order history reconstruction

### Option 3: Hybrid with Sync (Selected)
**Approach:** Load database state, sync from exchange, handle dust, set last_purchase appropriately.

**Pros:**
- Database as primary, exchange as verification
- Handles database cleared scenarios
- Proper last_purchase handling
- Dust filtering

**Cons:** More complex startup sequence

## Decision

**Chosen Option: Option 3 (Hybrid with Exchange Sync)**

### Sync Flow
```
Startup
  │
  ▼
Load positions from database
  │
  ▼
Sync positions from exchange
  ├─ Skip dust amounts (<$1)
  ├─ Create missing positions
  └─ Log existing positions
  │
  ▼
Sync last_purchase times
  ├─ Fresh start (no positions): Allow immediate buys
  └─ Restart (positions exist): Set last_purchase=now
  │
  ▼
Start trading loop
```

## Implementation

### Dust Amount Filtering
```python
# Skip dust amounts that Bybit leaves behind
position_value = amount_decimal * current_price
if position_value < Decimal("1.0"):
    logger.debug("skipping_dust_amount", ...)
    continue
```

### Fresh Start vs Restart Detection
```python
# Check if we have any positions
if not core_hodl_positions:
    # No positions - this is a fresh start
    logger.info("no_positions_fresh_start")
    return  # Don't set last_purchase, allow immediate buys

# Positions exist - this is a restart
for symbol in core_hodl_positions:
    strategy.last_purchase[symbol] = datetime.utcnow()
```

### Decimal Type Safety
```python
# Convert immediately to avoid float/Decimal errors
amount_decimal = Decimal(str(amount))
```

## Consequences

### Positive
- Handles all restart scenarios
- No duplicate purchases
- Dust amounts don't cause errors
- Fresh start works correctly

### Negative
- Startup takes longer (multiple API calls)
- Must handle exchange API failures gracefully
- Position values use current price (not entry price)

## Testing Scenarios

| Scenario | Expected Behavior | Status |
|----------|------------------|--------|
| Fresh start, no DB, no positions | Buy immediately | ✅ |
| Restart, DB intact | Wait 168h | ✅ |
| DB cleared, positions exist | Sync positions, wait 168h | ✅ |
| Dust amounts only | Ignore dust, buy immediately | ✅ |

## References
- [DEVLOG.md](../../DEVLOG.md) - Position Sync & State Management
- `src/core/engine.py:_sync_positions_from_exchange()`
- `src/core/engine.py:_sync_last_purchase_from_orders()`
