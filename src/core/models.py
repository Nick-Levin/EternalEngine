"""Data models for The Eternal Engine trading system.

This module defines all data structures used across the 4-engine architecture:
- CORE-HODL: Spot BTC/ETH accumulation with rebalancing
- TREND: Perp futures trend following
- FUNDING: Delta-neutral funding arbitrage
- TACTICAL: Crisis deployment strategy

All monetary values use Decimal for precision.
All timestamps are timezone-aware UTC datetime objects.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# =============================================================================
# Enums
# =============================================================================

class OrderSide(str, Enum):
    """Order side - buy or sell."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT_MARKET = "take_profit_market"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    """Order lifecycle status."""
    PENDING = "pending"           # Created but not submitted
    OPEN = "open"                 # Submitted to exchange
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(str, Enum):
    """Position side - long, short, or flat."""
    LONG = "long"
    SHORT = "short"
    NONE = "none"


class SignalType(str, Enum):
    """Trading signal types from strategies."""
    BUY = "buy"                   # Enter long position
    SELL = "sell"                 # Enter short position
    CLOSE = "close"               # Close existing position
    CLOSE_LONG = "close_long"     # Close long only
    CLOSE_SHORT = "close_short"   # Close short only
    HOLD = "hold"                 # No action
    REBALANCE = "rebalance"       # Rebalance portfolio
    EMERGENCY_EXIT = "emergency_exit"  # Immediate full exit


class CircuitBreakerLevel(str, Enum):
    """Circuit breaker levels for capital preservation.
    
    See AGENTS.md section 4.2 for full details on each level's actions.
    """
    NONE = "none"                 # No circuit breaker active
    LEVEL_1 = "level_1"           # 10% drawdown - reduce 25%
    LEVEL_2 = "level_2"           # 15% drawdown - reduce 50%, pause 72h
    LEVEL_3 = "level_3"           # 20% drawdown - close directional, move to Earn
    LEVEL_4 = "level_4"           # 25% drawdown - full liquidation to USDT


class EngineType(str, Enum):
    """The four engines of The Eternal Engine."""
    CORE_HODL = "core_hodl"       # 60% allocation - spot DCA + rebalance
    TREND = "trend"               # 20% allocation - trend following
    FUNDING = "funding"           # 15% allocation - funding arbitrage
    TACTICAL = "tactical"         # 5% allocation - crisis deployment


class TradeStatus(str, Enum):
    """Status of a completed trade record."""
    OPEN = "open"                 # Position still open
    CLOSED = "closed"             # Position closed
    PARTIALLY_CLOSED = "partially_closed"


# =============================================================================
# Market Data Models
# =============================================================================

class MarketData(BaseModel):
    """OHLCV market data snapshot with optional indicators.
    
    Used by all engines for strategy analysis and signal generation.
    
    Attributes:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        timestamp: Data timestamp (UTC)
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Trading volume
        timeframe: Candle timeframe (e.g., "1h", "4h", "1d")
        indicators: Optional technical indicators
        source: Data source identifier
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    symbol: str = Field(..., description="Trading pair symbol")
    timestamp: datetime = Field(..., description="Data timestamp (UTC)")
    open: Decimal = Field(..., description="Opening price")
    high: Decimal = Field(..., description="Highest price")
    low: Decimal = Field(..., description="Lowest price")
    close: Decimal = Field(..., description="Closing price")
    volume: Decimal = Field(..., description="Trading volume")
    timeframe: str = Field(default="1h", description="Candle timeframe")
    indicators: Dict[str, Decimal] = Field(default_factory=dict, description="Technical indicators")
    source: str = Field(default="bybit", description="Data source")
    
    @field_validator("high")
    @classmethod
    def high_gte_open(cls, v: Decimal, info) -> Decimal:
        """Validate high is >= open."""
        if info.data.get("open") and v < info.data["open"]:
            raise ValueError("High must be >= open")
        return v
    
    @field_validator("low")
    @classmethod
    def low_lte_high(cls, v: Decimal, info) -> Decimal:
        """Validate low is <= high."""
        if info.data.get("high") and v > info.data["high"]:
            raise ValueError("Low must be <= high")
        return v
    
    @property
    def range(self) -> Decimal:
        """Calculate price range (high - low)."""
        return self.high - self.low
    
    @property
    def body(self) -> Decimal:
        """Calculate candle body (close - open)."""
        return self.close - self.open
    
    @property
    def is_green(self) -> bool:
        """True if close > open (bullish candle)."""
        return self.close > self.open


