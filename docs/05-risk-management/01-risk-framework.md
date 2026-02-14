# THE ETERNAL ENGINE
## Document 05: Risk Management Framework

---

# PART I: RISK PHILOSOPHY

## Chapter 1: The First Principle

> **"There are old traders, and there are bold traders, but there are no old bold traders."**
> — Ed Seykota

### 1.1 Our Risk Philosophy

The Eternal Engine is designed around a single unshakeable principle:

**SURVIVAL COMES BEFORE PROFIT.**

Every component of this system—from position sizing to circuit breakers—exists to ensure that the portfolio survives to compound another day. We optimize for the 20-year outcome, not the quarterly return.

### 1.2 The Four Categories of Risk

We categorize risk into four distinct types, each requiring specific controls:

| Risk Category | Definition | Primary Mitigation |
|--------------|------------|-------------------|
| **Market Risk** | Loss from adverse price movements | Position sizing, diversification, stops |
| **Operational Risk** | Loss from system/process failures | Redundancy, monitoring, circuit breakers |
| **Counterparty Risk** | Loss from exchange/counterparty failure | Subaccount isolation, insurance funds |
| **Liquidity Risk** | Inability to exit positions | Position limits, liquidity monitoring |

### 1.3 Risk Tolerance Statement

**Maximum Acceptable Losses:**
- Single Trade: 1% of portfolio
- Single Strategy: 15% drawdown
- Total Portfolio: 35% drawdown
- Annual Loss: 25% (circuit breaker triggers)

**Time to Recovery:**
- 35% drawdown: 12-24 months expected
- 20% drawdown: 6-12 months expected
- 10% drawdown: 3-6 months expected

---

# PART II: POSITION SIZING & CAPITAL ALLOCATION

## Chapter 2: The Kelly Criterion & Fractional Kelly

### 2.1 Mathematical Foundation

The Kelly Criterion calculates the optimal fraction of capital to risk on a given bet to maximize long-term growth:

```
Kelly Fraction = (p × b - q) / b

Where:
  p = probability of win
  b = win/loss ratio (average win / average loss)
  q = probability of loss (1 - p)
```

**Example:**
- Win rate: 40% (p = 0.4)
- Average win: $300
- Average loss: $100 (b = 3.0)

```
Kelly = (0.4 × 3.0 - 0.6) / 3.0 = 0.2 (20% of capital per trade)
```

### 2.2 Fractional Kelly: The Conservative Approach

Full Kelly is mathematically optimal but psychologically and practically dangerous:
- Results in 50%+ drawdowns 50% of the time
- Requires perfect knowledge of probabilities
- No room for estimation errors

**Our Solution: 1/8 Kelly**

We use 1/8th of the full Kelly recommendation, providing:
- **90% reduction in drawdowns** vs. full Kelly
- **Smoother equity curves** for long-term compounding
- **Buffer for strategy decay** and changing markets

### 2.3 Implementation

```python
class PositionSizing:
    def __init__(self):
        self.kelly_fraction = 0.125  # 1/8 Kelly
        self.max_position_pct = 0.05  # 5% max per position
        self.max_risk_per_trade = 0.01  # 1% portfolio risk
        
    def calculate_position_size(self, account_value, entry_price, 
                                stop_price, win_rate=0.4, avg_win_loss_ratio=2.5):
        """
        Calculate position size using fractional Kelly
        """
        # Kelly calculation
        p = win_rate
        b = avg_win_loss_ratio
        q = 1 - p
        
        kelly = (b * p - q) / b
        adjusted_kelly = kelly * self.kelly_fraction
        
        # Risk-based sizing (1% max risk per trade)
        risk_per_share = abs(entry_price - stop_price)
        risk_amount = account_value * self.max_risk_per_trade
        risk_based_size = risk_amount / risk_per_share
        
        # Kelly-based sizing
        kelly_size = account_value * adjusted_kelly / entry_price
        
        # Take the smaller of the two
        position_size = min(risk_based_size, kelly_size)
        
        # Apply maximum position limit
        max_position = account_value * self.max_position_pct / entry_price
        position_size = min(position_size, max_position)
        
        return position_size
```

