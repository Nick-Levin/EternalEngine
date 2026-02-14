# THE ETERNAL ENGINE
## Document 03: System Architecture & Technical Design

---

# PART I: ARCHITECTURE PHILOSOPHY

## Chapter 1: The Autonomous Design Principles

### 1.1 Core Architectural Tenets

The Eternal Engine is built on five non-negotiable principles:

**TENET 1: DECENTRALIZED INTELLIGENCE**
No single point of failure. The system distributes decision-making across four independent engines. If one fails, three continue. If three struggle, one sustains.

**TENET 2: DEFENSE IN DEPTH**
Risk management isn't a module—it's the foundation. Every component assumes the others may fail and protects accordingly.

**TENET 3: MECHANICAL EXECUTION**
No discretion. No judgment calls. No "this time is different." Every action is rule-based and backtested.

**TENET 4: EVOLUTIONARY ADAPTATION**
The system monitors its own performance and adjusts. Strategies that decay are rotated. New opportunities are integrated.

**TENET 5: OBSERVABILITY**
Every decision, every trade, every heartbeat is logged, monitored, and auditable. Nothing happens in darkness.

### 1.2 The Multi-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 5: PRESENTATION                         │
│         (Dashboards, Alerts, Reports, API Consumers)            │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 4: GOVERNANCE                           │
│    (Circuit Breakers, Policy Enforcement, Human Override)       │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 3: ORCHESTRATION                        │
│    (Capital Allocation, Rebalancing, Strategy Rotation)         │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 2: EXECUTION                            │
│    (Order Management, Position Tracking, Risk Controls)         │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 1: INFRASTRUCTURE                       │
│    (Exchange Integration, Data Feeds, State Management)         │
└─────────────────────────────────────────────────────────────────┘
```

**Key Design Decision:**  
Each layer is isolated and communicates via well-defined interfaces. A failure in Layer 1 (exchange API down) triggers Layer 4 (circuit breaker), but doesn't corrupt Layer 3 (orchestration state).

---

# PART II: THE FOUR ENGINES

## Chapter 2: Engine 1 - CORE-HODL (Capital Preservation & Growth)

### 2.1 Purpose & Philosophy

**Mission:** Provide the foundation of long-term wealth compounding through systematic accumulation of the two dominant crypto assets.

**Core Belief:** Bitcoin and Ethereum represent the "digital gold" and "digital oil" of the 21st century. Over 10-20 year horizons, spot ownership outperforms 95% of active strategies.

**Differentiation:** This isn't passive holding. It's **active rebalancing** that harvests volatility premium while maintaining core exposure.

### 2.2 Technical Specifications

**Asset Allocation:**
```yaml
CORE-HODL:
  target_allocation:
    BTC: 40%  # 2/3 of engine (digital gold)
    ETH: 20%  # 1/3 of engine (digital oil)
  total_portfolio_weight: 60%
  
  rebalancing:
    frequency: quarterly
    trigger_threshold: 10%  # Drift from target
    method: threshold_with_calendar_fallback
    
  execution:
    primary_market: spot
    secondary_market: none  # No derivatives
    order_type: limit_maker  # Minimize fees
    
  yield_optimization:
    eth_staking: enabled
    staking_platform: bybit_earn
    minimum_yield_threshold: 2.0%
```

**Rebalancing Algorithm:**

```python
def rebalance_core_hodl(current_positions, target_allocation):
    """
    Quarterly rebalancing with threshold trigger
    """
    drift = calculate_allocation_drift(current_positions, target_allocation)
    
    # Check calendar trigger (quarterly)
    if is_quarter_end() or abs(drift) > REBALANCE_THRESHOLD:
        overweight_assets = get_overweight_assets(current_positions)
        underweight_assets = get_underweight_assets(current_positions)
        
        # Sell winners, buy losers
        for asset in overweight_assets:
            amount_to_sell = calculate_excess_position(asset, target_allocation)
            place_limit_sell(asset, amount_to_sell, price=best_bid)
            
        for asset in underweight_assets:
            amount_to_buy = calculate_deficit_position(asset, target_allocation)
            place_limit_buy(asset, amount_to_buy, price=best_ask)
            
        log_rebalance_event(drift, trades_executed)
```

### 2.3 State Machine

```
[INITIALIZING] → [ACCUMULATING] → [REBALANCING] → [EARN_OPTIMIZING] → [ACCUMULATING]
      ↑                                                              ↓
      └──────────────────────────────────────────────────────────────┘