# =============================================================================
# Order Models
# =============================================================================

class Order(BaseModel):
    """Order representation for exchange interaction.
    
    Supports all order types: market, limit, stop-loss, take-profit.
    Tracks order lifecycle from creation through fill/cancel.
    
    Attributes:
        symbol: Trading pair
        side: Buy or sell
        order_type: Market, limit, stop, etc.
        amount: Order quantity
        price: Limit price (None for market orders)
        id: Internal order ID (UUID)
        exchange_order_id: Exchange-assigned order ID
        status: Current order status
        filled_amount: Amount already filled
        average_price: Weighted average fill price
        created_at: Order creation timestamp
        updated_at: Last update timestamp
        filled_at: Completion timestamp
        stop_loss_price: Associated stop loss price
        take_profit_price: Associated take profit price
        metadata: Additional order data
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    # Required fields
    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side")
    order_type: OrderType = Field(..., description="Order type")
    amount: Decimal = Field(..., gt=0, description="Order quantity")
    
    # Price (None for market orders)
    price: Optional[Decimal] = Field(default=None, description="Limit price")
    
    # Identification
    id: str = Field(default_factory=lambda: str(uuid4()), description="Internal order ID")
    exchange_order_id: Optional[str] = Field(default=None, description="Exchange order ID")
    
    # Status
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Order status")
    filled_amount: Decimal = Field(default=Decimal("0"), ge=0, description="Filled quantity")
    average_price: Optional[Decimal] = Field(default=None, description="Average fill price")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: Optional[datetime] = Field(default=None, description="Last update time")
    filled_at: Optional[datetime] = Field(default=None, description="Fill completion time")
    
    # Risk management
    stop_loss_price: Optional[Decimal] = Field(default=None, description="Stop loss price")
    take_profit_price: Optional[Decimal] = Field(default=None, description="Take profit price")
    
    # Additional data
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    
    @field_validator("price")
    @classmethod
    def price_required_for_limit(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        """Validate limit orders have a price."""
        order_type = info.data.get("order_type")
        if order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT_LIMIT):
            if v is None or v <= 0:
                raise ValueError(f"Price required and must be positive for {order_type}")
        return v
    
    @property
    def remaining_amount(self) -> Decimal:
        """Amount yet to be filled."""
        return self.amount - self.filled_amount
    
    @property
    def is_filled(self) -> bool:
        """True if order is completely filled."""
        return self.filled_amount >= self.amount
    
    @property
    def is_active(self) -> bool:
        """True if order is still active (not filled/cancelled/rejected)."""
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)
    
    @property
    def fill_percentage(self) -> Decimal:
        """Percentage of order that has been filled."""
        if self.amount == 0:
            return Decimal("0")
        return (self.filled_amount / self.amount) * 100
    
    def mark_as_filled(self, filled_at: Optional[datetime] = None) -> None:
        """Mark order as fully filled."""
        self.status = OrderStatus.FILLED
        self.filled_amount = self.amount
        self.filled_at = filled_at or datetime.utcnow()
        self.updated_at = datetime.utcnow()


# =============================================================================
# Position Models
# =============================================================================

class Position(BaseModel):
    """Position tracking for a trading instrument.
    
    Tracks both spot and perpetual futures positions.
    Calculates unrealized and realized PnL.
    
    Attributes:
        symbol: Trading pair
        side: Long, short, or none
        entry_price: Average entry price
        amount: Position size
        id: Internal position ID
        opened_at: Position open timestamp
        closed_at: Position close timestamp
        unrealized_pnl: Current unrealized PnL
        realized_pnl: Realized PnL from partial closes
        stop_loss_price: Stop loss level
        take_profit_price: Take profit level
        leverage: Position leverage (1.0 for spot)
        margin_type: "isolated" or "cross"
        liquidation_price: Estimated liquidation price
        orders: Associated orders
        metadata: Additional position data
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    # Required fields
    symbol: str = Field(..., description="Trading pair symbol")
    side: PositionSide = Field(..., description="Position side")
    entry_price: Decimal = Field(..., gt=0, description="Average entry price")
    amount: Decimal = Field(..., ge=0, description="Position size")
    
    # Identification
    id: str = Field(default_factory=lambda: str(uuid4()), description="Position ID")
    
    # Timestamps
    opened_at: datetime = Field(default_factory=datetime.utcnow, description="Open time")
    closed_at: Optional[datetime] = Field(default=None, description="Close time")
    
    # PnL tracking
    unrealized_pnl: Decimal = Field(default=Decimal("0"), description="Unrealized PnL")
    realized_pnl: Decimal = Field(default=Decimal("0"), description="Realized PnL")
    
    # Risk management
    stop_loss_price: Optional[Decimal] = Field(default=None, description="Stop loss price")
    take_profit_price: Optional[Decimal] = Field(default=None, description="Take profit price")
    max_drawdown_pct: Optional[Decimal] = Field(default=None, description="Max drawdown %")
    
    # Perpetual futures specific
    leverage: Decimal = Field(default=Decimal("1"), ge=1, description="Leverage (1.0 = spot)")
    margin_type: Literal["isolated", "cross"] = Field(default="cross", description="Margin mode")
    liquidation_price: Optional[Decimal] = Field(default=None, description="Liquidation price")
    
    # Associated data
    orders: List[Order] = Field(default_factory=list, description="Associated orders")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    
    @property
    def is_open(self) -> bool:
        """True if position is currently open."""
        return self.side != PositionSide.NONE and self.amount > 0
    
    @property
    def position_value(self) -> Decimal:
        """Current position value at entry price."""
        return self.entry_price * self.amount
    
    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized PnL at given price.
        
        Args:
            current_price: Current market price
            
        Returns:
            Unrealized profit/loss as Decimal
        """
        if self.side == PositionSide.NONE or self.amount == 0:
            return Decimal("0")
        
        price_diff = current_price - self.entry_price
        
        if self.side == PositionSide.LONG:
            return price_diff * self.amount
        else:  # SHORT
            return -price_diff * self.amount
    
    def calculate_pnl_percentage(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized PnL percentage.
        
        Args:
            current_price: Current market price
            
        Returns:
            PnL percentage (e.g., 5.0 for 5% profit)
        """
        if self.entry_price == 0 or self.amount == 0:
            return Decimal("0")
        
        pnl = self.calculate_unrealized_pnl(current_price)
        position_value = self.entry_price * self.amount
        
        # Adjust for leverage
        margin_used = position_value / self.leverage
        return (pnl / margin_used) * 100 if margin_used > 0 else Decimal("0")
    
    def update_from_fill(self, fill_price: Decimal, fill_amount: Decimal, side: OrderSide) -> None:
        """Update position after an order fill.
        
        Args:
            fill_price: Price of the fill
            fill_amount: Amount filled
            side: Side of the fill (buy increases long, sell increases short)
        """
        # Calculate new average entry price
        if self.side == PositionSide.NONE:
            # New position
            self.entry_price = fill_price
            self.side = PositionSide.LONG if side == OrderSide.BUY else PositionSide.SHORT
        elif (self.side == PositionSide.LONG and side == OrderSide.BUY) or \
             (self.side == PositionSide.SHORT and side == OrderSide.SELL):
            # Adding to position - update average entry
            total_value = (self.entry_price * self.amount) + (fill_price * fill_amount)
            total_amount = self.amount + fill_amount
            self.entry_price = total_value / total_amount
        else:
            # Reducing position - calculate realized PnL
            if fill_amount >= self.amount:
                # Full close
                realized = self.calculate_unrealized_pnl(fill_price)
                self.realized_pnl += realized
                self.side = PositionSide.NONE
                self.amount = Decimal("0")
                self.closed_at = datetime.utcnow()
            else:
                # Partial close
                close_ratio = fill_amount / self.amount
                realized = self.unrealized_pnl * close_ratio
                self.realized_pnl += realized
        
        self.amount += fill_amount if side == OrderSide.BUY else -fill_amount
        self.amount = max(self.amount, Decimal("0"))