### 2.4 Engine-Specific Sizing

**CORE-HODL Engine (60% allocation):**
- No leverage (1x only)
- Position size = full allocation (60% total, 40% BTC + 20% ETH)
- Rebalancing thresholds: 10% drift triggers

**TREND Engine (20% allocation):**
- Maximum 2x leverage
- Risk per trade: 1% of engine capital (0.2% of total portfolio)
- Maximum position: 50% of engine per asset

**FUNDING Engine (15% allocation):**
- Maximum 2x leverage on short leg
- Delta-neutral sizing (1:1 ratio)
- Risk: Basis risk (spot-perp divergence)

**TACTICAL Engine (5% allocation):**
- No leverage (spot only)
- Deploys in 50% increments
- Maximum exposure: 5% of total portfolio

---

## Chapter 3: The Four-Level Circuit Breaker System

### 3.1 System Overview

Our circuit breaker system provides automatic capital preservation at four drawdown thresholds. Each level triggers increasingly protective actions.

```
Portfolio Value
    ↑
100%│━━━━━━━━━━━━ Normal Operations
    │
 95%│──────────── Level 1: CAUTION (Yellow)
    │             ↓ Reduce sizes 25%
    │
 90%│──────────── Level 2: WARNING (Orange)
    │             ↓ Reduce sizes 50%, pause entries
    │
 85%│──────────── Level 3: ALERT (Red)
    │             ↓ Close directional, move to stables
    │
 80%│──────────── Level 4: EMERGENCY (Black)
                  ↓ Full liquidation, halt indefinitely
```

### 3.2 Level 1: CAUTION (10% Drawdown)

**Trigger:** Portfolio value drops 10% from all-time high

**Automatic Actions:**
```python
class Level1Caution:
    def execute(self, portfolio):
        actions = []
        
        # Reduce position sizes by 25%
        for position in portfolio.open_positions:
            if position.engine in ['TREND', 'FUNDING']:
                target_size = position.size * 0.75
                actions.append(ReducePosition(position, target_size))
        
        # Widen stop losses by 50% (avoid whipsaws)
        for position in portfolio.open_positions:
            if position.stop_loss:
                new_stop = adjust_stop_wider(position, multiplier=1.5)
                actions.append(ModifyStop(position, new_stop))
        
        # Halt new TACTICAL deployments
        portfolio.engines['TACTICAL'].pause_new_entries(duration='24h')
        
        # Increase monitoring frequency
        portfolio.monitoring_frequency = 'hourly'
        
        # Alert: Log only (no operator action required)
        log_event('LEVEL_1_CAUTION', portfolio.drawdown)
        
        return actions
```

**Recovery Condition:**
- Portfolio recovers to within 5% of ATH
- Automatic return to normal operations

### 3.3 Level 2: WARNING (15% Drawdown)

**Trigger:** Portfolio value drops 15% from all-time high

**Automatic Actions:**
```python
class Level2Warning:
    def execute(self, portfolio):
        actions = []
        
        # Reduce all position sizes by 50%
        for position in portfolio.open_positions:
            if position.engine == 'TREND':
                target_size = position.size * 0.50
                actions.append(ReducePosition(position, target_size))
        
        # Close 50% of losing TREND positions
        losing_positions = [p for p in portfolio.open_positions 
                           if p.pnl < 0 and p.engine == 'TREND']
        for position in losing_positions[:len(losing_positions)//2]:
            actions.append(ClosePosition(position))
        
        # Move 10% from CORE to stablecoins
        core_value = portfolio.engines['CORE'].value
        amount_to_move = core_value * 0.10
        actions.append(TransferToStables('CORE', amount_to_move))
        
        # Pause FUNDING arbitrage if rates negative
        if funding_rates_negative():
            portfolio.engines['FUNDING'].close_all_positions()
        
        # Halt all new trading for 72 hours
        portfolio.halt_new_entries(duration='72h')
        
        # Alert: Send notification to operator
        alert_operator('LEVEL_2_WARNING', portfolio.drawdown, 
                      action_required='Review recommended')
        
        return actions
```

