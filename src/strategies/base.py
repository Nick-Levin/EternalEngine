"""Base class for all trading strategies."""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import structlog

from src.core.models import MarketData, TradingSignal, SignalType, Position

logger = structlog.get_logger(__name__)


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""
    
    def __init__(self, name: str, symbols: List[str], **kwargs):
        self.name = name
        self.symbols = symbols
        self.params = kwargs
        self.is_active = True
        self.logger = logger.bind(strategy=name)
        
        # Track strategy performance
        self.signals_generated = 0
        self.trades_executed = 0
        self.total_pnl = Decimal("0")
        
    @abstractmethod
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
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
        """Callback when an order is filled."""
        pass
    
    @abstractmethod
    async def on_position_closed(
        self, 
        symbol: str, 
        pnl: Decimal, 
        pnl_pct: Decimal
    ):
        """Callback when a position is closed."""
        pass
    
    def get_required_data(self) -> Dict[str, Any]:
        """
        Return data requirements for this strategy.
        Override to specify needed timeframes, indicators, etc.
        """
        return {
            'timeframes': ['1h'],
            'min_bars': 50,
            'indicators': []
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            'name': self.name,
            'symbols': self.symbols,
            'is_active': self.is_active,
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'total_pnl': str(self.total_pnl)
        }
    
    def pause(self):
        """Pause the strategy."""
        self.is_active = False
        self.logger.info("strategy.paused")
    
    def resume(self):
        """Resume the strategy."""
        self.is_active = True
        self.logger.info("strategy.resumed")
    
    def _create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        confidence: float = 0.5,
        metadata: Optional[Dict] = None
    ) -> TradingSignal:
        """Helper to create a trading signal."""
        signal = TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            strategy_name=self.name,
            timestamp=datetime.utcnow(),
            confidence=confidence,
            metadata=metadata or {}
        )
        self.signals_generated += 1
        return signal