# =============================================================================
# Trade Models
# =============================================================================

class Trade(BaseModel):
    """Completed trade record for performance tracking.
    
    Records the full lifecycle of a trade from entry to exit.
    Used for analytics, reporting, and strategy performance.
    
    Attributes:
        symbol: Trading pair
        side: Buy or sell entry
        amount: Trade size
        entry_price: Entry execution price
        exit_price: Exit execution price
        id: Trade ID
        entry_time: Entry timestamp
        exit_time: Exit timestamp
        realized_pnl: Gross realized PnL
        realized_pnl_pct: PnL percentage
        entry_fee: Entry commission
        exit_fee: Exit commission
        total_fee: Total fees paid
        strategy_name: Strategy that generated the trade
        engine_type: Which engine executed the trade
        close_reason: Why the trade closed
        status: Current trade status
        metadata: Additional trade data
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    # Required fields
    symbol: str = Field(..., description="Trading pair")
    side: OrderSide = Field(..., description="Entry side")
    amount: Decimal = Field(..., gt=0, description="Trade size")
    entry_price: Decimal = Field(..., gt=0, description="Entry price")
    
    # Identification
    id: str = Field(default_factory=lambda: str(uuid4()), description="Trade ID")
    
    # Prices
    exit_price: Optional[Decimal] = Field(default=None, description="Exit price")
    
    # Timestamps
    entry_time: datetime = Field(default_factory=datetime.utcnow, description="Entry time")
    exit_time: Optional[datetime] = Field(default=None, description="Exit time")
    
    # PnL
    realized_pnl: Decimal = Field(default=Decimal("0"), description="Gross realized PnL")
    realized_pnl_pct: Decimal = Field(default=Decimal("0"), description="PnL percentage")
    
    # Fees
    entry_fee: Decimal = Field(default=Decimal("0"), ge=0, description="Entry fee")
    exit_fee: Decimal = Field(default=Decimal("0"), ge=0, description="Exit fee")
    
    # Metadata
    strategy_name: str = Field(default="", description="Strategy name")
    engine_type: Optional[EngineType] = Field(default=None, description="Engine type")
    close_reason: str = Field(default="", description="Close reason")
    status: TradeStatus = Field(default=TradeStatus.OPEN, description="Trade status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    
    @property
    def total_fee(self) -> Decimal:
        """Total fees paid for this trade."""
        return self.entry_fee + self.exit_fee
    
    @property
    def net_pnl(self) -> Decimal:
        """Net PnL after fees."""
        return self.realized_pnl - self.total_fee
    
    @property
    def duration(self) -> Optional[float]:
        """Trade duration in seconds (None if still open)."""
        if self.exit_time is None:
            return None
        return (self.exit_time - self.entry_time).total_seconds()
    
    @property
    def is_profitable(self) -> bool:
        """True if trade was profitable (after fees)."""
        return self.net_pnl > 0
    
    def close(self, exit_price: Decimal, exit_time: Optional[datetime] = None,
              reason: str = "signal", exit_fee: Decimal = Decimal("0")) -> None:
        """Close the trade and calculate final PnL.
        
        Args:
            exit_price: Exit execution price
            exit_time: Exit timestamp (defaults to now)
            reason: Why the trade closed
            exit_fee: Exit commission
        """
        self.exit_price = exit_price
        self.exit_time = exit_time or datetime.utcnow()
        self.exit_fee = exit_fee
        self.close_reason = reason
        self.status = TradeStatus.CLOSED
        
        # Calculate PnL
        if self.side == OrderSide.BUY:
            self.realized_pnl = (exit_price - self.entry_price) * self.amount
        else:
            self.realized_pnl = (self.entry_price - exit_price) * self.amount
        
        # Calculate percentage
        entry_value = self.entry_price * self.amount
        if entry_value > 0:
            self.realized_pnl_pct = (self.realized_pnl / entry_value) * 100


# =============================================================================
# Signal Models
# =============================================================================

class TradingSignal(BaseModel):
    """Trading signal generated by a strategy.
    
    Signals are validated by the risk manager before execution.
    Support all 4 engines: CORE-HODL, TREND, FUNDING, TACTICAL.
    
    Attributes:
        symbol: Trading pair
        signal_type: Type of signal (buy, sell, close, etc.)
        strategy_name: Strategy that generated the signal
        engine_type: Which engine this signal belongs to
        timestamp: Signal generation time
        confidence: Signal confidence 0.0-1.0
        metadata: Signal-specific data (entry price, stop loss, etc.)
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    symbol: str = Field(..., description="Trading pair")
    signal_type: SignalType = Field(..., description="Signal type")
    strategy_name: str = Field(..., description="Strategy name")
    engine_type: Optional[EngineType] = Field(default=None, description="Engine type")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Signal time")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence 0-1")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Signal data")
    
    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure Decimal values in metadata are properly handled."""
        # Convert any float prices to Decimal strings for consistency
        for key in ["entry_price", "stop_loss", "take_profit", "size"]:
            if key in v and isinstance(v[key], float):
                v[key] = str(Decimal(str(v[key])))
        return v
    
    @property
    def is_entry(self) -> bool:
        """True if this is an entry signal."""
        return self.signal_type in (SignalType.BUY, SignalType.SELL)
    
    @property
    def is_exit(self) -> bool:
        """True if this is an exit signal."""
        return self.signal_type in (
            SignalType.CLOSE, SignalType.CLOSE_LONG, 
            SignalType.CLOSE_SHORT, SignalType.EMERGENCY_EXIT
        )
    
    def get_entry_price(self) -> Optional[Decimal]:
        """Get suggested entry price from metadata."""
        price = self.metadata.get("entry_price")
        return Decimal(price) if price is not None else None
    
    def get_stop_loss(self) -> Optional[Decimal]:
        """Get suggested stop loss from metadata."""
        sl = self.metadata.get("stop_loss")
        return Decimal(sl) if sl is not None else None
    
    def get_take_profit(self) -> Optional[Decimal]:
        """Get suggested take profit from metadata."""
        tp = self.metadata.get("take_profit")
        return Decimal(tp) if tp is not None else None


# =============================================================================
# Risk Management Models
# =============================================================================

class RiskCheck(BaseModel):
    """Result of risk validation for a trading signal.
    
    The risk manager validates all signals before execution.
    Failed signals include the reason for rejection.
    
    Attributes:
        passed: True if signal passes all risk checks
        reason: Reason for rejection (if failed)
        max_position_size: Approved position size (may be reduced)
        approved_leverage: Approved leverage level
        circuit_breaker_level: Current circuit breaker state
        adjusted_stop_loss: Risk-adjusted stop loss
        adjusted_take_profit: Risk-adjusted take profit
        checks_performed: List of checks that were run
        metadata: Additional risk data
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    passed: bool = Field(..., description="Whether signal passed risk checks")
    reason: Optional[str] = Field(default=None, description="Rejection reason")
    
    # Adjusted parameters
    max_position_size: Optional[Decimal] = Field(default=None, description="Approved size")
    approved_leverage: Optional[Decimal] = Field(default=None, description="Approved leverage")
    
    # Circuit breaker state
    circuit_breaker_level: CircuitBreakerLevel = Field(
        default=CircuitBreakerLevel.NONE, 
        description="Active circuit breaker level"
    )
    
    # Adjusted risk levels
    adjusted_stop_loss: Optional[Decimal] = Field(default=None, description="Adjusted stop")
    adjusted_take_profit: Optional[Decimal] = Field(default=None, description="Adjusted TP")
    
    # Audit trail
    checks_performed: List[str] = Field(default_factory=list, description="Checks performed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check time")
    
    @property
    def is_rejected(self) -> bool:
        """True if signal was rejected."""
        return not self.passed
    
    @classmethod
    def approved(cls, **kwargs) -> "RiskCheck":
        """Create an approved risk check result."""
        return cls(passed=True, **kwargs)
    
    @classmethod
    def rejected(cls, reason: str, **kwargs) -> "RiskCheck":
        """Create a rejected risk check result."""
        return cls(passed=False, reason=reason, **kwargs)


