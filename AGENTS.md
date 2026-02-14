# AGENTS.md - The Eternal Engine

> **⚠️ CRITICAL: READ THIS FILE BEFORE MODIFYING ANY CODE**
>
> This document is the SINGLE SOURCE OF TRUTH for AI agents working on The Eternal Engine.
> It contains non-negotiable principles, architectural patterns, and danger zones.
> When in doubt, refer to this document.

---

## 1. Project Identity

### The Eternal Engine

A **4-strategy autonomous trading system** designed for long-term capital compounding across crypto market regimes. This is not a trading bot—it is a capital compounding institution implemented in code.

**Core Philosophy:**
> "Survival comes before profit. You cannot compound capital that you've lost."

**System Purpose:**
- Provide diversified exposure across market conditions (bull, bear, sideways)
- Generate yield through multiple orthogonal strategies
- Protect capital through mechanical risk management
- Operate autonomously for decades

---

## 2. The Four Engines

Each engine operates independently in its own Bybit subaccount. If one fails, the others continue.

### 2.1 CORE-HODL (60% Allocation)
**Mission:** Long-term wealth compounding through systematic BTC/ETH accumulation

```yaml
Engine: CORE-HODL
Assets: BTC (40%), ETH (20%)
Market: Spot only (no derivatives)
Strategy: Quarterly rebalancing + DCA
Risk Level: MINIMAL
```

**Key Behaviors:**
- Buy fixed USD amount at regular intervals (DCA)
- Rebalance quarterly when allocation drifts >10%
- Move idle ETH to Bybit Earn for yield (min 2%)
- **NEVER sell during drawdowns** (accumulation phase only)

**Implementation:** See `src/strategies/dca_strategy.py`

### 2.2 TREND (20% Allocation)
**Mission:** Crisis alpha generation through 200DMA trend following

```yaml
Engine: TREND
Assets: BTC-PERP, ETH-PERP
Indicators: 200 SMA, 50 SMA, ADX(14), ATR(14)
Entry: Price > 200SMA, 50SMA > 200SMA, ADX > 25
Exit: Price closes below 200SMA
Risk Level: MODERATE
```

**Key Behaviors:**
- Long only when trend is up
- Exit to stables during bear markets
- ATR-based position sizing (1% risk per trade)
- Maximum 2x leverage (liquidation buffer >50%)

### 2.3 FUNDING (15% Allocation)
**Mission:** Market-neutral yield through funding rate arbitrage

```yaml
Engine: FUNDING
Strategy: Delta-neutral (Long spot + Short perp)
Assets: BTC, ETH, SOL
Entry: Predicted funding > 0.01% per 8h
Exit: Funding turns negative or basis > 2%
Risk Level: LOW
```

**Key Behaviors:**
- Harvest funding payments every 8 hours
- Maintain perfect 1:1 delta neutrality
- Reinvest 50% of profits, transfer 50% to TACTICAL
- Close immediately if basis exceeds 2%

### 2.4 TACTICAL (5% Allocation)
**Mission:** Extreme value deployment during market crashes

```yaml
Engine: TACTICAL
Trigger Levels:
  Level 1: BTC -50% from ATH → Deploy 50% of cash
  Level 2: BTC -70% from ATH → Deploy remaining 50%
Additional: Fear & Greed < 20, Funding < -0.05% for 3+ days
Exit: 100% profit target or 12 months
Risk Level: OPPORTUNISTIC
```

**Key Behaviors:**
- Does NOT trade regularly—waits for extremes
- Deploys immediately on trigger (market orders)
- 80% BTC, 20% ETH allocation
- Returns to CORE-HODL after profit target

**Implementation:** See `src/strategies/grid_strategy.py` (partial)

---

## 3. Architecture Overview

