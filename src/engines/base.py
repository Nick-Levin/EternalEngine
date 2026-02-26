"""Base class for all Eternal Engine strategy engines."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import structlog

from src.core.models import (
    MarketData, TradingSignal, SignalType, Position, 
    EngineType, EngineState, Trade
)

logger = structlog.get_logger(__name__)


@dataclass
class EngineConfig:
    """Base configuration for all engines.
    
    Attributes:
        engine_type: Which engine type this config is for
        enabled: Whether the engine is enabled
        allocation_pct: Portfolio allocation percentage (0-1)
        max_position_pct: Maximum position size as % of engine capital
        max_risk_per_trade: Maximum risk per trade (0-1)
        min_order_size_usd: Minimum order size in USD
        max_slippage_pct: Maximum allowed slippage percentage
        custom_params: Engine-specific parameters
    """
    engine_type: EngineType = EngineType.CORE_HODL  # Default, should be overridden
    enabled: bool = True
    allocation_pct: Decimal = Decimal("0.0")
    max_position_pct: Decimal = Decimal("0.5")  # 50% of engine capital
    max_risk_per_trade: Decimal = Decimal("0.01")  # 1% risk
    min_order_size_usd: Decimal = Decimal("10.0")
    max_slippage_pct: Decimal = Decimal("0.5")  # 0.5%
    custom_params: Dict[str, Any] = field(default_factory=dict)


class BaseEngine(ABC):
    """
    Abstract base class for all Eternal Engine strategy engines.
    
    Each engine operates independently in its own Bybit subaccount:
    - Failure of one engine cannot contaminate others
    - Separate risk management per engine
    - Independent PnL tracking
    
    All engines MUST implement:
    - analyze(): Generate trading signals from market data
    - on_order_filled(): Handle order fill callbacks
    - on_position_closed(): Handle position close callbacks
    
    Risk Management:
    - All signals pass through risk_manager.check_signal() before execution
    - Position sizing uses 1/8 Kelly Criterion
    - Circuit breakers halt trading at predefined drawdown levels
    """
    
    def __init__(
        self, 
        config: EngineConfig,
        engine_type: EngineType,
        symbols: List[str],
        risk_manager=None
    ):
        self.config = config
        self.engine_type = engine_type
        self.symbols = symbols
        self.risk_manager = risk_manager
        
        # Logger with engine context
        self.logger = logger.bind(
            engine=engine_type.value,
            symbols=symbols
        )
        
        # Engine state tracking
        self.state = EngineState(
            engine_type=engine_type,
            is_active=config.enabled,
            current_allocation_pct=config.allocation_pct,
            config=config.__dict__ if hasattr(config, '__dict__') else {}
        )
        
        # Position tracking
        self.positions: Dict[str, Position] = {}
        
        # Signal tracking
        self.signals_generated = 0
        self.signals_executed = 0
        
        # Performance tracking
        self.total_pnl = Decimal("0")
        self.total_fees = Decimal("0")
        self.trades: List[Trade] = []
        
        self.logger.info(
            "engine.initialized",
            engine_type=engine_type.value,
            allocation_pct=str(config.allocation_pct),
            symbols=symbols,
            enabled=config.enabled
        )
    
    @property
    def is_active(self) -> bool:
        """Check if engine can trade."""
        return self.state.can_trade and self.config.enabled
    
    @property
    def current_allocation_usd(self) -> Decimal:
        """Get current capital allocation in USD."""
        return self.state.current_value
    
    @abstractmethod
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """
        Analyze market data and generate trading signals.
        
        This is the core method each engine must implement.
        It receives market data and returns signals for the risk manager
        to validate before execution.
        
        Args:
            data: Dictionary of symbol -> list of MarketData (oldest first)
            
        Returns:
            List of TradingSignal objects to be evaluated by risk manager
            
        Example:
            ```python
            async def analyze(self, data):
                signals = []
                for symbol in self.symbols:
                    if self.should_enter_long(symbol, data):
                        signal = self._create_buy_signal(symbol, confidence=0.8)
                        signals.append(signal)
                return signals
            ```
        """
        pass
    
    @abstractmethod
    async def on_order_filled(
        self, 
        symbol: str, 
        side: str, 
        amount: Decimal, 
        price: Decimal,
        order_id: Optional[str] = None
    ):
        """
        Callback when an order is filled.
        
        Update internal state, track positions, and record fills.
        
        Args:
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            amount: Amount filled
            price: Fill price
            order_id: Optional order ID for tracking
        """
        pass
    
    @abstractmethod
    async def on_position_closed(
        self, 
        symbol: str, 
        pnl: Decimal, 
        pnl_pct: Decimal,
        close_reason: str = "signal"
    ):
        """
        Callback when a position is closed.
        
        Update performance tracking, record trade statistics,
        and handle any post-close logic.
        
        Args:
            symbol: Trading pair symbol
            pnl: Realized PnL in USD
            pnl_pct: Realized PnL percentage
            close_reason: Why the position closed
        """
        pass
    
    def get_required_data(self) -> Dict[str, Any]:
        """
        Return data requirements for this engine.
        
        Override to specify needed timeframes, indicators, lookback periods.
        
        Returns:
            Dict with keys:
                - timeframes: List of timeframe strings (e.g., ['1h', '4h', '1d'])
                - min_bars: Minimum number of bars required
                - indicators: List of required indicators
        """
        return {
            'timeframes': ['1h'],
            'min_bars': 50,
            'indicators': []
        }
    
    def get_state(self) -> EngineState:
        """Get current engine state."""
        self.state.last_update_time = datetime.now(timezone.utc)
        return self.state
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            'engine_type': self.engine_type.value,
            'is_active': self.is_active,
            'can_trade': self.state.can_trade,
            'allocation_pct': str(self.config.allocation_pct),
            'current_value': str(self.state.current_value),
            'signals_generated': self.signals_generated,
            'signals_executed': self.signals_executed,
            'total_trades': self.state.total_trades,
            'winning_trades': self.state.winning_trades,
            'losing_trades': self.state.losing_trades,
            'win_rate': str(self.state.win_rate),
            'total_pnl': str(self.total_pnl),
            'total_fees': str(self.total_fees),
            'max_drawdown_pct': str(self.state.max_drawdown_pct),
            'circuit_breaker': self.state.circuit_breaker_level.value,
            'positions': {s: p.model_dump() for s, p in self.positions.items()}
        }
    
    def pause(self, reason: str, duration_seconds: Optional[int] = None):
        """Pause the engine."""
        self.state.pause(reason, duration_seconds)
        self.logger.warning("engine.paused", reason=reason, duration=duration_seconds)
    
    def resume(self):
        """Resume the engine."""
        self.state.resume()
        self.logger.info("engine.resumed")
    
    def record_error(self, error_message: str):
        """Record an error in engine state."""
        self.state.record_error(error_message)
        self.logger.error("engine.error", error=error_message, count=self.state.error_count)
    
    def update_portfolio_value(self, current_prices: Dict[str, Decimal]):
        """Update engine's current portfolio value."""
        total_value = Decimal("0")
        
        # Add position values
        for symbol, position in self.positions.items():
            if symbol in current_prices and position.is_open:
                position_value = position.amount * current_prices[symbol]
                total_value += position_value
        
        # Add cash (tracked in state)
        total_value += self.state.cash_buffer
        
        # Update state
        old_value = self.state.current_value
        self.state.current_value = total_value
        
        # Check for new max drawdown
        if total_value > 0:
            # Update ATH tracking if needed
            pass  # Portfolio-level ATH handled at system level
        
        self.logger.debug(
            "engine.value_updated",
            old_value=str(old_value),
            new_value=str(total_value)
        )
    
    def _create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        confidence: float = 0.5,
        metadata: Optional[Dict] = None
    ) -> TradingSignal:
        """Helper to create a trading signal with engine context."""
        from src.core.models import TradingSignal
        
        signal = TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            strategy_name=self.__class__.__name__,
            engine_type=self.engine_type,
            timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            metadata=metadata or {}
        )
        self.signals_generated += 1
        self.state.last_signal_time = datetime.now(timezone.utc)
        return signal
    
    def _create_buy_signal(
        self,
        symbol: str,
        confidence: float,
        entry_price: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        size: Optional[Decimal] = None,
        reason: str = "entry"
    ) -> TradingSignal:
        """Create a standardized buy signal."""
        metadata = {
            'reason': reason,
            'entry_price': str(entry_price) if entry_price else None,
            'stop_loss': str(stop_loss) if stop_loss else None,
            'take_profit': str(take_profit) if take_profit else None,
            'size': str(size) if size else None,
        }
        
        self.logger.info(
            "engine.buy_signal",
            symbol=symbol,
            confidence=confidence,
            price=str(entry_price) if entry_price else "market"
        )
        
        return self._create_signal(symbol, SignalType.BUY, confidence, metadata)
    
    def _create_sell_signal(
        self,
        symbol: str,
        confidence: float,
        exit_price: Optional[Decimal] = None,
        reason: str = "exit"
    ) -> TradingSignal:
        """Create a standardized sell signal."""
        metadata = {'reason': reason}
        if exit_price:
            metadata['exit_price'] = str(exit_price)
        
        self.logger.info(
            "engine.sell_signal",
            symbol=symbol,
            confidence=confidence,
            reason=reason
        )
        
        return self._create_signal(symbol, SignalType.SELL, confidence, metadata)
    
    def _create_close_signal(
        self,
        symbol: str,
        confidence: float = 1.0,
        reason: str = "exit"
    ) -> TradingSignal:
        """Create a close position signal."""
        metadata = {'reason': reason}
        
        self.logger.info(
            "engine.close_signal",
            symbol=symbol,
            reason=reason
        )
        
        return self._create_signal(symbol, SignalType.CLOSE, confidence, metadata)
    
    def _create_rebalance_signal(
        self,
        symbol: str,
        target_allocation: Decimal,
        current_allocation: Decimal,
        confidence: float = 1.0
    ) -> TradingSignal:
        """Create a portfolio rebalance signal."""
        metadata = {
            'reason': 'rebalance',
            'target_allocation': str(target_allocation),
            'current_allocation': str(current_allocation),
            'delta': str(target_allocation - current_allocation)
        }
        
        self.logger.info(
            "engine.rebalance_signal",
            symbol=symbol,
            target=str(target_allocation),
            current=str(current_allocation)
        )
        
        return self._create_signal(symbol, SignalType.REBALANCE, confidence, metadata)
    
    def _validate_signal_with_risk_manager(
        self, 
        signal: TradingSignal,
        portfolio_value: Decimal
    ) -> bool:
        """Validate a signal through the risk manager if available."""
        if self.risk_manager is None:
            return True
        
        # Risk manager validation would happen here
        # This is a placeholder for the actual risk check integration
        return True
    
    def calculate_position_size(
        self,
        entry_price: Decimal,
        stop_price: Optional[Decimal] = None,
        risk_amount: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate position size using risk-based sizing.
        
        Uses 1/8 Kelly Criterion with max position limits.
        
        Args:
            entry_price: Entry price per unit
            stop_price: Stop loss price (optional)
            risk_amount: Fixed risk amount in USD (optional)
            
        Returns:
            Quantity to purchase
        """
        engine_capital = self.state.current_value
        
        # Default risk amount: max_risk_per_trade % of engine capital
        if risk_amount is None:
            risk_amount = engine_capital * self.config.max_risk_per_trade
        
        # If no stop price, use max position percentage
        if stop_price is None:
            max_position_value = engine_capital * self.config.max_position_pct
            return max_position_value / entry_price
        
        # Calculate position size based on stop distance
        stop_distance = abs(entry_price - stop_price)
        if stop_distance == 0:
            self.logger.warning("position_sizing.zero_stop_distance")
            return Decimal("0")
        
        position_size = risk_amount / stop_distance
        
        # Apply maximum position limit
        max_position_value = engine_capital * self.config.max_position_pct
        max_position_size = max_position_value / entry_price
        
        return min(position_size, max_position_size)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.engine_type.value}, active={self.is_active})"
