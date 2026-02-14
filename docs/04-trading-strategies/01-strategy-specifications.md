# Cryptocurrency Trading Strategies - Technical Documentation

## Table of Contents
1. [Trend Following Strategy](#1-trend-following-strategy)
2. [Funding Rate Arbitrage](#2-funding-rate-arbitrage)
3. [Grid Trading](#3-grid-trading)
4. [DCA/Rebalancing Strategy](#4-dcarebalancing-strategy)
5. [Tactical/Crisis Deployment](#5-tacticalcrisis-deployment)
6. [Risk Management Framework](#6-risk-management-framework)
7. [Implementation Reference](#7-implementation-reference)

---

## 1. Trend Following Strategy

### 1.1 Overview
Trend following captures sustained directional moves using multi-timeframe momentum confirmation. This strategy identifies established trends and rides them until reversal signals emerge.

### 1.2 Indicator Parameters

| Indicator | Parameter | Default Value | Description |
|-----------|-----------|---------------|-------------|
| Fast EMA | Period | 9 | Short-term trend direction |
| Slow EMA | Period | 21 | Long-term trend direction |
| ATR | Period | 14 | Volatility measurement for stop loss |
| ADX | Period | 14 | Trend strength confirmation |
| RSI | Period | 14 | Overbought/oversold conditions |
| Volume SMA | Period | 20 | Volume confirmation |

### 1.3 Timeframe Specifications

```yaml
Primary Timeframe: 4h      # Entry/exit decisions
Confirmation TF: 1d         # Trend direction bias
Execution TF: 1h           # Precision entry timing
Volume TF: 4h              # Volume analysis
```

### 1.4 Entry Rules

#### Long Entry (Buy Signal)
```
CONDITIONS_REQUIRED:
    1. Fast_EMA(9) > Slow_EMA(21) [Bullish alignment]
    2. ADX(14) > 25 [Strong trend confirmed]
    3. Close > Fast_EMA(9) [Price above short-term trend]
    4. Volume > Volume_SMA(20) * 1.2 [Volume confirmation]
    5. RSI(14) ∈ (30, 70) [Not extreme]
    
OPTIONAL_FILTERS:
    - Higher timeframe (1d) EMA alignment matches
    - No resistance within 2x ATR distance
```

#### Short Entry (Sell Signal)
```
CONDITIONS_REQUIRED:
    1. Fast_EMA(9) < Slow_EMA(21) [Bearish alignment]
    2. ADX(14) > 25 [Strong trend confirmed]
    3. Close < Fast_EMA(9) [Price below short-term trend]
    4. Volume > Volume_SMA(20) * 1.2 [Volume confirmation]
    5. RSI(14) ∈ (30, 70) [Not extreme]
```

### 1.5 Exit Rules

#### Take Profit (Tr分级 Exit)
```python
# Tiered profit-taking strategy
profit_targets = {
    'tp1': {'pct': 1.5, 'size': 0.30},   # 30% at 1.5R
    'tp2': {'pct': 3.0, 'size': 0.40},   # 40% at 3R
    'tp3': {'pct': 5.0, 'size': 0.30},   # 30% at 5R (runner)
}

# Trailing stop activation
trailing_activation = 2.0  # Activate after 2R profit
trailing_distance = 1.5 * ATR(14)  # Trail at 1.5 ATR
```

#### Stop Loss (ATR-Based)
```python
def calculate_stop_loss(entry_price, side, atr14, multiplier=2.0):
    """
    Calculate ATR-based stop loss.
    
    Formula:
        LONG_STOP = Entry - (ATR × Multiplier)
        SHORT_STOP = Entry + (ATR × Multiplier)
    """
    atr_distance = atr14 * multiplier
    
    if side == "long":
        return entry_price - atr_distance
    else:
        return entry_price + atr_distance

# Risk per trade: 1% of portfolio
risk_per_trade_pct = 0.01
```

### 1.6 Position Sizing Formula

```python
def calculate_position_size(portfolio_value, entry_price, stop_price, risk_pct=0.01):
    """
    Kelly Criterion inspired position sizing.
    
    Formula:
        RISK_AMOUNT = Portfolio × Risk_Pct
        STOP_DISTANCE = |Entry - Stop|
        POSITION_SIZE = RISK_AMOUNT / STOP_DISTANCE
    """
    risk_amount = portfolio_value * risk_pct
    stop_distance = abs(entry_price - stop_price)
    
    if stop_distance == 0:
        return 0
    
    quantity = risk_amount / stop_distance
    position_value = quantity * entry_price
    
    # Maximum position limit (5% of portfolio)
    max_position_value = portfolio_value * 0.05
    
    if position_value > max_position_value:
        quantity = max_position_value / entry_price
    
    return quantity

# Alternative: Fixed Fractional Sizing
def fixed_fractional_size(portfolio_value, confidence, base_risk=0.01):
    """
    Adjust size based on signal confidence.
    """
    confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5x to 1.0x
    return portfolio_value * base_risk * confidence_multiplier
```

### 1.7 Risk Management Rules

| Rule | Parameter | Action |
|------|-----------|--------|
| Max Position Size | 5% of portfolio | Hard limit per trade |
| Max Concurrent Trends | 3 positions | Limit correlation risk |
| Max Daily Loss | 2% of portfolio | Stop trading for day |
| Max Weekly Loss | 5% of portfolio | Stop trading for week |
| Correlation Limit | ρ > 0.7 | Don't add correlated positions |
| Drawdown Circuit | 10% from peak | Reduce size by 50% |

### 1.8 Pseudocode Implementation

```python
class TrendFollowingStrategy:
    
    def analyze(self, market_data):
        signals = []
        
        for symbol in self.symbols:
            # Calculate indicators
            df = market_data[symbol]
            df['fast_ema'] = EMA(df.close, 9)
            df['slow_ema'] = EMA(df.close, 21)
            df['atr'] = ATR(df, 14)
            df['adx'] = ADX(df, 14)
            df['rsi'] = RSI(df.close, 14)
            df['vol_sma'] = SMA(df.volume, 20)
            
            current = df.iloc[-1]
            
            # Long entry check
            if (current.fast_ema > current.slow_ema and      # Trend alignment
                current.adx > 25 and                          # Strong trend
                current.close > current.fast_ema and          # Price confirmation
                current.volume > current.vol_sma * 1.2 and    # Volume spike
                30 < current.rsi < 70):                       # Not extreme
                
                if not self.has_position(symbol):
                    stop_price = current.close - (current.atr * 2.0)
                    size = self.calculate_position_size(
                        self.portfolio_value,
                        current.close,
                        stop_price
                    )
                    signals.append(BuySignal(symbol, size, stop_price))
            
            # Exit checks for existing positions
            for position in self.open_positions:
                pnl_pct = position.unrealized_pnl_pct
                
                # Tiered take profit
                if pnl_pct >= 1.5 and not position.tp1_hit:
                    signals.append(PartialClose(position, 0.30))
                    position.tp1_hit = True
                elif pnl_pct >= 3.0 and not position.tp2_hit:
                    signals.append(PartialClose(position, 0.40))
                    position.tp2_hit = True
                    position.activate_trailing_stop(current.atr * 1.5)
                
                # Trend reversal exit
                if position.side == "long" and current.fast_ema < current.slow_ema:
                    signals.append(ClosePosition(position, reason="trend_reversal"))
        
        return signals
```

---

## 2. Funding Rate Arbitrage

### 2.1 Overview
Funding rate arbitrage captures the periodic funding payments between perpetual futures and spot markets while maintaining delta-neutral exposure.

### 2.2 Market Structure

```
PERPETUAL FUTURES:
    - No expiration date
    - Funding paid every 8 hours (00:00, 08:00, 16:00 UTC)
    - Funding Rate > 0: Longs pay shorts
    - Funding Rate < 0: Shorts pay longs

SPOT MARKET:
    - Immediate settlement
    - No funding costs
    - Requires full capital
```

### 2.3 Delta-Neutral Position Construction

```python
def construct_delta_neutral_position(symbol, funding_rate, capital):
    """
    Construct market-neutral arbitrage position.
    
    Position Structure:
        SPOT:   +1.0 BTC (Long spot)
        FUTURE: -1.0 BTC (Short perp)
        
    Net Delta: 0 (Price movements cancel)
    Funding Income: |Funding_Rate| × Notional every 8h
    """
    
    # Calculate position sizes
    spot_price = get_spot_price(symbol)
    perp_price = get_perp_price(symbol)
    
    # Basis risk check
    basis = (perp_price - spot_price) / spot_price
    if abs(basis) > 0.005:  # 0.5% max basis
        raise BasisRiskExceeded(f"Basis: {basis:.4%}")
    
    # Position sizing
    max_position_value = capital * 0.95  # 5% buffer for margin
    quantity = max_position_value / spot_price
    
    return {
        'spot': {'side': 'buy', 'quantity': quantity, 'price': spot_price},
        'perp': {'side': 'sell', 'quantity': quantity, 'price': perp_price},
        'expected_funding': quantity * perp_price * abs(funding_rate),
        'basis_at_entry': basis
    }
```

### 2.4 Entry Triggers

| Trigger Type | Condition | Minimum Threshold |
|--------------|-----------|-------------------|
| High Positive | Funding > 0 | +0.01% per 8h (0.03%/day) |
| High Negative | Funding < 0 | -0.01% per 8h |
| Extreme | Funding > 3σ | Historical 95th percentile |
| Predictive | Predicted > Current | Based on premium index |

```python
ENTRY_LOGIC:
    # Annualized funding threshold
    ANNUALIZED_THRESHOLD = 0.10  # 10% annualized
    
    # Calculate annualized rate
    periods_per_year = 365 * 3  # 3 funding periods per day
    annualized_rate = funding_rate * periods_per_year
    
    # Entry conditions
    if annualized_rate > ANNUALIZED_THRESHOLD:
        # Positive funding: Long spot, Short perp
        direction = "positive_carry"
    elif annualized_rate < -ANNUALIZED_THRESHOLD:
        # Negative funding: Short spot, Long perp
        direction = "negative_carry"
```

### 2.5 Exit Triggers

```python
EXIT_CONDITIONS = {
    'funding_compression': {
        'description': 'Funding rate normalized',
        'condition': 'abs(current_funding) < entry_threshold / 2'
    },
    'basis_expansion': {
        'description': 'Spot-perp spread too wide',
        'condition': 'abs(basis) > 1.0%',
        'action': 'Immediate unwind'
    },
    'margin_call_risk': {
        'description': 'Perp position near liquidation',
        'condition': 'margin_ratio < 20%',
        'action': 'Reduce position or add margin'
    },
    'time_decay': {
        'description': 'Position held too long without profit',
        'condition': 'days_held > 7 and unrealized_pnl < 0',
        'action': 'Consider exit'
    }
}
```

### 2.6 Position Monitoring Rules

```python
class FundingArbitrageMonitor:
    
    CHECK_INTERVAL_MINUTES = 5
    
    def monitor_position(self, position):
        alerts = []
        
        # 1. Basis monitoring
        current_basis = self.get_current_basis(position.symbol)
        basis_change = current_basis - position.entry_basis
        
        if abs(basis_change) > 0.005:  # 0.5% basis move
            alerts.append({
                'type': 'basis_warning',
                'severity': 'high',
                'message': f'Basis moved {basis_change:.4%}'
            })
        
        # 2. Margin monitoring (perp leg)
        margin_ratio = self.get_margin_ratio(position.perp_leg)
        if margin_ratio < 0.30:  # 30% margin ratio
            alerts.append({
                'type': 'margin_warning',
                'severity': 'critical',
                'message': f'Margin ratio: {margin_ratio:.2%}'
            })
        
        # 3. Funding accumulation tracking
        accumulated_funding = self.calculate_accumulated_funding(position)
        unrealized_pnl = self.calculate_unrealized_pnl(position)
        
        total_return = accumulated_funding + unrealized_pnl
        days_held = (now - position.entry_time).days
        
        # Break-even check
        if total_return < 0 and days_held > 3:
            alerts.append({
                'type': 'profitability_warning',
                'severity': 'medium',
                'message': f'Unprofitable after {days_held} days'
            })
        
        return alerts
```

### 2.7 Rebalancing Logic

```python
def rebalance_position(position, threshold_pct=0.02):
    """
    Rebalance when hedge ratio deviates.
    
    Deviation causes:
        - Different price moves (basis change)
        - Partial fills
        - Margin adjustments on perp leg
    """
    spot_value = position.spot.quantity * current_spot_price
    perp_value = position.perp.quantity * current_perp_price
    
    # Calculate hedge ratio deviation
    deviation = abs(spot_value - perp_value) / ((spot_value + perp_value) / 2)
    
    if deviation > threshold_pct:
        # Rebalance needed
        if spot_value > perp_value:
            # Reduce spot or increase perp
            rebalance_amount = (spot_value - perp_value) / 2
            return {
                'action': 'reduce_spot',
                'amount': rebalance_amount / current_spot_price
            }
        else:
            rebalance_amount = (perp_value - spot_value) / 2
            return {
                'action': 'reduce_perp',
                'amount': rebalance_amount / current_perp_price
            }
    
    return {'action': 'no_action'}
```

### 2.8 Risk of Basis Expansion

| Risk Factor | Description | Mitigation |
|-------------|-------------|------------|
| **Contango/Backwardation Flip** | Perp-spot spread reverses | Max 0.5% basis entry, stop at 1% |
| **Liquidity Mismatch** | Unable to exit one leg | Use liquid pairs only (BTC, ETH) |
| **Exchange Risk** | Counterparty failure | Split across 2+ exchanges |
| **Funding Rate Reversal** | Rate flips sign | Exit if rate crosses zero |
| **Margin Call** | Perp position liquidated | Maintain 200%+ margin ratio |

```python
# Basis risk calculation
def calculate_basis_risk_metrics(position):
    spot_price = get_spot_price(position.symbol)
    perp_price = get_perp_price(position.symbol)
    
    basis = perp_price - spot_price
    basis_pct = basis / spot_price
    
    # Mark-to-market P&L from basis
    basis_pnl = basis_pct * position.notional_value
    
    # Funding P&L (accumulated)
    funding_pnl = sum(position.funding_payments)
    
    # Total P&L
    total_pnl = basis_pnl + funding_pnl
    
    # Risk metrics
    return {
        'basis_pnl': basis_pnl,
        'funding_pnl': funding_pnl,
        'total_pnl': total_pnl,
        'basis_breakeven_days': abs(basis_pnl) / (abs(position.hourly_funding) * 3),
        'max_adverse_basis': calculate_var_basis(position.symbol, confidence=0.95)
    }
```

---

## 3. Grid Trading

### 3.1 Overview
Grid trading capitalizes on price oscillations within a defined range by placing buy orders below and sell orders above the current price.

### 3.2 Grid Spacing Calculations

#### Arithmetic Grid (Equal Price Intervals)
```python
def calculate_arithmetic_grid(center_price, grid_levels, grid_range_pct):
    """
    Equal price distance between levels.
    
    Formula:
        SPACING = (Center × Range%) / Levels
        Level_i = Center ± (i × Spacing)
    """
    total_range = center_price * (grid_range_pct / 100)
    spacing = total_range / grid_levels
    
    buy_levels = [center_price - (i * spacing) for i in range(1, grid_levels + 1)]
    sell_levels = [center_price + (i * spacing) for i in range(1, grid_levels + 1)]
    
    return {'buy_levels': buy_levels, 'sell_levels': sell_levels, 'spacing': spacing}
```

#### Geometric Grid (Equal Percentage Intervals)
```python
def calculate_geometric_grid(center_price, grid_levels, grid_spacing_pct):
    """
    Equal percentage distance between levels.
    
    Formula:
        Level_i = Center × (1 ± Spacing%)^i
    """
    spacing_factor = 1 + (grid_spacing_pct / 100)
    
    buy_levels = [center_price / (spacing_factor ** i) for i in range(1, grid_levels + 1)]
    sell_levels = [center_price * (spacing_factor ** i) for i in range(1, grid_levels + 1)]
    
    return {'buy_levels': buy_levels, 'sell_levels': sell_levels}
```

### 3.3 Position Limits Per Grid Level

```python
GRID_RISK_PARAMETERS = {
    'max_total_investment_pct': 50.0,    # Max 50% of portfolio in grid
    'max_position_per_level_pct': 5.0,   # Max 5% per grid level
    'grid_levels': 10,                    # Number of grid lines
    'grid_spacing_pct': 1.0,              # 1% between levels (geometric)
    'total_range_pct': 20.0,              # ±10% from center (arithmetic)
}

def calculate_grid_allocation(portfolio_value, num_levels, spacing_type='geometric'):
    """
    Calculate investment per grid level.
    
    Strategies:
        - EQUAL: Same amount at each level
        - PYRAMID: More at outer levels (mean reversion bias)
        - REVERSE_PYRAMID: More at inner levels (trend bias)
    """
    max_investment = portfolio_value * (GRID_RISK_PARAMETERS['max_total_investment_pct'] / 100)
    
    # Equal weighting
    if spacing_type == 'equal':
        per_level = max_investment / num_levels
        return [per_level] * num_levels
    
    # Pyramid (inverse weighting - more aggressive at extremes)
    elif spacing_type == 'pyramid':
        weights = list(range(1, num_levels + 1))  # 1, 2, 3, ...
        total_weight = sum(weights)
        return [max_investment * (w / total_weight) for w in weights]
    
    # Reverse pyramid (more conservative)
    elif spacing_type == 'reverse_pyramid':
        weights = list(range(num_levels, 0, -1))  # ..., 3, 2, 1
        total_weight = sum(weights)
        return [max_investment * (w / total_weight) for w in weights]
```

### 3.4 Grid Reset Conditions

```python
GRID_RESET_TRIGGERS = {
    'price_outside_range': {
        'condition': 'price < lower_stop OR price > upper_stop',
        'lower_stop': 'center × (1 - range% - buffer%)',
        'upper_stop': 'center × (1 + range% + buffer%)',
        'buffer_pct': 2.0,  # 2% buffer beyond grid
        'action': 'Close all, reset grid at new center'
    },
    'time_based': {
        'condition': 'grid_age > max_grid_age',
        'max_grid_age_hours': 168,  # 1 week
        'action': 'Evaluate grid profitability, reset if needed'
    },
    'volatility_expansion': {
        'condition': 'atr_14 > grid_range / 4',
        'action': 'Widen grid spacing or pause'
    },
    'profit_target': {
        'condition': 'grid_pnl > target_pnl',
        'target_pnl_pct': 5.0,
        'action': 'Reset grid to lock profits'
    }
}

def should_reset_grid(grid_state, current_price, current_atr):
    """Determine if grid needs reset."""
    
    # 1. Price outside range
    if current_price < grid_state.lower_stop or current_price > grid_state.upper_stop:
        return {'reset': True, 'reason': 'price_outside_range'}
    
    # 2. Time-based reset
    grid_age_hours = (datetime.utcnow() - grid_state.created_at).total_seconds() / 3600
    if grid_age_hours > GRID_RESET_TRIGGERS['time_based']['max_grid_age_hours']:
        # Only reset if profitable
        if grid_state.total_pnl > 0:
            return {'reset': True, 'reason': 'time_based_profitable'}
    
    # 3. Volatility expansion
    grid_range = grid_state.upper_bound - grid_state.lower_bound
    if current_atr > grid_range / 4:
        return {'reset': True, 'reason': 'volatility_expansion'}
    
    return {'reset': False}
```

### 3.5 Drawdown Controls

```python
GRID_DRAWDOWN_CONTROLS = {
    'max_grid_drawdown_pct': 10.0,      # Max loss before emergency stop
    'daily_grid_loss_limit_pct': 3.0,   # Daily loss limit
    'max_uncovered_exposure': 2,        # Max levels with open buy orders
    'hedge_on_breakout': True,          # Hedge if price breaks range
}

def calculate_grid_drawdown(grid_state, current_price):
    """
    Calculate worst-case scenario drawdown.
    
    Assumes all buy orders fill and price drops to lower_stop.
    """
    # Value of unfilled buy orders
    pending_buy_value = sum(
        level['quantity'] * level['price'] 
        for level in grid_state.pending_buys
    )
    
    # Current position value at current price
    current_position_value = grid_state.total_quantity * current_price
    
    # Value at lower stop (worst case)
    worst_case_value = grid_state.total_quantity * grid_state.lower_stop
    
    # Total invested
    total_invested = grid_state.invested_capital + pending_buy_value
    
    # Drawdown calculation
    paper_loss = current_position_value - worst_case_value
    drawdown_pct = paper_loss / total_invested * 100
    
    return {
        'current_drawdown_pct': drawdown_pct,
        'max_theoretical_loss': paper_loss + pending_buy_value * 0.5,
        'margin_of_safety': (current_price - grid_state.lower_stop) / current_price * 100
    }

# Dynamic hedge on breakout
def hedge_breakout(grid_state, current_price):
    """
    If price breaks grid range, hedge with opposite position
    to limit further losses.
    """
    if current_price > grid_state.upper_stop:
        # Breakout up - hedge with long
        hedge_size = grid_state.total_quantity * 0.5  # 50% hedge
        return {'action': 'buy', 'quantity': hedge_size, 'reason': 'upper_breakout_hedge'}
    
    elif current_price < grid_state.lower_stop:
        # Breakout down - hedge with short
        hedge_size = grid_state.total_quantity * 0.5
        return {'action': 'sell', 'quantity': hedge_size, 'reason': 'lower_breakout_hedge'}
    
    return {'action': 'none'}
```

### 3.6 Grid Implementation Pseudocode

```python
class GridTradingStrategy:
    
    def __init__(self, symbols, grid_levels=10, spacing_pct=1.0):
        self.grid_levels = grid_levels
        self.spacing_pct = spacing_pct
        self.active_grids = {}  # symbol -> grid_state
    
    def create_grid(self, symbol, center_price):
        """Initialize new grid around center price."""
        spacing = center_price * (self.spacing_pct / 100)
        
        grid = {
            'center_price': center_price,
            'buy_levels': [center_price - (i * spacing) for i in range(1, self.grid_levels + 1)],
            'sell_levels': [center_price + (i * spacing) for i in range(1, self.grid_levels + 1)],
            'lower_stop': center_price * 0.80,   # -20% stop
            'upper_stop': center_price * 1.20,   # +20% stop
            'orders': {},  # level_price -> order_id
            'filled_buys': [],  # Track filled buy levels
            'created_at': datetime.utcnow()
        }
        
        # Place initial orders
        for level in grid['buy_levels']:
            order = self.place_limit_buy(symbol, level, self.get_quantity_for_level())
            grid['orders'][level] = order.id
        
        for level in grid['sell_levels']:
            order = self.place_limit_sell(symbol, level, self.get_quantity_for_level())
            grid['orders'][level] = order.id
        
        return grid
    
    def on_fill(self, symbol, price, side):
        """Handle order fill - place opposite order."""
        grid = self.active_grids[symbol]
        
        if side == 'buy':
            grid['filled_buys'].append(price)
            # Place sell order one level up
            sell_price = price * (1 + self.spacing_pct / 100)
            if sell_price <= grid['upper_stop']:
                self.place_limit_sell(symbol, sell_price, self.get_quantity_for_level())
        
        elif side == 'sell':
            # Place buy order one level down
            buy_price = price / (1 + self.spacing_pct / 100)
            if buy_price >= grid['lower_stop']:
                self.place_limit_buy(symbol, buy_price, self.get_quantity_for_level())
    
    def analyze(self, market_data):
        """Main analysis loop."""
        signals = []
        
        for symbol in self.symbols:
            current_price = market_data[symbol].close
            
            # Check if grid needs reset
            if symbol in self.active_grids:
                reset_check = should_reset_grid(
                    self.active_grids[symbol], 
                    current_price,
                    market_data[symbol].atr
                )
                
                if reset_check['reset']:
                    signals.append(GridResetSignal(symbol, reset_check['reason']))
                    del self.active_grids[symbol]
            
            # Create new grid if none active
            if symbol not in self.active_grids:
                grid = self.create_grid(symbol, current_price)
                self.active_grids[symbol] = grid
                signals.append(GridCreatedSignal(symbol, grid))
        
        return signals
```

---

## 4. DCA/Rebalancing Strategy

### 4.1 Overview
Dollar-Cost Averaging (DCA) reduces timing risk by investing fixed amounts at regular intervals. Rebalancing maintains target portfolio allocations.

### 4.2 DCA Parameters

```yaml
DCA_CONFIGURATION:
    interval_hours: 24              # Time between purchases
    amount_usdt: 100.0              # Fixed USD amount per purchase
    symbols: ['BTCUSDT', 'ETHUSDT'] # Target assets
    max_slippage_pct: 0.5           # Max acceptable slippage
    order_type: 'market'            # Market or limit orders
    
ADVANCED_DCA:
    volatility_adjustment: true     # Increase amount on high volatility
    fear_greed_trigger: true        # Extra purchases on extreme fear (< 20)
    max_weekly_investment: 1000.0   # Weekly cap
```

### 4.3 Rebalancing Frequency and Thresholds

```python
REBALANCING_CONFIG = {
    # Frequency settings
    'frequency': {
        'type': 'threshold',        # 'time' or 'threshold' based
        'time_interval_days': 30,   # If time-based
        'threshold_pct': 5.0,       # Rebalance when allocation deviates 5%
    },
    
    # Target allocations
    'target_allocations': {
        'BTC': 0.50,    # 50% Bitcoin
        'ETH': 0.30,    # 30% Ethereum
        'USDT': 0.20,   # 20% Cash/stable
    },
    
    # Rebalancing bands (tolerance)
    'bands': {
        'inner': 0.02,   # 2% - no action zone
        'outer': 0.05,   # 5% - rebalance trigger
        'critical': 0.10 # 10% - immediate rebalance
    }
}

def check_rebalance_needed(current_allocations, target_allocations):
    """
    Determine if portfolio rebalancing is required.
    
    Uses threshold-based rebalancing with bands.
    """
    deviations = {}
    actions = []
    
    for asset, target in target_allocations.items():
        current = current_allocations.get(asset, 0)
        deviation = current - target
        deviations[asset] = deviation
        
        # Check bands
        if abs(deviation) > REBALANCING_CONFIG['bands']['critical']:
            actions.append({
                'asset': asset,
                'action': 'immediate_rebalance',
                'deviation': deviation,
                'priority': 'critical'
            })
        elif abs(deviation) > REBALANCING_CONFIG['bands']['outer']:
            actions.append({
                'asset': asset,
                'action': 'schedule_rebalance',
                'deviation': deviation,
                'priority': 'normal'
            })
    
    return {'deviations': deviations, 'actions': actions}
```

### 4.4 Tax-Efficient Rebalancing Methods

```python
TAX_EFFICIENT_METHODS = {
    # 1. Cash Flow Rebalancing (preferred)
    'cash_flow': {
        'description': 'Use new contributions to rebalance',
        'tax_impact': 'none',
        'implementation': 'Direct new DCA to underweight assets'
    },
    
    # 2. Withdrawal Rebalancing
    'withdrawal': {
        'description': 'Sell from overweight assets when withdrawing',
        'tax_impact': 'minimal',
        'implementation': 'Prioritize selling overweight positions'
    },
    
    # 3. Tax Loss Harvesting
    'tax_loss_harvesting': {
        'description': 'Realize losses to offset gains',
        'tax_impact': 'positive',
        'conditions': 'Asset has unrealized loss > $100',
        'wash_sale_rule': 'Avoid rebuying within 30 days'
    },
    
    # 4. Lot Selection
    'lot_selection': {
        'description': 'Select specific tax lots to minimize gain',
        'methods': {
            'hifo': 'Highest cost first - minimizes gains',
            'fifo': 'First in first out - default',
            'lifo': 'Last in first out - recent purchases'
        }
    }
}

def calculate_tax_efficient_rebalance(portfolio, target_allocations, tax_bracket=0.25):
    """
    Calculate rebalancing trades minimizing tax impact.
    """
    rebalance_plan = []
    
    for asset, target_pct in target_allocations.items():
        current_value = portfolio.get_asset_value(asset)
        target_value = portfolio.total_value * target_pct
        diff = target_value - current_value
        
        if diff > 0:  # Need to buy
            rebalance_plan.append({
                'asset': asset,
                'action': 'buy',
                'amount': diff,
                'tax_impact': 0
            })
        
        elif diff < 0:  # Need to sell
            # Calculate optimal lots to sell
            lots = portfolio.get_tax_lots(asset)
            
            # Sort by cost basis (HIFO)
            lots.sort(key=lambda x: x.cost_basis, reverse=True)
            
            amount_to_sell = abs(diff)
            lots_to_sell = []
            
            for lot in lots:
                if amount_to_sell <= 0:
                    break
                
                sell_amount = min(lot.quantity * lot.current_price, amount_to_sell)
                gain_loss = (lot.current_price - lot.cost_basis) * (sell_amount / lot.current_price)
                
                lots_to_sell.append({
                    'lot_id': lot.id,
                    'amount': sell_amount,
                    'gain_loss': gain_loss
                })
                amount_to_sell -= sell_amount
            
            total_gain = sum(l['gain_loss'] for l in lots_to_sell)
            tax_cost = max(0, total_gain) * tax_bracket
            
            rebalance_plan.append({
                'asset': asset,
                'action': 'sell',
                'amount': abs(diff),
                'lots': lots_to_sell,
                'estimated_gain': total_gain,
                'estimated_tax': tax_cost
            })
    
    return rebalance_plan
```

### 4.5 Contribution Allocation Logic

```python
class DCAAllocator:
    
    def __init__(self, target_allocations, volatility_adjustment=True):
        self.target_allocations = target_allocations
        self.volatility_adjustment = volatility_adjustment
    
    def allocate_contribution(self, contribution_amount, current_portfolio):
        """
        Allocate DCA contribution across assets.
        
        Strategies:
            1. Target-weighted: Proportional to target allocation
            2. Underweight-first: All to most underweight asset
            3. Volatility-adjusted: More to high volatility assets
        """
        allocations = {}
        
        # Calculate current weights
        total_value = current_portfolio.total_value
        current_weights = {
            asset: current_portfolio.get_value(asset) / total_value
            for asset in self.target_allocations.keys()
        }
        
        # Calculate deviations from target
        deviations = {
            asset: self.target_allocations[asset] - current_weights.get(asset, 0)
            for asset in self.target_allocations.keys()
        }
        
        # Strategy: Underweight-first with volatility adjustment
        if self.volatility_adjustment:
            # Get volatility scores (ATR-based)
            volatilities = self.calculate_volatility_scores()
            
            # Calculate allocation weights
            weights = {}
            for asset in self.target_allocations.keys():
                # Base on deviation (underweight = higher priority)
                base_weight = max(0, deviations[asset])
                
                # Adjust for volatility (higher vol = potentially higher return)
                vol_adjustment = 1 + (volatilities[asset] - 0.5) * 0.2
                
                weights[asset] = base_weight * vol_adjustment
            
            # Normalize weights
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v / total_weight for k, v in weights.items()}
            else:
                # If balanced, use target weights
                weights = self.target_allocations
        
        else:
            # Simple target-weighted
            weights = self.target_allocations
        
        # Calculate USD amounts
        allocations = {
            asset: contribution_amount * weight
            for asset, weight in weights.items()
        }
        
        return allocations
    
    def calculate_volatility_scores(self):
        """
        Calculate normalized volatility scores (0-1 scale).
        """
        atrs = {}
        for asset in self.target_allocations.keys():
            data = self.get_price_data(asset, days=30)
            atrs[asset] = calculate_atr(data, 14)
        
        # Normalize to 0-1 range
        max_atr = max(atrs.values())
        min_atr = min(atrs.values())
        
        if max_atr == min_atr:
            return {asset: 0.5 for asset in atrs}
        
        return {
            asset: (atr - min_atr) / (max_atr - min_atr)
            for asset, atr in atrs.items()
        }
```

---

## 5. Tactical/Crisis Deployment

### 5.1 Overview
Tactical deployment allocates additional capital during market dislocations based on predefined fear indicators and drawdown levels.

### 5.2 Trigger Conditions

```python
CRISIS_TRIGGERS = {
    # Fear & Greed Index
    'fear_greed_index': {
        'source': 'alternative.me',
        'update_frequency': 'daily',
        'triggers': {
            'extreme_fear': {'threshold': 20, 'multiplier': 2.0},
            'fear': {'threshold': 40, 'multiplier': 1.5},
            'neutral': {'threshold': 50, 'multiplier': 1.0},
            'greed': {'threshold': 75, 'multiplier': 0.5},
            'extreme_greed': {'threshold': 80, 'multiplier': 0.0}
        }
    },
    
    # Drawdown Triggers (from ATH)
    'drawdown_triggers': {
        'btc_drawdown': {
            '10_pct': {'allocation': 0.10, 'aggression': 1.0},
            '20_pct': {'allocation': 0.15, 'aggression': 1.5},
            '30_pct': {'allocation': 0.20, 'aggression': 2.0},
            '40_pct': {'allocation': 0.25, 'aggression': 2.5},
            '50_pct': {'allocation': 0.30, 'aggression': 3.0}
        }
    },
    
    # VIX-style Volatility (BVOL for crypto)
    'volatility_spike': {
        'threshold_14d': 0.80,  # 80th percentile
        'threshold_30d': 0.90,  # 90th percentile
        'allocation_boost': 1.5
    },
    
    # Capitulation Signals
    'capitulation': {
        'sopr': {'threshold': 0.95, 'description': 'SOPR < 1 (loss selling)'},
        'nupl': {'threshold': 0.0, 'description': 'NUPL negative'},
        'mvrv': {'threshold': 1.0, 'description': 'MVRV < 1'},
        'allocation_boost': 2.0
    }
}
```

### 5.3 Deployment Sizing Rules

```python
class CrisisDeploymentManager:
    
    def __init__(self, base_monthly_allocation, max_deployment_pct=0.50):
        self.base_monthly = base_monthly_allocation
        self.max_deployment_pct = max_deployment_pct  # Max 50% of reserve
        self.deployed_this_crisis = 0
        self.deployment_history = []
    
    def calculate_deployment_size(self, crisis_signals, available_reserve):
        """
        Calculate deployment amount based on crisis severity.
        
        Uses cumulative scoring system.
        """
        severity_score = 0
        multipliers = []
        
        # Fear & Greed contribution
        if 'fear_greed' in crisis_signals:
            fg = crisis_signals['fear_greed']
            if fg <= 20:
                severity_score += 3
                multipliers.append(2.0)
            elif fg <= 40:
                severity_score += 2
                multipliers.append(1.5)
        
        # Drawdown contribution
        if 'drawdown_pct' in crisis_signals:
            dd = crisis_signals['drawdown_pct']
            if dd >= 50:
                severity_score += 3
                multipliers.append(3.0)
            elif dd >= 40:
                severity_score += 2
                multipliers.append(2.5)
            elif dd >= 30:
                severity_score += 1
                multipliers.append(2.0)
        
        # Volatility contribution
        if 'volatility_percentile' in crisis_signals:
            vol = crisis_signals['volatility_percentile']
            if vol >= 0.90:
                severity_score += 2
                multipliers.append(1.5)
        
        # Capitulation signals
        if 'capitulation_signals' in crisis_signals:
            cap_count = sum(crisis_signals['capitulation_signals'].values())
            severity_score += cap_count
            if cap_count >= 2:
                multipliers.append(2.0)
        
        # Calculate deployment multiplier
        avg_multiplier = sum(multipliers) / len(multipliers) if multipliers else 1.0
        
        # Tiered deployment based on severity
        if severity_score >= 7:
            deployment_pct = 0.30  # 30% of reserve
        elif severity_score >= 5:
            deployment_pct = 0.20
        elif severity_score >= 3:
            deployment_pct = 0.10
        else:
            deployment_pct = 0.05
        
        # Apply multiplier
        deployment_pct *= avg_multiplier
        
        # Cap at maximum
        deployment_pct = min(deployment_pct, self.max_deployment_pct)
        
        # Check remaining reserve limit
        remaining_pct = 1 - (self.deployed_this_crisis / available_reserve)
        deployment_pct = min(deployment_pct, remaining_pct)
        
        deployment_amount = available_reserve * deployment_pct
        
        return {
            'amount': deployment_amount,
            'severity_score': severity_score,
            'multiplier': avg_multiplier,
            'deployment_pct': deployment_pct,
            'remaining_reserve': available_reserve - deployment_amount
        }
    
    def time_weighted_deployment(self, total_amount, days=30):
        """
        Deploy over time to avoid catching a falling knife.
        
        Implements dollar-cost averaging into the crisis.
        """
        daily_amount = total_amount / days
        
        schedule = []
        for day in range(days):
            # Accelerate deployment if conditions worsen
            day_multiplier = 1 + (day / days) * 0.5  # Up to 1.5x at end
            
            schedule.append({
                'day': day + 1,
                'base_amount': daily_amount,
                'adjusted_amount': daily_amount * day_multiplier,
                'cumulative': sum(s['adjusted_amount'] for s in schedule) + daily_amount * day_multiplier
            })
        
        return schedule
```

### 5.4 Exit Conditions

```python
EXIT_TRIGGERS = {
    'profit_targets': {
        'tier_1': {'gain': 0.25, 'action': 'sell_25_pct'},
        'tier_2': {'gain': 0.50, 'action': 'sell_30_pct'},
        'tier_3': {'gain': 1.00, 'action': 'sell_25_pct'},
        'tier_4': {'gain': 2.00, 'action': 'sell_20_pct'},
        'runner': {'description': 'Hold remaining with trailing stop'}
    },
    
    'fear_greed_recovery': {
        'exit_start': 50,    # Neutral
        'full_exit': 75,     # Greed
        'action': 'begin_profit_taking'
    },
    
    'time_based': {
        'min_hold_days': 90,
        'max_hold_days': 365,
        'action_at_max': 'evaluate_and_exit'
    },
    
    'drawdown_recovery': {
        'exit_trigger': 'price_within_10_pct_of_ath',
        'action': 'take_profits_return_to_base'
    },
    
    'emergency_exit': {
        'new_crisis': 'deployed_capital_drawdown > 20%',
        'action': 'stop_loss_exit'
    }
}
```

### 5.5 Return to Base Logic

```python
class ReturnToBaseManager:
    
    def __init__(self, base_allocation, tactical_allocation):
        self.base = base_allocation
        self.tactical = tactical_allocation
        self.profits_taken = 0
    
    def evaluate_return_to_base(self, current_state):
        """
        Determine if tactical deployment should return to base strategy.
        """
        signals = []
        
        # 1. Profit target achieved
        unrealized_pnl = current_state['tactical_unrealized_pnl']
        if unrealized_pnl > 0.50:  # 50%+ gains
            signals.append({
                'signal': 'return_to_base',
                'priority': 'high',
                'reason': f'Profit target exceeded: {unrealized_pnl:.2%}'
            })
        
        # 2. Market sentiment recovered
        fear_greed = current_state['fear_greed_index']
        if fear_greed > 60:  # Greed territory
            signals.append({
                'signal': 'begin_profit_taking',
                'priority': 'medium',
                'reason': f'Market sentiment recovered: {fear_greed}'
            })
        
        # 3. Drawdown recovered
        drawdown = current_state['drawdown_from_ath']
        if drawdown < 0.10:  # Within 10% of ATH
            signals.append({
                'signal': 'return_to_base',
                'priority': 'medium',
                'reason': f'Drawdown recovered: {drawdown:.2%}'
            })
        
        # 4. Time limit
        days_deployed = current_state['days_since_deployment']
        if days_deployed > 365:
            signals.append({
                'signal': 'mandatory_rebalance',
                'priority': 'high',
                'reason': f'Time limit reached: {days_deployed} days'
            })
        
        return signals
    
    def execute_return_to_base(self, current_holdings, target_base_allocations):
        """
        Gradually return tactical allocation to base strategy.
        """
        rebalance_trades = []
        
        total_value = sum(current_holdings.values())
        
        for asset, target_pct in target_base_allocations.items():
            target_value = total_value * target_pct
            current_value = current_holdings.get(asset, 0)
            
            diff = target_value - current_value
            
            if abs(diff) > total_value * 0.01:  # 1% minimum trade
                rebalance_trades.append({
                    'asset': asset,
                    'action': 'buy' if diff > 0 else 'sell',
                    'amount': abs(diff),
                    'reason': 'return_to_base_allocation'
                })
        
        return rebalance_trades
```

### 5.6 Crisis Deployment Pseudocode

```python
class CrisisDeploymentStrategy:
    
    def __init__(self, reserve_fund_pct=0.30):
        self.reserve_fund_pct = reserve_fund_pct
        self.deployment_active = False
        self.deployed_amount = 0
        self.base_strategy_allocation = 0.70  # 70% base, 30% reserve
    
    async def analyze(self, market_data):
        signals = []
        
        # Gather crisis indicators
        crisis_signals = {
            'fear_greed': await self.get_fear_greed_index(),
            'drawdown_pct': self.calculate_drawdown(market_data),
            'volatility_percentile': self.get_volatility_percentile(market_data),
            'capitulation_signals': self.check_onchain_capitulation()
        }
        
        # Check for crisis conditions
        is_crisis = self.evaluate_crisis_conditions(crisis_signals)
        
        if is_crisis and not self.deployment_active:
            # Calculate deployment
            available_reserve = self.portfolio.value * self.reserve_fund_pct
            
            deployment = self.calculate_deployment_size(
                crisis_signals, 
                available_reserve
            )
            
            # Create deployment schedule
            schedule = self.time_weighted_deployment(
                deployment['amount'], 
                days=30
            )
            
            signals.append(CrisisDeploymentSignal(
                amount=deployment['amount'],
                schedule=schedule,
                severity=deployment['severity_score']
            ))
            
            self.deployment_active = True
            self.deployed_amount = deployment['amount']
        
        elif self.deployment_active:
            # Check exit conditions
            exit_signals = self.evaluate_exit_conditions(market_data, crisis_signals)
            
            if exit_signals:
                for signal in exit_signals:
                    if signal['type'] == 'profit_taking':
                        signals.append(PartialExitSignal(
                            pct=signal['pct'],
                            reason=signal['reason']
                        ))
                    elif signal['type'] == 'return_to_base':
                        signals.append(ReturnToBaseSignal())
                        self.deployment_active = False
        
        return signals
    
    def evaluate_crisis_conditions(self, signals):
        """Determine if crisis deployment criteria are met."""
        score = 0
        
        if signals['fear_greed'] <= 25:
            score += 2
        elif signals['fear_greed'] <= 40:
            score += 1
        
        if signals['drawdown_pct'] >= 0.30:
            score += 2
        elif signals['drawdown_pct'] >= 0.20:
            score += 1
        
        if any(signals['capitulation_signals'].values()):
            score += 1
        
        return score >= 3  # Deploy if score >= 3
```

---

## 6. Risk Management Framework

### 6.1 Universal Risk Limits

```yaml
HARD_LIMITS:
    max_position_size: 5%          # Per position
    max_sector_exposure: 15%       # Per correlated group
    max_daily_loss: 2%             # Stop trading
    max_weekly_loss: 5%            # Emergency stop
    max_drawdown: 15%              # Circuit breaker
    max_leverage: 1.0              # Spot only (no margin)

POSITION_RISK:
    stop_loss_atr_multiplier: 2.0
    take_profit_risk_reward: 2.0
    max_risk_per_trade: 1.0%

CORRELATION_LIMITS:
    max_correlated_positions: 3
    correlation_threshold: 0.70
    correlation_lookback: 30_days
```

### 6.2 Position Sizing Matrix

| Strategy Type | Base Risk | Max Size | Confidence Multiplier |
|--------------|-----------|----------|----------------------|
| Trend Following | 1.0% | 5% | 0.5x - 1.0x |
| Funding Arbitrage | 0.5% | 10% | Fixed |
| Grid Trading | 0.5% per level | 50% total | Fixed |
| DCA | 1.0% per purchase | 20% weekly | Fixed |
| Crisis Deploy | 2.0% | 30% reserve | Dynamic |

### 6.3 Stop Loss Hierarchy

```python
STOP_LOSS_HIERARCHY = {
    # Level 1: Strategy Stop (tightest)
    'strategy_stop': {
        'trigger': 'strategy specific signal',
        'execution': 'immediate_market_order',
        'priority': 1
    },
    
    # Level 2: Technical Stop
    'technical_stop': {
        'trigger': 'ATR_based or support_break',
        'distance': '2x ATR',
        'execution': 'stop_limit_order',
        'priority': 2
    },
    
    # Level 3: Portfolio Stop (emergency)
    'portfolio_stop': {
        'trigger': 'daily_loss_limit OR drawdown_limit',
        'execution': 'close_all_positions',
        'priority': 3
    }
}
```

---

## 7. Implementation Reference

### 7.1 Strategy Class Structure

```python
from abc import ABC, abstractmethod
from typing import List, Dict
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class Signal:
    symbol: str
    side: str  # 'buy', 'sell', 'close'
    size: Decimal
    price: Decimal
    stop_loss: Decimal = None
    take_profit: Decimal = None
    metadata: Dict = None

class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, name: str, symbols: List[str], params: Dict):
        self.name = name
        self.symbols = symbols
        self.params = params
        self.is_active = True
        self.positions = {}
    
    @abstractmethod
    def analyze(self, market_data: Dict) -> List[Signal]:
        """Generate trading signals from market data."""
        pass
    
    @abstractmethod
    def on_fill(self, symbol: str, side: str, price: Decimal, size: Decimal):
        """Handle order fill events."""
        pass
    
    def calculate_position_size(
        self, 
        portfolio_value: Decimal,
        entry_price: Decimal,
        stop_price: Decimal,
        risk_pct: float = 0.01
    ) -> Decimal:
        """Calculate position size based on risk."""
        risk_amount = portfolio_value * Decimal(str(risk_pct))
        stop_distance = abs(entry_price - stop_price)
        
        if stop_distance == 0:
            return Decimal('0')
        
        quantity = risk_amount / stop_distance
        return quantity
    
    def calculate_atr(self, highs, lows, closes, period=14):
        """Calculate Average True Range."""
        tr1 = [h - l for h, l in zip(highs, lows)]
        tr2 = [abs(h - c) for h, c in zip(highs[1:], closes[:-1])]
        tr3 = [abs(l - c) for l, c in zip(lows[1:], closes[:-1])]
        
        tr = [max(t1, t2, t3) for t1, t2, t3 in zip(tr1[1:], tr2, tr3)]
        
        # Wilder's smoothing
        atr = [sum(tr[:period]) / period]
        for i in range(period, len(tr)):
            atr.append((atr[-1] * (period - 1) + tr[i]) / period)
        
        return atr[-1] if atr else 0
```

### 7.2 Configuration Schema

```yaml
# config/strategies.yaml
strategies:
  trend_following:
    enabled: true
    symbols: ['BTCUSDT', 'ETHUSDT']
    timeframes: ['1h', '4h']
    indicators:
      ema_fast: {period: 9, type: 'ema'}
      ema_slow: {period: 21, type: 'ema'}
      atr: {period: 14}
      adx: {period: 14}
    entry:
      ema_cross: true
      adx_min: 25
      volume_confirm: 1.2
    risk:
      stop_atr_mult: 2.0
      risk_per_trade: 0.01
      max_position: 0.05

  funding_arbitrage:
    enabled: false
    min_annualized_rate: 0.10
    max_basis_pct: 0.005
    rebalance_threshold: 0.02
    exchanges: ['bybit', 'binance']

  grid_trading:
    enabled: true
    grid_levels: 10
    spacing_pct: 1.0
    range_pct: 20.0
    max_investment_pct: 50.0
    reset_on_breakout: true

  dca:
    enabled: true
    interval_hours: 24
    amount_usdt: 100
    volatility_adjust: true
    targets:
      BTC: 0.50
      ETH: 0.30
      USDT: 0.20

  crisis_deployment:
    enabled: false
    reserve_pct: 0.30
    triggers:
      fear_greed_threshold: 25
      drawdown_threshold: 0.30
    deployment_schedule_days: 30
```

### 7.3 Key Metrics Dashboard

```python
METRICS_TO_TRACK = {
    # Performance
    'total_return': 'cumulative_pnl / starting_capital',
    'sharpe_ratio': 'excess_return / volatility',
    'sortino_ratio': 'excess_return / downside_volatility',
    'max_drawdown': 'peak_to_trough_decline',
    'calmar_ratio': 'annual_return / max_drawdown',
    
    # Trade Metrics
    'win_rate': 'winning_trades / total_trades',
    'profit_factor': 'gross_profit / gross_loss',
    'avg_win_loss_ratio': 'avg_win / avg_loss',
    'expectancy': '(win_rate * avg_win) - (loss_rate * avg_loss)',
    
    # Risk Metrics
    'var_95': '5th percentile of returns',
    'cvar_95': 'average of worst 5% returns',
    'beta': 'correlation_to_benchmark',
    'correlation_matrix': 'inter-asset_correlations',
    
    # Operational
    'uptime_pct': 'strategy_execution_time / total_time',
    'slippage_avg': 'expected_vs_actual_fill_difference',
    'fill_rate': 'filled_orders / total_orders'
}
```

---

## Appendix: Formula Reference

### Technical Indicators

```
EMA:    EMA_today = Price_today × k + EMA_yesterday × (1 - k)
        where k = 2 / (N + 1)

ATR:    TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        ATR = SMA(TR, N)  [or Wilder's smoothing]

ADX:    +DM = High_today - High_yesterday (if positive, else 0)
        -DM = Low_yesterday - Low_today (if positive, else 0)
        +DI = 100 × SMA(+DM, N) / ATR
        -DI = 100 × SMA(-DM, N) / ATR
        DX = 100 × |+DI - -DI| / (+DI + -DI)
        ADX = SMA(DX, N)

RSI:    RS = SMA(Gains, N) / SMA(Losses, N)
        RSI = 100 - (100 / (1 + RS))

Bollinger Bands:
        Middle = SMA(Close, 20)
        Upper = Middle + (2 × StdDev)
        Lower = Middle - (2 × StdDev)
```

### Risk Formulas

```
Position Size (Fixed Fractional):
        Q = (Capital × Risk%) / (Entry - Stop)

Kelly Criterion:
        f* = (p × b - q) / b
        where p = win probability, q = loss probability, b = win/loss ratio

Sharpe Ratio:
        S = (Rp - Rf) / σp

Maximum Drawdown:
        MDD = max[(Peak - Trough) / Peak]
```

---

*Document Version: 1.0*  
*Last Updated: 2026-02-13*  
*Intended Use: Developer Implementation Guide*