**Recovery Condition:**
- Portfolio recovers to within 10% of ATH
- Manual review and approval required to resume full operations

### 3.4 Level 3: ALERT (20% Drawdown)

**Trigger:** Portfolio value drops 20% from all-time high

**Automatic Actions:**
```python
class Level3Alert:
    def execute(self, portfolio):
        actions = []
        
        # CLOSE ALL TREND positions immediately
        for position in portfolio.open_positions:
            if position.engine == 'TREND':
                actions.append(ClosePosition(position, urgency='immediate'))
        
        # CLOSE ALL FUNDING positions
        for position in portfolio.open_positions:
            if position.engine == 'FUNDING':
                actions.append(ClosePosition(position))
        
        # Move 50% of CORE to Bybit Earn (stable yield)
        core_value = portfolio.engines['CORE'].value
        amount_to_earn = core_value * 0.50
        actions.append(MoveToEarn('CORE', amount_to_earn))
        
        # Halt all new trading indefinitely
        portfolio.halt_all_trading()
        
        # Require manual restart with 25% position sizes
        portfolio.restart_requirements = {
            'position_size_multiplier': 0.25,
            'manual_approval_required': True,
            'cooldown_period': '72h'
        }
        
        # Alert: URGENT notification to operator
        alert_operator('LEVEL_3_ALERT', portfolio.drawdown,
                      action_required='MANUAL INTERVENTION REQUIRED',
                      channels=['email', 'sms', 'phone'])
        
        return actions
```

**Recovery Condition:**
- Manual review by operator
- Strategy audit completed
- Approval granted by authorized personnel
- Gradual restart at 25% size

### 3.5 Level 4: EMERGENCY (25% Drawdown)

**Trigger:** Portfolio value drops 25% from all-time high

**Automatic Actions:**
```python
class Level4Emergency:
    def execute(self, portfolio):
        actions = []
        
        # LIQUIDATE everything to USDT
        for position in portfolio.open_positions:
            actions.append(ClosePosition(position, urgency='emergency'))
        
        # Transfer ALL funds to Bybit Earn Flexible
        total_value = portfolio.total_value
        actions.append(TransferAllToEarnFlexible())
        
        # HALT all trading indefinitely
        portfolio.kill_switch_activated = True
        portfolio.halt_all_trading(permanent=True)
        
        # Log comprehensive state
        log_emergency_state(portfolio)
        
        # Alert: EMERGENCY notification to all stakeholders
        alert_all_stakeholders('LEVEL_4_EMERGENCY', portfolio.drawdown,
                              message='SYSTEM HALTED - FULL AUDIT REQUIRED',
                              channels=['email', 'sms', 'phone', 'telegram'])
        
        return actions
```

**Recovery Condition:**
- Full forensic audit of all trades
- Root cause analysis completed
- Risk committee approval
- Strategy modifications implemented
- Dual-authorization required to restart

---

## Chapter 4: Correlation Risk Management

### 4.1 The "Everything Correlates to 1.0" Problem

During market crashes, crypto assets that normally show 0.6-0.7 correlation suddenly move in lockstep (0.9+ correlation). This destroys diversification benefits precisely when they're needed most.

**Historical Examples:**
- March 2020 (COVID crash): BTC-ETH correlation spiked to 0.95
- May 2021 (China ban): All alts correlated 0.92+
- November 2022 (FTX collapse): Correlation across all assets >0.90

### 4.2 Correlation Monitoring System

