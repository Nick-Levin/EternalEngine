"""
Dollar-Cost Averaging (DCA) Strategy

This is the most conservative strategy - it invests a fixed amount
at regular intervals regardless of price, reducing timing risk.
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import structlog

from src.core.models import MarketData, TradingSignal, SignalType, Position
from src.core.config import strategy_config
from src.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class DCAStrategy(BaseStrategy):
    """
    Dollar-Cost Averaging Strategy.
    
    Strategy Logic:
    - Buy fixed USD amount every X hours
    - No sell signals (long-term accumulation)
    - Ignores price action completely
    - Reduces timing risk through regularity
    
    Risk Level: VERY LOW
    Best For: Long-term crypto accumulation
    """
    
    def __init__(self, symbols: List[str], **kwargs):
        super().__init__("DCA", symbols, **kwargs)
        
        # DCA configuration
        self.interval_hours = kwargs.get(
            'interval_hours', 
            strategy_config.dca_interval_hours
        )
        self.amount_usdt = kwargs.get(
            'amount_usdt', 
            strategy_config.dca_amount_usdt
        )
        
        # Track last purchase time per symbol
        self.last_purchase: Dict[str, datetime] = {}
        
        # Statistics
        self.total_invested: Dict[str, Decimal] = {s: Decimal("0") for s in symbols}
        self.purchase_count: Dict[str, int] = {s: 0 for s in symbols}
        
        self.logger.info(
            "dca_strategy.initialized",
            interval_hours=self.interval_hours,
            amount_usdt=self.amount_usdt,
            symbols=symbols
        )
    
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """
        Generate buy signals at regular intervals.
        """
        signals = []
        now = datetime.utcnow()
        
        for symbol in self.symbols:
            if symbol not in data or not data[symbol]:
                continue
            
            last_price = data[symbol][-1].close
            
            # Check if it's time for next purchase
            last_purchase = self.last_purchase.get(symbol)
            
            if last_purchase is None:
                # First purchase - create signal
                signals.append(self._create_buy_signal(symbol, last_price, "initial"))
            else:
                time_since_last = now - last_purchase
                if time_since_last >= timedelta(hours=self.interval_hours):
                    signals.append(self._create_buy_signal(symbol, last_price, "scheduled"))
        
        return signals
    
    def _create_buy_signal(
        self, 
        symbol: str, 
        price: Decimal, 
        reason: str
    ) -> TradingSignal:
        """Create a DCA buy signal."""
        metadata = {
            'strategy': 'DCA',
            'amount_usdt': float(self.amount_usdt),
            'current_price': float(price),
            'reason': reason,
            'interval_hours': self.interval_hours
        }
        
        self.logger.info(
            "dca_strategy.signal",
            symbol=symbol,
            price=str(price),
            reason=reason
        )
        
        return self._create_signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            confidence=1.0,  # DCA is deterministic
            metadata=metadata
        )
    
    async def on_order_filled(
        self, 
        symbol: str, 
        side: str, 
        amount: Decimal, 
        price: Decimal
    ):
        """Track DCA purchases."""
        if side == "buy":
            self.last_purchase[symbol] = datetime.utcnow()
            self.total_invested[symbol] += amount * price
            self.purchase_count[symbol] += 1
            
            self.logger.info(
                "dca_strategy.purchase_recorded",
                symbol=symbol,
                amount=str(amount),
                price=str(price),
                total_invested=str(self.total_invested[symbol]),
                purchase_count=self.purchase_count[symbol]
            )
    
    async def on_position_closed(
        self, 
        symbol: str, 
        pnl: Decimal, 
        pnl_pct: Decimal
    ):
        """Track position close (rarely used in DCA)."""
        self.total_pnl += pnl
        self.logger.info(
            "dca_strategy.position_closed",
            symbol=symbol,
            pnl=str(pnl),
            pnl_pct=str(pnl_pct)
        )
    
    def get_time_to_next_purchase(self, symbol: str) -> Optional[timedelta]:
        """Get time remaining until next scheduled purchase."""
        if symbol not in self.last_purchase:
            return timedelta(0)
        
        next_purchase = self.last_purchase[symbol] + timedelta(hours=self.interval_hours)
        remaining = next_purchase - datetime.utcnow()
        
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
    
    def get_stats(self) -> Dict:
        """Get DCA strategy statistics."""
        base_stats = super().get_stats()
        base_stats.update({
            'interval_hours': self.interval_hours,
            'amount_usdt': float(self.amount_usdt),
            'total_invested': {k: str(v) for k, v in self.total_invested.items()},
            'purchase_count': self.purchase_count,
            'avg_investment_per_symbol': {
                    k: str(v / self.purchase_count[k]) if self.purchase_count[k] > 0 else "0"
                    for k, v in self.total_invested.items()
                }
        })
        return base_stats