### 3.1 Multi-Layer System

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 5: PRESENTATION    - Dashboards, Alerts, Reports         │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 4: GOVERNANCE      - Circuit Breakers, Human Override    │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: ORCHESTRATION   - Capital Allocation, Rebalancing     │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: EXECUTION       - Order Management, Position Tracking │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: INFRASTRUCTURE  - Exchange Integration, Data Feeds    │
└─────────────────────────────────────────────────────────────────┘
```

**Design Principle:** Each layer is isolated and communicates via well-defined interfaces. A failure in Layer 1 (exchange API down) triggers Layer 4 (circuit breaker), but doesn't corrupt Layer 3 (orchestration state).

### 3.2 Data Flow

```
Bybit API → Data Pipeline → Strategy Engines → Risk Manager → Order Execution
                ↓
          Time-Series DB (InfluxDB) → Analytics Dashboard
```

### 3.3 Key Components

| Component | Purpose | File Location |
|-----------|---------|---------------|
| TradingEngine | Main orchestrator | `src/core/engine.py` |
| RiskManager | All risk controls | `src/risk/risk_manager.py` |
| ByBitClient | Exchange interface | `src/exchange/bybit_client.py` |
| BaseStrategy | Strategy template | `src/strategies/base.py` |
| Database | State persistence | `src/storage/database.py` |

---

## 4. Key Principles (NEVER Violate)

### 4.1 Position Sizing: 1/8 Kelly Criterion

We use **1/8th of the full Kelly recommendation** to provide 90% drawdown reduction vs. full Kelly.

```python
# CORRECT
kelly_fraction = 0.125  # 1/8 Kelly
max_position_pct = 0.05  # 5% max per position
max_risk_per_trade = 0.01  # 1% portfolio risk

# WRONG - NEVER DO THIS
kelly_fraction = 1.0  # Full Kelly - DANGEROUS
max_position_pct = 0.25  # 25% in one trade - DANGEROUS
```

**Why 1/8 Kelly:**
- Mathematically impossible to liquidate (survival > profit)
- Smooth equity curves for long-term compounding
- Buffer for strategy decay and changing markets

### 4.2 Four-Level Circuit Breakers

Automatic capital preservation at four drawdown thresholds:

| Level | Drawdown | Action | Recovery |
|-------|----------|--------|----------|
| **Level 1** | 10% | Reduce sizes 25%, widen stops | Auto at 5% from ATH |
| **Level 2** | 15% | Reduce sizes 50%, pause 72h | Manual approval required |
| **Level 3** | 20% | Close TREND/FUNDING, move 50% to Earn | Full audit required |
| **Level 4** | 25% | Full liquidation to USDT, halt | Dual auth + strategy changes |

```python
# In risk_manager.py - NEVER modify these thresholds without approval
CIRCUIT_BREAKERS = {
    'level_1': {'drawdown': 0.10, 'action': 'reduce_25_percent'},
    'level_2': {'drawdown': 0.15, 'action': 'reduce_50_percent_pause'},
    'level_3': {'drawdown': 0.20, 'action': 'close_directional'},
    'level_4': {'drawdown': 0.25, 'action': 'full_liquidation'},
}
```

### 4.3 Risk Manager Gate

**ALL trading signals MUST pass risk_manager.check_signal()**

```python
# CORRECT - Always check with risk manager
risk_check = self.risk_manager.check_signal(
    signal, self.portfolio, self.positions
)
if not risk_check.passed:
    logger.warning("Signal rejected", reason=risk_check.reason)
    return

# WRONG - NEVER execute without risk check
await self.exchange.create_order(...)  # DANGEROUS!
```

### 4.4 Decimal for ALL Monetary Calculations

```python
from decimal import Decimal

# CORRECT
position_value = Decimal("1000.50") * Decimal("2.5")
pnl = (current_price - entry_price) * amount

# WRONG - NEVER use float for money
position_value = 1000.50 * 2.5  # Floating point errors!
```

### 4.5 Async for ALL Exchange Operations

```python
# CORRECT
balance = await self.exchange.fetch_balance()
order = await self.exchange.create_order(...)

# WRONG - Blocking operations freeze the engine
balance = self.exchange.fetch_balance()  # NEVER!
```

### 4.6 API Key Security

```python
# CORRECT - Load from environment
api_key = bybit_config.api_key  # From .env file

