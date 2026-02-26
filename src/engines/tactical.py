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
from typing import Any, Dict, List, Optional

import structlog

from src.core.models import (EngineType, MarketData, Position, PositionSide,
                             SignalType, TradingSignal)
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
    trigger_levels: List[tuple] = field(
        default_factory=lambda: [
            (Decimal("0.50"), Decimal("0.50")),  # -50% ATH: deploy 50%
            (Decimal("0.70"), Decimal("1.00")),  # -70% ATH: deploy remaining 100%
        ]
    )
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
        if not hasattr(self, "engine_type"):
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
        risk_manager=None,
    ):
        # Default symbols: BTC and ETH spot
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT"]

        self.tactical_config = config or TacticalEngineConfig(
            engine_type=EngineType.TACTICAL, allocation_pct=Decimal("0.05")
        )

        super().__init__(
            config=self.tactical_config,
            engine_type=EngineType.TACTICAL,
            symbols=symbols,
            risk_manager=risk_manager,
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
            eth_alloc=f"{self.tactical_config.eth_allocation:.0%}",
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

        now = datetime.now(timezone.utc)

        # Update market state
        self._update_market_state(data, now)

        # Check if we have positions to manage
        has_positions = any(
            s in self.positions and self.positions[s].is_open for s in self.symbols
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
            simulated_funding = Decimal("-0.0005") * (
                self.current_drawdown / Decimal("0.50")
            )
        else:
            simulated_funding = Decimal("0.0001")

        self.funding_history.append((now, simulated_funding))

        # Keep last 30 days
        cutoff = now - timedelta(days=30)
        self.funding_history = [h for h in self.funding_history if h[0] > cutoff]

    def _check_deployment_triggers(
        self, data: Dict[str, List[MarketData]], now: datetime
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
        for level_idx, (drawdown_threshold, deploy_amount) in enumerate(
            self.tactical_config.trigger_levels
        ):
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
                deploy_pct = (
                    Decimal("0.30") * self.deployment_cash_remaining
                )  # Deploy 30%

        # Trigger 3: Funding capitulation
        if not triggered:
            capitulation_days = self._count_capitulation_days()
            if capitulation_days >= self.tactical_config.funding_capitulation_days:
                triggered = True
                trigger_reason = f"funding_capitulation_{capitulation_days}d"
                deploy_pct = (
                    Decimal("0.25") * self.deployment_cash_remaining
                )  # Deploy 25%

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
        trigger_reason: str,
    ) -> List[TradingSignal]:
        """Create deployment signals for crisis entry."""
        signals = []

        # Calculate deployment amount
        available_capital = self.state.current_value
        deployment_amount = available_capital * deploy_pct

        # Split between BTC and ETH
        btc_amount = deployment_amount * self.tactical_config.btc_allocation
        eth_amount = deployment_amount * self.tactical_config.eth_allocation

        now = datetime.now(timezone.utc)

        # BTC signal
        if "BTCUSDT" in data and data["BTCUSDT"]:
            btc_price = data["BTCUSDT"][-1].close
            btc_qty = btc_amount / btc_price

            btc_metadata = {
                "strategy": "TACTICAL",
                "trigger": trigger_reason,
                "deployment_pct": str(deploy_pct),
                "btc_drawdown": str(self.current_drawdown),
                "quantity": str(btc_qty),
                "entry_price": str(btc_price),
                "profit_target": str(
                    btc_price * (Decimal("1") + self.tactical_config.profit_target_pct)
                ),
                "max_exit_date": (
                    now + timedelta(days=self.tactical_config.max_hold_days)
                ).isoformat(),
            }

            signals.append(
                self._create_signal(
                    symbol="BTCUSDT",
                    signal_type=SignalType.BUY,
                    confidence=0.95,
                    metadata=btc_metadata,
                )
            )

            # Track entry
            self.entry_prices["BTCUSDT"] = btc_price
            self.position_entry_times["BTCUSDT"] = now
            self.position_sizes["BTCUSDT"] = btc_qty

        # ETH signal
        if "ETHUSDT" in data and data["ETHUSDT"]:
            eth_price = data["ETHUSDT"][-1].close
            eth_qty = eth_amount / eth_price

            eth_metadata = {
                "strategy": "TACTICAL",
                "trigger": trigger_reason,
                "deployment_pct": str(deploy_pct),
                "btc_drawdown": str(self.current_drawdown),
                "quantity": str(eth_qty),
                "entry_price": str(eth_price),
                "profit_target": str(
                    eth_price * (Decimal("1") + self.tactical_config.profit_target_pct)
                ),
                "max_exit_date": (
                    now + timedelta(days=self.tactical_config.max_hold_days)
                ).isoformat(),
            }

            signals.append(
                self._create_signal(
                    symbol="ETHUSDT",
                    signal_type=SignalType.BUY,
                    confidence=0.95,
                    metadata=eth_metadata,
                )
            )

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
            cash_remaining=f"{self.deployment_cash_remaining:.1%}",
        )

        return signals

    def _check_exit_conditions(
        self, data: Dict[str, List[MarketData]], now: datetime
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
                signals.append(
                    self._create_exit_signal(
                        symbol, current_price, profit_pct, "profit_target"
                    )
                )
                continue

            # Exit 2: Max hold time reached
            if hold_duration.days >= self.tactical_config.max_hold_days:
                signals.append(
                    self._create_exit_signal(
                        symbol, current_price, profit_pct, "max_hold_time"
                    )
                )
                continue

            # Exit 3: Min hold passed AND euphoria signals (optional early exit)
            if hold_duration.days >= self.tactical_config.min_hold_days:
                # Check for euphoria conditions
                if self._is_euphoria_condition():
                    signals.append(
                        self._create_exit_signal(
                            symbol, current_price, profit_pct, "euphoria_early_exit"
                        )
                    )

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
        self, symbol: str, current_price: Decimal, profit_pct: Decimal, reason: str
    ) -> TradingSignal:
        """Create an exit signal."""
        entry_price = self.entry_prices.get(symbol, current_price)

        metadata = {
            "strategy": "TACTICAL",
            "exit_reason": reason,
            "entry_price": str(entry_price),
            "exit_price": str(current_price),
            "profit_pct": str(profit_pct),
            "transfer_to_core": "true",  # Flag to return profits to CORE-HODL
        }

        self.logger.info(
            "tactical_engine.exit_signal",
            symbol=symbol,
            reason=reason,
            entry=str(entry_price),
            current=str(current_price),
            profit=f"{profit_pct:.1%}",
        )

        return self._create_signal(
            symbol=symbol,
            signal_type=SignalType.CLOSE,
            confidence=1.0,
            metadata=metadata,
        )

    async def on_order_filled(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Decimal,
        order_id: Optional[str] = None,
    ):
        """Track order fills for tactical positions."""
        if side == "buy":
            # Entry
            if symbol not in self.positions:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    entry_price=price,
                    amount=amount,
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
                total_deployed=str(self.total_deployed),
            )

        elif side == "sell":
            # Exit (will trigger on_position_closed)
            self.logger.info(
                "tactical_engine.exit_filled",
                symbol=symbol,
                amount=str(amount),
                price=str(price),
            )

    async def on_position_closed(
        self, symbol: str, pnl: Decimal, pnl_pct: Decimal, close_reason: str = "signal"
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
                total_pending_transfer=str(self.pending_core_transfer),
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
            total_profits=str(self.profits_realized),
        )

    def update_fear_greed_index(self, index: int):
        """Update Fear & Greed Index from external source."""
        self.fear_greed_index = index
        self.logger.debug("tactical_engine.fgi_updated", index=index)

    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status."""
        return {
            "btc_ath": str(self.btc_ath),
            "current_drawdown": f"{self.current_drawdown:.2%}",
            "trigger_levels_triggered": self.deployment_levels_triggered,
            "cash_remaining": f"{self.deployment_cash_remaining:.1%}",
            "total_deployed": str(self.total_deployed),
            "deployments_made": self.deployments_made,
            "fear_greed_index": self.fear_greed_index,
            "capitulation_days": self._count_capitulation_days(),
            "active_positions": [
                {
                    "symbol": s,
                    "entry_price": str(self.entry_prices.get(s)),
                    "entry_time": (
                        self.position_entry_times.get(s).isoformat()
                        if self.position_entry_times.get(s)
                        else None
                    ),
                    "size": str(self.position_sizes.get(s)),
                }
                for s in self.symbols
                if s in self.positions and self.positions[s].is_open
            ],
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get TACTICAL engine statistics."""
        base_stats = super().get_stats()
        base_stats.update(
            {
                "deployment_status": self.get_deployment_status(),
                "profits_realized": str(self.profits_realized),
                "pending_core_transfer": str(self.pending_core_transfer),
                "deployments_made": self.deployments_made,
                "full_exits": self.full_exits,
                "partial_exits": self.partial_exits,
            }
        )
        return base_stats

    def get_full_state(self) -> Dict[str, Any]:
        """
        Get complete state for persistence.

        Returns:
            Dictionary with all critical TACTICAL state that must survive restarts.
        """
        # Serialize funding history (keep last 100 entries)
        funding_history_serializable = [
            {"timestamp": ts.isoformat(), "rate": str(rate)}
            for ts, rate in self.funding_history[-100:]
        ]

        return {
            "engine_type": self.engine_type.value,
            "symbols": self.symbols,
            # Market state tracking
            "btc_ath": str(self.btc_ath),
            "current_drawdown": str(self.current_drawdown),
            "fear_greed_index": self.fear_greed_index,
            "funding_history": funding_history_serializable,
            # Deployment tracking
            "deployment_levels_triggered": self.deployment_levels_triggered,
            "last_deployment_time": (
                self.last_deployment_time.isoformat()
                if self.last_deployment_time
                else None
            ),
            "total_deployed": str(self.total_deployed),
            "deployment_cash_remaining": str(self.deployment_cash_remaining),
            # Position tracking
            "entry_prices": {k: str(v) for k, v in self.entry_prices.items()},
            "position_entry_times": {
                k: v.isoformat() if v else None
                for k, v in self.position_entry_times.items()
            },
            "position_sizes": {k: str(v) for k, v in self.position_sizes.items()},
            # Exit tracking
            "profits_realized": str(self.profits_realized),
            "pending_core_transfer": str(self.pending_core_transfer),
            # Statistics
            "deployments_made": self.deployments_made,
            "full_exits": self.full_exits,
            "partial_exits": self.partial_exits,
            # Engine state
            "state": {
                "is_active": self.state.is_active,
                "can_trade": self.state.can_trade,
                "is_paused": self.state.is_paused,
                "pause_reason": self.state.pause_reason,
                "pause_until": (
                    self.state.pause_until.isoformat()
                    if self.state.pause_until
                    else None
                ),
                "current_value": str(self.state.current_value),
                "cash_buffer": str(self.state.cash_buffer),
                "total_trades": self.state.total_trades,
                "winning_trades": self.state.winning_trades,
                "losing_trades": self.state.losing_trades,
            },
            # Performance tracking
            "signals_generated": self.signals_generated,
            "signals_executed": self.signals_executed,
            "total_pnl": str(self.total_pnl),
            "total_fees": str(self.total_fees),
        }

    def restore_full_state(self, state: Dict[str, Any]):
        """
        Restore state from persisted data.

        Args:
            state: State dictionary previously returned by get_full_state()
        """
        from datetime import datetime

        try:
            # Restore market state tracking
            if "btc_ath" in state:
                try:
                    self.btc_ath = Decimal(state["btc_ath"])
                except (ValueError, TypeError):
                    self.btc_ath = Decimal("69000")

            if "current_drawdown" in state:
                try:
                    self.current_drawdown = Decimal(state["current_drawdown"])
                except (ValueError, TypeError):
                    self.current_drawdown = Decimal("0")

            if "fear_greed_index" in state:
                self.fear_greed_index = state["fear_greed_index"]

            # Restore funding history
            if "funding_history" in state:
                restored_history = []
                for entry in state["funding_history"]:
                    try:
                        ts = datetime.fromisoformat(entry["timestamp"])
                        rate = Decimal(entry["rate"])
                        restored_history.append((ts, rate))
                    except (ValueError, TypeError, KeyError):
                        continue
                self.funding_history = restored_history

            # Restore deployment tracking
            if "deployment_levels_triggered" in state:
                self.deployment_levels_triggered = state["deployment_levels_triggered"]

            if "last_deployment_time" in state and state["last_deployment_time"]:
                try:
                    self.last_deployment_time = datetime.fromisoformat(
                        state["last_deployment_time"]
                    )
                except (ValueError, TypeError):
                    self.last_deployment_time = None

            if "total_deployed" in state:
                try:
                    self.total_deployed = Decimal(state["total_deployed"])
                except (ValueError, TypeError):
                    self.total_deployed = Decimal("0")

            if "deployment_cash_remaining" in state:
                try:
                    self.deployment_cash_remaining = Decimal(
                        state["deployment_cash_remaining"]
                    )
                except (ValueError, TypeError):
                    self.deployment_cash_remaining = Decimal("1.0")

            # Restore position tracking
            if "entry_prices" in state:
                for symbol, value_str in state["entry_prices"].items():
                    try:
                        self.entry_prices[symbol] = Decimal(value_str)
                    except (ValueError, TypeError):
                        self.entry_prices[symbol] = Decimal("0")

            if "position_entry_times" in state:
                for symbol, timestamp_str in state["position_entry_times"].items():
                    if timestamp_str:
                        try:
                            self.position_entry_times[symbol] = datetime.fromisoformat(
                                timestamp_str
                            )
                        except (ValueError, TypeError):
                            self.position_entry_times[symbol] = None

            if "position_sizes" in state:
                for symbol, value_str in state["position_sizes"].items():
                    try:
                        self.position_sizes[symbol] = Decimal(value_str)
                    except (ValueError, TypeError):
                        self.position_sizes[symbol] = Decimal("0")

            # Restore exit tracking
            if "profits_realized" in state:
                try:
                    self.profits_realized = Decimal(state["profits_realized"])
                except (ValueError, TypeError):
                    self.profits_realized = Decimal("0")

            if "pending_core_transfer" in state:
                try:
                    self.pending_core_transfer = Decimal(state["pending_core_transfer"])
                except (ValueError, TypeError):
                    self.pending_core_transfer = Decimal("0")

            # Restore statistics
            if "deployments_made" in state:
                self.deployments_made = state["deployments_made"]
            if "full_exits" in state:
                self.full_exits = state["full_exits"]
            if "partial_exits" in state:
                self.partial_exits = state["partial_exits"]

            # Restore engine state
            if "state" in state:
                state_data = state["state"]
                self.state.is_active = state_data.get("is_active", self.state.is_active)
                # Note: can_trade is computed from is_active, is_paused, circuit_breaker_level, pause_until
                self.state.is_paused = state_data.get("is_paused", self.state.is_paused)
                self.state.pause_reason = state_data.get("pause_reason")

                if "pause_until" in state_data and state_data["pause_until"]:
                    try:
                        self.state.pause_until = datetime.fromisoformat(
                            state_data["pause_until"]
                        )
                    except (ValueError, TypeError):
                        self.state.pause_until = None

                if "current_value" in state_data:
                    try:
                        self.state.current_value = Decimal(state_data["current_value"])
                    except (ValueError, TypeError):
                        pass

                if "cash_buffer" in state_data:
                    try:
                        self.state.cash_buffer = Decimal(state_data["cash_buffer"])
                    except (ValueError, TypeError):
                        pass

                self.state.total_trades = state_data.get(
                    "total_trades", self.state.total_trades
                )
                self.state.winning_trades = state_data.get(
                    "winning_trades", self.state.winning_trades
                )
                self.state.losing_trades = state_data.get(
                    "losing_trades", self.state.losing_trades
                )

            # Restore performance tracking
            if "signals_generated" in state:
                self.signals_generated = state["signals_generated"]
            if "signals_executed" in state:
                self.signals_executed = state["signals_executed"]
            if "total_pnl" in state:
                try:
                    self.total_pnl = Decimal(state["total_pnl"])
                except (ValueError, TypeError):
                    pass
            if "total_fees" in state:
                try:
                    self.total_fees = Decimal(state["total_fees"])
                except (ValueError, TypeError):
                    pass

            self.logger.info(
                "tactical_engine.state_restored",
                deployment_levels=self.deployment_levels_triggered,
                total_deployed=str(self.total_deployed),
                cash_remaining=str(self.deployment_cash_remaining),
                deployments_made=self.deployments_made,
            )
        except Exception as e:
            self.logger.error("tactical_engine.state_restore_error", error=str(e))
            # Continue with default values - don't crash on restore failure