```

**States:**
- **INITIALIZING**: Build positions to target allocation via DCA
- **ACCUMULATING**: Hold positions, monitor drift
- **REBALANCING**: Execute sell-high/buy-low when threshold hit
- **EARN_OPTIMIZING**: Move idle ETH to staking during stable periods

### 2.4 Risk Controls

**Position Limits:**
- Maximum single asset: 45% (prevents concentration)
- Minimum cash buffer: 5% (emergency liquidity)

**Circuit Breakers:**
- If asset drops >70% from ATH: Pause rebalancing (don't sell the bottom)
- If exchange withdrawal issues detected: Halt all activity, alert operator

**Monitoring Metrics:**
- Allocation drift (target: <10%)
- Rebalancing frequency (target: quarterly ± 2 weeks)
- Staking yield vs. opportunity cost

---

## Chapter 3: Engine 2 - TREND (Crisis Alpha Generation)

### 3.1 Purpose & Philosophy

**Mission:** Capture directional trends in crypto markets while providing positive returns during crashes (crisis alpha).

**Core Belief:** Crypto exhibits strong momentum persistence due to behavioral biases (herding, FOMO, panic). Trend following exploits these predictable patterns.

**Differentiation:** Unlike buy-and-hold, this engine exits during bear markets, preserving capital for re-deployment at lower prices.

### 3.2 Technical Specifications

**Strategy Parameters:**
```yaml
TREND:
  market: perpetual_futures
  assets:
    - BTC-PERP
    - ETH-PERP
    
  indicators:
    long_term_ma: 200_period_sma
    medium_term_ma: 50_period_sma
    trend_strength: adx_14
    volatility: atr_14
    
  entry_rules:
    long:
      - price > 200_sma
      - 50_sma > 200_sma
      - adx > 25  # Strong trend
    short:
      - price < 200_sma
      - 50_sma < 200_sma
      - adx > 25
      
  exit_rules:
    long_exit: price_closes_below_200_sma
    short_exit: price_closes_above_200_sma
    trailing_stop: 3x_atr
    
  position_sizing:
    risk_per_trade: 1.0%  # Of subaccount
    max_position: 50%     # Of subaccount per asset
    leverage_max: 2x
    
  total_portfolio_weight: 20%
  subaccount_split:
    TREND-1: 15%  # Primary trend parameters
    TREND-2: 5%   # Alternative parameters (diversification)
```

### 3.3 The Dual Momentum Algorithm

```python
class TrendEngine:
    def __init__(self):
        self.fast_ma = 50
        self.slow_ma = 200
        self.adx_threshold = 25
        self.atr_multiplier = 3.0
        
    def analyze_market(self, ohlcv_data):
        """
        Daily market analysis
        """
        close = ohlcv_data['close']
        high = ohlcv_data['high']
        low = ohlcv_data['low']
        
        # Calculate indicators
        sma_50 = calculate_sma(close, self.fast_ma)
        sma_200 = calculate_sma(close, self.slow_ma)
        adx = calculate_adx(high, low, close, 14)
        atr = calculate_atr(high, low, close, 14)
        
        # Determine regime
        if close[-1] > sma_200[-1] and sma_50[-1] > sma_200[-1] and adx[-1] > self.adx_threshold:
            return Signal.LONG, self.calculate_position_size(atr)
        elif close[-1] < sma_200[-1] and sma_50[-1] < sma_200[-1] and adx[-1] > self.adx_threshold:
            return Signal.SHORT, self.calculate_position_size(atr)
        else:
            return Signal.FLAT, 0
            
    def calculate_position_size(self, atr, account_value):
        """
        ATR-based position sizing (1% risk per trade)
        """
        risk_amount = account_value * 0.01
        stop_distance = atr * 2  # 2x ATR stop
        position_size = risk_amount / stop_distance
        
        # Apply leverage constraint
        max_notional = account_value * 2  # 2x max leverage
        position_size = min(position_size, max_notional / current_price)
        
        return position_size
```

### 3.4 State Machine

```
[SCANNING] → [SIGNAL_DETECTED] → [ENTERING] → [IN_POSITION] → [EXITING] → [SCANNING]
                ↓                      ↓              ↓
           [NO_TRADE]           [STOPPED_OUT]  [TRAILING_STOP]
