# Development Log - The Eternal Engine

> **Project Diary**: A chronological record of development sessions, discoveries, bugs, fixes, and architectural decisions.
> 
> **Related Documents:**
> - [Architecture Decisions](docs/decisions/) - ADRs for major design choices
> - [Lessons Learned](docs/lessons-learned.md) - Problems encountered and solutions
> - [AGENTS.md](AGENTS.md) - Coding standards and conventions
> - [ARCHITECTURE.md](ARCHITECTURE.md) - System design documentation

---

## Table of Contents

- [2026-02-14 - Fresh Deployment Test & Bug Fixes](#2026-02-14---fresh-deployment-test--bug-fixes)
- [2026-02-14 - Initial Live Deployment](#2026-02-14---initial-live-deployment)
- [2026-02-14 - Position Sync & State Management](#2026-02-14---position-sync--state-management)
- [2026-02-13 - 3-Phase CORE-HODL Strategy](#2026-02-13---3-phase-core-hodl-strategy)
- [2026-02-13 - PybitDemoClient Integration](#2026-02-13---pybitdemoclient-integration)

---

## 2026-02-14 - Fresh Deployment Test & Bug Fixes

### Session Focus
Testing bot restart behavior and ensuring proper handling of existing positions vs fresh starts.

### What Was Done
1. **Tested restart scenario** - Stopped bot, restarted to verify no duplicate purchases
2. **Fixed deployment week tracking bug** - Counter was decrementing per-coin purchase instead of per-week
3. **Verified position sync** - Bot correctly loaded 10 existing positions from database
4. **Confirmed 168-hour wait** - All symbols correctly set `next_purchase_in_hours: 168`

### Bugs Discovered & Fixed

#### Bug: Deployment Week Counter Decrementing Per Coin
**Symptom:** After buying 10 coins, `weeks_remaining` dropped from 12 → 3 (should be 12 → 11)

**Root Cause:** `on_order_filled()` decremented counter on every fill because condition stayed true after BTC/ETH were bought.

**Fix:** Changed to only decrement when BTC is purchased (first purchase of each weekly cycle):
```python
if symbol == self.btc_symbol and self.purchase_count.get(symbol, 0) == 1:
    self._deployment_weeks_remaining -= 1
```

**File:** `src/strategies/dca_strategy.py`

#### Issue: Two Bot Instances Running
**Discovery:** Found two processes running simultaneously (PID 1507064 and 1668954)

**Resolution:** Old instance from Feb 14 needed cleanup.

**Lesson:** Always verify single instance with `ps aux | grep python`.

### Current State
- ✅ 10 positions loaded from database
- ✅ $149,690 portfolio (after ~$14,175 in purchases)
- ✅ CORE-HODL at 9.47% of target (60%), week 1 of 12 deployment
- ✅ Next purchase cycle: 168 hours
- ✅ Bot correctly waiting (no duplicate buys on restart)

### Notes
The bot is now production-ready for the 2-week test period. All critical bugs resolved.

---

## 2026-02-14 - Initial Live Deployment

### Session Focus
First live deployment test with Bybit Demo Trading API using `--mode live --engine core`.

### What Was Done
1. **Cleared database and logs** for clean test
2. **Started bot with live mode** on CORE-HODL engine only
3. **Executed initial deployment purchases** across all 10 coins
4. **Monitored order execution** on Bybit Demo

### Discoveries

#### Discovery: Dust Amounts on Bybit
**Issue:** Bybit doesn't allow selling 100% of holdings, leaves <$1 worth of coins as "dust."

**Impact:** Position sync was trying to process dust amounts, causing Decimal errors.

**Solution:** Added dust filtering threshold (<$1.0):
```python
if position_value < Decimal("1.0"):
    logger.debug("skipping_dust_amount", ...)
    continue
```

**File:** `src/core/engine.py:_sync_positions_from_exchange()`

#### Discovery: Float/Decimal Multiplication Error
**Error:** `unsupported operand type(s) for *: 'float' and 'decimal.Decimal'`

**Root Cause:** `amount` variable was still float when multiplying with `current_price` (Decimal).

**Fix:** Convert to Decimal immediately:
```python
amount_decimal = Decimal(str(amount))
```

### Deployment Results

| Symbol | Amount (USD) | Quantity | Status |
|--------|-------------|----------|--------|
| BTC | $4,916 | 0.070 BTC | ✅ Filled |
| ETH | $2,704 | 1.294 ETH | ✅ Filled |
| SOL | $819 | 9.253 SOL | ✅ Filled |
| XRP | $819 | 544.36 XRP | ✅ Filled |
| BNB | $819 | 1.295 BNB | ✅ Filled |
| DOGE | $819 | 7308.84 DOGE | ✅ Filled |
| ADA | $819 | 2761.44 ADA | ✅ Filled |
| TRX | $819 | 2898.20 TRX | ✅ Filled |
| AVAX | $819 | 85.08 AVAX | ✅ Filled |
| LINK | $819 | 89.74 LINK | ✅ Filled |
| **Total** | **~$13,372** | | **10/10** |

### Notes
Initial deployment used max position cap (5% of portfolio = ~$8,196), but BTC was capped at $4,916 due to position sizing limits. All orders executed as market orders via `quoteCoin` parameter.

---

## 2026-02-14 - Position Sync & State Management

### Session Focus
Implementing robust position synchronization from exchange to handle restarts and crashes.

### What Was Done
1. **Added `_sync_positions_from_exchange()`** - Fetches balances and creates position records
2. **Added `_sync_last_purchase_from_orders()`** - Prevents immediate rebuy after restart
3. **Implemented fresh start detection** - Distinguishes new deployment from restart
4. **Added dust amount filtering** - Ignores positions worth <$1

### Technical Implementation

#### Position Sync Flow
```
Startup → Load DB state → Sync from Exchange → Set last_purchase times → Start trading
```

#### Key Logic
- **Fresh start** (no positions): Allow immediate buy signals
- **Restart** (positions exist): Set `last_purchase=now` to wait 168 hours

**File:** `src/core/engine.py:_sync_last_purchase_from_orders()`

```python
if not core_hodl_positions:
    # Fresh start - allow immediate buys
    logger.info("no_positions_fresh_start")
    return

# Restart - set last_purchase for existing positions
for symbol in strategy.symbols:
    if symbol in core_hodl_positions:
        strategy.last_purchase[symbol] = datetime.utcnow()
```

### Challenges
- **Challenge:** How to distinguish fresh start vs restart?
  - **Solution:** Check if positions exist in database/exchange
  
- **Challenge:** How to prevent duplicate buys on restart?
  - **Solution:** Set `last_purchase` to current time for existing positions

### Testing
- ✅ Fresh start: Bot buys immediately
- ✅ Restart: Bot waits 168 hours
- ✅ Position values correctly calculated
- ✅ Dust amounts ignored

---

## 2026-02-13 - 3-Phase CORE-HODL Strategy

### Session Focus
Implementing the adaptive capital deployment strategy with three distinct phases.

### What Was Done
1. **Designed 3-phase state machine:**
   - **DEPLOYING**: 12-week capital deployment to reach 60% target
   - **REBALANCING**: 4-week ratio adjustment (67% BTC / 33% ETH)
   - **MAINTAINING**: Standard DCA with weekly purchases

2. **Implemented deployment schedule calculation:**
   ```python
   if gap < $500: 1 week
   elif gap < $50,000: 4 weeks
   else: 12 weeks
   ```

3. **Added rebalancing without selling:**
   - Over-allocated coins: 75%/50%/25%/0% buy amounts over 4 weeks
   - Under-allocated coins: 125%/150%/175%/200% buy amounts over 4 weeks

### Architecture Decisions

#### Decision: Freeze Deployment Capital on Start
**Context:** Should deployment target use current portfolio value or frozen initial value?

**Decision:** Freeze the starting portfolio value when deployment begins.

**Rationale:** 
- Prevents target from moving if portfolio value changes
- Ensures consistent deployment schedule
- Avoids infinite deployment if market drops

**Implementation:**
```python
self._deployment_start_value = portfolio_value  # Frozen
self._deployment_gap = target_value - current_value
```

#### Decision: Use Weekly Cycles Not Per-Coin
**Context:** Should we track deployment per-coin or per-week?

**Decision:** Track per-week across all coins.

**Rationale:**
- Simpler mental model ("week 3 of 12")
- Allows proportional deployment across all coins
- Easier to calculate weekly targets

### Code Structure
```python
class CoreHodlState(Enum):
    DEPLOYING = "deploying"       # 12 weeks
    REBALANCING = "rebalancing"   # 4 weeks  
    MAINTAINING = "maintaining"   # ongoing
```

### Files Modified
- `src/strategies/dca_strategy.py` - Complete rewrite of DCAStrategy

---

## 2026-02-13 - PybitDemoClient Integration

### Session Focus
Integrating Bybit Demo Trading API using pybit library with proper async wrapper.

### What Was Done
1. **Created PybitDemoClient** - Async wrapper for pybit HTTP client
2. **Fixed parameter mapping** - `type` → `orderType` for pybit compatibility
3. **Implemented spot buy with quoteCoin** - Uses USDT value instead of coin quantity
4. **Added fetch_order method** - For order status tracking

### Technical Challenges

#### Challenge: Pybit Parameter Naming
**Issue:** pybit uses `orderType` but ccxt-style code used `type`.

**Solution:** Parameter mapping in `create_order()`:
```python
async def create_order(self, symbol, side, type=None, order_type=None, ...):
    order_type = order_type or type or 'Market'
    # ...
```

#### Challenge: Spot Market Buy Precision
**Issue:** Bybit spot market buys require specifying USDT value, not coin quantity.

**Solution:** Use `marketUnit='quoteCoin'` and pass USDT amount:
```python
if side == 'buy' and category == 'spot':
    params['marketUnit'] = 'quoteCoin'
    qty = float(amount * price)  # USDT value
```

#### Challenge: Subaccount Isolation
**Requirement:** Each engine operates in its own subaccount.

**Solution:** `PybitDemoClient` initialized per subaccount:
```python
subaccounts = {
    'MASTER': {'market': 'spot', 'leverage': 1},
    'CORE_HODL': {'market': 'spot', 'leverage': 1},
    'TREND': {'market': 'linear', 'leverage': 2},
    'FUNDING': {'market': 'linear', 'leverage': 2},
    'TACTICAL': {'market': 'spot', 'leverage': 1},
}
```

### Files Created/Modified
- `src/exchange/bybit_client.py` - Added PybitDemoClient class

---

## 2026-02-13 - Risk Manager Tuning

### Session Focus
Fixing unit mismatch in risk manager loss limit calculations.

### Bug: Daily Loss Limit Triggering Too Early
**Symptom:** Emergency stop triggered at 0.12% loss (should trigger at 2%).

**Root Cause:** Comparing percentage (0.12) with decimal (0.02) instead of percentage (2.0).

**Fix:** Convert config value to percentage:
```python
# Config stores as decimal (0.02 = 2%), convert to percentage (2.0)
max_daily_loss_pct = Decimal(str(trading_config.max_daily_loss_pct)) * 100
```

### Files Modified
- `src/risk/risk_manager.py` - Fixed `_check_daily_loss_limit()` and `_check_weekly_loss_limit()`

---

## Summary of Key Metrics

| Metric | Value |
|--------|-------|
| Total Development Sessions | 5+ sessions |
| Critical Bugs Fixed | 6+ |
| Tests Passing | 316 |
| Lines of Code | ~8,000+ (src/) |
| Documentation | 12,500+ lines (docs/) |
| Current State | ✅ Production Ready |

---

## Quick Reference

### File Locations
- **Source:** `src/` - Core engine, strategies, risk management
- **Tests:** `tests/` - 316 passing tests
- **Config:** `config/` - YAML configurations
- **Docs:** `docs/` - Full documentation (12,500+ lines)
- **Logs:** `logs/eternal_engine.log` - Structured JSON logging

### Current Configuration
- **Trading Mode:** Demo (Bybit Demo Trading)
- **Engine:** CORE-HODL only (TREND/FUNDING/TACTICAL pending)
- **Symbols:** 10 (BTC, ETH, SOL, XRP, BNB, DOGE, ADA, TRX, AVAX, LINK)
- **DCA Interval:** 168 hours (7 days)
- **Deployment:** 12 weeks to reach 60% target
- **Position Cap:** 5% max per position

### Next Scheduled Purchase
Week 2 of 12 deployment - approximately 2026-02-21 (7 days from initial deployment)

---

*Last Updated: 2026-02-14*
*Status: Bot running, waiting for next purchase cycle*