# WRONG - NEVER hardcode keys
api_key = "actual_key_here"  # SECURITY BREACH!
```

### 4.7 Subaccount Isolation

Each engine operates in its own Bybit subaccount:
- Failure of one engine cannot contaminate others
- Master account controls capital allocation
- Separate API keys per engine (if possible)

---

## 5. File Organization

### 5.1 Directory Structure

```
/home/valard/dev/AiProjects/BybitTrader/
├── src/
│   ├── core/              # Engine, config, models
│   │   ├── engine.py      # Main TradingEngine
│   │   ├── config.py      # All configuration classes
│   │   └── models.py      # Data models (Order, Position, etc.)
│   │
│   ├── engines/           # Four strategy engines (future)
│   │   ├── core_engine.py
│   │   ├── trend_engine.py
│   │   ├── funding_engine.py
│   │   └── tactical_engine.py
│   │
│   ├── strategies/        # Current strategy implementations
│   │   ├── base.py        # BaseStrategy abstract class
│   │   ├── dca_strategy.py      # Maps to CORE-HODL
│   │   └── grid_strategy.py     # Maps to TACTICAL
│   │
│   ├── exchange/          # Exchange integration
│   │   └── bybit_client.py      # ByBit API wrapper
│   │
│   ├── risk/              # Risk management
│   │   └── risk_manager.py      # CRITICAL - All risk controls
│   │
│   ├── storage/           # Data persistence
│   │   └── database.py          # SQLite/PostgreSQL interface
│   │
│   ├── monitoring/        # Dashboards, alerts (future)
│   │   ├── dashboard.py
│   │   └── alerts.py
│   │
│   └── utils/             # Utilities
│       ├── logging_config.py
│       └── backtest.py
│
├── config/                # YAML configurations per engine
│   ├── core_hodl.yaml
│   ├── trend.yaml
│   ├── funding.yaml
│   └── tactical.yaml
│
├── docs/                  # Full documentation (12,500+ lines)
│   ├── 01-executive-summary/
│   ├── 02-investment-thesis/
│   ├── 03-system-architecture/
│   ├── 04-trading-strategies/
│   ├── 05-risk-management/
│   ├── 06-infrastructure/
│   ├── 07-monitoring-governance/
│   ├── 08-financial-projections/
│   ├── 09-implementation/
│   └── 10-appendices/
│
├── tests/                 # Test suite
│   ├── unit/
│   ├── integration/
│   └── backtest/
│
├── main.py               # Entry point
├── requirements.txt      # Python dependencies
└── .env.example          # Environment template
```

### 5.2 Current vs. Target Architecture

The codebase is currently in **Phase 1** (foundation). The four engines are partially implemented:

| Engine | Current Implementation | Target Location |
|--------|----------------------|-----------------|
| CORE-HODL | `DCAStrategy` | `src/engines/core_engine.py` |
| TREND | Not implemented | `src/engines/trend_engine.py` |
| FUNDING | Not implemented | `src/engines/funding_engine.py` |
| TACTICAL | `GridStrategy` (partial) | `src/engines/tactical_engine.py` |

When implementing new engines, follow the pattern in `src/strategies/base.py`.

---

## 6. Strategy Implementation Pattern

### 6.1 Base Class Contract

All strategies MUST inherit from `BaseStrategy` and implement three methods:

```python
from abc import abstractmethod
from typing import Dict, List
from decimal import Decimal
from src.core.models import MarketData, TradingSignal
from src.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    """
    Strategy description here.
    
    Risk Level: LOW/MEDIUM/HIGH
    Timeframe: 1h/4h/1d
    Assets: BTC, ETH
    """
    
    def __init__(self, name: str, symbols: List[str], **kwargs):
        super().__init__(name, symbols, **kwargs)
        # Initialize strategy-specific parameters
        
    @abstractmethod
    async def analyze(
        self, 
        data: Dict[str, List[MarketData]]
    ) -> List[TradingSignal]:
        """
        Analyze market data and generate trading signals.
        
        Args:
            data: Dictionary of symbol -> list of MarketData
            
        Returns:
            List of TradingSignal objects
        """
        pass
    
    @abstractmethod
    async def on_order_filled(
        self, 
        symbol: str, 
        side: str, 
        amount: Decimal, 
        price: Decimal
    ):
        """Callback when an order is filled. Update internal state."""
        pass
    
    @abstractmethod
    async def on_position_closed(
        self, 
        symbol: str, 
        pnl: Decimal, 
        pnl_pct: Decimal
    ):
        """Callback when a position is closed. Track performance."""
        pass