# =============================================================================
# Portfolio Models
# =============================================================================

class Portfolio(BaseModel):
    """Portfolio state tracking for risk management and reporting.
    
    Tracks balances, positions, PnL, and exposure across all engines.
    
    Attributes:
        total_balance: Total portfolio value in USD
        available_balance: Unallocated cash
        positions: Current positions by symbol
        daily_pnl: Today's realized PnL
        weekly_pnl: This week's realized PnL
        monthly_pnl: This month's realized PnL
        daily_starting_balance: Balance at start of day
        weekly_starting_balance: Balance at start of week
        monthly_starting_balance: Balance at start of month
        all_time_high: Portfolio ATH
        max_drawdown_pct: Current drawdown from ATH
        timestamp: Last update time
        metadata: Additional portfolio data
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    # Balances
    total_balance: Decimal = Field(..., ge=0, description="Total portfolio value")
    available_balance: Decimal = Field(..., ge=0, description="Available cash")
    
    # Positions
    positions: Dict[str, Position] = Field(default_factory=dict, description="Positions")
    
    # PnL tracking
    daily_pnl: Decimal = Field(default=Decimal("0"), description="Today's PnL")
    weekly_pnl: Decimal = Field(default=Decimal("0"), description="This week's PnL")
    monthly_pnl: Decimal = Field(default=Decimal("0"), description="This month's PnL")
    yearly_pnl: Decimal = Field(default=Decimal("0"), description="This year's PnL")
    
    # Starting balances for PnL calc
    daily_starting_balance: Decimal = Field(default=Decimal("0"), description="Day start balance")
    weekly_starting_balance: Decimal = Field(default=Decimal("0"), description="Week start balance")
    monthly_starting_balance: Decimal = Field(default=Decimal("0"), description="Month start balance")
    yearly_starting_balance: Decimal = Field(default=Decimal("0"), description="Year start balance")
    
    # Drawdown tracking
    all_time_high: Decimal = Field(default=Decimal("0"), description="Portfolio ATH")
    max_drawdown_pct: Decimal = Field(default=Decimal("0"), description="Max drawdown %")
    
    # Engine allocations
    engine_allocations: Dict[EngineType, Decimal] = Field(
        default_factory=dict, 
        description="Capital allocation per engine"
    )
    engine_values: Dict[EngineType, Decimal] = Field(
        default_factory=dict,
        description="Current value per engine"
    )
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Last update")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    
    @property
    def used_balance(self) -> Decimal:
        """Balance allocated to positions."""
        return self.total_balance - self.available_balance
    
    @property
    def exposure_pct(self) -> Decimal:
        """Percentage of portfolio in positions."""
        if self.total_balance == 0:
            return Decimal("0")
        return (self.used_balance / self.total_balance) * 100
    
    @property
    def current_drawdown_pct(self) -> Decimal:
        """Current drawdown from ATH."""
        if self.all_time_high == 0:
            return Decimal("0")
        return ((self.all_time_high - self.total_balance) / self.all_time_high) * 100
    
    @property
    def total_unrealized_pnl(self) -> Decimal:
        """Sum of unrealized PnL across all positions."""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    @property
    def total_realized_pnl(self) -> Decimal:
        """Sum of realized PnL across all positions."""
        return sum(pos.realized_pnl for pos in self.positions.values())
    
    def update_ath(self) -> None:
        """Update all-time high and recalculate drawdown."""
        if self.total_balance > self.all_time_high:
            self.all_time_high = self.total_balance
        if self.all_time_high > 0:
            self.max_drawdown_pct = ((self.all_time_high - self.total_balance) / self.all_time_high) * 100
    
    def get_engine_exposure(self, engine: EngineType) -> Decimal:
        """Get exposure percentage for a specific engine."""
        value = self.engine_values.get(engine, Decimal("0"))
        if self.total_balance == 0:
            return Decimal("0")
        return (value / self.total_balance) * 100
    
    def calculate_total_equity(self, current_prices: Dict[str, Decimal]) -> Decimal:
        """Calculate total equity including unrealized PnL.
        
        Args:
            current_prices: Dictionary of symbol -> current price
            
        Returns:
            Total portfolio equity
        """
        unrealized = Decimal("0")
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                unrealized += position.calculate_unrealized_pnl(current_prices[symbol])
        return self.total_balance + unrealized


# =============================================================================
# Engine State Models
# =============================================================================

class EngineState(BaseModel):
    """State tracking for each of the 4 engines.
    
    Tracks operational status, performance, and configuration for each engine.
    
    Attributes:
        engine_type: Which engine this state represents
        is_active: Whether engine is currently active
        is_paused: Whether engine is manually paused
        current_allocation_pct: Current capital allocation
        current_value: Current portfolio value for this engine
        total_trades: Total number of trades
        winning_trades: Number of profitable trades
        losing_trades: Number of losing trades
        total_pnl: Total realized PnL
        max_drawdown_pct: Max drawdown experienced
        circuit_breaker_level: Current circuit breaker state
        last_trade_time: Timestamp of last trade
        error_count: Number of consecutive errors
        last_error: Last error message
        config: Engine-specific configuration
        metadata: Additional engine data
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    # Engine identification
    engine_type: EngineType = Field(..., description="Engine type")
    
    # Operational status
    is_active: bool = Field(default=True, description="Engine active")
    is_paused: bool = Field(default=False, description="Manually paused")
    pause_reason: Optional[str] = Field(default=None, description="Pause reason")
    pause_until: Optional[datetime] = Field(default=None, description="Auto-resume time")
    
    # Financial state
    current_allocation_pct: Decimal = Field(default=Decimal("0"), description="Allocation %")
    current_value: Decimal = Field(default=Decimal("0"), description="Current value")
    cash_buffer: Decimal = Field(default=Decimal("0"), description="Cash reserves")
    
    # Performance tracking
    total_trades: int = Field(default=0, ge=0, description="Total trades")
    winning_trades: int = Field(default=0, ge=0, description="Winners")
    losing_trades: int = Field(default=0, ge=0, description="Losers")
    total_pnl: Decimal = Field(default=Decimal("0"), description="Total PnL")
    total_fees: Decimal = Field(default=Decimal("0"), description="Total fees")
    max_drawdown_pct: Decimal = Field(default=Decimal("0"), description="Max drawdown %")
    
    # Circuit breaker
    circuit_breaker_level: CircuitBreakerLevel = Field(
        default=CircuitBreakerLevel.NONE,
        description="Active circuit breaker"
    )
    
    # Error tracking
    error_count: int = Field(default=0, ge=0, description="Consecutive errors")
    last_error: Optional[str] = Field(default=None, description="Last error")
    last_error_time: Optional[datetime] = Field(default=None, description="Error timestamp")
    
    # Activity tracking
    last_trade_time: Optional[datetime] = Field(default=None, description="Last trade")
    last_signal_time: Optional[datetime] = Field(default=None, description="Last signal")
    last_update_time: datetime = Field(default_factory=datetime.utcnow, description="Last update")
    
    # Configuration
    config: Dict[str, Any] = Field(default_factory=dict, description="Engine config")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    
    @property
    def win_rate(self) -> Decimal:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return Decimal("0")
        return (Decimal(self.winning_trades) / Decimal(self.total_trades)) * 100
    
    @property
    def profit_factor(self) -> Optional[Decimal]:
        """Calculate profit factor (gross profit / gross loss)."""
        gross_profit = self.metadata.get("gross_profit", Decimal("0"))
        gross_loss = self.metadata.get("gross_loss", Decimal("0"))
        if gross_loss == 0:
            return None if gross_profit == 0 else Decimal("inf")
        return gross_profit / abs(gross_loss)
    
    @property
    def can_trade(self) -> bool:
        """True if engine can currently trade."""
        if not self.is_active or self.is_paused:
            return False
        if self.circuit_breaker_level in (CircuitBreakerLevel.LEVEL_3, CircuitBreakerLevel.LEVEL_4):
            return False
        if self.pause_until and datetime.utcnow() < self.pause_until:
            return False
        return True
    
    def record_trade(self, trade: Trade) -> None:
        """Record a completed trade in engine statistics."""
        self.total_trades += 1
        self.total_pnl += trade.net_pnl
        self.total_fees += trade.total_fee
        
        if trade.is_profitable:
            self.winning_trades += 1
            self.metadata["gross_profit"] = self.metadata.get("gross_profit", Decimal("0")) + trade.net_pnl
        else:
            self.losing_trades += 1
            self.metadata["gross_loss"] = self.metadata.get("gross_loss", Decimal("0")) + trade.net_pnl
        
        self.last_trade_time = datetime.utcnow()
        self.last_update_time = datetime.utcnow()
    
    def record_error(self, error_message: str) -> None:
        """Record an error and increment error count."""
        self.error_count += 1
        self.last_error = error_message
        self.last_error_time = datetime.utcnow()
        self.last_update_time = datetime.utcnow()
    
    def clear_errors(self) -> None:
        """Clear error count after successful operation."""
        self.error_count = 0
        self.last_error = None
    
    def pause(self, reason: str, duration_seconds: Optional[int] = None) -> None:
        """Pause the engine.
        
        Args:
            reason: Why the engine is being paused
            duration_seconds: Auto-resume after this many seconds (None = indefinite)
        """
        self.is_paused = True
        self.pause_reason = reason
        if duration_seconds:
            self.pause_until = datetime.utcnow() + __import__("datetime").timedelta(seconds=duration_seconds)
    
    def resume(self) -> None:
        """Resume the engine from pause."""
        self.is_paused = False
        self.pause_reason = None
        self.pause_until = None


