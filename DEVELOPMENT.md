# THE ETERNAL ENGINE - Developer Guide

> **Version:** 1.0.0 | **Last Updated:** 2026-02-13  
> **Purpose:** Comprehensive developer guide for building, deploying, and maintaining The Eternal Engine

---

## Table of Contents

1. [Development Workflow](#1-development-workflow)
2. [Phase-Based Development](#2-phase-based-development)
3. [Implementing the Four Engines](#3-implementing-the-four-engines)
4. [Adding Risk Checks](#4-adding-risk-checks)
5. [Database Schema](#5-database-schema)
6. [Bybit Integration](#6-bybit-integration)
7. [Testing Strategy](#7-testing-strategy)
8. [Deployment](#8-deployment)
9. [Monitoring](#9-monitoring)
10. [Security](#10-security)

---

## 1. Development Workflow

### 1.1 Environment Setup

```bash
# Clone repository
git clone https://github.com/your-org/eternal-engine.git
cd eternal-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

### 1.2 Code Style Standards

We use **Black**, **isort**, and **mypy** for code quality:

```bash
# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/ --strict

# Linting
flake8 src/ tests/

# Security scan
bandit -r src/

# Run all checks
make lint
```

**Configuration** (in `pyproject.toml`):

```toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### 1.3 Pre-Commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.0.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.13.0
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```

### 1.4 Git Workflow

```
main        → Production-ready code
  ↓
develop     → Integration branch for features
  ↓
feature/*   → Individual feature branches
  ↓
hotfix/*    → Critical production fixes
```

**Branch Naming:**
- `feature/TICKET-123-add-trend-engine`
- `bugfix/TICKET-456-fix-position-sizing`
- `hotfix/critical-api-timeout`

**Commit Messages:**
```
feat: Add TREND engine with ADX filtering
fix: Correct ATR calculation for stop losses
docs: Update API integration guide
refactor: Simplify position sizing logic
test: Add unit tests for circuit breaker
security: Rotate API keys, update secrets
```

---

## 2. Phase-Based Development

### 2.1 Phase Overview

| Phase | Duration | Goal | Capital | Risk Level |
|-------|----------|------|---------|------------|
| **Phase 1** | Weeks 1-4 | Foundation | $5K-$10K | Minimal |
| **Phase 2** | Weeks 5-12 | Validation | $0 (Demo) | Low |
| **Phase 3** | Weeks 13-20 | Activation | $20K-$50K | Medium |
| **Phase 4** | Months 6-12 | Scale | $100K+ | Managed |

### 2.2 Phase 1: Foundation (Weeks 1-4)

**Goal:** Deploy CORE-HODL engine with basic infrastructure

```python
# src/engines/core_hodl.py
class CoreHodlEngine:
    """Phase 1: Simple DCA + quarterly rebalancing."""
    
    TARGET_ALLOCATION = {
        'BTC': 0.40,  # 40% of total portfolio
        'ETH': 0.20,  # 20% of total portfolio
    }
    
    REBALANCE_THRESHOLD = 0.10  # 10% drift triggers rebalance
    
    async def initialize(self, capital: Decimal):
        """Deploy capital over 14 days via DCA."""
        daily_btc = (capital * self.TARGET_ALLOCATION['BTC']) / 14
        daily_eth = (capital * self.TARGET_ALLOCATION['ETH']) / 14
        
        for day in range(1, 15):
            await self.place_market_buy('BTC/USDT', daily_btc)
            await self.place_market_buy('ETH/USDT', daily_eth)
            await asyncio.sleep(86400)  # Wait 24 hours
    
    async def check_rebalance(self):
        """Quarterly rebalancing logic."""
        current = await self.get_current_allocation()
        
        for asset, target in self.TARGET_ALLOCATION.items():
            drift = current[asset] - target
            if abs(drift) > self.REBALANCE_THRESHOLD:
                await self.execute_rebalance(asset, drift)
```

**Success Metrics:**
- Positions established >90% of target
- Infrastructure uptime >99%
- API error rate <1%

### 2.3 Phase 2: Validation (Weeks 5-12)

**Goal:** Backtest and demo trade all engines

```python
# research/backtest_engine.py
class BacktestEngine:
    """Phase 2: Validate strategies before live deployment."""
    
    def run_trend_backtest(
        self, 
        start_date: datetime, 
        end_date: datetime,
        params: TrendParams
    ) -> BacktestResult:
        """Backtest TREND engine."""
        equity = self.initial_capital
        max_equity = equity
        trades = []
        
        for i in range(200, len(self.data)):
            window = self.data[i-200:i]
            
            # Calculate indicators
            sma_50 = calculate_sma(window['close'], 50)
            sma_200 = calculate_sma(window['close'], 200)
            adx = calculate_adx(window, 14)
            atr = calculate_atr(window, 14)
            
            current_price = self.data[i]['close']
            
            # Entry signal
            if (current_price > sma_200[-1] and 
                sma_50[-1] > sma_200[-1] and 
                adx[-1] > 25):
                
                position_size = self.calculate_position_size(
                    equity, current_price, atr
                )
                
                # Simulate trade
                trades.append(self.simulate_long_entry(
                    price=current_price,
                    size=position_size,
                    stop=current_price - (2 * atr)
                ))
        
        return self.calculate_metrics(trades)
```

**Pass Criteria:**

| Engine | Min Win Rate | Min Profit Factor | Max Drawdown |
|--------|--------------|-------------------|--------------|
| TREND | 35% | 1.5 | <30% |
| FUNDING | 90% | 2.0 | <5% |
| TACTICAL | N/A | >3.0 per deployment | <20% |

### 2.4 Phase 3: Activation (Weeks 13-20)

**Goal:** Deploy live with small capital

```python
# deployment/phase3_activation.py
class Phase3Activation:
    """Gradual live capital deployment."""
    
    ALLOCATION = {
        'CORE': Decimal('30000'),
        'TREND': Decimal('10000'),
        'FUNDING': Decimal('7500'),
        'TACTICAL': Decimal('2500'),
    }
    
    INCREASE_SCHEDULE = [
        (15, Decimal('50000')),   # Week 15
        (17, Decimal('75000')),   # Week 17
        (19, Decimal('100000')),  # Week 19
    ]
    
    async def gradual_increase(self):
        """Increase capital only if conditions met."""
        for week, amount in self.INCREASE_SCHEDULE:
            # Check conditions
            if await self.check_increase_conditions():
                await self.deploy_additional_capital(amount)
            else:
                logger.warning(f"Capital increase deferred - conditions not met")
    
    async def check_increase_conditions(self) -> bool:
        """Strict conditions for capital increase."""
        return (
            self.drawdown < 0.10 and                    # <10% DD
            self.error_rate < 0.01 and                   # Low errors
            self.days_since_error >= 7 and               # Clean week
            self.manual_approval_received                # Human sign-off
        )
```

### 2.5 Phase 4: Scale (Months 6-12)

**Goal:** Full autonomy with target capital

```python
# deployment/phase4_scale.py
class Phase4Autonomy:
    """Full-scale autonomous operation."""
    
    TARGET_CAPITAL = Decimal('500000')
    
    FINAL_ALLOCATION = {
        'CORE': Decimal('300000'),    # 60%
        'TREND': Decimal('100000'),   # 20%
        'FUNDING': Decimal('75000'),  # 15%
        'TACTICAL': Decimal('25000'), # 5%
    }
    
    AUTONOMY_CHECKLIST = [
        "30 consecutive days without manual intervention",
        "99.9% uptime achieved",
        "<0.1% error rate maintained",
        "All circuit breakers tested successfully",
        "Returns within 10% of backtest projections",
        "Sharpe ratio >1.0 achieved",
    ]
```

---

## 3. Implementing the Four Engines

### 3.1 CORE-HODL Engine

**Purpose:** Long-term wealth compounding via DCA + rebalancing

```python
# src/engines/core_hodl.py
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List

@dataclass
class CoreHodlConfig:
    """Configuration for CORE-HODL engine."""
    btc_target: Decimal = Decimal('0.40')      # 40% BTC
    eth_target: Decimal = Decimal('0.20')      # 20% ETH
    rebalance_threshold: Decimal = Decimal('0.10')  # 10% drift
    dca_interval_hours: int = 24
    dca_amount_usdt: Decimal = Decimal('100')


class CoreHodlEngine(BaseStrategy):
    """
    CORE-HODL Engine Implementation.
    
    Strategy:
    1. Dollar-cost average into BTC/ETH
    2. Quarterly rebalancing to harvest volatility
    3. ETH staking for yield optimization
    """
    
    def __init__(self, config: CoreHodlConfig):
        super().__init__("CORE-HODL", symbols=['BTCUSDT', 'ETHUSDT'])
        self.config = config
        self.last_rebalance = datetime.min
        self.dca_schedule: Dict[str, datetime] = {}
        
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """Generate DCA and rebalance signals."""
        signals = []
        now = datetime.utcnow()
        
        # 1. Check DCA schedule
        for symbol in self.symbols:
            last_dca = self.dca_schedule.get(symbol)
            if last_dca is None or (now - last_dca).hours >= self.config.dca_interval_hours:
                signals.append(self._create_dca_signal(symbol, data[symbol][-1].close))
        
        # 2. Check rebalancing (quarterly or threshold)
        if self._should_rebalance(now):
            allocation = await self._get_current_allocation()
            rebalance_signals = self._calculate_rebalance_trades(allocation)
            signals.extend(rebalance_signals)
        
        return signals
    
    def _should_rebalance(self, now: datetime) -> bool:
        """Determine if rebalancing is needed."""
        # Calendar trigger (quarterly)
        days_since_rebalance = (now - self.last_rebalance).days
        if days_since_rebalance >= 90:
            return True
        
        # Threshold trigger (10% drift)
        drift = self._calculate_allocation_drift()
        return drift > self.config.rebalance_threshold
    
    def _calculate_rebalance_trades(
        self, 
        current: Dict[str, Decimal]
    ) -> List[TradingSignal]:
        """Calculate trades to rebalance portfolio."""
        signals = []
        total = sum(current.values())
        
        targets = {
            'BTCUSDT': self.config.btc_target,
            'ETHUSDT': self.config.eth_target
        }
        
        for symbol, target_pct in targets.items():
            current_value = current.get(symbol, Decimal('0'))
            target_value = total * target_pct
            diff = target_value - current_value
            
            if abs(diff) > (total * Decimal('0.05')):  # 5% min trade
                signal_type = SignalType.BUY if diff > 0 else SignalType.SELL
                signals.append(self._create_signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    metadata={'rebalance': True, 'diff_usd': float(abs(diff))}
                ))
        
        return signals
```

### 3.2 TREND Engine

**Purpose:** Capture directional trends using 200DMA/ADX

```python
# src/engines/trend_engine.py
import pandas as pd
import pandas_ta as ta
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class TrendConfig:
    """Configuration for TREND engine."""
    fast_ema: int = 50
    slow_ema: int = 200
    adx_period: int = 14
    adx_threshold: float = 25.0
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_per_trade: Decimal = Decimal('0.01')  # 1%
    max_leverage: float = 2.0


class TrendEngine(BaseStrategy):
    """
    TREND Engine - Dual Momentum Trend Following.
    
    Entry Rules (Long):
    1. Price > 200 SMA (bullish trend)
    2. 50 SMA > 200 SMA (golden cross)
    3. ADX > 25 (strong trend)
    4. Volume > 1.2x average
    
    Exit Rules:
    1. Price closes below 200 SMA
    2. Trailing stop at 3x ATR
    3. Time stop after 30 days
    """
    
    def __init__(self, config: TrendConfig):
        super().__init__("TREND", symbols=['BTCUSDT', 'ETHUSDT'])
        self.config = config
        self.positions: Dict[str, Position] = {}
        
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """Generate trend-following signals."""
        signals = []
        
        for symbol, candles in data.items():
            if len(candles) < self.config.slow_ema + 10:
                continue
            
            # Convert to DataFrame
            df = self._to_dataframe(candles)
            
            # Calculate indicators
            df['sma_50'] = ta.sma(df['close'], length=self.config.fast_ema)
            df['sma_200'] = ta.sma(df['close'], length=self.config.slow_ema)
            df['adx'] = ta.adx(df['high'], df['low'], df['close'], length=self.config.adx_period)['ADX_14']
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=self.config.atr_period)
            df['volume_sma'] = ta.sma(df['volume'], length=20)
            
            current = df.iloc[-1]
            
            # Check entry conditions
            if self._check_long_entry(current, df):
                if symbol not in self.positions:
                    stop_price = current['close'] - (current['atr'] * self.config.atr_multiplier)
                    size = self._calculate_position_size(
                        current['close'], 
                        stop_price,
                        current['atr']
                    )
                    
                    signals.append(self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        confidence=current['adx'] / 50,  # Normalize ADX to confidence
                        metadata={
                            'stop_loss': float(stop_price),
                            'atr': float(current['atr']),
                            'entry_price': float(current['close'])
                        }
                    ))
            
            # Check exit conditions for existing positions
            elif symbol in self.positions:
                if self._check_exit(current, df, self.positions[symbol]):
                    signals.append(self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.CLOSE,
                        metadata={'exit_reason': 'trend_reversal'}
                    ))
        
        return signals
    
    def _check_long_entry(self, current: pd.Series, df: pd.DataFrame) -> bool:
        """Validate all entry conditions."""
        return (
            current['close'] > current['sma_200'] and          # Price above 200 SMA
            current['sma_50'] > current['sma_200'] and         # Golden cross
            current['adx'] > self.config.adx_threshold and     # Strong trend
            current['volume'] > current['volume_sma'] * 1.2    # Volume confirmation
        )
    
    def _calculate_position_size(
        self, 
        entry_price: float, 
        stop_price: float,
        atr: float
    ) -> Decimal:
        """
        ATR-based position sizing.
        
        Formula: Risk Amount / Stop Distance
        """
        portfolio_value = self.get_portfolio_value()
        risk_amount = portfolio_value * self.config.risk_per_trade
        
        stop_distance = abs(entry_price - stop_price)
        if stop_distance == 0:
            return Decimal('0')
        
        position_value = risk_amount / Decimal(str(stop_distance))
        max_position = portfolio_value * Decimal(str(self.config.max_leverage))
        
        # Cap at max leverage
        position_value = min(position_value, max_position)
        
        return position_value / Decimal(str(entry_price))
```

### 3.3 FUNDING Engine

**Purpose:** Delta-neutral funding rate arbitrage

```python
# src/engines/funding_engine.py
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from datetime import datetime

@dataclass
class FundingConfig:
    """Configuration for FUNDING engine."""
    min_annualized_rate: Decimal = Decimal('0.10')  # 10%
    max_basis_pct: Decimal = Decimal('0.02')        # 2%
    max_hold_days: int = 14
    rebalance_threshold: Decimal = Decimal('0.02')  # 2%
    auto_compound: bool = True
    compound_ratio: Decimal = Decimal('0.5')        # 50% reinvest


class FundingEngine(BaseStrategy):
    """
    FUNDING Engine - Delta-Nutral Funding Rate Arbitrage.
    
    Strategy:
    1. Long spot BTC/ETH
    2. Short perpetual futures (same notional)
    3. Collect funding payments every 8 hours
    4. Net delta = 0 (price-neutral)
    
    Entry Conditions:
    - Annualized funding rate > 10%
    - Spot-perp basis < 2%
    - Consecutive positive funding periods >= 2
    
    Exit Conditions:
    - Funding turns negative
    - Basis expands > 2%
    - Max hold time (14 days)
    """
    
    def __init__(self, config: FundingConfig):
        super().__init__("FUNDING", symbols=['BTC', 'ETH'])
        self.config = config
        self.positions: Dict[str, FundingPosition] = {}
        
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """Generate funding arbitrage signals."""
        signals = []
        
        for symbol in self.symbols:
            # Get funding rate
            funding_rate = await self._get_predicted_funding(symbol)
            annualized = self._annualize_rate(funding_rate)
            
            # Get basis (spot-perp spread)
            spot_price = await self._get_spot_price(symbol)
            perp_price = await self._get_perp_price(symbol)
            basis = (perp_price - spot_price) / spot_price
            
            # Entry opportunity
            if (annualized > self.config.min_annualized_rate and 
                abs(basis) < self.config.max_basis_pct and
                symbol not in self.positions):
                
                signals.append(self._create_entry_signal(
                    symbol, spot_price, perp_price, funding_rate
                ))
            
            # Exit conditions
            elif symbol in self.positions:
                position = self.positions[symbol]
                
                if self._should_exit(position, funding_rate, basis):
                    signals.append(self._create_exit_signal(symbol, position))
        
        return signals
    
    def _create_entry_signal(
        self, 
        symbol: str, 
        spot_price: Decimal,
        perp_price: Decimal,
        funding_rate: Decimal
    ) -> TradingSignal:
        """Create delta-neutral entry signal."""
        return self._create_signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            metadata={
                'strategy': 'funding_arbitrage',
                'spot_price': float(spot_price),
                'perp_price': float(perp_price),
                'funding_rate': float(funding_rate),
                'annualized_rate': float(self._annualize_rate(funding_rate)),
                'basis': float((perp_price - spot_price) / spot_price),
                'structure': 'long_spot_short_perp'
            }
        )
    
    def _should_exit(
        self, 
        position: FundingPosition,
        current_funding: Decimal,
        current_basis: Decimal
    ) -> bool:
        """Check if position should be closed."""
        # Funding turned negative
        if current_funding < 0:
            return True
        
        # Basis risk too high
        if abs(current_basis) > self.config.max_basis_pct:
            return True
        
        # Max hold time exceeded
        days_held = (datetime.utcnow() - position.entry_time).days
        if days_held > self.config.max_hold_days:
            return True
        
        # Funding compression (rate dropped significantly)
        if self._annualize_rate(current_funding) < (self.config.min_annualized_rate / 2):
            return True
        
        return False
    
    async def on_funding_payment(self, symbol: str, amount: Decimal):
        """Handle funding payment (every 8 hours)."""
        if amount > 0:
            logger.info(f"Funding received: {symbol} ${amount}")
            
            if self.config.auto_compound:
                compound = amount * self.config.compound_ratio
                tactical = amount * (Decimal('1') - self.config.compound_ratio)
                
                # Reinvest 50%
                await self.increase_position(symbol, compound)
                
                # Transfer 50% to TACTICAL
                await self.transfer_to_engine('TACTICAL', tactical)
    
    def _annualize_rate(self, funding_rate: Decimal) -> Decimal:
        """Convert 8-hour funding rate to annualized."""
        periods_per_year = Decimal('365') * Decimal('3')  # 3 periods per day
        return funding_rate * periods_per_year
```

### 3.4 TACTICAL Engine

**Purpose:** Crisis deployment during market crashes

```python
# src/engines/tactical_engine.py
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime, timedelta

@dataclass
class TacticalConfig:
    """Configuration for TACTICAL engine."""
    initial_allocation: Decimal = Decimal('0.05')  # 5% of portfolio
    
    # Deployment triggers
    btc_drawdown_levels = {
        'level_1': {'drawdown': Decimal('-0.50'), 'deploy_pct': Decimal('0.50')},
        'level_2': {'drawdown': Decimal('-0.70'), 'deploy_pct': Decimal('0.50')},
    }
    
    fear_greed_threshold: int = 20  # Extreme fear
    min_days_between_deployments: int = 30
    
    # Exit rules
    profit_target: Decimal = Decimal('1.00')  # 100% gain
    max_hold_days: int = 365
    
    # Allocation within deployment
    btc_allocation: Decimal = Decimal('0.80')  # 80% BTC
    eth_allocation: Decimal = Decimal('0.20')  # 20% ETH


class TacticalEngine(BaseStrategy):
    """
    TACTICAL Engine - Extreme Opportunity Deployment.
    
    Strategy:
    - Accumulate cash from FUNDING profits
    - Wait for extreme fear/crash conditions
    - Deploy aggressively during crises
    - Return profits to CORE-HODL
    
    Triggers:
    1. BTC drawdown >50% from ATH (deploy 50%)
    2. BTC drawdown >70% from ATH (deploy remaining 50%)
    3. Fear & Greed Index < 20
    4. Funding rates deeply negative (< -0.05% for 3+ days)
    """
    
    def __init__(self, config: TacticalConfig):
        super().__init__("TACTICAL", symbols=['BTCUSDT', 'ETHUSDT'])
        self.config = config
        
        self.btc_ath: Decimal = Decimal('0')
        self.deployed: bool = False
        self.last_deployment: Optional[datetime] = None
        self.deployment_history: List[Deployment] = []
        
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """Generate crisis deployment signals."""
        signals = []
        
        # Update ATH tracking
        btc_price = data['BTCUSDT'][-1].close
        self._update_ath(btc_price)
        
        # Skip if already deployed or cooling down
        if self.deployed or not self._can_deploy():
            return signals
        
        # Gather crisis signals
        crisis_score = 0
        triggers = []
        
        # 1. Check drawdown levels
        drawdown = (btc_price - self.btc_ath) / self.btc_ath
        if drawdown <= self.config.btc_drawdown_levels['level_2']['drawdown']:
            crisis_score += 3
            triggers.append('level_2_crash')
        elif drawdown <= self.config.btc_drawdown_levels['level_1']['drawdown']:
            crisis_score += 2
            triggers.append('level_1_crash')
        
        # 2. Check fear index
        fear_greed = await self._get_fear_greed_index()
        if fear_greed <= self.config.fear_greed_threshold:
            crisis_score += 2
            triggers.append('extreme_fear')
        
        # 3. Check capitulation indicators
        if await self._check_capitulation_signals():
            crisis_score += 1
            triggers.append('capitulation')
        
        # Deploy if crisis score >= 3
        if crisis_score >= 3:
            available_cash = await self._get_available_cash()
            deploy_amount = self._calculate_deployment_size(
                available_cash, triggers, crisis_score
            )
            
            if deploy_amount > 0:
                # Create deployment signals
                btc_amount = deploy_amount * self.config.btc_allocation
                eth_amount = deploy_amount * self.config.eth_allocation
                
                signals.append(self._create_signal(
                    symbol='BTCUSDT',
                    signal_type=SignalType.BUY,
                    confidence=min(1.0, crisis_score / 5),
                    metadata={
                        'deployment': True,
                        'amount_usd': float(btc_amount),
                        'crisis_score': crisis_score,
                        'triggers': triggers,
                        'drawdown': float(drawdown)
                    }
                ))
                
                signals.append(self._create_signal(
                    symbol='ETHUSDT',
                    signal_type=SignalType.BUY,
                    confidence=min(1.0, crisis_score / 5),
                    metadata={
                        'deployment': True,
                        'amount_usd': float(eth_amount),
                        'crisis_score': crisis_score,
                        'triggers': triggers
                    }
                ))
        
        return signals
    
    def _update_ath(self, current_price: Decimal):
        """Track all-time high, reset deployment after new ATH."""
        if current_price > self.btc_ath:
            self.btc_ath = current_price
            if self.deployed:
                # Reset after new ATH - ready for next cycle
                self.deployed = False
                logger.info("TACTICAL: New ATH reached, deployment reset")
    
    def _can_deploy(self) -> bool:
        """Check if enough time passed since last deployment."""
        if self.last_deployment is None:
            return True
        
        days_since = (datetime.utcnow() - self.last_deployment).days
        return days_since >= self.config.min_days_between_deployments
    
    async def check_exit_conditions(self, position) -> Optional[TradingSignal]:
        """Check if tactical deployment should return to CORE."""
        current_price = await self._get_current_price(position.symbol)
        entry_price = position.entry_price
        
        # Profit target
        pnl_pct = (current_price - entry_price) / entry_price
        if pnl_pct >= self.config.profit_target:
            return self._create_signal(
                symbol=position.symbol,
                signal_type=SignalType.CLOSE,
                metadata={'exit_reason': 'profit_target', 'pnl_pct': float(pnl_pct)}
            )
        
        # Time limit
        days_held = (datetime.utcnow() - position.entry_time).days
        if days_held >= self.config.max_hold_days:
            return self._create_signal(
                symbol=position.symbol,
                signal_type=SignalType.CLOSE,
                metadata={'exit_reason': 'time_limit', 'days_held': days_held}
            )
        
        return None
```

---

## 4. Adding Risk Checks

### 4.1 Risk Manager Architecture

```python
# src/risk/risk_manager.py
from typing import List, Callable
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class RiskRule:
    """A risk check rule."""
    name: str
    check: Callable[[TradingSignal, Portfolio, Dict], RiskCheck]
    priority: int  # Higher = checked first


class RiskManager:
    """Extensible risk management system."""
    
    def __init__(self):
        self.rules: List[RiskRule] = []
        self.emergency_stop = False
        
        # Register default rules
        self._register_default_rules()
    
    def _register_default_rules(self):
        """Register built-in risk rules."""
        self.add_rule(RiskRule(
            name="emergency_stop",
            check=self._check_emergency_stop,
            priority=100
        ))
        self.add_rule(RiskRule(
            name="daily_loss_limit",
            check=self._check_daily_loss,
            priority=90
        ))
        self.add_rule(RiskRule(
            name="position_size",
            check=self._check_position_size,
            priority=80
        ))
        self.add_rule(RiskRule(
            name="correlation",
            check=self._check_correlation,
            priority=70
        ))
    
    def add_rule(self, rule: RiskRule):
        """Add a new risk rule."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def check_signal(
        self, 
        signal: TradingSignal, 
        portfolio: Portfolio,
        positions: Dict[str, Position]
    ) -> RiskCheck:
        """Run all risk checks against a signal."""
        for rule in self.rules:
            result = rule.check(signal, portfolio, positions)
            if not result.passed:
                logger.warning(
                    f"Risk check failed: {rule.name}",
                    reason=result.reason
                )
                return result
        
        return RiskCheck(passed=True)
```

### 4.2 Adding a Custom Risk Rule

```python
# Example: Adding a new "weekend volatility" risk rule

from src.risk.risk_manager import RiskManager, RiskRule, RiskCheck

def check_weekend_volatility(
    signal: TradingSignal, 
    portfolio: Portfolio,
    positions: Dict[str, Position]
) -> RiskCheck:
    """
    Reduce position size on weekends due to lower liquidity.
    """
    from datetime import datetime
    
    now = datetime.utcnow()
    is_weekend = now.weekday() >= 5  # Saturday = 5, Sunday = 6
    
    if is_weekend and signal.signal_type == SignalType.BUY:
        return RiskCheck(
            passed=False,
            reason="Weekend trading restricted - reduced liquidity",
            risk_level="warning",
            metadata={'suggested_action': 'reduce_size_50pct'}
        )
    
    return RiskCheck(passed=True)

# Register the new rule
risk_manager = RiskManager()
risk_manager.add_rule(RiskRule(
    name="weekend_volatility",
    check=check_weekend_volatility,
    priority=60  # Lower priority = checked later
))
```

### 4.3 Circuit Breaker Implementation

```python
# src/risk/circuit_breaker.py
from enum import Enum
from decimal import Decimal
from datetime import datetime

class CircuitLevel(Enum):
    NORMAL = 0
    CAUTION = 1      # 10% drawdown
    WARNING = 2      # 15% drawdown
    ALERT = 3        # 20% drawdown
    EMERGENCY = 4    # 25% drawdown


class CircuitBreaker:
    """
    Four-level circuit breaker system.
    
    Level 1 (10%): Reduce sizes 25%, widen stops
    Level 2 (15%): Reduce sizes 50%, pause entries
    Level 3 (20%): Close directional, move to stables
    Level 4 (25%): Full liquidation, halt indefinitely
    """
    
    THRESHOLDS = {
        CircuitLevel.CAUTION: Decimal('0.10'),
        CircuitLevel.WARNING: Decimal('0.15'),
        CircuitLevel.ALERT: Decimal('0.20'),
        CircuitLevel.EMERGENCY: Decimal('0.25'),
    }
    
    def __init__(self):
        self.current_level = CircuitLevel.NORMAL
        self.all_time_high: Decimal = Decimal('0')
        self.last_triggered: Optional[datetime] = None
        
    def update(self, current_value: Decimal) -> CircuitLevel:
        """Update circuit breaker status."""
        # Update ATH
        if current_value > self.all_time_high:
            self.all_time_high = current_value
        
        # Calculate drawdown
        drawdown = (self.all_time_high - current_value) / self.all_time_high
        
        # Determine level
        new_level = CircuitLevel.NORMAL
        for level, threshold in self.THRESHOLDS.items():
            if drawdown >= threshold:
                new_level = level
        
        # Handle level change
        if new_level != self.current_level:
            self._on_level_change(self.current_level, new_level, drawdown)
            self.current_level = new_level
        
        return self.current_level
    
    def _on_level_change(self, old: CircuitLevel, new: CircuitLevel, drawdown: Decimal):
        """Execute actions for circuit breaker level change."""
        actions = {
            CircuitLevel.CAUTION: self._action_caution,
            CircuitLevel.WARNING: self._action_warning,
            CircuitLevel.ALERT: self._action_alert,
            CircuitLevel.EMERGENCY: self._action_emergency,
        }
        
        if new in actions:
            actions[new](drawdown)
    
    def _action_caution(self, drawdown: Decimal):
        """Level 1: Reduce sizes, widen stops."""
        logger.warning(f"CIRCUIT BREAKER LEVEL 1: Caution ({drawdown:.2%} drawdown)")
        
        # Reduce position sizes by 25%
        for position in self.get_open_positions():
            if position.engine in ['TREND', 'FUNDING']:
                self.reduce_position(position, factor=0.75)
        
        # Widen stop losses
        self.widen_stop_losses(factor=1.5)
        
        # Increase monitoring
        self.set_monitoring_frequency('hourly')
        
        # Alert
        self.send_alert('LEVEL_1_CAUTION', drawdown)
    
    def _action_emergency(self, drawdown: Decimal):
        """Level 4: Full liquidation."""
        logger.critical(f"CIRCUIT BREAKER LEVEL 4: EMERGENCY ({drawdown:.2%} drawdown)")
        
        # Liquidate everything
        for position in self.get_open_positions():
            self.emergency_close(position)
        
        # Move to stables
        self.transfer_all_to_stables()
        
        # Halt trading
        self.halt_all_trading(permanent=True)
        
        # Critical alert
        self.send_alert('LEVEL_4_EMERGENCY', drawdown, channels=['sms', 'phone', 'email'])
```

---

## 5. Database Schema

### 5.1 PostgreSQL Schema

```sql
-- migrations/001_initial_schema.sql

-- Orders table
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_order_id VARCHAR(255),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    amount NUMERIC(36, 18) NOT NULL,
    price NUMERIC(36, 18),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    filled_amount NUMERIC(36, 18) DEFAULT 0,
    average_price NUMERIC(36, 18),
    stop_loss_price NUMERIC(36, 18),
    take_profit_price NUMERIC(36, 18),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    filled_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    strategy_name VARCHAR(50),
    engine_name VARCHAR(50)
);

CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);

-- Positions table
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL UNIQUE,
    side VARCHAR(10) NOT NULL,
    entry_price NUMERIC(36, 18) NOT NULL,
    amount NUMERIC(36, 18) NOT NULL,
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    unrealized_pnl NUMERIC(36, 18) DEFAULT 0,
    realized_pnl NUMERIC(36, 18) DEFAULT 0,
    stop_loss_price NUMERIC(36, 18),
    take_profit_price NUMERIC(36, 18),
    metadata JSONB DEFAULT '{}',
    strategy_name VARCHAR(50),
    engine_name VARCHAR(50)
);

CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_closed ON positions(closed_at) WHERE closed_at IS NULL;

-- Trades table (completed positions)
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    amount NUMERIC(36, 18) NOT NULL,
    entry_price NUMERIC(36, 18) NOT NULL,
    exit_price NUMERIC(36, 18) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    realized_pnl NUMERIC(36, 18) NOT NULL,
    realized_pnl_pct NUMERIC(36, 18) NOT NULL,
    entry_fee NUMERIC(36, 18) DEFAULT 0,
    exit_fee NUMERIC(36, 18) DEFAULT 0,
    total_fee NUMERIC(36, 18) DEFAULT 0,
    strategy_name VARCHAR(50),
    engine_name VARCHAR(50),
    close_reason VARCHAR(50),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_exit_time ON trades(exit_time DESC);
CREATE INDEX idx_trades_strategy ON trades(strategy_name);

-- Daily statistics
CREATE TABLE daily_stats (
    date DATE PRIMARY KEY,
    starting_balance NUMERIC(36, 18) NOT NULL,
    ending_balance NUMERIC(36, 18),
    total_pnl NUMERIC(36, 18) DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    max_drawdown_pct NUMERIC(10, 4),
    sharpe_ratio NUMERIC(10, 4),
    metadata JSONB DEFAULT '{}'
);

-- Audit log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    engine_name VARCHAR(50),
    details JSONB NOT NULL,
    portfolio_value NUMERIC(36, 18),
    authorization_source VARCHAR(50)
);

CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_event_type ON audit_log(event_type);

-- Funding payments (for FUNDING engine)
CREATE TABLE funding_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    funding_time TIMESTAMP WITH TIME ZONE NOT NULL,
    funding_rate NUMERIC(20, 10) NOT NULL,
    payment_amount NUMERIC(36, 18) NOT NULL,
    position_size NUMERIC(36, 18) NOT NULL,
    engine_name VARCHAR(50) DEFAULT 'FUNDING'
);

CREATE INDEX idx_funding_symbol_time ON funding_payments(symbol, funding_time);
```

### 5.2 Migration Management

```python
# migrations/manager.py
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

class MigrationManager:
    """Database migration manager."""
    
    async def migrate(self):
        """Run all pending migrations."""
        engine = create_async_engine(self.database_url)
        
        async with engine.begin() as conn:
            # Create migrations table if not exists
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Get applied migrations
            result = await conn.execute(
                text("SELECT version FROM schema_migrations")
            )
            applied = {row[0] for row in result.fetchall()}
            
            # Run pending migrations
            for migration in self.get_migration_files():
                if migration.version not in applied:
                    logger.info(f"Applying migration: {migration.version}")
                    await conn.execute(text(migration.sql))
                    await conn.execute(
                        text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                        {"version": migration.version}
                    )
```

---

## 6. Bybit Integration

### 6.1 API Client Architecture

```python
# src/exchange/bybit_client.py
import ccxt.async_support as ccxt
from typing import Optional, Dict, List
from decimal import Decimal

class BybitClient:
    """
    Bybit API V5 client wrapper.
    
    Features:
    - Unified Trading Account (UTA) support
    - Rate limiting with automatic backoff
    - Retry logic for transient failures
    - Paper trading mode
    """
    
    def __init__(
        self, 
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        sandbox: bool = False
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.sandbox = sandbox
        self.exchange: Optional[ccxt.bybit] = None
        
        # Rate limiting
        self.rate_limiter = RateLimiter()
        
    async def initialize(self):
        """Initialize exchange connection."""
        config = {
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'sandbox': self.testnet or self.sandbox,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
            }
        }
        
        self.exchange = ccxt.bybit(config)
        await self.exchange.load_markets()
        
        logger.info(
            "Bybit client initialized",
            testnet=self.testnet,
            sandbox=self.sandbox
        )
    
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: Decimal,
        price: Optional[Decimal] = None,
        params: Optional[Dict] = None
    ) -> Order:
        """
        Create order with retry logic.
        """
        max_retries = 3
        retry_delay = [1, 5, 15]  # Exponential backoff
        
        for attempt in range(max_retries):
            try:
                # Check rate limit
                await self.rate_limiter.acquire('order')
                
                # Execute order
                result = await self.exchange.create_order(
                    symbol=symbol,
                    type=order_type.value,
                    side=side.value,
                    amount=float(amount),
                    price=float(price) if price else None,
                    params=params or {}
                )
                
                return self._parse_order(result)
                
            except ccxt.NetworkError as e:
                logger.warning(f"Network error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay[attempt])
                    continue
                raise
                
            except ccxt.InsufficientFunds as e:
                logger.error(f"Insufficient funds: {e}")
                raise
                
            except ccxt.InvalidOrder as e:
                logger.error(f"Invalid order: {e}")
                raise
```

### 6.2 WebSocket Integration

```python
# src/exchange/bybit_ws.py
import websockets
import json
import hmac
import hashlib
from typing import Callable, Dict

class BybitWebSocket:
    """
    Bybit WebSocket client for real-time data.
    
    Supports:
    - Public streams (orderbook, trades, tickers)
    - Private streams (orders, positions, wallet)
    - Automatic reconnection
    - Heartbeat/ping handling
    """
    
    PUBLIC_URL = "wss://stream.bybit.com/v5/public/linear"
    PRIVATE_URL = "wss://stream.bybit.com/v5/private"
    TESTNET_PUBLIC = "wss://stream-testnet.bybit.com/v5/public/linear"
    TESTNET_PRIVATE = "wss://stream-testnet.bybit.com/v5/private"
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.ws = None
        self.running = False
        self.subscriptions = set()
        
        # Callbacks
        self.orderbook_callback: Optional[Callable] = None
        self.trade_callback: Optional[Callable] = None
        self.order_callback: Optional[Callable] = None
        self.position_callback: Optional[Callable] = None
        
    async def connect_public(self):
        """Connect to public WebSocket."""
        url = self.TESTNET_PUBLIC if self.testnet else self.PUBLIC_URL
        self.ws = await websockets.connect(url)
        self.running = True
        
        # Start handlers
        asyncio.create_task(self._message_handler())
        asyncio.create_task(self._heartbeat())
        
    async def connect_private(self):
        """Connect and authenticate to private WebSocket."""
        url = self.TESTNET_PRIVATE if self.testnet else self.PRIVATE_URL
        self.ws = await websockets.connect(url)
        
        # Authenticate
        expires = int(asyncio.get_event_loop().time() + 10) * 1000
        signature = self._generate_signature(expires)
        
        auth_msg = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        await self.ws.send(json.dumps(auth_msg))
        
        response = await self.ws.recv()
        data = json.loads(response)
        
        if not data.get("success"):
            raise AuthenticationError(f"Auth failed: {data}")
        
        self.running = True
        asyncio.create_task(self._message_handler())
        asyncio.create_task(self._heartbeat())
    
    async def subscribe_orderbook(self, symbols: List[str], depth: int = 25):
        """Subscribe to orderbook updates."""
        args = [{"channel": f"orderbook.{depth}.{s}"} for s in symbols]
        await self._subscribe(args)
    
    async def subscribe_orders(self):
        """Subscribe to order updates (private)."""
        await self._subscribe([{"channel": "order"}])
    
    async def subscribe_positions(self):
        """Subscribe to position updates (private)."""
        await self._subscribe([{"channel": "position"}])
    
    async def _subscribe(self, args: List[Dict]):
        """Send subscription message."""
        msg = {"op": "subscribe", "args": args}
        await self.ws.send(json.dumps(msg))
    
    def _generate_signature(self, expires: int) -> str:
        """Generate HMAC signature for authentication."""
        message = f"GET/realtime{expires}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _message_handler(self):
        """Handle incoming WebSocket messages."""
        while self.running:
            try:
                msg = await self.ws.recv()
                data = json.loads(msg)
                
                topic = data.get("topic", "")
                
                if "orderbook" in topic:
                    if self.orderbook_callback:
                        self.orderbook_callback(data)
                
                elif topic == "order" and self.order_callback:
                    for item in data.get("data", []):
                        self.order_callback(item)
                
                elif topic == "position" and self.position_callback:
                    for item in data.get("data", []):
                        self.position_callback(item)
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed, reconnecting...")
                await self._reconnect()
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
    
    async def _heartbeat(self):
        """Send periodic ping messages."""
        while self.running:
            try:
                await self.ws.send(json.dumps({"op": "ping"}))
                await asyncio.sleep(20)
            except Exception:
                break
```

### 6.3 Error Handling

```python
# src/exchange/error_handler.py
import asyncio
from enum import Enum
from typing import Optional

class ErrorCategory(Enum):
    TRANSIENT = "transient"      # Retryable (network, rate limit)
    PERMANENT = "permanent"      # Don't retry (invalid params)
    AUTH = "authentication"      # Auth failure
    INSUFFICIENT_FUNDS = "funds" # Need more capital


class ExchangeErrorHandler:
    """Centralized error handling for exchange operations."""
    
    RETRYABLE_ERRORS = [
        'NetworkError',
        'RequestTimeout',
        'ExchangeNotAvailable',
        'RateLimitExceeded',
    ]
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        
    async def execute_with_retry(
        self, 
        operation: Callable,
        max_retries: int = 3,
        backoff: List[int] = [1, 5, 15]
    ):
        """Execute operation with retry logic."""
        for attempt in range(max_retries):
            try:
                return await operation()
                
            except Exception as e:
                error_type = self._classify_error(e)
                
                if error_type == ErrorCategory.TRANSIENT:
                    if attempt < max_retries - 1:
                        wait = backoff[attempt]
                        logger.warning(f"Transient error, retrying in {wait}s: {e}")
                        await asyncio.sleep(wait)
                        continue
                
                elif error_type == ErrorCategory.AUTH:
                    logger.critical("Authentication error - check API keys")
                    self.circuit_breaker.trigger("auth_failure")
                
                elif error_type == ErrorCategory.INSUFFICIENT_FUNDS:
                    logger.error("Insufficient funds for operation")
                    self._alert_operator("Funding required")
                
                raise
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error type."""
        error_name = type(error).__name__
        
        if error_name in self.RETRYABLE_ERRORS:
            return ErrorCategory.TRANSIENT
        
        if 'authentication' in str(error).lower() or 'apikey' in str(error).lower():
            return ErrorCategory.AUTH
        
        if 'insufficient' in str(error).lower():
            return ErrorCategory.INSUFFICIENT_FUNDS
        
        return ErrorCategory.PERMANENT
```

---

## 7. Testing Strategy

### 7.1 Test Structure

```
tests/
├── unit/                          # Unit tests
│   ├── strategies/
│   │   ├── test_dca_strategy.py
│   │   ├── test_trend_engine.py
│   │   └── test_funding_engine.py
│   ├── risk/
│   │   ├── test_risk_manager.py
│   │   └── test_circuit_breaker.py
│   └── exchange/
│       └── test_bybit_client.py
├── integration/                   # Integration tests
│   ├── test_exchange_integration.py
│   └── test_database_integration.py
├── backtest/                      # Backtesting tests
│   ├── test_trend_backtest.py
│   └── test_full_system.py
└── conftest.py                    # Shared fixtures
```

### 7.2 Unit Testing

```python
# tests/unit/strategies/test_trend_engine.py
import pytest
from decimal import Decimal
from datetime import datetime

from src.engines.trend_engine import TrendEngine, TrendConfig
from src.core.models import MarketData, SignalType


class TestTrendEngine:
    """Unit tests for TREND engine."""
    
    @pytest.fixture
    def engine(self):
        config = TrendConfig(
            fast_ema=50,
            slow_ema=200,
            adx_threshold=25.0
        )
        return TrendEngine(config)
    
    @pytest.fixture
    def bullish_market_data(self):
        """Generate bullish trend data (price > 200 SMA)."""
        data = []
        base_price = Decimal('50000')
        
        for i in range(250):
            # Upward trending prices
            price = base_price + (i * Decimal('100'))
            data.append(MarketData(
                symbol='BTCUSDT',
                timestamp=datetime.utcnow(),
                open=price - Decimal('50'),
                high=price + Decimal('100'),
                low=price - Decimal('100'),
                close=price,
                volume=Decimal('1000'),
                timeframe='1h'
            ))
        
        return {'BTCUSDT': data}
    
    @pytest.mark.asyncio
    async def test_bullish_signal_generation(self, engine, bullish_market_data):
        """Test signal generation in bullish trend."""
        signals = await engine.analyze(bullish_market_data)
        
        assert len(signals) > 0
        assert signals[0].signal_type == SignalType.BUY
        assert signals[0].confidence > 0.5
    
    def test_position_size_calculation(self, engine):
        """Test ATR-based position sizing."""
        entry_price = Decimal('50000')
        stop_price = Decimal('49000')  # 2% stop
        atr = Decimal('500')
        
        size = engine._calculate_position_size(entry_price, stop_price, atr)
        
        # Should respect max position limit
        assert size > 0
        assert size <= engine.max_position_size
    
    def test_adx_filtering(self, engine):
        """Test that weak trends are filtered."""
        # Data with ADX < 25 should not generate signals
        weak_trend_data = self._generate_weak_trend_data()
        
        signals = engine.analyze(weak_trend_data)
        
        # Should not generate buy signal with weak trend
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        assert len(buy_signals) == 0
```

### 7.3 Integration Testing

```python
# tests/integration/test_exchange_integration.py
import pytest
from decimal import Decimal

from src.exchange.bybit_client import BybitClient
from src.core.models import OrderSide, OrderType


@pytest.mark.integration
class TestBybitIntegration:
    """Integration tests with Bybit testnet."""
    
    @pytest.fixture
    async def client(self):
        """Create testnet client."""
        client = BybitClient(
            api_key="TESTNET_API_KEY",
            api_secret="TESTNET_SECRET",
            testnet=True
        )
        await client.initialize()
        yield client
        await client.close()
    
    @pytest.mark.asyncio
    async def test_fetch_balance(self, client):
        """Test balance fetching."""
        balance = await client.get_balance()
        
        assert balance is not None
        assert balance.total_balance >= 0
    
    @pytest.mark.asyncio
    async def test_fetch_ohlcv(self, client):
        """Test OHLCV data fetching."""
        data = await client.fetch_ohlcv('BTCUSDT', '1h', limit=100)
        
        assert len(data) == 100
        assert data[0].close > 0
        assert data[0].volume >= 0
    
    @pytest.mark.asyncio
    async def test_paper_order_creation(self, client):
        """Test order creation in paper mode."""
        order = await client.create_order(
            symbol='BTCUSDT',
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal('0.001')
        )
        
        assert order is not None
        assert order.status.value in ['filled', 'pending']
```

### 7.4 Backtesting

```python
# tests/backtest/test_trend_backtest.py
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from research.backtest_engine import BacktestEngine


class TestTrendBacktest:
    """Backtest validation for TREND engine."""
    
    def test_historical_performance(self):
        """Test strategy on 2020-2024 data."""
        engine = BacktestEngine(
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2024, 1, 1),
            initial_capital=Decimal('100000')
        )
        
        # Load historical data
        engine.load_data()
        
        # Run backtest
        results = engine.run_trend_strategy(
            fast_ema=50,
            slow_ema=200,
            adx_threshold=25
        )
        
        # Validate results
        metrics = engine.calculate_metrics(results)
        
        assert metrics['total_return'] > 0
        assert metrics['max_drawdown'] < Decimal('0.30')  # < 30% DD
        assert metrics['sharpe_ratio'] > 1.0
        assert metrics['win_rate'] > 0.35
    
    def test_stress_test_covid_crash(self):
        """Test behavior during March 2020 crash."""
        engine = BacktestEngine(
            start_date=datetime(2020, 2, 1),
            end_date=datetime(2020, 5, 1),
            initial_capital=Decimal('100000')
        )
        
        engine.load_data()
        results = engine.run_trend_strategy()
        
        # Should have exited before major drawdown
        assert results['max_drawdown'] < Decimal('0.20')
```

### 7.5 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m backtest

# Run with verbose output
pytest -v

# Run with parallel execution
pytest -n auto
```

---

## 8. Deployment

### 8.1 Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY main.py ./

# Create non-root user
RUN useradd -m -u 1000 eternal && chown -R eternal:eternal /app
USER eternal

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run application
CMD ["python", "main.py", "--mode", "live"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  eternal-engine:
    build: .
    container_name: eternal-engine
    restart: unless-stopped
    environment:
      - TRADING_MODE=${TRADING_MODE:-paper}
      - BYBIT_API_KEY=${BYBIT_API_KEY}
      - BYBIT_API_SECRET=${BYBIT_API_SECRET}
      - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/eternal
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config:ro
    depends_on:
      - db
      - redis
    networks:
      - eternal-network

  db:
    image: postgres:15-alpine
    container_name: eternal-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=eternal
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - eternal-network

  redis:
    image: redis:7-alpine
    container_name: eternal-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - eternal-network

  grafana:
    image: grafana/grafana:latest
    container_name: eternal-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    networks:
      - eternal-network

volumes:
  postgres_data:
  redis_data:
  grafana_data:

networks:
  eternal-network:
    driver: bridge
```

### 8.2 Kubernetes Deployment

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: eternal-engine
  labels:
    app: eternal-engine
    environment: production

---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: eternal-engine
  namespace: eternal-engine
spec:
  replicas: 1
  strategy:
    type: Recreate  # Only one instance running at a time
  selector:
    matchLabels:
      app: eternal-engine
  template:
    metadata:
      labels:
        app: eternal-engine
    spec:
      serviceAccountName: eternal-engine
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: eternal-engine
          image: eternal-engine:latest
          imagePullPolicy: Always
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2000m"
          env:
            - name: TRADING_MODE
              value: "live"
            - name: BYBIT_API_KEY
              valueFrom:
                secretKeyRef:
                  name: bybit-credentials
                  key: api-key
            - name: BYBIT_API_SECRET
              valueFrom:
                secretKeyRef:
                  name: bybit-credentials
                  key: api-secret
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: url
          volumeMounts:
            - name: config
              mountPath: /app/config
              readOnly: true
          livenessProbe:
            exec:
              command:
                - python
                - -c
                - "import requests; requests.get('http://localhost:8080/health')"
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            exec:
              command:
                - python
                - -c
                - "import requests; requests.get('http://localhost:8080/ready')"
            initialDelaySeconds: 10
            periodSeconds: 10
      volumes:
        - name: config
          configMap:
            name: eternal-config

---
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: bybit-credentials
  namespace: eternal-engine
type: Opaque
data:
  api-key: <base64-encoded-key>
  api-secret: <base64-encoded-secret>

---
# k8s/cronjob-backup.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: eternal-db-backup
  namespace: eternal-engine
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:15-alpine
              command:
                - pg_dump
                - $(DATABASE_URL)
                - -f
                - /backup/eternal-$(date +%Y%m%d-%H%M%S).sql
              env:
                - name: DATABASE_URL
                  valueFrom:
                    secretKeyRef:
                      name: db-credentials
                      key: url
              volumeMounts:
                - name: backup
                  mountPath: /backup
          volumes:
            - name: backup
              persistentVolumeClaim:
                claimName: backup-pvc
          restartPolicy: OnFailure
```

### 8.3 AWS Deployment

```hcl
# infrastructure/terraform/main.tf
provider "aws" {
  region = "ap-southeast-1"  # Singapore (closest to Bybit)
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "eternal-engine-vpc"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "eternal-engine-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "eternal" {
  family                   = "eternal-engine"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "eternal-engine"
      image = "${aws_ecr_repository.eternal.repository_url}:latest"
      essential = true
      
      environment = [
        { name = "TRADING_MODE", value = "live" },
        { name = "LOG_LEVEL", value = "INFO" }
      ]
      
      secrets = [
        {
          name      = "BYBIT_API_KEY"
          valueFrom = aws_secretsmanager_secret.bybit_key.arn
        },
        {
          name      = "BYBIT_API_SECRET"
          valueFrom = aws_secretsmanager_secret.bybit_secret.arn
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.eternal.name
          awslogs-region        = "ap-southeast-1"
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

# RDS PostgreSQL
resource "aws_db_instance" "main" {
  identifier           = "eternal-engine-db"
  engine              = "postgres"
  engine_version      = "15"
  instance_class      = "db.t3.micro"
  allocated_storage   = 20
  
  db_name  = "eternal_engine"
  username = "eternal_admin"
  password = var.db_password
  
  backup_retention_period = 7
  multi_az               = true
  
  vpc_security_group_ids = [aws_security_group.db.id]
  
  tags = {
    Name = "Eternal Engine Database"
  }
}

# Secrets Manager
resource "aws_secretsmanager_secret" "bybit_key" {
  name                    = "eternal/bybit/api-key"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "bybit_key" {
  secret_id     = aws_secretsmanager_secret.bybit_key.id
  secret_string = var.bybit_api_key
}
```

---

## 9. Monitoring

### 9.1 Metrics Collection

```python
# src/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Optional

# Define metrics
TRADES_TOTAL = Counter(
    'eternal_trades_total',
    'Total number of trades executed',
    ['strategy', 'symbol', 'side']
)

TRADE_LATENCY = Histogram(
    'eternal_trade_latency_seconds',
    'Trade execution latency',
    buckets=[.001, .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5]
)

PORTFOLIO_VALUE = Gauge(
    'eternal_portfolio_value',
    'Current portfolio value in USD',
    ['engine']
)

POSITION_PNL = Gauge(
    'eternal_position_pnl',
    'Unrealized PnL per position',
    ['symbol', 'engine']
)

CIRCUIT_BREAKER_LEVEL = Gauge(
    'eternal_circuit_breaker_level',
    'Current circuit breaker level (0-4)'
)

API_ERRORS = Counter(
    'eternal_api_errors_total',
    'Total API errors',
    ['exchange', 'error_type']
)

SYSTEM_INFO = Info(
    'eternal_system_info',
    'System information'
)


class MetricsCollector:
    """Collect and expose metrics for monitoring."""
    
    def __init__(self):
        SYSTEM_INFO.info({
            'version': '1.0.0',
            'environment': 'production'
        })
    
    def record_trade(self, strategy: str, symbol: str, side: str):
        """Record trade execution."""
        TRADES_TOTAL.labels(
            strategy=strategy,
            symbol=symbol,
            side=side
        ).inc()
    
    def update_portfolio_value(self, engine: str, value: float):
        """Update portfolio value gauge."""
        PORTFOLIO_VALUE.labels(engine=engine).set(value)
    
    def record_api_error(self, exchange: str, error_type: str):
        """Record API error."""
        API_ERRORS.labels(
            exchange=exchange,
            error_type=error_type
        ).inc()
    
    def set_circuit_breaker(self, level: int):
        """Update circuit breaker level."""
        CIRCUIT_BREAKER_LEVEL.set(level)
```

### 9.2 Logging

```python
# src/utils/logging_config.py
import structlog
import logging
import sys
from pathlib import Path

def setup_logging():
    """Configure structured logging."""
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Add file handler for persistent logs
    file_handler = logging.FileHandler("logs/eternal_engine.log")
    file_handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
```

### 9.3 Alerts

```python
# src/monitoring/alerts.py
from enum import Enum
from typing import List, Dict
import aiohttp

class AlertSeverity(Enum):
    P0_CRITICAL = "p0"
    P1_HIGH = "p1"
    P2_MEDIUM = "p2"
    P3_LOW = "p3"

class AlertManager:
    """Multi-channel alert management."""
    
    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        webhook_url: Optional[str] = None
    ):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.webhook_url = webhook_url
        
        # Channel routing
        self.routing = {
            AlertSeverity.P0_CRITICAL: ['telegram', 'sms', 'email', 'phone'],
            AlertSeverity.P1_HIGH: ['telegram', 'email'],
            AlertSeverity.P2_MEDIUM: ['email'],
            AlertSeverity.P3_LOW: ['dashboard'],
        }
    
    async def send_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        metadata: Dict = None
    ):
        """Send alert through appropriate channels."""
        channels = self.routing.get(severity, ['dashboard'])
        
        for channel in channels:
            try:
                if channel == 'telegram':
                    await self._send_telegram(title, message)
                elif channel == 'webhook':
                    await self._send_webhook(severity, title, message, metadata)
            except Exception as e:
                logger.error(f"Failed to send {channel} alert: {e}")
    
    async def _send_telegram(self, title: str, message: str):
        """Send Telegram notification."""
        if not self.telegram_token or not self.telegram_chat_id:
            return
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": f"🚨 *{title}*\n\n{message}",
            "parse_mode": "Markdown"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    raise AlertError(f"Telegram API error: {resp.status}")
    
    async def _send_webhook(
        self, 
        severity: AlertSeverity, 
        title: str, 
        message: str,
        metadata: Dict
    ):
        """Send webhook notification."""
        if not self.webhook_url:
            return
        
        payload = {
            "severity": severity.value,
            "title": title,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload) as resp:
                resp.raise_for_status()
```

### 9.4 Dashboard

```python
# src/monitoring/dashboard.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import asyncio

app = FastAPI(title="Eternal Engine Dashboard")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard view."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>The Eternal Engine</title>
        <style>
            body { font-family: monospace; background: #1a1a1a; color: #00ff00; }
            .panel { border: 1px solid #333; padding: 20px; margin: 10px; }
            .value { font-size: 24px; font-weight: bold; }
            .green { color: #00ff00; }
            .red { color: #ff0000; }
            .yellow { color: #ffff00; }
        </style>
    </head>
    <body>
        <h1>🤖 THE ETERNAL ENGINE</h1>
        <div id="metrics"></div>
        <script>
            async function updateMetrics() {
                const resp = await fetch('/api/status');
                const data = await resp.json();
                document.getElementById('metrics').innerHTML = `
                    <div class="panel">
                        <h2>Portfolio Value: $${data.portfolio.total}</h2>
                        <p>24h Change: <span class="${data.performance.change_24h >= 0 ? 'green' : 'red'}">${data.performance.change_24h}%</span></p>
                        <p>Drawdown: ${data.risk.drawdown_pct}%</p>
                        <p>Circuit Breaker: ${data.risk.circuit_breaker}</p>
                    </div>
                    <div class="panel">
                        <h3>Engine Status</h3>
                        ${Object.entries(data.engines).map(([name, status]) => `
                            <p>${name}: ${status.is_active ? '🟢' : '🔴'} ${status.signals_generated} signals</p>
                        `).join('')}
                    </div>
                `;
            }
            setInterval(updateMetrics, 5000);
            updateMetrics();
        </script>
    </body>
    </html>
    """

@app.get("/api/status")
async def api_status():
    """API endpoint for current status."""
    return {
        "portfolio": {
            "total": "127450.00",
            "available": "45600.00"
        },
        "performance": {
            "change_24h": 2.3,
            "change_7d": 5.1,
            "sharpe_ratio": 1.47
        },
        "risk": {
            "drawdown_pct": 8.4,
            "circuit_breaker": "GREEN",
            "heat_score": 2.1
        },
        "engines": {
            "CORE": {"is_active": True, "signals_generated": 45},
            "TREND": {"is_active": True, "signals_generated": 12},
            "FUNDING": {"is_active": True, "signals_generated": 8},
            "TACTICAL": {"is_active": False, "signals_generated": 0}
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
```

---

## 10. Security

### 10.1 API Key Management

```python
# src/security/secrets.py
import os
from typing import Optional
import boto3
from botocore.exceptions import ClientError

class SecretsManager:
    """Secure API key management."""
    
    def __init__(self, region: str = "ap-southeast-1"):
        self.region = region
        self._secrets = {}
        
        # Try to use AWS Secrets Manager
        try:
            self.client = boto3.client('secretsmanager', region_name=region)
        except Exception:
            self.client = None
    
    def get_secret(self, name: str) -> Optional[str]:
        """Retrieve secret from secure storage."""
        # Check cache
        if name in self._secrets:
            return self._secrets[name]
        
        # Try AWS Secrets Manager
        if self.client:
            try:
                response = self.client.get_secret_value(SecretId=name)
                secret = response['SecretString']
                self._secrets[name] = secret
                return secret
            except ClientError as e:
                logger.warning(f"Could not retrieve from AWS: {e}")
        
        # Fall back to environment variable
        env_name = name.replace('/', '_').upper()
        secret = os.getenv(env_name)
        if secret:
            self._secrets[name] = secret
            return secret
        
        return None
    
    def rotate_api_key(self, secret_name: str):
        """Rotate API key (for scheduled rotation)."""
        # Implementation depends on exchange API
        logger.info(f"Rotating API key: {secret_name}")
        
        # Clear cache
        if secret_name in self._secrets:
            del self._secrets[secret_name]
```

### 10.2 IP Whitelisting

```python
# src/security/ip_whitelist.py
import ipaddress
from typing import List
from fastapi import Request, HTTPException

class IPWhitelist:
    """IP whitelist middleware."""
    
    def __init__(self, allowed_ips: List[str]):
        self.allowed_networks = [
            ipaddress.ip_network(ip) for ip in allowed_ips
        ]
    
    def is_allowed(self, ip: str) -> bool:
        """Check if IP is in whitelist."""
        try:
            client_ip = ipaddress.ip_address(ip)
            return any(
                client_ip in network 
                for network in self.allowed_networks
            )
        except ValueError:
            return False
    
    async def __call__(self, request: Request, call_next):
        """Middleware for FastAPI."""
        client_ip = request.client.host
        
        if not self.is_allowed(client_ip):
            raise HTTPException(
                status_code=403,
                detail="IP not in whitelist"
            )
        
        return await call_next(request)

# Usage
whitelist = IPWhitelist([
    "192.168.1.0/24",      # Office network
    "10.0.0.0/8",          # VPN
    "203.0.113.50/32",     # Specific server
])
```

### 10.3 Encryption

```python
# src/security/encryption.py
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

class DataEncryption:
    """Encryption for sensitive data at rest."""
    
    def __init__(self, master_key: str):
        """Initialize with master encryption key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=os.urandom(16),
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt string data."""
        return self.cipher.decrypt(encrypted.encode()).decode()
    
    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt sensitive fields in a dictionary."""
        encrypted = {}
        for key, value in data.items():
            if self._is_sensitive_field(key):
                encrypted[key] = self.encrypt(str(value))
            else:
                encrypted[key] = value
        return encrypted
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """Determine if field should be encrypted."""
        sensitive = ['api_key', 'api_secret', 'password', 'private_key']
        return any(s in field_name.lower() for s in sensitive)
```

### 10.4 Security Checklist

```markdown
## Pre-Deployment Security Checklist

### Code Security
- [ ] No hardcoded secrets in code
- [ ] All inputs validated
- [ ] SQL injection protection enabled
- [ ] No debug endpoints in production
- [ ] Bandit security scan passed

### Infrastructure Security
- [ ] VPC isolated from public internet
- [ ] Security groups restrict access
- [ ] Database encrypted at rest (AES-256)
- [ ] TLS 1.3 for all connections
- [ ] API keys in Secrets Manager

### Operational Security
- [ ] 2FA enabled on all accounts
- [ ] IP whitelisting configured on exchange
- [ ] Withdrawal whitelist set
- [ ] API keys have minimum permissions (no withdraw)
- [ ] Regular key rotation scheduled

### Exchange Security (Bybit)
- [ ] Separate API keys per subaccount
- [ ] Read-only keys for monitoring
- [ ] Trading keys IP-restricted
- [ ] Master account secured offline
- [ ] Insurance fund monitored
```

---

## Appendix: Quick Reference

### Environment Variables

```bash
# Required
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
DATABASE_URL=postgresql://user:pass@host/db

# Optional
TRADING_MODE=paper          # paper or live
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
TELEGRAM_BOT_TOKEN=token    # For alerts
TELEGRAM_CHAT_ID=chat_id    # For alerts
```

### Make Commands

```bash
make install      # Install dependencies
make test         # Run tests
make lint         # Run linting
make format       # Format code
make build        # Build Docker image
make deploy       # Deploy to production
make logs         # View logs
make stop         # Stop services
```

### Key Documentation References

| Document | Location | Purpose |
|----------|----------|---------|
| Strategy Specs | `docs/04-trading-strategies/` | Trading logic details |
| Risk Framework | `docs/05-risk-management/` | Risk management rules |
| Bybit Integration | `docs/06-infrastructure/` | API implementation |
| Implementation Roadmap | `docs/09-implementation/` | Development phases |
| Configuration Examples | `docs/10-appendices/` | Sample configs |

---

**Document Version:** 1.0.0  
**Last Updated:** 2026-02-13  
**Maintainer:** Development Team

*For questions or issues, refer to the main documentation in the `docs/` folder.*