```

### 3.5 Risk Controls

**Position Management:**
- Maximum 2 concurrent positions (BTC + ETH)
- Risk per trade: 1% of subaccount (0.2% of total portfolio)
- Leverage: Maximum 2x (liquidation buffer >50%)

**Stop Loss Architecture:**
- Hard stop: 2x ATR from entry
- Trailing stop: 3x ATR once profitable
- Time stop: Close after 30 days regardless of P&L (prevents stagnation)

**Circuit Breakers:**
- If ADX < 20 for 14 days: Pause new entries (no trend)
- If correlation > 0.9: Reduce position sizes 50%
- If funding rate > 0.1% per 8h: Consider closing (expensive to hold)

---

## Chapter 4: Engine 3 - FUNDING (Market-Neutral Yield)

### 4.1 Purpose & Philosophy

**Mission:** Generate consistent, market-neutral yield by capturing perpetual futures funding rate premiums.

**Core Belief:** Long bias in crypto markets creates persistent funding rate imbalances. Delta-neutral positions harvest this premium without directional risk.

**Differentiation:** Provides positive returns even in bear markets when other engines struggle.

### 4.2 Technical Specifications

```yaml
FUNDING:
  strategy: delta_neutral_funding_arbitrage
  assets:
    - BTC
    - ETH
    - SOL
    
  structure:
    long_leg: spot_market
    short_leg: perpetual_futures
    ratio: 1:1  # Perfect delta neutrality
    
  entry_conditions:
    predicted_funding_rate: "> 0.01% per 8h"  # Positive funding
    consecutive_positive_periods: ">= 2"
    max_position_duration: 14_days
    
  exit_conditions:
    funding_turns_negative: true
    perp_premium_spot: "> 2%"  # Basis risk too high
    hold_time_exceeded: 14_days
    
  reinvestment:
    auto_compound: true
    compound_ratio: 0.5  # 50% reinvest, 50% to tactical
    
  total_portfolio_weight: 15%
```

### 4.3 Delta-Neutral Execution

```python
class FundingArbitrageEngine:
    def __init__(self):
        self.min_funding_rate = 0.0001  # 0.01% per 8h
        self.max_hold_days = 14
        self.max_basis = 0.02  # 2% spot-perp premium
        
    def check_opportunity(self, asset):
        """
        Check if funding arbitrage is attractive
        """
        funding_rate = get_predicted_funding_rate(asset)
        spot_price = get_spot_price(asset)
        perp_price = get_perp_price(asset)
        basis = (perp_price - spot_price) / spot_price
        
        if (funding_rate > self.min_funding_rate and 
            basis < self.max_basis and
            self.funding_trend_positive(asset, periods=2)):
            return True
        return False
        
    def enter_position(self, asset, notional_size):
        """
        Enter delta-neutral position
        """
        # Long spot
        spot_order = place_spot_buy(
            symbol=f"{asset}/USDT",
            notional=notional_size,
            order_type='market'
        )
        
        # Short perp (same notional)
        perp_order = place_perp_sell(
            symbol=f"{asset}-PERP",
            notional=notional_size,
            order_type='market',
            reduce_only=False
        )
        
        # Monitor funding payments
        self.schedule_funding_collection(asset, position_id)
        
    def on_funding_payment(self, asset, amount):
        """
        Handle funding payment (received every 8 hours)
        """
        if amount > 0:
            # Received funding - profitable
            self.profits += amount
            
            # Compound 50%
            compound_amount = amount * 0.5
            self.increase_position_size(asset, compound_amount)
            
            # Transfer 50% to tactical
            tactical_amount = amount * 0.5
            self.transfer_to_subaccount('TACTICAL', tactical_amount)
```

### 4.4 State Machine

```
[MONITORING] → [OPPORTUNITY_DETECTED] → [ENTERING] → [FUNDING_COLLECTING] → [EXITING]
                                                      ↓
                                               [HOLDING_MAX_DAYS]
                                                      ↓
                                               [FUNDING_NEGATIVE]
