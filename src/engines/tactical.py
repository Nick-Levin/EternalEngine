"""
TACTICAL Engine (5% Allocation)

Crisis deployment strategy for extreme market conditions.
Deploys capital during market crashes to capture extreme value.

Strategy:
- Purpose: Extreme value deployment during crashes
- Triggers:
  * Level 1: BTC -50% from ATH → Deploy 50% of cash
  * Level 2: BTC -70% from ATH → Deploy remaining 50%
  * Fear & Greed < 20 (Extreme Fear)
  * Funding < -0.05% for 3+ days (capitulation)
- Allocation: 80% BTC, 20% ETH
- Exit: 100% profit target or 12 months
- Return profits to CORE-HODL

Risk Level: OPPORTUNISTIC
Market: Spot only (long-term holds)
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import structlog

from src.core.models import (
    MarketData, TradingSignal, SignalType, Position, EngineType, PositionSide
)
from src.engines.base import BaseEngine, EngineConfig

logger = structlog.get_logger(__name__)


@dataclass
class TacticalEngineConfig(EngineConfig):
    """Configuration for TACTICAL engine.
    
    Attributes:
        trigger_levels: List of (drawdown_pct, deploy_pct) tuples
        fear_greed_extreme_fear: Fear & Greed threshold for extreme fear (default: 20)
        funding_capitulation_threshold: Funding rate indicating capitulation (default: -0.0005)
        funding_capitulation_days: Days of negative funding to trigger (default: 3)
        btc_allocation: BTC allocation within engine (default: 80%)
        eth_allocation: ETH allocation within engine (default: 20%)
        profit_target_pct: Profit target to exit (default: 100%)
        max_hold_days: Maximum days to hold (default: 365)
        min_hold_days: Minimum days before allowing exit (default: 90)
        deployment_cooldown_days: Days between deployments (default: 30)
    """
    # Drawdown triggers: [(drawdown%, deploy% of cash), ...]
    trigger_levels: List[tuple] = field(default_factory=lambda: [
        (Decimal("0.50"), Decimal("0.50")),  # -50% ATH: deploy 50%
        (Decimal("0.70"), Decimal("1.00")),  # -70% ATH: deploy remaining 100%
    ])
    fear_greed_extreme_fear: int = 20
    fear_greed_fear: int = 40
    funding_capitulation_threshold: Decimal = Decimal("-0.0005")  # -0.05%
    funding_capitulation_days: int = 3
    btc_allocation: Decimal = Decimal("0.80")
    eth_allocation: Decimal = Decimal("0.20")
    profit_target_pct: Decimal = Decimal("1.00")  # 100%
    max_hold_days: int = 365
    min_hold_days: int = 90
    deployment_cooldown_days: int = 30
    
    def __post_init__(self):
        if not hasattr(self, 'engine_type'):
            self.engine_type = EngineType.TACTICAL


class TacticalEngine(BaseEngine):
    """
    TACTICAL Engine - Crisis deployment for extreme value capture.
    
    This engine does NOT trade regularly - it waits patiently for
    generational buying opportunities during market crashes.
    
    Key Behaviors:
    1. Extreme Patience: Waits months/years for triggers
    2. Mechanical Deployment: No discretion on entry
    3. Long-term Hold: 100% profit target or 12 months
    4. Returns to CORE: Profits transferred to CORE-HODL
    5. Multiple Triggers: Price, sentiment, or funding based
    
    Deployment Triggers:
    - Price: BTC -50% / -70% from all-time high
    - Sentiment: Fear & Greed Index < 20 (Extreme Fear)
    - Derivatives: Funding < -0.05% for 3+ days (capitulation)
    
    Exit Rules:
    - 100% profit target achieved
    - 12 months holding period (max)
    - Funding rates turn extremely positive (market euphoria)
    
    References:
    - See docs/04-trading-strategies/01-strategy-specifications.md
    - AGENTS.md section 2.4
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        config: Optional[TacticalEngineConfig] = None,
        risk_manager=None
    ):
        # Default symbols: BTC and ETH spot
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT"]
        
        self.tactical_config = config or TacticalEngineConfig(
            engine_type=EngineType.TACTICAL,
            allocation_pct=Decimal("0.05")
        )
        
        super().__init__(
            config=self.tactical_config,
            engine_type=EngineType.TACTICAL,
            symbols=symbols,
            risk_manager=risk_manager
        )
        
        # Market state tracking
        self.btc_ath: Decimal = Decimal("69000")  # Will be updated from market data
        self.current_drawdown: Decimal = Decimal("0")
        self.fear_greed_index: Optional[int] = None
        self.funding_history: List[Tuple[datetime, Decimal]] = []
        
        # Deployment tracking
        self.deployment_levels_triggered: List[int] = []
        self.last_deployment_time: Optional[datetime] = None
        self.total_deployed: Decimal = Decimal("0")
        self.deployment_cash_remaining: Decimal = Decimal("1.0")  # 100% initially
        
        # Position tracking
        self.entry_prices: Dict[str, Decimal] = {}
        self.position_entry_times: Dict[str, datetime] = {}
        self.position_sizes: Dict[str, Decimal] = {}
        
        # Exit tracking
        self.profits_realized: Decimal = Decimal("0")
        self.pending_core_transfer: Decimal = Decimal("0")
        
        # Statistics
        self.deployments_made: int = 0
        self.full_exits: int = 0
        self.partial_exits: int = 0
        
        self.logger.info(
            "tactical_engine.initialized",
            trigger_levels=self.tactical_config.trigger_levels,
            profit_target=f"{self.tactical_config.profit_target_pct:.0%}",
            max_hold_days=self.tactical_config.max_hold_days,
            btc_alloc=f"{self.tactical_config.btc_allocation:.0%}",
            eth_alloc=f"{self.tactical_config.eth_allocation:.0%}"
        )
    
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """
        Analyze market for crisis deployment opportunities.
        
        Entry Triggers (ANY can trigger deployment):
        1. BTC drawdown reaches trigger level (-50%, -70%)
        2. Fear & Greed Index < 20 (Extreme Fear)
        3. Funding < -0.05% for 3+ consecutive days
        
        Exit Triggers (ANY can trigger exit):
        1. 100% profit target reached
        2. Max hold time (12 months) reached
        3. Min hold time (3 months) passed AND euphoria signals
        """
        signals = []
        
        if not self.is_active:
            return signals
        
        now = datetime.utcnow()
        
        # Update market state
        self._update_market_state(data, now)
        
        # Check if we have positions to manage
        has_positions = any(
            s in self.positions and self.positions[s].is_open 
            for s in self.symbols
        )
        
        if has_positions:
            # Check exit conditions
            exit_signals = self._check_exit_conditions(data, now)
            signals.extend(exit_signals)
        else:
            # Check entry conditions
            deployment_signal = self._check_deployment_triggers(data, now)
            if deployment_signal:
                signals.extend(deployment_signal)
        
        return signals
    
    def _update_market_state(self, data: Dict[str, List[MarketData]], now: datetime):
        """Update market state indicators."""
        # Update BTC ATH and drawdown
        if "BTCUSDT" in data and data["BTCUSDT"]:
            btc_data = data["BTCUSDT"]
            current_price = btc_data[-1].close
            
            # Update ATH (in production, fetch historical ATH)
            for bar in btc_data:
                if bar.high > self.btc_ath:
                    self.btc_ath = bar.high
            
            # Calculate drawdown
            if self.btc_ath > 0:
                self.current_drawdown = (self.btc_ath - current_price) / self.btc_ath
        
        # Update funding history (placeholder - would come from exchange)
        # In production, fetch funding rates from Bybit
        self._update_funding_history(now)
    
    def _update_funding_history(self, now: datetime):
        """Update funding rate history for capitulation detection."""
        # Placeholder - in production fetch from exchange API
        # For now, simulate based on drawdown (deeper drawdown = more negative funding)
        if self.current_drawdown > Decimal("0.40"):
            simulated_funding = Decimal("-0.0005") * (self.current_drawdown / Decimal("0.50"))
        else:
            simulated_funding = Decimal("0.0001")
        
        self.funding_history.append((now, simulated_funding))
        
        # Keep last 30 days
        cutoff = now - timedelta(days=30)
        self.funding_history = [h for h in self.funding_history if h[0] > cutoff]
    
    def _check_deployment_triggers(
        self, 
        data: Dict[str, List[MarketData]], 
        now: datetime
    ) -> Optional[List[TradingSignal]]:
        """Check if any deployment triggers are met."""
        # Check cooldown period
        if self.last_deployment_time:
            cooldown = timedelta(days=self.tactical_config.deployment_cooldown_days)
            if now - self.last_deployment_time < cooldown:
                return None
        
        # Check if we have cash to deploy
        if self.deployment_cash_remaining <= 0:
            return None
        
        triggered = False
        trigger_reason = ""
        deploy_pct = Decimal("0")
        
        # Trigger 1: Price drawdown levels
        for level_idx, (drawdown_threshold, deploy_amount) in enumerate(self.tactical_config.trigger_levels):
            if level_idx in self.deployment_levels_triggered:
                continue  # Already triggered this level
            
            if self.current_drawdown >= drawdown_threshold:
                triggered = True
                trigger_reason = f"btc_drawdown_{drawdown_threshold:.0%}"
                deploy_pct = deploy_amount * self.deployment_cash_remaining
                self.deployment_levels_triggered.append(level_idx)
                break
        
        # Trigger 2: Extreme fear
        if not triggered and self.fear_greed_index is not None:
            if self.fear_greed_index <= self.tactical_config.fear_greed_extreme_fear:
                triggered = True
                trigger_reason = f"extreme_fear_fgi_{self.fear_greed_index}"
                deploy_pct = Decimal("0.30") * self.deployment_cash_remaining  # Deploy 30%
        
        # Trigger 3: Funding capitulation
        if not triggered:
            capitulation_days = self._count_capitulation_days()
            if capitulation_days >= self.tactical_config.funding_capitulation_days:
                triggered = True
                trigger_reason = f"funding_capitulation_{capitulation_days}d"
                deploy_pct = Decimal("0.25") * self.deployment_cash_remaining  # Deploy 25%
        
        if triggered:
            return self._create_deployment_signals(data, deploy_pct, trigger_reason)
        
        return None
    
    def _count_capitulation_days(self) -> int:
        """Count consecutive days of capitulation funding."""
        threshold = self.tactical_config.funding_capitulation_threshold
        
        consecutive_days = 0
        current_day = None
        day_has_capitulation = False
        
        for timestamp, funding in reversed(self.funding_history):
            day = timestamp.date()
            
            if day != current_day:
                if day_has_capitulation:
                    consecutive_days += 1
                else:
                    break  # Streak broken
                current_day = day
                day_has_capitulation = False
            
            if funding <= threshold:
                day_has_capitulation = True
        
        return consecutive_days
    
    def _create_deployment_signals(
        self, 
        data: Dict[str, List[MarketData]],
        deploy_pct: Decimal,
        trigger_reason: str
    ) -> List[TradingSignal]:
        """Create deployment signals for crisis entry."""
        signals = []
        
        # Calculate deployment amount
        available_capital = self.state.current_value
        deployment_amount = available_capital * deploy_pct
        
        # Split between BTC and ETH
        btc_amount = deployment_amount * self.tactical_config.btc_allocation
        eth_amount = deployment_amount * self.tactical_config.eth_allocation
        
        now = datetime.utcnow()
        
        # BTC signal
        if "BTCUSDT" in data and data["BTCUSDT"]:
            btc_price = data["BTCUSDT"][-1].close
            btc_qty = btc_amount / btc_price
            
            btc_metadata = {
                'strategy': 'TACTICAL',
                'trigger': trigger_reason,
                'deployment_pct': str(deploy_pct),
                'btc_drawdown': str(self.current_drawdown),
                'quantity': str(btc_qty),
                'entry_price': str(btc_price),
                'profit_target': str(btc_price * (Decimal("1") + self.tactical_config.profit_target_pct)),
                'max_exit_date': (now + timedelta(days=self.tactical_config.max_hold_days)).isoformat()
            }
            
            signals.append(self._create_signal(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                confidence=0.95,
                metadata=btc_metadata
            ))
            
            # Track entry
            self.entry_prices["BTCUSDT"] = btc_price
            self.position_entry_times["BTCUSDT"] = now
            self.position_sizes["BTCUSDT"] = btc_qty
        
        # ETH signal
        if "ETHUSDT" in data and data["ETHUSDT"]:
            eth_price = data["ETHUSDT"][-1].close
            eth_qty = eth_amount / eth_price
            
            eth_metadata = {
                'strategy': 'TACTICAL',
                'trigger': trigger_reason,
                'deployment_pct': str(deploy_pct),
                'btc_drawdown': str(self.current_drawdown),
                'quantity': str(eth_qty),
                'entry_price': str(eth_price),
                'profit_target': str(eth_price * (Decimal("1") + self.tactical_config.profit_target_pct)),
                'max_exit_date': (now + timedelta(days=self.tactical_config.max_hold_days)).isoformat()
            }
            
            signals.append(self._create_signal(
                symbol="ETHUSDT",
                signal_type=SignalType.BUY,
                confidence=0.95,
                metadata=eth_metadata
            ))
            
            # Track entry
            self.entry_prices["ETHUSDT"] = eth_price
            self.position_entry_times["ETHUSDT"] = now
            self.position_sizes["ETHUSDT"] = eth_qty
        
        # Update deployment tracking
        self.last_deployment_time = now
        self.total_deployed += deployment_amount
        self.deployment_cash_remaining -= deploy_pct
        self.deployments_made += 1
        
        self.logger.info(
            "tactical_engine.deployment",
            trigger=trigger_reason,
            amount=str(deployment_amount),
            btc_drawdown=str(self.current_drawdown),
            deployments_made=self.deployments_made,
            cash_remaining=f"{self.deployment_cash_remaining:.1%}"
        )
        
        return signals
    
    def _check_exit_conditions(
        self, 
        data: Dict[str, List[MarketData]],
        now: datetime
    ) -> List[TradingSignal]:
        """Check if any positions should be exited."""
        signals = []
        
        for symbol in self.symbols:
            if symbol not in data or not data[symbol]:
                continue
            
            if symbol not in self.positions or not self.positions[symbol].is_open:
                continue
            
            current_price = data[symbol][-1].close
            entry_price = self.entry_prices.get(symbol, current_price)
            entry_time = self.position_entry_times.get(symbol, now)
            
            # Calculate holding period and profit
            hold_duration = now - entry_time
            profit_pct = (current_price - entry_price) / entry_price
            
            # Exit 1: Profit target reached
            if profit_pct >= self.tactical_config.profit_target_pct:
                signals.append(self._create_exit_signal(
                    symbol, current_price, profit_pct, "profit_target"
                ))
                continue
            
            # Exit 2: Max hold time reached
            if hold_duration.days >= self.tactical_config.max_hold_days:
                signals.append(self._create_exit_signal(
                    symbol, current_price, profit_pct, "max_hold_time"
                ))
                continue
            
            # Exit 3: Min hold passed AND euphoria signals (optional early exit)
            if hold_duration.days >= self.tactical_config.min_hold_days:
                # Check for euphoria conditions
                if self._is_euphoria_condition():
                    signals.append(self._create_exit_signal(
                        symbol, current_price, profit_pct, "euphoria_early_exit"
                    ))
        
        return signals
    
    def _is_euphoria_condition(self) -> bool:
        """Check for market euphoria conditions (contrarian exit signal)."""
        # Euphoria: Extreme greed in FGI
        if self.fear_greed_index and self.fear_greed_index >= 80:
            return True
        
        # Euphoria: Very positive funding rates for extended period
        recent_funding = [f for t, f in self.funding_history[-10:]]
        if recent_funding and all(f > Decimal("0.001") for f in recent_funding):
            return True
        
        return False
    
    def _create_exit_signal(
        self, 
        symbol: str, 
        current_price: Decimal,
        profit_pct: Decimal,
        reason: str
    ) -> TradingSignal:
        """Create an exit signal."""
        entry_price = self.entry_prices.get(symbol, current_price)
        
        metadata = {
            'strategy': 'TACTICAL',
            'exit_reason': reason,
            'entry_price': str(entry_price),
            'exit_price': str(current_price),
            'profit_pct': str(profit_pct),
            'transfer_to_core': 'true'  # Flag to return profits to CORE-HODL
        }
        
        self.logger.info(
            "tactical_engine.exit_signal",
            symbol=symbol,
            reason=reason,
            entry=str(entry_price),
            current=str(current_price),
            profit=f"{profit_pct:.1%}"
        )
        
        return self._create_signal(
            symbol=symbol,
            signal_type=SignalType.CLOSE,
            confidence=1.0,
            metadata=metadata
        )
    
    async def on_order_filled(
        self, 
        symbol: str, 
        side: str, 
        amount: Decimal, 
        price: Decimal,
        order_id: Optional[str] = None
    ):
        """Track order fills for tactical positions."""
        if side == "buy":
            # Entry
            if symbol not in self.positions:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    entry_price=price,
                    amount=amount
                )
            else:
                # Adding to position
                pos = self.positions[symbol]
                total_value = (pos.entry_price * pos.amount) + (price * amount)
                pos.amount += amount
                pos.entry_price = total_value / pos.amount
            
            self.signals_executed += 1
            self.state.total_trades += 1
            
            self.logger.info(
                "tactical_engine.entry_filled",
                symbol=symbol,
                amount=str(amount),
                price=str(price),
                total_deployed=str(self.total_deployed)
            )
        
        elif side == "sell":
            # Exit (will trigger on_position_closed)
            self.logger.info(
                "tactical_engine.exit_filled",
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
        """Track position close and prepare profit transfer to CORE."""
        self.total_pnl += pnl
        
        # Update statistics
        if pnl > 0:
            self.state.winning_trades += 1
        else:
            self.state.losing_trades += 1
        
        # Transfer profits to CORE-HODL
        if pnl > 0:
            self.pending_core_transfer += pnl
            self.profits_realized += pnl
            self.logger.info(
                "tactical_engine.profit_to_core",
                symbol=symbol,
                profit=str(pnl),
                total_pending_transfer=str(self.pending_core_transfer)
            )
        
        # Cleanup
        if symbol in self.positions:
            del self.positions[symbol]
        if symbol in self.entry_prices:
            del self.entry_prices[symbol]
        if symbol in self.position_entry_times:
            del self.position_entry_times[symbol]
        if symbol in self.position_sizes:
            del self.position_sizes[symbol]
        
        self.full_exits += 1
        
        self.logger.info(
            "tactical_engine.position_closed",
            symbol=symbol,
            pnl=str(pnl),
            pnl_pct=str(pnl_pct),
            reason=close_reason,
            total_profits=str(self.profits_realized)
        )
    
    def update_fear_greed_index(self, index: int):
        """Update Fear & Greed Index from external source."""
        self.fear_greed_index = index
        self.logger.debug("tactical_engine.fgi_updated", index=index)
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status."""
        return {
            'btc_ath': str(self.btc_ath),
            'current_drawdown': f"{self.current_drawdown:.2%}",
            'trigger_levels_triggered': self.deployment_levels_triggered,
            'cash_remaining': f"{self.deployment_cash_remaining:.1%}",
            'total_deployed': str(self.total_deployed),
            'deployments_made': self.deployments_made,
            'fear_greed_index': self.fear_greed_index,
            'capitulation_days': self._count_capitulation_days(),
            'active_positions': [
                {
                    'symbol': s,
                    'entry_price': str(self.entry_prices.get(s)),
                    'entry_time': self.position_entry_times.get(s).isoformat() if self.position_entry_times.get(s) else None,
                    'size': str(self.position_sizes.get(s))
                }
                for s in self.symbols
                if s in self.positions and self.positions[s].is_open
            ]
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get TACTICAL engine statistics."""
        base_stats = super().get_stats()
        base_stats.update({
            'deployment_status': self.get_deployment_status(),
            'profits_realized': str(self.profits_realized),
            'pending_core_transfer': str(self.pending_core_transfer),
            'deployments_made': self.deployments_made,
            'full_exits': self.full_exits,
            'partial_exits': self.partial_exits
        })
        return base_stats