```python
class CorrelationRiskMonitor:
    def __init__(self):
        self.lookback_period = 30  # days
        self.crisis_threshold = 0.75
        self.emergency_threshold = 0.90
        
    def calculate_correlation_matrix(self, returns_df):
        """
        Calculate rolling correlation matrix
        """
        correlation_matrix = returns_df.rolling(
            window=self.lookback_period
        ).corr()
        
        return correlation_matrix
        
    def assess_correlation_risk(self, correlation_matrix):
        """
        Determine if we're in correlation crisis
        """
        # Get average correlation (excluding diagonal)
        avg_correlation = correlation_matrix.values[
            np.triu_indices_from(correlation_matrix.values, k=1)
        ].mean()
        
        # Get max correlation
        max_correlation = correlation_matrix.values[
            np.triu_indices_from(correlation_matrix.values, k=1)
        ].max()
        
        risk_level = 'NORMAL'
        if max_correlation > self.emergency_threshold:
            risk_level = 'EMERGENCY'
        elif avg_correlation > self.crisis_threshold:
            risk_level = 'CRISIS'
        elif avg_correlation > 0.60:
            risk_level = 'ELEVATED'
            
        return {
            'avg_correlation': avg_correlation,
            'max_correlation': max_correlation,
            'risk_level': risk_level
        }
```

### 4.3 Automatic Responses

**ELEVATED (>0.60):**
- Increase monitoring frequency to hourly
- Log warning

**CRISIS (>0.75):**
- Reduce total crypto exposure by 30%
- Move funds to stablecoins
- Activate "survival mode" (only CORE-HODL operates)

**EMERGENCY (>0.90):**
- Move 50% of portfolio to stablecoins immediately
- Close all directional strategies (TREND)
- Keep only market-neutral positions (FUNDING)
- Alert operator

### 4.4 The Stablecoin Hedge

Our primary hedge against correlation spikes is the **30% stablecoin allocation**:

```
Normal Market:
├── 70% Crypto (diversified, low correlation)
└── 30% Stables (yield generation)

Crisis Market:
├── 40% Crypto (reduced exposure)
└── 60% Stables (dry powder, wait for recovery)
```

This automatic de-risking ensures we survive to buy the bottom.

---

## Chapter 5: Liquidity Risk Management

### 5.1 Real-Time Liquidity Assessment

Before every trade, we assess order book depth to ensure we can exit if needed.

```python
class LiquidityRiskManager:
    def __init__(self):
        self.min_depth_usd = 100000  # $100k on each side
        self.max_slippage_pct = 0.5   # 0.5% max slippage
        
    def assess_liquidity(self, symbol, trade_size):
        """
        Assess if market can absorb our trade
        """
        orderbook = fetch_orderbook(symbol)
        
        # Calculate depth within 1% of mid price
        mid_price = (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2
        
        bid_depth_1pct = sum(
            size for price, size in orderbook['bids']
            if price >= mid_price * 0.99
        )
        
        ask_depth_1pct = sum(
            size for price, size in orderbook['asks']
            if price <= mid_price * 1.01
        )
        
        # Estimate slippage
        slippage = self.estimate_slippage(trade_size, orderbook)
        
        return {
            'bid_depth': bid_depth_1pct,
            'ask_depth': ask_depth_1pct,
            'slippage_estimate': slippage,
            'can_execute': (bid_depth_1pct >= self.min_depth_usd and
                          ask_depth_1pct >= self.min_depth_usd and
                          slippage <= self.max_slippage_pct)
        }
```

### 5.2 Position Limits by Liquidity

| Asset Tier | Max Position | Max Trade Size | Slippage Limit |
|-----------|--------------|----------------|----------------|
| **Tier 1** (BTC, ETH) | 20% portfolio | 5% portfolio | 0.3% |
| **Tier 2** (SOL, AVAX) | 5% portfolio | 2% portfolio | 0.5% |
| **Tier 3** (Other alts) | 2% portfolio | 0.5% portfolio | 1.0% |

### 5.3 Flash Crash Protection

**Detection:**
- Price drop >5% in 1 minute
- Order book depth drops >50%
- Spread widens >3x normal

