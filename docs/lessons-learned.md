# Lessons Learned

> **Development War Stories**: Problems encountered, mistakes made, and solutions found during the development of The Eternal Engine.
> 
> **Related:**
> - [DEVLOG.md](../DEVLOG.md) - Chronological development diary
> - [Architecture Decisions](decisions/) - Formal ADRs
> - [AGENTS.md](../AGENTS.md) - Coding standards

---

## Table of Contents

- [Bybit Demo Trading Quirks](#bybit-demo-trading-quirks)
- [Type Safety with Decimal](#type-safety-with-decimal)
- [Async Wrapper Patterns](#async-wrapper-patterns)
- [State Management on Restart](#state-management-on-restart)
- [Risk Manager Unit Mismatch](#risk-manager-unit-mismatch)
- [Position Sync Edge Cases](#position-sync-edge-cases)

---

## Bybit Demo Trading Quirks

### The Problem: Dust Amounts

**What Happened:**
Bybit doesn't allow selling 100% of your holdings. When you sell, it leaves behind tiny amounts ("dust") worth less than $1. These can't be sold and accumulate in the account.

**Impact:**
Our position sync code tried to process these dust amounts, causing:
1. Decimal/float multiplication errors
2. False position creation in database
3. Incorrect portfolio value calculations

**Solution:**
Added dust filtering in `_sync_positions_from_exchange()`:

```python
# Skip dust amounts (less than $1.0 worth)
position_value = amount_decimal * current_price
if position_value < Decimal("1.0"):
    logger.debug("trading_engine.skipping_dust_amount",
               symbol=trading_symbol,
               value_usd=str(position_value))
    continue
```

**Lesson:** Always validate exchange data before processing. Exchanges have quirks that aren't documented.

---

## Type Safety with Decimal

### The Problem: Float × Decimal

**Error Message:**
```
unsupported operand type(s) for *: 'float' and 'decimal.Decimal'
```

**What Happened:**
The exchange API returns amounts as floats. We tried to multiply directly with Decimal prices:

```python
# WRONG - This fails
position_value = amount * current_price  # float * Decimal = Error
```

**Solution:**
Convert to Decimal immediately upon receiving:

```python
# CORRECT
amount_decimal = Decimal(str(amount))
position_value = amount_decimal * current_price  # Decimal * Decimal = OK
```

**Lesson:** Never mix float and Decimal. Convert to Decimal at the system boundary (API input/output).

**Files Affected:**
- `src/core/engine.py:_sync_positions_from_exchange()`
- `src/exchange/bybit_client.py` (multiple methods)

---

## Async Wrapper Patterns

### The Problem: Pybit is Sync, We Need Async

**Context:**
Pybit (Bybit's SDK) is synchronous, but our entire engine is built on asyncio for concurrent operations.

**Solution Pattern:**
```python
class PybitDemoClient:
    def __init__(self, ...):
        self.session = HTTP(...)  # Sync pybit session
    
    async def create_order(self, ...):
        # Wrap sync call in async
        return await asyncio.to_thread(
            self._create_order_sync, ...
        )
    
    def _create_order_sync(self, ...):
        # Actual sync implementation
        return self.session.place_order(...)
```

**Key Insight:**
`asyncio.to_thread()` is the cleanest way to wrap sync libraries. It runs the sync code in a thread pool without blocking the event loop.

---

## State Management on Restart

### The Problem: Duplicate Purchases on Restart

**Scenario:**
1. Bot buys BTC at 10:00 AM
2. Bot stopped at 10:05 AM
3. Bot restarted at 10:10 AM
4. **Bug:** Bot buys BTC again immediately!

**Root Cause:**
The DCA strategy's `last_purchase` dict was empty on restart, so `analyze()` thought it was time to buy again.

**The Fix:**
Two-part solution:

1. **Fresh Start Detection:** Check if positions exist
```python
if not core_hodl_positions:
    # Fresh start - don't set last_purchase
    logger.info("no_positions_fresh_start")
    return
```

2. **Set last_purchase on Restart:**
```python
# Positions exist - set last_purchase to prevent rebuy
for symbol in core_hodl_positions:
    strategy.last_purchase[symbol] = datetime.utcnow()
```

**Lesson:** Always consider restart scenarios. State must be either reconstructed from database or synced from exchange.

---

## Risk Manager Unit Mismatch

### The Problem: Emergency Stop Too Early

**Symptom:**
Emergency stop triggered at 0.12% loss when limit was set to 2%.

**Root Cause:**
Config stores `max_daily_loss_pct=0.02` (meaning 2%), but risk manager was comparing:
```python
# WRONG - Comparing percentage with decimal
daily_loss_pct = 0.12  # 0.12% loss
max_daily_loss_pct = 0.02  # Config value (meaning 2%)

if daily_loss_pct >= max_daily_loss_pct:  # 0.12 >= 0.02 is True!
    trigger_emergency_stop()
```

**The Fix:**
Convert config decimal to percentage:
```python
# CORRECT
max_daily_loss_pct = Decimal(str(trading_config.max_daily_loss_pct)) * 100
# Now: 0.02 * 100 = 2.0

if daily_loss_pct >= max_daily_loss_pct:  # 0.12 >= 2.0 is False - OK
```

**Lesson:** Be explicit about units. Document whether a config value is a decimal (0.02) or percentage (2.0).

---

## Position Sync Edge Cases

### Edge Case 1: Database Cleared, Positions Exist

**Scenario:**
User clears database but positions still on exchange.

**Behavior Before Fix:**
Bot would buy again, creating duplicate positions.

**Behavior After Fix:**
Bot syncs positions from exchange, sets `last_purchase`, waits 168h.

### Edge Case 2: Partial Position Data

**Scenario:**
Position exists in database but was manually closed on exchange.

**Behavior:**
Bot keeps position in memory but it's stale. Next balance update shows discrepancy.

**Mitigation:**
Regular balance updates (every 5 minutes) catch discrepancies.

### Edge Case 3: Position With Zero Value

**Scenario:**
Position exists but current price makes it worth $0 (extreme edge case).

**Handling:**
```python
if position_value <= 0:
    logger.warning("sync_zero_value_position", symbol=symbol)
    continue
```

---

## Testing Lessons

### Lesson: Always Test Restart Behavior

**What We Did Wrong:**
Only tested fresh starts. Didn't test restart with existing positions until late in development.

**What We Should Have Done:**
Test matrix should include:
- Fresh start (no DB, no positions)
- Restart (DB intact)
- Restart (DB cleared, positions exist)
- Restart (dust amounts only)

### Lesson: Log Everything During Development

Structured logging (JSON) saved us multiple times:
- Easy to grep for specific events
- Can replay what happened
- Helps with debugging production issues

---

## Performance Lessons

### Lesson: Don't Block the Event Loop

**Mistake:** Early versions called sync exchange methods directly:
```python
# WRONG - Blocks entire engine
balance = self.exchange.fetch_balance_sync()  # 500ms block
```

**Solution:** Always use async wrappers:
```python
# CORRECT - Non-blocking
balance = await self.exchange.fetch_balance()  # 500ms in thread, engine continues
```

---

## Deployment Lessons

### Lesson: Demo First, Live Later

Bybit Demo Trading API was essential for testing:
- Can test with $100k+ without risk
- Identified dust amount issue
- Verified order execution flow

**Recommendation:** Never test new strategies with live funds. Demo trading is identical to live in terms of API behavior.

---

## Quick Reference: Common Issues

| Issue | Solution | File |
|-------|----------|------|
| Dust amounts | Filter positions < $1 | `engine.py:_sync_positions_from_exchange()` |
| Float/Decimal | `Decimal(str(value))` | All monetary calculations |
| Duplicate buys | Set `last_purchase` on restart | `engine.py:_sync_last_purchase_from_orders()` |
| Unit mismatch | Document and convert units | `risk_manager.py` |
| Sync API | Use `asyncio.to_thread()` | `bybit_client.py` |

---

*Last Updated: 2026-02-14*
*Contributors: Development Team*