```

### 6.2 Signal Creation Pattern

```python
from src.core.models import TradingSignal, SignalType

def _create_buy_signal(
    self, 
    symbol: str, 
    confidence: float,
    metadata: dict
) -> TradingSignal:
    """Create a standardized buy signal."""
    return self._create_signal(
        symbol=symbol,
        signal_type=SignalType.BUY,
        confidence=confidence,  # 0.0 to 1.0
        metadata={
            'strategy': self.name,
            'reason': 'entry_condition_met',
            'entry_price': float(current_price),
            'stop_loss': float(stop_price),
            **metadata
        }
    )
```

### 6.3 Risk Check Integration

```python
async def analyze(self, data):
    signals = []
    
    # Generate signals based on strategy logic
    if self.should_enter_long(symbol, data):
        signal = self._create_buy_signal(symbol, 0.8, {})
        signals.append(signal)
    
    # Risk manager will validate these signals
    # before any execution happens
    return signals
```

---

## 7. Configuration

### 7.1 Environment Variables (.env)

Copy `.env.example` to `.env` and configure:

```bash
# ByBit API Configuration
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=true  # Set false for live

# Trading Mode
TRADING_MODE=paper  # paper or live
DEFAULT_SYMBOLS=BTCUSDT,ETHUSDT

# Risk Management - THESE ARE HARD LIMITS
MAX_POSITION_PCT=5          # Max % per position
MAX_DAILY_LOSS_PCT=2        # Stop trading if daily loss exceeds
MAX_WEEKLY_LOSS_PCT=5       # Stop trading if weekly loss exceeds
MAX_CONCURRENT_POSITIONS=3  # Max positions at once

# Stop Loss / Take Profit
ENABLE_STOP_LOSS=true
STOP_LOSS_PCT=3
ENABLE_TAKE_PROFIT=true
TAKE_PROFIT_PCT=6
```

### 7.2 YAML Configuration (Future)

Engine-specific configurations will be in `config/`:

```yaml
# config/trend.yaml
engine: TREND
allocation_pct: 20
subaccount: TREND-1

indicators:
  fast_ema: 50
  slow_ema: 200
  adx_period: 14
  atr_period: 14

entry_rules:
  long:
    - price_above_200sma
    - fast_above_slow
    - adx_gt_25
  
exit_rules:
  long_exit: price_below_200sma
  trailing_stop: 3x_atr

position_sizing:
  risk_per_trade: 0.01  # 1%
  max_leverage: 2.0
  max_position_pct: 0.50  # 50% of engine capital
```

### 7.3 Configuration Classes

All configs use Pydantic for validation:

```python
from pydantic_settings import BaseSettings
from pydantic import Field, validator

class TradingConfig(BaseSettings):
    trading_mode: str = Field(default="paper", env="TRADING_MODE")
    max_position_pct: float = Field(default=5.0, env="MAX_POSITION_PCT")
    
    @validator("trading_mode")
    def validate_mode(cls, v):
        if v not in ("paper", "live"):
            raise ValueError("trading_mode must be 'paper' or 'live'")
        return v
    
    class Config:
        env_file = ".env"
```

---

## 8. Testing Approach

### 8.1 Test Structure

```
tests/
├── unit/                   # Individual component tests
│   ├── test_models.py
│   ├── test_risk_manager.py
│   └── test_strategies.py
│
├── integration/            # Multi-component tests
│   ├── test_exchange.py
│   └── test_engine.py
│
└── backtest/               # Historical simulation
    ├── test_trend_strategy.py
    └── test_funding_strategy.py
```

### 8.2 Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_risk_manager.py -v

# Run with coverage
pytest --cov=src --cov-report=html
```

### 8.3 Backtesting New Strategies