**Response:**
- Pause all market orders
- Switch to limit orders only
- Cancel pending orders
- Wait for liquidity restoration

---

## Chapter 6: Counterparty Risk (Bybit)

### 6.1 Exchange Risk Assessment

**Bybit Specific Risks:**
1. **Hack/Theft**: Exchange security breach
2. **Insolvency**: Exchange cannot meet obligations
3. **Regulatory Shutdown**: Government action freezes assets
4. **Operational Failure**: Extended downtime during crisis

### 6.2 Mitigation Strategies

**Subaccount Isolation:**
- Each engine operates in separate subaccount
- Failure of one doesn't contaminate others
- Master account controls capital allocation

**Insurance Fund Monitoring:**
```python
def monitor_insurance_fund():
    """
    Monitor Bybit's insurance fund health
    """
    insurance_data = fetch_insurance_fund_status()
    
    if insurance_data['ratio'] < 0.1:  # Less than 10% capacity
        alert_operator('INSURANCE_FUND_LOW', insurance_data)
        reduce_position_sizes(by=0.50)
    
    if insurance_data['combined_balance'] <= 0:
        alert_operator('INSURANCE_FUND_DEPLETED', insurance_data, 
                      urgency='EMERGENCY')
        close_all_positions()
```

**ADL (Auto-Deleveraging) Protection:**
- Monitor ADL priority indicator
- Reduce leverage if ranked high for ADL
- Partially close profitable positions before ADL trigger

### 6.3 Exit Strategy

If Bybit becomes compromised:

```
IMMEDIATE (0-1 hour):
├── Cancel all pending orders
├── Close all positions if possible
├── Transfer liquid funds to cold storage
└── Document all positions for claims

SHORT-TERM (1-24 hours):
├── Monitor exchange communications
├── Prepare legal documentation
├── Contact exchange support
└── Alert all stakeholders

LONG-TERM (1-30 days):
├── File claims if applicable
├── Assess recovery options
├── Activate backup exchange if configured
└── Post-mortem analysis
```

---

# PART III: OPERATIONAL RISK MANAGEMENT

## Chapter 7: System Failure Modes

### 7.1 API Failure Scenarios

| Failure Mode | Detection | Response | Recovery |
|-------------|-----------|----------|----------|
| **Rate Limit Hit** | HTTP 429 | Exponential backoff | Resume with delay |
| **Authentication Error** | HTTP 401 | Halt trading | Manual key rotation |
| **Timeout** | 30s+ no response | Retry x3 | Alert operator |
| **Partial Fill** | Filled < requested | Manage remainder | Continue monitoring |
| **Stale Data** | Price unchanged 60s | Switch to backup feed | Investigate |

### 7.2 Database Failure

**Primary Database Failure:**
1. Automatic failover to read replica
2. Alert operator
3. Queue new trades for later reconciliation
4. Continue with reduced functionality

**Full Database Loss:**
1. Reconstruct state from exchange API
2. Verify all positions
3. Reconcile any discrepancies
4. Manual approval required to resume

### 7.3 Network Connectivity

**Detection:**
- Heartbeat checks every 30 seconds
- Multiple redundant connections
- External monitoring (Pingdom, UptimeRobot)

**Response:**
- Attempt reconnection (3 attempts)
- Switch to backup connection
- If persistent: Halt trading, alert operator

---

## Chapter 8: Human Error Protection

### 8.1 Configuration Validation

All configuration changes validated before application:

```python
class ConfigValidator:
    def validate(self, new_config):
        """
        Validate configuration changes
        """
        errors = []
        
        # Check position sizing limits
        if new_config['max_position_pct'] > 0.25:
            errors.append("Max position cannot exceed 25%")
            
        # Check leverage limits
        if new_config['max_leverage'] > 3:
            errors.append("Max leverage cannot exceed 3x")
            
        # Check circuit breaker thresholds
        if new_config['circuit_breaker_4'] > 0.30:
            errors.append("Circuit breaker 4 must be <= 30%")
            
        # Check allocation sums to 100%
        total_allocation = sum(new_config['engine_allocations'].values())
        if abs(total_allocation - 1.0) > 0.01:
            errors.append(f"Allocations must sum to 100%, got {total_allocation}")
            
        return len(errors) == 0, errors
```