```

### 4.5 Risk Controls

**Basis Risk Management:**
- If spot-perp premium exceeds 2%: Close position (arbitrage broken)
- Monitor funding rate trend: Exit if turning negative

**Liquidity Constraints:**
- Maximum position: 5% of funding engine capital per asset
- Prioritize BTC/ETH (deepest liquidity)

**Circuit Breakers:**
- If funding negative for 3 consecutive periods: Close ALL positions
- If insurance fund depletion detected: Emergency exit

---

## Chapter 5: Engine 4 - TACTICAL (Extreme Value Deployment)

### 5.1 Purpose & Philosophy

**Mission:** Capitalize on generational buying opportunities during market crashes by deploying dry powder when others panic.

**Core Belief:** Crypto markets exhibit cyclical behavior with 70-85% drawdowns every 4 years. Buying these crashes has historically yielded 300-1000% returns.

**Differentiation:** This engine doesn't trade regularly—it waits patiently for extreme fear, then strikes decisively.

### 5.2 Technical Specifications

```yaml
TACTICAL:
  purpose: extreme_opportunity_deployment
  initial_allocation: 5%  # Of total portfolio
  
  trigger_conditions:
    btc_drawdown_from_ath:
      level_1: -50%  # Deploy 50% of tactical cash
      level_2: -70%  # Deploy remaining 50%
    crypto_fear_greed_index:
      extreme_fear: < 20
    funding_rates:
      deeply_negative: "< -0.05% for 3+ days"
    vix_crypto_equivalent:
      extreme_volatility: "> 80"
      
  deployment_rules:
    primary_asset: BTC  # 80% of deployment
    secondary_asset: ETH  # 20% of deployment
    execution: immediate_market_orders
    
  exit_rules:
    profit_target: 100%  # Double initial deployment
    time_limit: 12_months
    return_to_core: true  # Transfer back to CORE-HODL
```

### 5.3 Opportunity Detection

```python
class TacticalEngine:
    def __init__(self):
        self.btc_ath = 0
        self.deployment_levels = {
            'level_1': {'drawdown': -0.50, 'deploy_pct': 0.50},
            'level_2': {'drawdown': -0.70, 'deploy_pct': 0.50}
        }
        self.deployed = False
        
    def update_ath(self, current_price):
        """Track all-time high"""
        if current_price > self.btc_ath:
            self.btc_ath = current_price
            self.deployed = False  # Reset after new ATH
            
    def check_triggers(self, current_price, fear_greed, funding_rates):
        """
        Check if deployment conditions met
        """
        if self.deployed:
            return None
            
        drawdown = (current_price - self.btc_ath) / self.btc_ath
        
        # Check drawdown levels
        if drawdown <= self.deployment_levels['level_2']['drawdown']:
            return {
                'trigger': 'level_2_crash',
                'deploy_amount': self.get_cash_balance() * 0.50,
                'reason': f'BTC down {drawdown:.1%} from ATH'
            }
        elif drawdown <= self.deployment_levels['level_1']['drawdown']:
            return {
                'trigger': 'level_1_crash',
                'deploy_amount': self.get_cash_balance() * 0.50,
                'reason': f'BTC down {drawdown:.1%} from ATH'
            }
            
        # Check fear index
        if fear_greed < 20:
            return {
                'trigger': 'extreme_fear',
                'deploy_amount': self.get_cash_balance() * 0.25,
                'reason': f'Crypto Fear Index: {fear_greed}'
            }
            
        return None
        
    def deploy_capital(self, amount):
        """
        Deploy tactical cash into BTC/ETH
        """
        btc_amount = amount * 0.80
        eth_amount = amount * 0.20
        
        place_market_buy('BTC/USDT', btc_amount)
        place_market_buy('ETH/USDT', eth_amount)
        
        self.deployed = True
        log_deployment_event(amount, btc_amount, eth_amount)
```

### 5.4 State Machine

```
[ACCUMULATING_CASH] → [MONITORING_MARKETS] → [TRIGGER_DETECTED] → [DEPLOYING]
         ↑                                                               ↓
         └────────────────────[RETURNING_TO_CORE] ← [PROFIT_TARGET_HIT]──┘