```python
# In tests/backtest/test_my_strategy.py
from src.utils.backtest import BacktestRunner
from src.strategies.my_strategy import MyStrategy

def test_strategy_on_historical_data():
    runner = BacktestRunner(
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_capital=10000
    )
    
    strategy = MyStrategy(
        symbols=["BTCUSDT"],
        param1=10,
        param2=20
    )
    
    results = runner.run(strategy)
    
    # Assertions
    assert results.max_drawdown < 0.20  # Less than 20%
    assert results.sharpe_ratio > 1.0   # Positive risk-adjusted returns
    assert results.total_trades > 10    # Sufficient sample size
```

---

## 9. Danger Zones (Modify with EXTREME Caution)

### 9.1 CRITICAL: risk_manager.py

**Why it's dangerous:** This file contains all safety controls. A bug here can lead to catastrophic losses.

**Before modifying:**
1. Read `docs/05-risk-management/01-risk-framework.md`
2. Get explicit approval for any threshold changes
3. Add tests that verify the change
4. Test in paper mode for 1 week minimum

**Protected code sections:**
```python
# NEVER modify these without approval
CIRCUIT_BREAKER_LEVELS = [0.10, 0.15, 0.20, 0.25]
MAX_POSITION_PCT = 5.0
MAX_RISK_PER_TRADE = 0.01
```

### 9.2 CRITICAL: bybit_client.py Order Creation

**Why it's dangerous:** Direct exchange interaction. Errors can create unintended positions.

**Safety requirements:**
```python
async def create_order(self, ...):
    # 1. Validate in paper mode first
    if trading_config.trading_mode == "paper":
        logger.warning("PAPER TRADE", ...)
        return simulated_order
    
    # 2. Use Decimal for calculations
    amount = Decimal(str(amount))
    
    # 3. Verify risk manager approved this
    # (Risk check happens in TradingEngine)
```

### 9.3 CRITICAL: Circuit Breaker Override

**Never implement a "manual override" without:**
- Dual authorization (two people)
- Audit logging
- Automatic time limit (resets after X hours)
- Alert to all stakeholders

```python
# WRONG - Never do this
if user.is_admin:
    circuit_breaker.disable()  # DANGEROUS!

# CORRECT - If absolutely necessary
if dual_auth_verified() and audit_logged():
    circuit_breaker.temporarily_disable(
        duration=timedelta(hours=1),
        reason=reason,
        authorized_by=user.id
    )
```

### 9.4 HIGH RISK: Position Sizing Changes

Any change to position sizing formulas must:
1. Be backtested on 5+ years of data
2. Pass stress tests (COVID crash, FTX collapse, etc.)
3. Be reviewed by someone who understands Kelly Criterion
4. Include margin of safety calculations

### 9.5 HIGH RISK: Leverage Changes

Current maximum: **2x leverage**

To change leverage limits:
1. Calculate liquidation buffer at new level
2. Verify circuit breakers trigger before liquidation
3. Test with simulated margin calls
4. Document the change in `docs/05-risk-management/`

---

## 10. Documentation References

For deep dives into specific topics, refer to these docs:

| Topic | Document | Lines |
|-------|----------|-------|
| System Architecture | `docs/03-system-architecture/01-technical-overview.md` | 898 |
| Risk Management | `docs/05-risk-management/01-risk-framework.md` | 762 |
| Trading Strategies | `docs/04-trading-strategies/01-strategy-specifications.md` | 1000+ |
| Bybit Integration | `docs/06-infrastructure/01-bybit-integration.md` | - |
| Configuration Examples | `docs/10-appendices/03-configuration-examples.md` | - |
| Glossary | `docs/10-appendices/01-glossary.md` | - |

### Quick Reference Commands

```bash
# View project structure
tree -L 3 -I '__pycache__|*.pyc|.git|venv'

# Check code quality
flake8 src/

# Type checking
mypy src/

# Run security scan
bandit -r src/

# Start in paper mode
python main.py --mode paper

# Check status
python main.py --status

# View logs
tail -f logs/trading_bot.log
```

---

## 11. Code Style & Conventions

### 11.1 Python Style

