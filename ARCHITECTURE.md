# THE ETERNAL ENGINE
## Technical Architecture Document

**Version:** 1.0  
**Last Updated:** February 2026  
**Classification:** Technical Reference

---

# Table of Contents

1. [System Overview](#1-system-overview)
2. [The Five-Layer Architecture](#2-the-five-layer-architecture)
3. [The Four Engines](#3-the-four-engines)
4. [Data Flow Architecture](#4-data-flow-architecture)
5. [State Management](#5-state-management)
6. [Risk Management Flow](#6-risk-management-flow)
7. [Bybit Integration](#7-bybit-integration)
8. [Database Schema](#8-database-schema)
9. [Error Handling](#9-error-handling)
10. [Deployment Architecture](#10-deployment-architecture)
11. [Monitoring & Observability](#11-monitoring--observability)

---

# 1. System Overview

## 1.1 Vision

The Eternal Engine is a **multi-layer autonomous trading architecture** designed for decades of unsupervised capital compounding. It combines four distinct trading engines, each optimized for different market regimes, within a unified risk-managed framework.

## 1.2 Core Principles

| Principle | Implementation |
|-----------|----------------|
| **Decentralized Intelligence** | Four independent engines; failure of one doesn't cascade |
| **Defense in Depth** | Risk management at every layer, not just a module |
| **Mechanical Execution** | Zero discretion; all decisions are rule-based and backtested |
| **Evolutionary Adaptation** | Self-monitoring performance with automatic strategy rotation |
| **Observability** | Every decision logged, monitored, and auditable |

## 1.3 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           THE ETERNAL ENGINE                                 │
│                     Autonomous Wealth Generation System                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         PRESENTATION LAYER                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │  │
│  │  │  Dashboard   │  │   Alerts     │  │   Reports    │  │   API     │  │  │
│  │  │  (Grafana)   │  │ (Telegram)   │  │  (Daily)     │  │  (REST)   │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                         │
│                                    │                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          GOVERNANCE LAYER                              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │  │
│  │  │   Circuit    │  │    Policy    │  │   Human      │  │  Config   │  │  │
│  │  │  Breakers    │  │  Enforcement │  │  Override    │  │  Mgmt     │  │  │
│  │  │  (4 Levels)  │  │              │  │              │  │           │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                         │
│                                    │                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        ORCHESTRATION LAYER                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │  │
│  │  │   Capital    │  │  Strategy    │  │ Monthly DCA  │  │ Engine    │  │  │
│  │  │ Allocation   │  │  Rotation    │  │ Integration  │  │ Rotation  │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                         │
│                                    │                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          EXECUTION LAYER                               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │  │
│  │  │    Order     │  │   Position   │  │  Risk Check  │  │  Smart    │  │  │
│  │  │ Management   │  │  Tracking    │  │   Pre-Trade  │  │  Routing  │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                         │
│                                    │                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        INFRASTRUCTURE LAYER                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │  │
│  │  │   Bybit      │  │   WebSocket  │  │  State Mgmt  │  │  Redis    │  │  │
│  │  │   API V5     │  │  (Real-time) │  │  (SQL/NoSQL) │  │  Cache    │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 2. The Five-Layer Architecture

## 2.1 Layer 1: Infrastructure

**Purpose:** Exchange integration, data feeds, state persistence

**Components:**
- **Bybit API V5 Integration** (REST + WebSocket)
- **Market Data Pipeline** (OHLCV, orderbook, trades)
- **State Management** (PostgreSQL for persistence, Redis for cache)
- **Connection Management** (auto-reconnect, heartbeat monitoring)

```python
# Infrastructure Layer: BybitClient
class BybitClient:
    """
    Handles all exchange communication:
    - Market data fetching (REST)
    - Real-time streaming (WebSocket)
    - Order execution with retry logic
    - Rate limit management
    """
    async def initialize()      # Connect and authenticate
    async def get_balance()     # Fetch portfolio state
    async def fetch_ohlcv()     # Historical data
    async def create_order()    # Execute trades
```

## 2.2 Layer 2: Execution

**Purpose:** Order management, position tracking, risk controls

**Components:**
- **Order Management System** (lifecycle: Created → Validated → Submitted → Acknowledged → Open → Filled)
- **Position Tracker** (realized/unrealized PnL, average entry)
- **Pre-Trade Risk Check** (position limits, exposure checks)
- **Smart Order Router** (market vs. limit, slippage protection)

```python
# Execution Layer: TradingEngine
class TradingEngine:
    """
    Orchestrates trading operations:
    - Runs strategy analysis loop
    - Processes signals through risk manager
    - Executes orders via exchange client
    - Tracks positions and portfolio
    """
    async def _run_analysis()       # Generate signals from strategies
    async def _process_signal()     # Risk check + execution
    async def _execute_buy/sell()   # Order creation
    async def _on_order_filled()    # Position updates
```

## 2.3 Layer 3: Orchestration

**Purpose:** Capital allocation, rebalancing, strategy rotation

**Components:**
- **Capital Allocation Engine** (dynamic weight adjustment)
- **Rebalancing Engine** (threshold-based with calendar fallback)
- **Strategy Rotation** (performance-based activation/deactivation)
- **Monthly DCA Integration** (automatic contribution allocation)

```python
# Orchestration Logic
class CapitalOrchestrator:
    """
    Manages capital flows:
    - Default: CORE 60%, TREND 20%, FUNDING 15%, TACTICAL 5%
    - Dynamic adjustments based on market regime
    - Inter-engine rebalancing when allocations drift
    """
    def rebalance_if_needed()
    def allocate_monthly_contribution(amount)
    def rotate_strategies(performance_data)
```

## 2.4 Layer 4: Governance

**Purpose:** Circuit breakers, policy enforcement, human override

**Components:**
- **Four-Level Circuit Breaker System**
  - Level 1 (10% DD): Reduce sizes 25%, widen stops
  - Level 2 (15% DD): Reduce sizes 50%, pause entries
  - Level 3 (20% DD): Close directional, move to stables
  - Level 4 (25% DD): Full liquidation, indefinite halt
- **Policy Enforcement** (hard limits validation)
- **Human Override** (emergency controls)

```python
# Circuit Breaker Implementation
class CircuitBreaker:
    def check_drawdown(portfolio_value):
        dd = calculate_drawdown(portfolio_value)
        if dd >= 0.25: return Level4Emergency().execute()
        if dd >= 0.20: return Level3Alert().execute()
        if dd >= 0.15: return Level2Warning().execute()
        if dd >= 0.10: return Level1Caution().execute()
```

## 2.5 Layer 5: Presentation

**Purpose:** Dashboards, alerts, reporting, API access

**Components:**
- **Executive Dashboard** (portfolio value, performance, allocation)
- **Operational Dashboard** (risk metrics, positions, activity)
- **Technical Dashboard** (system health, latency, errors)
- **Alert System** (P0-P3 severity routing)
- **Reporting** (daily, weekly, monthly, quarterly)

---

# 3. The Four Engines

## 3.1 Engine 1: CORE-HODL (60% Allocation)

**Mission:** Long-term wealth compounding through systematic BTC/ETH accumulation

**Specifications:**
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
    order_type: limit_maker  # Minimize fees
    
  yield_optimization:
    eth_staking: enabled
    staking_platform: bybit_earn
    minimum_yield_threshold: 2.0%
```

**State Machine:**
```
[INITIALIZING] → [ACCUMULATING] → [REBALANCING] → [EARN_OPTIMIZING] → [ACCUMULATING]
      ↑                                                              ↓
      └──────────────────────────────────────────────────────────────┘
```

## 3.2 Engine 2: TREND (20% Allocation)

**Mission:** Capture directional trends with crisis alpha generation

**Specifications:**
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
```

**State Machine:**
```
[SCANNING] → [SIGNAL_DETECTED] → [ENTERING] → [IN_POSITION] → [EXITING] → [SCANNING]
                ↓                      ↓              ↓
           [NO_TRADE]           [STOPPED_OUT]  [TRAILING_STOP]
```

## 3.3 Engine 3: FUNDING (15% Allocation)

**Mission:** Market-neutral yield through funding rate arbitrage

**Specifications:**
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
    predicted_funding_rate: "> 0.01% per 8h"
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

**Delta-Neutral Construction:**
```
Position Structure:
    SPOT:   +1.0 BTC (Long spot)
    FUTURE: -1.0 BTC (Short perp)
    
Net Delta: 0 (Price movements cancel)
Funding Income: |Funding_Rate| × Notional every 8h
```

## 3.4 Engine 4: TACTICAL (5% Allocation)

**Mission:** Capitalize on generational buying opportunities during crashes

**Specifications:**
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
      
  deployment_rules:
    primary_asset: BTC  # 80% of deployment
    secondary_asset: ETH  # 20% of deployment
    execution: immediate_market_orders
    
  exit_rules:
    profit_target: 100%  # Double initial deployment
    time_limit: 12_months
    return_to_core: true  # Transfer back to CORE-HODL
```

**State Machine:**
```
[ACCUMULATING_CASH] → [MONITORING_MARKETS] → [TRIGGER_DETECTED] → [DEPLOYING]
         ↑                                                               ↓
         └────────────────────[RETURNING_TO_CORE] ← [PROFIT_TARGET_HIT]──┘
```

---

# 4. Data Flow Architecture

## 4.1 Main Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐ │
│   │  Market Data │───▶│   Analysis   │───▶│  Risk Check  │───▶│   Order  │ │
│   │   Sources    │    │   Engines    │    │              │    │          │ │
│   └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘ │
│          │                   │                   │                 │        │
│          ▼                   ▼                   ▼                 ▼        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         DATA STORAGE                                 │  │
│   │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │  │
│   │  │  Orders    │  │ Positions  │  │   Trades   │  │   Market   │    │  │
│   │  │  (Active)  │  │  (Open)    │  │ (History)  │  │   Data     │    │  │
│   │  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 4.2 Detailed Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DETAILED DATA FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐                                                         │
│  │   Bybit API     │                                                         │
│  │   (REST/WS)     │                                                         │
│  └────────┬────────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      DATA NORMALIZATION LAYER                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ OHLCV Data  │  │ Orderbook   │  │   Trades    │  │  Funding    │  │   │
│  │  │  (1m-1D)    │  │  (L2/L3)    │  │  (Real-time)│  │   Rates     │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      STRATEGY PROCESSING LAYER                        │   │
│  │                                                                       │   │
│  │   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐       │   │
│  │   │  CORE-HODL    │    │    TREND      │    │   FUNDING     │       │   │
│  │   │  • Rebalance  │    │  • 200DMA     │    │  • Rate Mon.  │       │   │
│  │   │  • DCA Check  │    │  • ADX Filter │    │  • Basis Arb  │       │   │
│  │   └───────┬───────┘    └───────┬───────┘    └───────┬───────┘       │   │
│  │           │                    │                    │               │   │
│  │   ┌───────▼────────────────────▼────────────────────▼───────┐       │   │
│  │   │              SIGNAL AGGREGATION BUS                      │       │   │
│  │   │   [BUY BTC] [SELL ETH] [REBALANCE] [CLOSE POSITION]     │       │   │
│  │   └───────────────────────┬─────────────────────────────────┘       │   │
│  │                           │                                          │   │
│  │                           ▼                                          │   │
│  │   ┌───────────────────────────────────────────────────────────┐     │   │
│  │   │                   RISK MANAGER                             │     │   │
│  │   │  ┌────────────┐ ┌────────────┐ ┌────────────┐            │     │   │
│  │   │  │  Position  │ │   Daily    │ │  Circuit   │            │     │   │
│  │   │  │   Limits   │ │   Loss     │ │  Breaker   │            │     │   │
│  │   │  └────────────┘ └────────────┘ └────────────┘            │     │   │
│  │   └────────────────────────┬────────────────────────────────┘     │   │
│  │                            │                                       │   │
│  │                    ┌───────┴───────┐                               │   │
│  │                    ▼               ▼                               │   │
│  │            ┌──────────┐    ┌──────────┐                           │   │
│  │            │ APPROVED │    │ REJECTED │                           │   │
│  │            └────┬─────┘    └──────────┘                           │   │
│  │                 │                                                  │   │
│  │                 ▼                                                  │   │
│  │   ┌──────────────────────────────────────────────────────────┐    │   │
│  │   │                 EXECUTION ENGINE                          │    │   │
│  │   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │    │   │
│  │   │  │ Position │ │   Stop   │ │   Take   │ │  Order   │    │    │   │
│  │   │  │  Sizing  │ │   Loss   │ │  Profit  │ │  Type    │    │    │   │
│  │   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │    │   │
│  │   └────────────────────────┬─────────────────────────────────┘    │   │
│  │                            │                                       │   │
│  │                            ▼                                       │   │
│  │   ┌──────────────────────────────────────────────────────────┐    │   │
│  │   │                  BYBIT API V5                             │    │   │
│  │   │              (Order Submission)                           │    │   │
│  │   └────────────────────────┬─────────────────────────────────┘    │   │
│  │                            │                                       │   │
│  │                            ▼                                       │   │
│  │   ┌──────────────────────────────────────────────────────────┐    │   │
│  │   │               DATABASE PERSISTENCE                        │    │   │
│  │   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │    │   │
│  │   │  │  Orders  │ │ Positions│ │  Trades  │ │  Events  │    │    │   │
│  │   │  │  (PgSQL) │ │  (PgSQL) │ │  (PgSQL) │ │  (Redis) │    │    │   │
│  │   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │    │   │
│  │   └──────────────────────────────────────────────────────────┘    │   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 4.3 Data Flow Sequence

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Market  │────▶│ Strategy │────▶│   Risk   │────▶│ Execution│────▶│ Database │
│   Data   │     │ Analysis │     │  Check   │     │          │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
      │               │               │               │               │
      │ 1. Fetch      │ 2. Generate   │ 3. Validate   │ 4. Submit     │ 5. Persist
      │    OHLCV      │    Signals    │    Limits     │    Order      │    State
      │               │               │               │               │
      ▼               ▼               ▼               ▼               ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ WebSocket│     │ Technical│     │ Position │     │ Bybit    │     │ PostgreSQL│
│   Feed   │     │Indicators│     │  Limits  │     │  API V5  │     │ + Redis  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
```

---

# 5. State Management

## 5.1 State Types

| State Type | Storage | Persistence | Recovery |
|------------|---------|-------------|----------|
| **Portfolio** | PostgreSQL | Permanent | On restart |
| **Positions** | PostgreSQL + Memory | Permanent | Reconcile with exchange |
| **Orders** | PostgreSQL | Permanent | Query exchange status |
| **Market Data** | Redis | Ephemeral (1h) | Refetch from API |
| **Engine States** | PostgreSQL | Permanent | Resume from checkpoint |

## 5.2 State Recovery Protocol

```
ON system_restart:
  1. Load persistent state from PostgreSQL
  2. Reconcile with Bybit exchange (get current positions)
  3. Identify any discrepancies
  4. Alert operator if manual intervention needed
  5. Resume normal operation
```

## 5.3 State Synchronization

```python
class StateManager:
    """
    Ensures consistency between internal state and exchange reality.
    """
    async def reconcile_state(self):
        # 1. Load from database
        db_positions = await self.database.get_open_positions()
        
        # 2. Fetch from exchange
        exchange_positions = await self.exchange.get_positions()
        
        # 3. Compare and resolve
        for pos in db_positions:
            if pos.symbol not in exchange_positions:
                # Position closed externally
                await self.handle_external_close(pos)
        
        for symbol, pos in exchange_positions.items():
            if symbol not in db_positions:
                # Position opened externally
                await self.handle_external_open(pos)
```

---

# 6. Risk Management Flow

## 6.1 Risk Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RISK MANAGEMENT FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐                                                               │
│  │  SIGNAL  │                                                               │
│  │Generated │                                                               │
│  └────┬─────┘                                                               │
│       │                                                                     │
│       ▼                                                                     │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      PRE-TRADE RISK CHECK                         │    │
│  │                                                                    │    │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌──────────┐  │    │
│  │  │ 1. Circuit │   │ 2. Position│   │ 3. Daily   │   │ 4. Conf. │  │    │
│  │  │  Breaker   │   │   Limits   │   │   Loss     │   │  idence  │  │    │
│  │  │   Check    │──▶│   Check    │──▶│   Check    │──▶│  Check   │  │    │
│  │  └────────────┘   └────────────┘   └────────────┘   └──────────┘  │    │
│  │         │                │                │               │        │    │
│  │         ▼                ▼                ▼               ▼        │    │
│  │    [PASSED?]         [PASSED?]         [PASSED?]      [PASSED?]    │    │
│  │         │                │                │               │        │    │
│  │         └────────────────┴────────────────┴───────────────┘        │    │
│  │                              │                                     │    │
│  │                              ▼                                     │    │
│  │                    ┌─────────────────┐                             │    │
│  │                    │ ALL CHECKS PASS │                             │    │
│  │                    └────────┬────────┘                             │    │
│  │                             │                                      │    │
│  └─────────────────────────────┼──────────────────────────────────────┘    │
│                                │                                            │
│                                ▼                                            │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    POSITION SIZING ENGINE                         │    │
│  │                                                                    │    │
│  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │    │
│  │   │ Kelly Criterion│   │  Risk-Based  │   │   Maximum    │       │    │
│  │   │  (1/8 Kelly)   │   │  (1% risk)   │   │   Position   │       │    │
│  │   └───────┬────────┘    └───────┬────────┘    └───────┬────────┘       │    │
│  │           │                     │                     │               │    │
│  │           └─────────────────────┼─────────────────────┘               │    │
│  │                                 │                                     │    │
│  │                                 ▼                                     │    │
│  │                    ┌─────────────────────┐                           │    │
│  │                    │  FINAL POSITION SIZE │                           │    │
│  │                    └──────────┬──────────┘                           │    │
│  │                               │                                       │    │
│  └───────────────────────────────┼───────────────────────────────────────┘    │
│                                  │                                            │
│                                  ▼                                            │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                        EXECUTION                                   │    │
│  │                                                                    │    │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐                    │    │
│  │   │  Order   │    │   Stop   │    │   Take   │                    │    │
│  │   │  Submit  │    │   Loss   │    │  Profit  │                    │    │
│  │   └──────────┘    └──────────┘    └──────────┘                    │    │
│  │                                                                    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 6.2 Risk Check Implementation

```python
class RiskManager:
    """
    Central risk management system with hard limits.
    """
    def check_signal(self, signal, portfolio, positions) -> RiskCheck:
        # Rule 1: Emergency stop check
        if self.emergency_stop:
            return RiskCheck(passed=False, reason="Emergency stop active")
        
        # Rule 2: Daily loss limit
        daily_loss = self._calculate_daily_loss_pct(portfolio)
        if daily_loss >= MAX_DAILY_LOSS_PCT:
            self._trigger_emergency_stop()
            return RiskCheck(passed=False, reason="Daily loss limit reached")
        
        # Rule 3: Weekly loss limit
        weekly_loss = self._calculate_weekly_loss_pct(portfolio)
        if weekly_loss >= MAX_WEEKLY_LOSS_PCT:
            return RiskCheck(passed=False, reason="Weekly loss limit reached")
        
        # Rule 4: Max concurrent positions
        if len(positions) >= MAX_CONCURRENT_POSITIONS:
            return RiskCheck(passed=False, reason="Max positions reached")
        
        # Rule 5: Already have position in symbol
        if signal.symbol in positions:
            return RiskCheck(passed=False, reason="Position already exists")
        
        # Rule 6: Signal confidence
        if signal.confidence < MIN_CONFIDENCE:
            return RiskCheck(passed=False, reason="Low confidence")
        
        return RiskCheck(passed=True)
```

## 6.3 Position Sizing Formula

```python
def calculate_position_size(portfolio, entry_price, stop_price):
    """
    Kelly Criterion inspired position sizing with fractional Kelly.
    """
    # 1/8 Kelly calculation
    kelly_fraction = 0.125
    p = win_rate  # Probability of win
    b = win_loss_ratio  # Average win / average loss
    q = 1 - p
    
    kelly = (b * p - q) / b
    adjusted_kelly = kelly * kelly_fraction
    
    # Risk-based sizing (1% max risk per trade)
    risk_amount = portfolio.total_balance * 0.01
    stop_distance = abs(entry_price - stop_price)
    risk_based_size = risk_amount / stop_distance
    
    # Kelly-based sizing
    kelly_size = portfolio.total_balance * adjusted_kelly / entry_price
    
    # Take the smaller of the two
    position_size = min(risk_based_size, kelly_size)
    
    # Apply maximum position limit
    max_position = portfolio.total_balance * MAX_POSITION_PCT / entry_price
    return min(position_size, max_position)
```

---

# 7. Bybit Integration

## 7.1 API Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BYBIT INTEGRATION LAYER                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        API V5 UNIFIED INTERFACE                        │  │
│  │                                                                        │  │
│  │   REST API                    WebSocket Public           WebSocket    │  │
│  │   (Request/Response)          (Market Data)             Private       │  │
│  │                                                                        │  │
│  │  ┌──────────────┐            ┌──────────────┐        ┌──────────────┐ │  │
│  │  │ Market Data  │            │ Orderbook    │        │ Order        │ │  │
│  │  │ • Klines     │            │   Streams    │        │ Updates      │ │  │
│  │  │ • Tickers    │            │ • Ticker     │        │ • Position   │ │  │
│  │  │ • Orderbook  │            │ • Trades     │        │ • Wallet     │ │  │
│  │  │              │            │ • Liquidation│        │ • Execution  │ │  │
│  │  ├──────────────┤            └──────────────┘        └──────────────┘ │  │
│  │  │ Trading      │                                                      │  │
│  │  │ • Orders     │            Authentication: HMAC SHA256               │  │
│  │  │ • Positions  │            Rate Limits: 120 req/sec (private)        │  │
│  │  │ • Account    │            Regions: Singapore (closest to Bybit)     │  │
│  │  └──────────────┘                                                      │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 7.2 Unified Trading Account (UTA)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      UNIFIED TRADING ACCOUNT (UTA)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     SHARED MARGIN & COLLATERAL                         │  │
│  │                                                                        │  │
│  │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │   │   Spot     │  │  Linear    │  │  Inverse   │  │  Options   │     │  │
│  │   │ (BTC/ETH)  │  │ (USDT-M)   │  │ (Coin-M)   │  │            │     │  │
│  │   └────────────┘  └────────────┘  └────────────┘  └────────────┘     │  │
│  │                                                                        │  │
│  │   All markets share unified margin and cross-collateral               │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      SUBACCOUNT ARCHITECTURE                           │  │
│  │                                                                        │  │
│  │   Master Account                                                       │  │
│  │   └── Subaccount: CORE-HODL (60%)     [Spot Only]                     │  │
│  │   └── Subaccount: TREND (20%)         [Perps, 2x max]                 │  │
│  │   └── Subaccount: FUNDING (15%)       [Spot + Perps]                  │  │
│  │   └── Subaccount: TACTICAL (5%)       [Spot Only]                     │  │
│  │                                                                        │  │
│  │   Isolation prevents cross-contamination between engines              │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 7.3 Key Integration Points

| Component | API Endpoint | Purpose |
|-----------|--------------|---------|
| Market Data | `/v5/market/kline` | OHLCV data for analysis |
| Orderbook | `/v5/market/orderbook` | Liquidity assessment |
| Balance | `/v5/account/wallet-balance` | Portfolio tracking |
| Order Create | `/v5/order/create` | Trade execution |
| Positions | `/v5/position/list` | Position monitoring |
| Funding | `/v5/market/funding/history` | Funding rate arbitrage |

---

# 8. Database Schema

## 8.1 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE SCHEMA                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         ┌──────────────┐ │
│  │      orders      │         │    positions     │         │    trades    │ │
│  ├──────────────────┤         ├──────────────────┤         ├──────────────┤ │
│  │ PK id            │         │ PK id            │         │ PK id        │ │
│  │    symbol        │────────▶│    symbol (UQ)   │◀────────│    symbol    │ │
│  │    side          │         │    side          │         │    side      │ │
│  │    order_type    │         │    entry_price   │         │    entry_px  │ │
│  │    amount        │         │    amount        │         │    exit_px   │ │
│  │    price         │         │    opened_at     │         │    entry_time│ │
│  │    status        │         │    closed_at     │         │    exit_time │ │
│  │    filled_amount │         │    unrealized_pnl│         │    realized  │ │
│  │    avg_price     │         │    realized_pnl  │         │    _pnl      │ │
│  │    stop_loss_px  │         │    stop_loss_px  │         │    total_fee │ │
│  │    take_profit_px│         │    take_profit_px│         │    strategy  │ │
│  │    created_at    │         │    metadata_json │         │    close_reason││
│  │    metadata_json │         └──────────────────┘         └──────────────┘ │
│  └──────────────────┘                                                       │
│           │                                                                  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐         ┌──────────────┐ │
│  │   daily_stats    │         │  engine_states   │         │    alerts    │ │
│  ├──────────────────┤         ├──────────────────┤         ├──────────────┤ │
│  │ PK date          │         │ PK engine_name   │         │ PK id        │ │
│  │    starting_bal  │         │    state         │         │    timestamp │ │
│  │    ending_bal    │         │    allocation_pct│         │    severity  │ │
│  │    total_pnl     │         │    performance   │         │    type      │ │
│  │    trade_count   │         │    last_updated  │         │    message   │ │
│  │    win_count     │         │    metadata_json │         │    acked     │ │
│  │    loss_count    │         └──────────────────┘         └──────────────┘ │
│  └──────────────────┘                                                       │
│                                                                              │
│  LEGEND: PK = Primary Key, UQ = Unique, FK = Foreign Key                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 8.2 Table Definitions

### orders
```sql
CREATE TABLE orders (
    id VARCHAR(36) PRIMARY KEY,
    exchange_order_id VARCHAR(100),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'buy' or 'sell'
    order_type VARCHAR(20) NOT NULL,  -- 'market', 'limit', etc.
    amount DECIMAL(36, 18) NOT NULL,
    price DECIMAL(36, 18),
    status VARCHAR(20) NOT NULL,  -- 'pending', 'filled', 'cancelled'
    filled_amount DECIMAL(36, 18) DEFAULT 0,
    average_price DECIMAL(36, 18),
    stop_loss_price DECIMAL(36, 18),
    take_profit_price DECIMAL(36, 18),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    filled_at TIMESTAMP,
    metadata_json JSON DEFAULT '{}'
);
```

### positions
```sql
CREATE TABLE positions (
    id VARCHAR(36) PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'long', 'short', 'none'
    entry_price DECIMAL(36, 18) NOT NULL,
    amount DECIMAL(36, 18) NOT NULL,
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    unrealized_pnl DECIMAL(36, 18) DEFAULT 0,
    realized_pnl DECIMAL(36, 18) DEFAULT 0,
    stop_loss_price DECIMAL(36, 18),
    take_profit_price DECIMAL(36, 18),
    metadata_json JSON DEFAULT '{}'
);
```

### trades
```sql
CREATE TABLE trades (
    id VARCHAR(36) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    amount DECIMAL(36, 18) NOT NULL,
    entry_price DECIMAL(36, 18) NOT NULL,
    exit_price DECIMAL(36, 18) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    realized_pnl DECIMAL(36, 18) NOT NULL,
    realized_pnl_pct DECIMAL(36, 18) NOT NULL,
    entry_fee DECIMAL(36, 18) DEFAULT 0,
    exit_fee DECIMAL(36, 18) DEFAULT 0,
    total_fee DECIMAL(36, 18) DEFAULT 0,
    strategy_name VARCHAR(50),
    close_reason VARCHAR(50)  -- 'stop_loss', 'take_profit', 'signal', 'manual'
);
```

## 8.3 Redis Cache Schema

```
# Market Data (TTL: 1 hour)
market:ohlcv:{symbol}:{timeframe}  →  JSON array of candles
market:orderbook:{symbol}          →  JSON {bids: [], asks: []}
market:ticker:{symbol}             →  JSON {last, bid, ask, volume}

# Session Data (TTL: 24 hours)
session:portfolio                  →  Portfolio snapshot
session:positions                  →  Open positions list

# Rate Limiting (TTL: sliding window)
ratelimit:orders:{api_key}         →  Counter for order endpoint
ratelimit:general:{api_key}        →  Counter for general endpoints
```

---

# 9. Error Handling

## 9.1 Error Classification

| Error Category | Examples | Response Strategy |
|----------------|----------|-------------------|
| **Exchange Errors** | Rate limit, invalid params, insufficient funds | Exponential backoff, alert operator |
| **Network Errors** | Timeout, connection reset, DNS failure | Auto-retry with circuit breaker |
| **Risk Limit Hits** | Position too large, daily loss exceeded | Reject signal, emergency stop |
| **Data Errors** | Stale prices, malformed response | Fallback to backup source |
| **System Errors** | Database failure, out of memory | Graceful degradation |

## 9.2 Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ERROR HANDLING ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         ERROR DETECTION                                │  │
│  │                                                                        │  │
│  │   Exchange Error    Network Error    Risk Error    System Error       │  │
│  │        │                 │               │              │             │  │
│  │        └─────────────────┴───────────────┴──────────────┘             │  │
│  │                          │                                           │  │
│  └──────────────────────────┼───────────────────────────────────────────┘  │
│                             │                                              │
│                             ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      ERROR CLASSIFICATION                              │  │
│  │                                                                        │  │
│  │   Retriable? ──YES──▶ Retry Logic (exponential backoff)               │  │
│  │        │                                                              │  │
│  │       NO                                                               │  │
│  │        │                                                              │  │
│  │        ▼                                                              │  │
│  │   Critical? ───YES──▶ Emergency Stop + Alert                          │  │
│  │        │                                                              │  │
│  │       NO                                                               │  │
│  │        │                                                              │  │
│  │        ▼                                                              │  │
│  │   Log & Continue (degraded mode)                                      │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 9.3 Retry Logic Implementation

```python
class ExecutionManager:
    """
    Handles order execution with retry logic.
    """
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
                await asyncio.sleep(self.retry_delay[attempt])
                continue
            except InsufficientFundsError:
                self.alert_operator("Funding issue")
                raise
            except ExchangeError as e:
                self.log_error(e)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay[attempt])
                    continue
                raise
```

---

# 10. Deployment Architecture

## 10.1 Container Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DEPLOYMENT ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    KUBERNETES CLUSTER (EKS/GKE)                        │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────┐     │  │
│  │  │                      Trading Pod                             │     │  │
│  │  │  ┌─────────────────┐  ┌─────────────────┐                   │     │  │
│  │  │  │  Trading Engine │  │  Risk Manager   │                   │     │  │
│  │  │  │   Container     │  │   Container     │                   │     │  │
│  │  │  └─────────────────┘  └─────────────────┘                   │     │  │
│  │  │  ┌─────────────────┐  ┌─────────────────┐                   │     │  │
│  │  │  │  Strategy       │  │  Bybit Client   │                   │     │  │
│  │  │  │   Containers    │  │   Container     │                   │     │  │
│  │  │  └─────────────────┘  └─────────────────┘                   │     │  │
│  │  └─────────────────────────────────────────────────────────────┘     │  │
│  │                                                                        │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │  PostgreSQL     │  │  Redis          │  │  Grafana        │       │  │
│  │  │  StatefulSet    │  │  Cache          │  │  Dashboard      │       │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        AWS SERVICES                                    │  │
│  │                                                                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  │
│  │  │ CloudWatch   │  │ Secrets      │  │   KMS        │              │  │
│  │  │ (Logs/Metrics)│  │   Manager    │  │ (Encryption) │              │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 10.2 High Availability Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HIGH AVAILABILITY SETUP                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     MULTI-AZ DEPLOYMENT                                │  │
│  │                                                                        │  │
│  │   Availability Zone 1 (ap-southeast-1a)                               │  │
│  │   ├── Trading Pod (Primary)                                           │  │
│  │   └── PostgreSQL (Primary)                                            │  │
│  │                                                                        │  │
│  │   Availability Zone 2 (ap-southeast-1b)                               │  │
│  │   ├── Trading Pod (Standby)                                           │  │
│  │   └── PostgreSQL (Replica)                                            │  │
│  │                                                                        │  │
│  │   Availability Zone 3 (ap-southeast-1c)                               │  │
│  │   ├── Trading Pod (Standby)                                           │  │
│  │   └── PostgreSQL (Replica)                                            │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Recovery Objectives:                                                       │
│  • RPO (Recovery Point Objective): 1 hour                                   │
│  • RTO (Recovery Time Objective): 4 hours                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 10.3 Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SECURITY LAYERS                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Layer 5: Application                                                       │
│  ├── Input validation                                                       │
│  ├── Rate limiting                                                          │
│  └── Request signing (HMAC)                                                 │
│                                                                              │
│  Layer 4: Network                                                           │
│  ├── VPC isolation                                                          │
│  ├── Security groups                                                        │
│  └── No public IP (private subnets only)                                    │
│                                                                              │
│  Layer 3: Data                                                              │
│  ├── Encryption at rest (AES-256)                                           │
│  ├── Encryption in transit (TLS 1.3)                                        │
│  └── Database encryption                                                    │
│                                                                              │
│  Layer 2: Secrets                                                           │
│  ├── AWS Secrets Manager                                                    │
│  ├── Automatic rotation (quarterly)                                         │
│  └── No hardcoded credentials                                               │
│                                                                              │
│  Layer 1: Access                                                            │
│  ├── IAM roles (no root access)                                             │
│  ├── IP whitelisting                                                        │
│  └── Multi-factor authentication                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 11. Monitoring & Observability

## 11.1 The Three Pillars

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     OBSERVABILITY PILLARS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │    METRICS      │  │     LOGS        │  │    TRACES       │             │
│  │   (The Vitals)  │  │  (The Narrative)│  │  (The Journey)  │             │
│  │                 │  │                 │  │                 │             │
│  │ • Portfolio     │  │ • Trade         │  │ • Signal        │             │
│  │   Value         │  │   execution     │  │   detection     │             │
│  │ • P&L           │  │ • Risk checks   │  │ • Risk          │             │
│  │ • Sharpe Ratio  │  │ • Errors        │  │   validation    │             │
│  │ • Latency       │  │ • Decisions     │  │ • Order         │             │
│  │ • Throughput    │  │ • State changes │  │   execution     │             │
│  │                 │  │                 │  │ • DB persist    │             │
│  │  Prometheus     │  │  Structured     │  │  OpenTelemetry  │             │
│  │  + Grafana      │  │  (JSON)         │  │  + Jaeger       │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 11.2 Alert Severity Levels

| Level | Name | Response Time | Channels | Examples |
|-------|------|---------------|----------|----------|
| **P0** | CRITICAL | Immediate | SMS, Phone, Email, Telegram | Circuit breaker triggered, major loss |
| **P1** | HIGH | 15 minutes | Email, Telegram | API errors, elevated risk |
| **P2** | MEDIUM | 1 hour | Email, Dashboard | Performance degradation |
| **P3** | LOW | 4 hours | Dashboard, Daily report | Minor anomalies |

## 11.3 Key Metrics Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    KEY METRICS OVERVIEW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PORTFOLIO METRICS                    RISK METRICS                          │
│  ┌─────────────────────────────┐     ┌─────────────────────────────┐       │
│  │ Total Value: $127,450      │     │ Heat: 2.1% 🟢               │       │
│  │ 24h Change: +2.3%          │     │ VaR(95%): $1,247            │       │
│  │ YTD Return: +7.8%          │     │ Correlation: 0.68           │       │
│  │ Drawdown: -8.4%            │     │ Leverage: 1.2x              │       │
│  │ Sharpe: 1.47               │     │ Circuit: GREEN              │       │
│  └─────────────────────────────┘     └─────────────────────────────┘       │
│                                                                              │
│  SYSTEM METRICS                       ENGINE PERFORMANCE                    │
│  ┌─────────────────────────────┐     ┌─────────────────────────────┐       │
│  │ Uptime: 99.9%              │     │ CORE:   +1.8% (60%)         │       │
│  │ API Latency: 45ms          │     │ TREND:  +4.2% (20%)         │       │
│  │ Error Rate: 0.01%          │     │ FUND:   +0.03% (15%)        │       │
│  │ Orders/sec: 2.3            │     │ TACT:   0.0% (5%)           │       │
│  │ Trades/day: 12             │     │                             │       │
│  └─────────────────────────────┘     └─────────────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 11.4 Reporting Schedule

| Report | Frequency | Distribution | Format |
|--------|-----------|--------------|--------|
| Daily Summary | 00:00 UTC | All stakeholders | Email + Telegram |
| Weekly Report | Sundays | Investors, Management | PDF + Email |
| Monthly Report | 1st of month | Board, Major investors | Comprehensive PDF |
| Quarterly Report | Q1, Q2, Q3, Q4 | All investors, Public | Investor-grade (20-30 pages) |

---

# Appendix A: File Structure

```
BybitTrader/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── ARCHITECTURE.md           # This document
│
├── config/
│   └── strategies.yaml       # Strategy configurations
│
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py         # Configuration management
│   │   ├── engine.py         # Main trading engine
│   │   └── models.py         # Data models
│   │
│   ├── exchange/
│   │   ├── __init__.py
│   │   └── bybit_client.py   # Bybit API integration
│   │
│   ├── risk/
│   │   ├── __init__.py
│   │   └── risk_manager.py   # Risk management system
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   └── database.py       # Database operations
│   │
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py           # Base strategy class
│   │   ├── dca_strategy.py   # DCA implementation
│   │   └── grid_strategy.py  # Grid trading implementation
│   │
│   └── utils/
│       ├── __init__.py
│       ├── backtest.py       # Backtesting utilities
│       └── logging_config.py # Logging configuration
│
├── tests/                    # Test suite
├── data/                     # Data storage
├── logs/                     # Log files
└── docs/                     # Documentation
    ├── 01-executive-summary/
    ├── 02-investment-thesis/
    ├── 03-system-architecture/
    ├── 04-trading-strategies/
    ├── 05-risk-management/
    ├── 06-infrastructure/
    ├── 07-monitoring-governance/
    ├── 08-financial-projections/
    ├── 09-implementation/
    └── 10-appendices/
```

---

# Appendix B: Configuration Reference

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BYBIT_API_KEY` | Yes | - | Bybit API key |
| `BYBIT_API_SECRET` | Yes | - | Bybit API secret |
| `BYBIT_TESTNET` | No | `true` | Use testnet |
| `TRADING_MODE` | No | `paper` | `paper` or `live` |
| `DATABASE_URL` | No | `sqlite:///./trading_bot.db` | Database connection |
| `MAX_POSITION_PCT` | No | `5.0` | Max position size % |
| `MAX_DAILY_LOSS_PCT` | No | `2.0` | Daily loss limit % |
| `MAX_WEEKLY_LOSS_PCT` | No | `5.0` | Weekly loss limit % |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram notifications |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

**Document End**

*For questions or clarifications, refer to the complete documentation in the `docs/` folder.*