```

### 5.5 Risk Controls

**Deployment Discipline:**
- Only deploy on confirmed triggers (not "seems cheap")
- Never deploy more than 50% of tactical cash in single event
- Wait minimum 30 days between deployments

**Exit Discipline:**
- Automatic return to CORE-HODL after 12 months
- Profit-taking at 100% gain (mechanical, not emotional)
- Partial exit if 50% gain reached quickly

**Circuit Breakers:**
- If deployed and price drops additional 30%: Hold (don't panic)
- If exchange issues during deployment: Cancel and retry

---

# PART III: SYSTEM-WIDE ARCHITECTURE

## Chapter 6: The Orchestration Layer

### 6.1 Capital Allocation Engine

The orchestration layer dynamically allocates capital across engines based on market conditions.

**Default Allocation:**
```
CORE-HODL:   60% (base case)
TREND:       20% (base case)
FUNDING:     15% (base case)
TACTICAL:     5% (base case)
```

**Dynamic Adjustments:**

| Market Condition | CORE | TREND | FUNDING | TACTICAL |
|------------------|------|-------|---------|----------|
| Strong Bull (ADX>40) | 50% | 35% | 10% | 5% |
| Bear Market | 70% | 5% | 15% | 10% |
| High Volatility | 55% | 15% | 25% | 5% |
| Pre-Halving (BTC) | 50% | 30% | 15% | 5% |

### 6.2 The Master Controller

```python
class EternalEngine:
    def __init__(self):
        self.engines = {
            'core': CoreHodlEngine(),
            'trend': TrendEngine(),
            'funding': FundingArbitrageEngine(),
            'tactical': TacticalEngine()
        }
        self.risk_manager = RiskManager()
        self.orchestrator = CapitalOrchestrator()
        
    def run_daily_cycle(self):
        """
        Main daily execution loop
        """
        # 1. Update market data
        market_data = self.fetch_market_data()
        
        # 2. Risk check
        risk_status = self.risk_manager.assess_portfolio()
        if risk_status.action != 'NORMAL':
            self.execute_risk_action(risk_status)
            return
            
        # 3. Run each engine
        for name, engine in self.engines.items():
            signals = engine.analyze(market_data)
            for signal in signals:
                if self.risk_manager.approve(signal):
                    self.execute_signal(signal)
                    
        # 4. Orchestrate capital
        rebalancing_trades = self.orchestrator.rebalance_if_needed()
        for trade in rebalancing_trades:
            self.execute_trade(trade)
            
        # 5. Log and report
        self.log_daily_summary()
        
    def execute_signal(self, signal):
        """
        Execute approved trading signal
        """
        try:
            order = self.place_order(signal)
            self.monitor_execution(order)
        except Exception as e:
            self.handle_execution_error(e, signal)
```

### 6.3 Rebalancing Mechanics

**Inter-Engine Rebalancing:**

```
IF TREND engine grows to 30% of portfolio (from 20%):
  → Sell 10% worth of TREND positions
  → Redistribute: 50% to CORE, 30% to FUNDING, 20% to TACTICAL
  → Log as "volatility harvesting event"
```

**Monthly Contribution Integration:**

```
ON monthly_deposit(amount):
  → Identify most underweight engine
  → Deposit flows to that engine first
  → If all engines at target, split by allocation weights
```

## Chapter 7: Data Architecture

### 7.1 Data Sources

**Primary: Bybit API**
- Real-time trades (WebSocket)
- Order book updates (WebSocket)
- OHLCV data (REST)
- Account/position data (REST + WebSocket)
- Funding rate predictions (REST)

**Secondary: External**
- Fear & Greed Index (alternative.me)
- On-chain metrics (Glassnode API)
- Social sentiment (LunarCrush)

### 7.2 Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Bybit API     │────▶│  Data Pipeline   │────▶│  Strategy       │
│   (Raw Data)    │     │  (Cleaning)      │     │  Engines        │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Time-Series DB  │
                        │  (InfluxDB)      │
                        └──────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Analytics       │
                        │  (Dashboards)    │
                        └──────────────────┘
```

### 7.3 State Management

**Persistent State (Database):**
- Open positions
- Historical trades
- Performance metrics
- Configuration parameters

**Ephemeral State (Memory):**
- Current market data
- Pending orders
- Session variables

**Recovery Protocol:**
```
ON system_restart:
  1. Load persistent state from DB
  2. Reconcile with exchange (get current positions)
  3. Identify any discrepancies
  4. Alert operator if manual intervention needed
  5. Resume normal operation
```

## Chapter 8: Execution Layer

### 8.1 Order Management System

**Order Lifecycle:**
```
[CREATED] → [VALIDATED] → [SUBMITTED] → [ACKNOWLEDGED] → [OPEN] → [FILLED]
                                              ↓
                                         [REJECTED]
                                              ↓
                                         [CANCELLED]
```

**Smart Order Routing:**
```python
def place_smart_order(signal):
    """
    Intelligent order execution
    """
    if signal.urgency == 'HIGH':
        # Market order with slippage protection
        return place_market_order(
            symbol=signal.symbol,
            side=signal.side,
            size=signal.size,
            max_slippage=0.5  # 0.5% max
        )
    else:
        # Limit order at maker price
        return place_limit_order(
            symbol=signal.symbol,
            side=signal.side,
            size=signal.size,
            price=calculate_maker_price(signal),
            post_only=True
        )
```