- **Formatter:** Black (line length 88)
- **Imports:** isort (sorted, grouped)
- **Types:** All functions must have type hints
- **Docstrings:** Google style

```python
from typing import Dict, List, Optional
from decimal import Decimal

async def calculate_position_size(
    portfolio_value: Decimal,
    entry_price: Decimal,
    stop_price: Decimal,
    risk_pct: float = 0.01
) -> Decimal:
    """
    Calculate position size using risk-based sizing.
    
    Args:
        portfolio_value: Total portfolio value in USD
        entry_price: Entry price per unit
        stop_price: Stop loss price
        risk_pct: Percentage of portfolio to risk (default 1%)
        
    Returns:
        Quantity to purchase
        
    Raises:
        ValueError: If stop_distance is zero
    """
    risk_amount = portfolio_value * Decimal(str(risk_pct))
    stop_distance = abs(entry_price - stop_price)
    
    if stop_distance == 0:
        raise ValueError("Stop distance cannot be zero")
    
    return risk_amount / stop_distance
```

### 11.2 Logging

Use structlog for structured logging:

```python
import structlog

logger = structlog.get_logger(__name__)

# CORRECT - Structured logging
logger.info(
    "order.filled",
    order_id=order.id,
    symbol=symbol,
    side=side,
    amount=str(amount),
    price=str(price)
)

# WRONG - String formatting
logger.info(f"Order filled: {order.id} {symbol}")  # Hard to query
```

### 11.3 Error Handling

```python
from typing import Optional

async def fetch_data(symbol: str) -> Optional[MarketData]:
    """
    Fetch market data with proper error handling.
    
    Returns None on recoverable errors.
    Raises on critical errors.
    """
    try:
        return await exchange.fetch_ticker(symbol)
    except ExchangeNotAvailable:
        # Recoverable - return None, caller will retry
        logger.warning("exchange.unavailable", symbol=symbol)
        return None
    except AuthenticationError:
        # Critical - halt trading
        logger.critical("exchange.auth_failed")
        raise
```

---

## 12. Getting Started Checklist

Before making any changes:

- [ ] Read this entire AGENTS.md file
- [ ] Understand the Four Engines architecture
- [ ] Review the relevant documentation in `docs/`
- [ ] Run existing tests: `pytest`
- [ ] Verify you're in paper mode: `TRADING_MODE=paper`
- [ ] Check current risk settings in `.env`
- [ ] Understand the change impact on all four engines

Before submitting changes:

- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Type hints present on all functions
- [ ] Docstrings follow Google style
- [ ] No hardcoded secrets or API keys
- [ ] Decimal used for all monetary values
- [ ] Risk manager validation added where needed
- [ ] Logging added for significant events

---

## 13. Emergency Procedures

### 13.1 If You Suspect a Bug in Risk Manager

1. **DO NOT** restart the system
2. Check if emergency stop is active: `python main.py --status`
3. If running, immediately switch to paper mode
4. Document current positions and P&L
5. Notify the team
6. Review recent logs: `tail -n 1000 logs/trading_bot.log`

### 13.2 If Circuit Breaker Triggers

1. **DO NOT** override without dual authorization
2. Review the trigger reason in logs
3. Assess if it's a false positive
4. Document the decision to reset
5. If resetting, require manual approval and time limits

### 13.3 Contact Information

For critical issues, document all actions taken and notify stakeholders through appropriate channels (as configured in notification system).

---

## 14. Summary

**Remember these five principles:**

1. **Survival before profit** - The 1/8 Kelly sizing and circuit breakers exist to prevent ruin
2. **Mechanical execution** - No discretion, no "this time is different"
3. **Defense in depth** - Multiple layers of risk controls
4. **Observability** - Everything is logged, monitored, and auditable
5. **Decentralized intelligence** - Four independent engines, no single point of failure

**When in doubt:**
- Refer to this document
- Check the detailed docs in `docs/`
- Err on the side of caution
- Get a second opinion on risk-related changes

---

*Last Updated: 2026-02-13*
*Version: 1.0*
*The Eternal Engine - Built to last decades*
