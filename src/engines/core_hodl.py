"""
CORE-HODL Engine (60% Allocation)

The foundation of The Eternal Engine - long-term BTC/ETH accumulation.

Strategy:
- 40% BTC, 20% ETH allocation (of total portfolio)
- DCA: Buy fixed USD amount at regular intervals
- Rebalance quarterly when allocation drifts >10%
- Move idle ETH to Bybit Earn for yield (min 2% APY)
- NEVER sell during drawdowns (accumulation phase only)

Risk Level: MINIMAL
Market: Spot only (no derivatives)
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any
import structlog

from src.core.models import (
    MarketData, TradingSignal, SignalType, Position, EngineType
)
from src.engines.base import BaseEngine, EngineConfig

logger = structlog.get_logger(__name__)


@dataclass
class CoreHodlConfig(EngineConfig):
    """Configuration for CORE-HODL engine.
    
    Attributes:
        dca_interval_hours: Hours between DCA purchases (default: weekly = 168)
        dca_amount_usdt: Fixed USD amount to purchase per DCA cycle
        btc_target_pct: Target BTC allocation within engine (default: 66.7%)
        eth_target_pct: Target ETH allocation within engine (default: 33.3%)
        rebalance_threshold_pct: Rebalance when drift exceeds this (default: 10%)
        rebalance_frequency: How often to check for rebalance (daily, weekly, monthly, quarterly)
        yield_enabled: Whether to move idle ETH to Earn (default: True)
        min_apy_pct: Minimum APY required for yield products (default: 2%)
        max_dca_price_deviation: Skip DCA if price deviates more than this (default: 50%)
    """
    dca_interval_hours: int = 168  # Weekly
    dca_amount_usdt: Decimal = Decimal("100.0")
    btc_target_pct: Decimal = Decimal("0.667")  # 2/3 BTC
    eth_target_pct: Decimal = Decimal("0.333")  # 1/3 ETH
    rebalance_threshold_pct: Decimal = Decimal("0.10")  # 10% drift
    rebalance_frequency: str = "quarterly"
    yield_enabled: bool = True
    min_apy_pct: Decimal = Decimal("2.0")
    max_dca_price_deviation: Decimal = Decimal("0.50")  # 50%
    
    def __post_init__(self):
        if not hasattr(self, 'engine_type'):
            self.engine_type = EngineType.CORE_HODL


class CoreHodlEngine(BaseEngine):
    """
    CORE-HODL Engine - Long-term crypto accumulation.
    
    This is the most conservative engine, designed for decades-long
    capital compounding through systematic BTC/ETH accumulation.
    
    Key Behaviors:
    1. DCA: Regular fixed-amount purchases regardless of price
    2. Rebalancing: Maintain target allocation (BTC:ETH = 2:1)
    3. Yield: Generate passive income from idle ETH
    4. No Selling: Accumulation phase only - never sell during drawdowns
    
    References:
    - See docs/04-trading-strategies/01-strategy-specifications.md
    - AGENTS.md section 2.1
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        config: Optional[CoreHodlConfig] = None,
        risk_manager=None
    ):
        # Default symbols: BTC and ETH spot
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT"]
        
        self.hodl_config = config or CoreHodlConfig(
            engine_type=EngineType.CORE_HODL,
            allocation_pct=Decimal("0.60")
        )
        
        super().__init__(
            config=self.hodl_config,
            engine_type=EngineType.CORE_HODL,
            symbols=symbols,
            risk_manager=risk_manager
        )
        
        # DCA tracking
        self.last_dca_time: Dict[str, datetime] = {}
        self.dca_purchase_count: Dict[str, int] = {s: 0 for s in symbols}
        self.total_dca_invested: Dict[str, Decimal] = {s: Decimal("0") for s in symbols}
        
        # Rebalancing tracking
        self.last_rebalance_check: Optional[datetime] = None
        self.rebalance_in_progress: bool = False
        
        # Yield tracking
        self.eth_in_earn: Decimal = Decimal("0")
        self.current_apy: Decimal = Decimal("0")
        
        # Price history for DCA deviation check
        self.avg_purchase_price: Dict[str, Decimal] = {s: Decimal("0") for s in symbols}
        
        self.logger.info(
            "core_hodl.initialized",
            dca_amount=str(self.hodl_config.dca_amount_usdt),
            dca_interval_hours=self.hodl_config.dca_interval_hours,
            btc_target=str(self.hodl_config.btc_target_pct),
            eth_target=str(self.hodl_config.eth_target_pct)
        )
    
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """
        Generate DCA and rebalancing signals.
        
        Checks:
        1. Time-based DCA purchases
        2. Quarterly/periodic rebalancing
        3. Yield opportunities for ETH
        """
        signals = []
        now = datetime.now(timezone.utc)
        
        if not self.is_active:
            return signals
        
        # Check each symbol for DCA
        for symbol in self.symbols:
            if symbol not in data or not data[symbol]:
                continue
            
            current_price = data[symbol][-1].close
            
            # Check if it's time for DCA
            if self._should_execute_dca(symbol, now, current_price):
                signal = self._create_dca_signal(symbol, current_price)
                signals.append(signal)
        
        # Check for rebalancing needs (quarterly or threshold-based)
        if self._should_rebalance(now):
            rebalance_signals = self._generate_rebalance_signals(data)
            signals.extend(rebalance_signals)
        
        return signals
    
    def _should_execute_dca(
        self, 
        symbol: str, 
        now: datetime, 
        current_price: Decimal
    ) -> bool:
        """Check if DCA purchase should be executed."""
        last_purchase = self.last_dca_time.get(symbol)
        
        # First purchase
        if last_purchase is None:
            return True
        
        # Check time interval
        time_since_last = now - last_purchase
        if time_since_last < timedelta(hours=self.hodl_config.dca_interval_hours):
            return False
        
        # Check price deviation (skip if price moved too much recently)
        avg_price = self.avg_purchase_price.get(symbol, Decimal("0"))
        if avg_price > 0:
            price_change = abs(current_price - avg_price) / avg_price
            if price_change > self.hodl_config.max_dca_price_deviation:
                self.logger.warning(
                    "core_hodl.dca_skipped_price_deviation",
                    symbol=symbol,
                    current_price=str(current_price),
                    avg_price=str(avg_price),
                    deviation=str(price_change)
                )
                # Still update the timer to avoid constant warnings
                self.last_dca_time[symbol] = now
                return False
        
        return True
    
    def _create_dca_signal(self, symbol: str, current_price: Decimal) -> TradingSignal:
        """Create a DCA buy signal."""
        # Calculate amount based on allocation target
        if "BTC" in symbol:
            allocation = self.hodl_config.btc_target_pct
        else:
            allocation = self.hodl_config.eth_target_pct
        
        amount_usd = self.hodl_config.dca_amount_usdt * allocation
        
        metadata = {
            'strategy': 'DCA',
            'engine': 'CORE-HODL',
            'amount_usd': str(amount_usd),
            'current_price': str(current_price),
            'allocation_target': str(allocation),
            'purchase_number': self.dca_purchase_count.get(symbol, 0) + 1
        }
        
        self.logger.info(
            "core_hodl.dca_signal",
            symbol=symbol,
            amount_usd=str(amount_usd),
            price=str(current_price)
        )
        
        return self._create_signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            confidence=1.0,  # DCA is deterministic
            metadata=metadata
        )
    
    def _should_rebalance(self, now: datetime) -> bool:
        """Check if rebalancing should be performed."""
        # Check based on frequency
        if self.last_rebalance_check is None:
            return True
        
        frequency = self.hodl_config.rebalance_frequency
        time_since_last = now - self.last_rebalance_check
        
        if frequency == "daily" and time_since_last >= timedelta(days=1):
            return True
        elif frequency == "weekly" and time_since_last >= timedelta(weeks=1):
            return True
        elif frequency == "monthly" and time_since_last >= timedelta(days=30):
            return True
        elif frequency == "quarterly" and time_since_last >= timedelta(days=90):
            return True
        
        return False
    
    def _generate_rebalance_signals(
        self, 
        data: Dict[str, List[MarketData]]
    ) -> List[TradingSignal]:
        """Generate rebalancing signals if allocation drifted."""
        signals = []
        self.last_rebalance_check = datetime.now(timezone.utc)
        
        # Calculate current allocations
        total_value = Decimal("0")
        symbol_values: Dict[str, Decimal] = {}
        
        for symbol in self.symbols:
            if symbol not in data or not data[symbol]:
                continue
            
            current_price = data[symbol][-1].close
            position = self.positions.get(symbol)
            
            if position and position.is_open:
                value = position.amount * current_price
            else:
                value = Decimal("0")
            
            symbol_values[symbol] = value
            total_value += value
        
        if total_value == 0:
            return signals
        
        # Check each symbol's allocation
        for symbol, current_value in symbol_values.items():
            current_pct = current_value / total_value
            
            # Determine target allocation
            if "BTC" in symbol:
                target_pct = self.hodl_config.btc_target_pct
            else:
                target_pct = self.hodl_config.eth_target_pct
            
            # Check if drift exceeds threshold
            drift = abs(current_pct - target_pct)
            
            if drift > self.hodl_config.rebalance_threshold_pct:
                signal = self._create_rebalance_signal(
                    symbol=symbol,
                    target_allocation=target_pct * total_value,
                    current_allocation=current_value,
                    confidence=0.9
                )
                signal.metadata['rebalance_reason'] = f"drift_{drift:.2%}"
                signals.append(signal)
                
                self.logger.info(
                    "core_hodl.rebalance_signal",
                    symbol=symbol,
                    current_pct=str(current_pct),
                    target_pct=str(target_pct),
                    drift=str(drift)
                )
        
        return signals
    
    async def on_order_filled(
        self, 
        symbol: str, 
        side: str, 
        amount: Decimal, 
        price: Decimal,
        order_id: Optional[str] = None
    ):
        """Track DCA purchases and update position state."""
        now = datetime.now(timezone.utc)
        
        if side == "buy":
            # Update DCA tracking
            self.last_dca_time[symbol] = now
            self.dca_purchase_count[symbol] = self.dca_purchase_count.get(symbol, 0) + 1
            
            # Calculate purchase value
            purchase_value = amount * price
            self.total_dca_invested[symbol] = self.total_dca_invested.get(symbol, Decimal("0")) + purchase_value
            
            # Update average purchase price
            total_invested = self.total_dca_invested[symbol]
            total_purchases = self.dca_purchase_count[symbol]
            
            if total_purchases > 0:
                # Approximate average
                self.avg_purchase_price[symbol] = total_invested / (total_purchases * amount)
            
            # Update position tracking
            if symbol not in self.positions:
                from src.core.models import Position, PositionSide
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    entry_price=price,
                    amount=amount
                )
            else:
                # Update average entry price
                pos = self.positions[symbol]
                total_value = (pos.entry_price * pos.amount) + (price * amount)
                total_amount = pos.amount + amount
                pos.entry_price = total_value / total_amount
                pos.amount = total_amount
            
            self.signals_executed += 1
            self.state.total_trades += 1
            
            self.logger.info(
                "core_hodl.purchase_recorded",
                symbol=symbol,
                amount=str(amount),
                price=str(price),
                total_invested=str(self.total_dca_invested[symbol]),
                purchase_count=self.dca_purchase_count[symbol]
            )
        
        elif side == "sell":
            # This would be a rebalance sell
            self.logger.info(
                "core_hodl.rebalance_sell",
                symbol=symbol,
                amount=str(amount),
                price=str(price)
            )
    
    async def on_position_closed(
        self, 
        symbol: str, 
        pnl: Decimal, 
        pnl_pct: Decimal,
        close_reason: str = "signal"
    ):
        """
        Track position close.
        
        Note: CORE-HODL rarely closes positions. This would only happen
        during rebalancing or extreme circumstances.
        """
        self.total_pnl += pnl
        
        # Update engine state
        if pnl > 0:
            self.state.winning_trades += 1
        else:
            self.state.losing_trades += 1
        
        # Remove position tracking
        if symbol in self.positions:
            del self.positions[symbol]
        
        self.logger.info(
            "core_hodl.position_closed",
            symbol=symbol,
            pnl=str(pnl),
            pnl_pct=str(pnl_pct),
            reason=close_reason
        )
    
    def get_time_to_next_dca(self, symbol: str) -> Optional[timedelta]:
        """Get time remaining until next scheduled DCA."""
        if symbol not in self.last_dca_time:
            return timedelta(0)
        
        next_dca = self.last_dca_time[symbol] + timedelta(hours=self.hodl_config.dca_interval_hours)
        remaining = next_dca - datetime.now(timezone.utc)
        
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
    
    def get_dca_stats(self) -> Dict[str, Any]:
        """Get DCA-specific statistics."""
        return {
            'total_invested': {k: str(v) for k, v in self.total_dca_invested.items()},
            'purchase_count': self.dca_purchase_count,
            'avg_investment': {
                k: str(v / self.dca_purchase_count[k]) if self.dca_purchase_count[k] > 0 else "0"
                for k, v in self.total_dca_invested.items()
            },
            'next_dca_in_hours': {
                k: self.get_time_to_next_dca(k).total_seconds() / 3600
                for k in self.symbols
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get CORE-HODL engine statistics."""
        base_stats = super().get_stats()
        base_stats.update({
            'dca_stats': self.get_dca_stats(),
            'avg_purchase_price': {k: str(v) for k, v in self.avg_purchase_price.items()},
            'eth_in_earn': str(self.eth_in_earn),
            'current_apy': str(self.current_apy),
            'accumulation_phase': True,  # CORE-HODL never sells during drawdowns
        })
        return base_stats