### 8.2 Error Handling & Retry Logic

```python
class ExecutionManager:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = [1, 5, 15]  # Exponential backoff
        
    async def execute_with_retry(self, order):
        for attempt in range(self.max_retries):
            try:
                result = await self.submit_order(order)
                if result.status == 'SUCCESS':
                    return result
            except RateLimitError:
                await sleep(self.retry_delay[attempt])
                continue
            except InsufficientFundsError:
                self.alert_operator("Funding issue")
                raise
            except ExchangeError as e:
                self.log_error(e)
                if attempt < self.max_retries - 1:
                    await sleep(self.retry_delay[attempt])
                    continue
                raise
```

---

## Chapter 9: Communication Interfaces

### 9.1 Internal APIs

**Engine-to-Engine Communication:**
- Event bus for signals
- Shared state for portfolio composition
- Async messaging for non-blocking execution

**Engine-to-RiskManager:**
- Pre-trade validation
- Position limit checks
- Drawdown monitoring

### 9.2 External APIs

**Bybit Integration:**
- V5 Unified API
- WebSocket for real-time data
- REST for order execution
- Rate limit management

**Monitoring Integration:**
- Telegram alerts
- Email reports
- Web dashboard API

---

# PART IV: DEPLOYMENT ARCHITECTURE

## Chapter 10: Infrastructure Design

### 10.1 Cloud Architecture

**Provider:** AWS (or equivalent)
**Regions:** ap-southeast-1 (Singapore) - closest to Bybit servers

**Components:**
```
┌─────────────────────────────────────────────────────────┐
│                    VPC (Isolated Network)               │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  ECS/Fargate │  │   RDS        │  │  ElastiCache │  │
│  │  (Trading    │  │  (PostgreSQL)│  │  (Redis)     │  │
│  │   Engine)    │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│  CloudWatch (Monitoring & Logging)                      │
│  Secrets Manager (API Keys)                             │
│  KMS (Encryption)                                       │
└─────────────────────────────────────────────────────────┘
```

### 10.2 High Availability

**Redundancy:**
- Multi-AZ deployment
- Auto-scaling for load spikes
- Database backups every 6 hours
- Hot standby in secondary region

**Disaster Recovery:**
- RPO (Recovery Point Objective): 1 hour
- RTO (Recovery Time Objective): 4 hours
- Automated failover procedures

### 10.3 Security Architecture

**Defense Layers:**
1. **Network**: VPC isolation, security groups, no public IP
2. **Application**: Input validation, rate limiting, request signing
3. **Data**: Encryption at rest (AES-256) and in transit (TLS 1.3)
4. **Secrets**: AWS Secrets Manager, automatic rotation
5. **Access**: IAM roles, no hardcoded credentials

**API Key Management:**
- Read-only keys for monitoring
- Trade-restricted keys per subaccount
- IP whitelisting
- Regular rotation (quarterly)

---

# Chapter 11: Scalability Considerations

### 11.1 Horizontal Scaling

**Strategy:**
- Stateless engine instances
- Shared database for persistence
- Load balancer for API requests
- Message queue for order flow

**Capacity:**
- Current: Handles $100K-$1M portfolios
- Scaled: Can handle $100M+ without architectural changes

### 11.2 Performance Optimization

**Latency Reduction:**
- Co-located in Singapore (near Bybit)
- WebSocket connections for real-time data
- Connection pooling
- Async I/O throughout

**Throughput:**
- Target: 100 orders/second sustained
- Burst: 1000 orders/second

---

# CONCLUSION

The Eternal Engine's architecture is designed for **decades of autonomous operation**.

**Key Design Decisions:**
1. **Four engines** provide diversification and regime coverage
2. **Subaccount isolation** prevents catastrophic contamination
3. **Layered architecture** ensures failures are contained
4. **Mechanical execution** removes emotion and discretion
5. **Comprehensive monitoring** provides observability

**Technical Specifications:**
- **Languages**: Python (strategies), Go (execution), SQL (data)
- **Infrastructure**: AWS cloud-native
- **Database**: PostgreSQL (relational), InfluxDB (time-series)
- **Monitoring**: CloudWatch, Grafana, PagerDuty
- **Security**: Defense in depth, zero-trust

This is not a trading bot. It is a **capital compounding institution** implemented in code.

---

*Next Document: [04-trading-strategies.md](./04-trading-strategies.md) - Detailed Strategy Specifications & Parameters*
