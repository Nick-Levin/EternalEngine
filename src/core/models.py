"""Data models for the trading bot."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


@dataclass
class MarketData:
    """Market data snapshot."""
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timeframe: str = "1h"
    
    # Additional indicators
    indicators: Dict[str, Decimal] = field(default_factory=dict)


@dataclass
class TradingSignal:
    """Trading signal from a strategy."""
    symbol: str
    signal_type: SignalType
    strategy_name: str
    timestamp: datetime
    confidence: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")


@dataclass
class Order:
    """Order representation."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: Decimal
    price: Optional[Decimal] = None
    
    # Order identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    exchange_order_id: Optional[str] = None
    
    # Order status
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: Decimal = field(default=Decimal("0"))
    average_price: Optional[Decimal] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # Risk management
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    
    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def remaining_amount(self) -> Decimal:
        return self.amount - self.filled_amount
    
    @property
    def is_filled(self) -> bool:
        return self.filled_amount >= self.amount
    
    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)


@dataclass
class Position:
    """Position representation."""
    symbol: str
    side: PositionSide
    entry_price: Decimal
    amount: Decimal
    
    # Position identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Timestamps
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    # Current state
    unrealized_pnl: Decimal = field(default=Decimal("0"))
    realized_pnl: Decimal = field(default=Decimal("0"))
    
    # Risk management
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    max_drawdown_pct: Optional[Decimal] = None
    
    # Orders associated with this position
    orders: List[Order] = field(default_factory=list)
    
    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized PnL."""
        if self.side == PositionSide.LONG:
            return (current_price - self.entry_price) * self.amount
        elif self.side == PositionSide.SHORT:
            return (self.entry_price - current_price) * self.amount
        return Decimal("0")
    
    def calculate_pnl_pct(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized PnL percentage."""
        if self.entry_price == 0:
            return Decimal("0")
        pnl = self.calculate_pnl(current_price)
        position_value = self.entry_price * self.amount
        return (pnl / position_value) * 100


@dataclass
class Portfolio:
    """Portfolio state."""
    total_balance: Decimal
    available_balance: Decimal
    
    # Track positions
    positions: Dict[str, Position] = field(default_factory=dict)
    
    # Daily/Weekly tracking
    daily_pnl: Decimal = field(default=Decimal("0"))
    weekly_pnl: Decimal = field(default=Decimal("0"))
    daily_starting_balance: Decimal = field(default=Decimal("0"))
    weekly_starting_balance: Decimal = field(default=Decimal("0"))
    
    @property
    def used_balance(self) -> Decimal:
        return self.total_balance - self.available_balance
    
    @property
    def exposure_pct(self) -> Decimal:
        if self.total_balance == 0:
            return Decimal("0")
        return (self.used_balance / self.total_balance) * 100


@dataclass
class Trade:
    """Completed trade record."""
    symbol: str
    side: OrderSide
    amount: Decimal
    entry_price: Decimal
    exit_price: Decimal
    
    # Trade identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Timestamps
    entry_time: datetime = field(default_factory=datetime.utcnow)
    exit_time: Optional[datetime] = None
    
    # PnL
    realized_pnl: Decimal = field(default=Decimal("0"))
    realized_pnl_pct: Decimal = field(default=Decimal("0"))
    
    # Fees
    entry_fee: Decimal = field(default=Decimal("0"))
    exit_fee: Decimal = field(default=Decimal("0"))
    total_fee: Decimal = field(default=Decimal("0"))
    
    # Metadata
    strategy_name: str = ""
    close_reason: str = ""  # stop_loss, take_profit, signal, manual
    
    @property
    def net_pnl(self) -> Decimal:
        return self.realized_pnl - self.total_fee