# =============================================================================
# System State Model
# =============================================================================

class SystemState(BaseModel):
    """Complete system state snapshot.
    
    Used for persistence, monitoring, and recovery.
    
    Attributes:
        timestamp: Snapshot timestamp
        portfolio: Global portfolio state
        engines: State for each of the 4 engines
        positions: All open positions
        orders: Active orders
        circuit_breaker_level: Global circuit breaker state
        is_trading_halted: Whether all trading is stopped
        metadata: Additional system data
    """
    model_config = ConfigDict(json_encoders={Decimal: str})
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    portfolio: Portfolio
    engines: Dict[EngineType, EngineState] = Field(default_factory=dict)
    positions: Dict[str, Position] = Field(default_factory=dict)
    orders: List[Order] = Field(default_factory=list)
    circuit_breaker_level: CircuitBreakerLevel = Field(default=CircuitBreakerLevel.NONE)
    is_trading_halted: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def all_engines_active(self) -> bool:
        """True if all engines are active and can trade."""
        return all(engine.can_trade for engine in self.engines.values())
    
    @property
    def total_exposure_pct(self) -> Decimal:
        """Total portfolio exposure percentage."""
        return self.portfolio.exposure_pct


# =============================================================================
# Utility Functions
# =============================================================================

def create_market_order(
    symbol: str, 
    side: OrderSide, 
    amount: Decimal,
    **kwargs
) -> Order:
    """Factory function to create a market order.
    
    Args:
        symbol: Trading pair
        side: Buy or sell
        amount: Order quantity
        **kwargs: Additional order parameters
        
    Returns:
        Configured market order
    """
    return Order(
        symbol=symbol,
        side=side,
        order_type=OrderType.MARKET,
        amount=amount,
        **kwargs
    )