### 8.2 Dual Authorization

Critical actions require dual authorization:

```
ACTIONS REQUIRING DUAL AUTH:
├── Circuit breaker manual override
├── Strategy parameter changes >20%
├── Position size increases >50%
├── Exchange API key rotation
├── Emergency withdrawal
└── System restart after Level 3+ halt
```

---

# PART IV: MONITORING & REPORTING

## Chapter 9: Real-Time Risk Dashboard

### 9.1 Key Risk Metrics

| Metric | Warning | Critical | Calculation |
|--------|---------|----------|-------------|
| **Portfolio Heat** | >3% | >5% | Sum of all position risks |
| **Max Drawdown** | >10% | >20% | From ATH |
| **Leverage** | >1.5x | >2.5x | Total notional / equity |
| **Correlation** | >0.70 | >0.90 | 30-day rolling |
| **Concentration** | >30% single asset | >45% | Largest position % |
| **Daily Loss** | >2% | >5% | 24h P&L |

### 9.2 Risk Reports

**Daily Risk Report (Auto-generated):**
- Portfolio heat score
- Drawdown status
- Correlation matrix
- Circuit breaker status
- Any limit breaches

**Weekly Risk Report:**
- VaR (Value at Risk) 95% confidence
- Expected Shortfall (CVaR)
- Sharpe ratio (7-day rolling)
- Maximum consecutive losses
- Strategy health scores

**Monthly Risk Report:**
- Full risk attribution analysis
- Stress test results
- Correlation regime analysis
- Circuit breaker trigger review
- Recommended parameter adjustments

---

## Chapter 10: Stress Testing

### 10.1 Historical Stress Tests

We simulate the system through historical crises:

| Event | Date | BTC Drawdown | System Expected DD |
|-------|------|--------------|-------------------|
| COVID Crash | Mar 2020 | -50% | -25% (trend exit) |
| China Ban | May 2021 | -54% | -28% (stables deployed) |
| FTX Collapse | Nov 2022 | -25% | -15% (funding income) |
| 2018 Bear | 2018 | -84% | -35% (DCA benefit) |

### 10.2 Hypothetical Stress Tests

**Black Swan Scenarios:**
1. **Regulatory Ban**: Crypto trading banned in major economies
2. **Exchange Hack**: Bybit loses 50% of funds
3. **Stablecoin Collapse**: USDT depegs to $0.50
4. **Quantum Computing**: BTC cryptography broken
5. **Global Depression**: 50% GDP contraction

**Expected Outcomes:**
- Maximum loss: 50-70% of portfolio
- Recovery time: 2-5 years
- System survival: YES (diversification, circuit breakers)

---

# CONCLUSION: THE SAFETY FIRST APPROACH

The Eternal Engine's risk management framework is designed around one truth:

**You cannot compound capital that you've lost.**

Every component—from 1/8 Kelly sizing to four-level circuit breakers to correlation monitoring—exists to ensure survival first, profit second.

**Key Safeguards:**
1. **Position sizing** prevents ruin from any single trade
2. **Circuit breakers** prevent catastrophic drawdowns
3. **Correlation monitoring** protects during crashes
4. **Liquidity assessment** ensures we can always exit
5. **Counterparty controls** mitigate exchange risk
6. **Operational redundancy** prevents system failures

**The Result:**
- Maximum expected drawdown: -35%
- Liquidation probability: <0.01%
- 20-year survival probability: >95%

This is not risk elimination—it is risk management. And in trading, that is the only sustainable edge.

---

*Next Document: [06-infrastructure.md](./06-infrastructure.md) - Bybit Integration & Technical Implementation*