def create_limit_order(
    symbol: str,
    side: OrderSide,
    amount: Decimal,
    price: Decimal,
    **kwargs
) -> Order:
    """Factory function to create a limit order.
    
    Args:
        symbol: Trading pair
        side: Buy or sell
        amount: Order quantity
        price: Limit price
        **kwargs: Additional order parameters
        
    Returns:
        Configured limit order
    """
    return Order(
        symbol=symbol,
        side=side,
        order_type=OrderType.LIMIT,
        amount=amount,
        price=price,
        **kwargs
    )


def create_buy_signal(
    symbol: str,
    strategy_name: str,
    confidence: float = 0.5,
    entry_price: Optional[Decimal] = None,
    stop_loss: Optional[Decimal] = None,
    take_profit: Optional[Decimal] = None,
    engine_type: Optional[EngineType] = None,
    **kwargs
) -> TradingSignal:
    """Factory function to create a buy signal.
    
    Args:
        symbol: Trading pair
        strategy_name: Strategy name
        confidence: Signal confidence 0-1
        entry_price: Suggested entry price
        stop_loss: Suggested stop loss
        take_profit: Suggested take profit
        engine_type: Which engine
        **kwargs: Additional metadata
        
    Returns:
        Configured buy signal
    """
    metadata = {
        "entry_price": str(entry_price) if entry_price else None,
        "stop_loss": str(stop_loss) if stop_loss else None,
        "take_profit": str(take_profit) if take_profit else None,
        **kwargs
    }
    return TradingSignal(
        symbol=symbol,
        signal_type=SignalType.BUY,
        strategy_name=strategy_name,
        engine_type=engine_type,
        confidence=confidence,
        metadata=metadata
    )
