"""
FUNDING Engine (15% Allocation)

Delta-neutral funding rate arbitrage strategy.
Generates yield from perpetual funding payments while maintaining market neutrality.

Strategy:
- Long spot + Short perp (1:1 ratio for delta neutrality)
- Assets: BTC, ETH, SOL
- Entry: Predicted funding > 0.01% per 8h (10.95% annualized)
- Exit: Funding turns negative or basis > 2%
- Auto-compound: 50% reinvest, 50% to TACTICAL
- Max hold: 14 days

Risk Level: LOW
Market: Spot + Perpetual Futures (Delta Neutral)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.core.models import (EngineType, MarketData, Position, PositionSide,
                             SignalType, TradingSignal)
from src.engines.base import BaseEngine, EngineConfig

logger = structlog.get_logger(__name__)


@dataclass
class FundingEngineConfig(EngineConfig):
    """Configuration for FUNDING engine.

    Attributes:
        min_funding_rate: Minimum funding rate to enter (per 8h, default: 0.0001 = 0.01%)
        max_basis_pct: Maximum basis before exit (default: 0.02 = 2%)
        max_hold_days: Maximum days to hold position (default: 14)
        rebalance_threshold_pct: Rebalance if delta deviates > this (default: 2%)
        compound_pct: Percentage to reinvest vs transfer to TACTICAL (default: 0.5 = 50%)
        min_margin_ratio: Minimum margin ratio required (default: 0.30 = 30%)
        max_leverage: Maximum leverage for perp leg (default: 2.0)
        prediction_lookback_hours: Hours to look back for funding prediction (default: 168 = 1 week)
        assets: List of assets to trade (default: ['BTC', 'ETH', 'SOL'])
    """

    min_funding_rate: Decimal = Decimal("0.0001")  # 0.01% per 8h
    max_basis_pct: Decimal = Decimal("0.02")  # 2%
    max_hold_days: int = 14
    rebalance_threshold_pct: Decimal = Decimal("0.02")  # 2%
    compound_pct: Decimal = Decimal("0.5")  # 50% reinvest
    max_leverage: Decimal = Decimal("2.0")
    min_margin_ratio: Decimal = Decimal("0.30")  # 30%
    prediction_lookback_hours: int = 168  # 1 week
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH", "SOL"])

    def __post_init__(self):
        if not hasattr(self, "engine_type"):
            self.engine_type = EngineType.FUNDING

    @property
    def min_annualized_rate(self) -> Decimal:
        """Calculate minimum annualized funding rate (3 periods per day * 365)."""
        return self.min_funding_rate * 3 * 365


class FundingEngine(BaseEngine):
    """
    FUNDING Engine - Delta-neutral funding rate arbitrage.

    This engine harvests funding payments from perpetual futures while
    maintaining perfect delta neutrality through spot hedging.

    Key Behaviors:
    1. Delta Neutrality: Equal long spot and short perp positions
    2. Funding Harvest: Collect payments every 8 hours when funding > 0
    3. Auto-Rebalance: Maintain 1:1 ratio as prices move
    4. Profit Distribution: 50% compound, 50% to TACTICAL engine
    5. Risk Controls: Exit if basis > 2% or funding turns negative

    Position Structure:
    - Long Spot: Buy BTC/ETH/SOL in spot market
    - Short Perp: Short equivalent amount in perpetual futures
    - Net Delta: ~0 (neutral to price movements)
    - PnL Source: Funding payments received every 8 hours

    References:
    - See docs/04-trading-strategies/01-strategy-specifications.md
    - AGENTS.md section 2.3
    """

    def __init__(
        self,
        symbols: List[str] = None,
        config: Optional[FundingEngineConfig] = None,
        risk_manager=None,
    ):
        # Default symbols: Spot and Perp pairs
        if symbols is None:
            symbols = [
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT",
                "BTC-PERP",
                "ETH-PERP",
                "SOL-PERP",
            ]

        self.funding_config = config or FundingEngineConfig(
            engine_type=EngineType.FUNDING, allocation_pct=Decimal("0.15")
        )

        super().__init__(
            config=self.funding_config,
            engine_type=EngineType.FUNDING,
            symbols=symbols,
            risk_manager=risk_manager,
        )

        # Funding rate tracking
        self.current_funding_rates: Dict[str, Decimal] = {}
        self.predicted_funding_rates: Dict[str, Decimal] = {}
        self.funding_history: Dict[str, List[Tuple[datetime, Decimal]]] = {
            s: [] for s in self.funding_config.assets
        }

        # Active arbitrage positions
        # Structure: {asset: {'spot_size': Decimal, 'perp_size': Decimal, 'entry_time': datetime}}
        self.arbitrage_positions: Dict[str, Dict] = {}

        # Delta tracking (should stay near 0)
        self.delta_exposure: Dict[str, Decimal] = {
            a: Decimal("0") for a in self.funding_config.assets
        }

        # Profit tracking for distribution
        self.total_funding_earned: Decimal = Decimal("0")
        self.pending_tactical_transfer: Decimal = Decimal("0")

        # Rebalancing tracking
        self.last_rebalance_time: Dict[str, datetime] = {}

        # Statistics
        self.funding_collections: int = 0
        self.positions_opened: int = 0
        self.positions_closed: int = 0

        self.logger.info(
            "funding_engine.initialized",
            min_funding_rate=str(self.funding_config.min_funding_rate),
            min_annualized=str(self.funding_config.min_annualized_rate),
            max_basis=str(self.funding_config.max_basis_pct),
            assets=self.funding_config.assets,
        )

    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """
        Analyze funding rates and generate arbitrage signals.

        Entry Conditions:
        1. Predicted funding rate > min_funding_rate (0.01% per 8h)
        2. Sufficient margin available
        3. No existing position or small position

        Exit Conditions:
        1. Funding rate turns negative
        2. Basis exceeds max_basis_pct (2%)
        3. Position held > max_hold_days (14 days)
        4. Delta deviation > rebalance_threshold
        """
        signals = []

        if not self.is_active:
            return signals

        now = datetime.utcnow()

        for asset in self.funding_config.assets:
            spot_symbol = f"{asset}USDT"
            perp_symbol = f"{asset}-PERP"

            # Check if we have data for both legs
            if spot_symbol not in data or perp_symbol not in data:
                continue
            if not data[spot_symbol] or not data[perp_symbol]:
                continue

            # Get current prices
            spot_price = data[spot_symbol][-1].close
            perp_price = data[perp_symbol][-1].close

            # Calculate basis
            basis = (perp_price - spot_price) / spot_price

            # Update funding rate (would come from exchange in production)
            self._update_funding_rate(asset, now)

            # Check existing position
            has_position = asset in self.arbitrage_positions

            if has_position:
                # Check exit conditions
                exit_signal = self._check_exit_conditions(
                    asset, spot_price, perp_price, basis, now
                )
                if exit_signal:
                    signals.append(exit_signal)
                else:
                    # Check if rebalancing needed
                    rebalance_signal = self._check_rebalance_needed(
                        asset, spot_price, perp_price
                    )
                    if rebalance_signal:
                        signals.append(rebalance_signal)
            else:
                # Check entry conditions
                if self._check_entry_conditions(asset, basis):
                    entry_signals = self._create_entry_signals(
                        asset, spot_price, perp_price
                    )
                    signals.extend(entry_signals)

        return signals

    def _update_funding_rate(self, asset: str, now: datetime):
        """Update funding rate from market data (placeholder)."""
        # In production, this would fetch from exchange
        # For now, use simulated/predicted values
        predicted = self._predict_funding_rate(asset)
        self.predicted_funding_rates[asset] = predicted

    def _predict_funding_rate(self, asset: str) -> Decimal:
        """Predict next funding rate based on recent history and premium."""
        # Simplified prediction - in production use more sophisticated model
        # Could use: recent funding history, premium index, order book imbalance

        history = self.funding_history.get(asset, [])
        if len(history) < 3:
            return Decimal("0.0001")  # Conservative default

        # Simple average of recent funding rates
        recent = history[-5:]
        avg = sum(r[1] for r in recent) / len(recent)
        return max(avg, Decimal("0"))  # Don't predict negative

    def _check_entry_conditions(self, asset: str, basis: Decimal) -> bool:
        """Check if funding arbitrage entry conditions are met."""
        predicted = self.predicted_funding_rates.get(asset, Decimal("0"))
        min_rate = self.funding_config.min_funding_rate

        # Check funding rate threshold
        if predicted <= min_rate:
            return False

        # Check basis is not too wide (avoid high entry cost)
        if abs(basis) > self.funding_config.max_basis_pct:
            return False

        # Check we have capital available
        if self.state.current_value <= 0:
            return False

        self.logger.debug(
            "funding_engine.entry_check_passed",
            asset=asset,
            predicted=str(predicted),
            basis=str(basis),
            min_rate=str(min_rate),
        )

        return True

    def _check_exit_conditions(
        self,
        asset: str,
        spot_price: Decimal,
        perp_price: Decimal,
        basis: Decimal,
        now: datetime,
    ) -> Optional[TradingSignal]:
        """Check if funding arbitrage should be closed."""
        position = self.arbitrage_positions.get(asset)
        if not position:
            return None

        predicted = self.predicted_funding_rates.get(asset, Decimal("0"))
        entry_time = position.get("entry_time", now)
        hold_duration = now - entry_time

        # Exit 1: Funding turns negative (no longer profitable to hold)
        if predicted < 0:
            return self._create_exit_signal(
                asset,
                "funding_negative",
                f"Predicted funding turned negative: {predicted}",
            )

        # Exit 2: Basis exceeds threshold (futures too expensive vs spot)
        if abs(basis) > self.funding_config.max_basis_pct:
            return self._create_exit_signal(
                asset,
                "basis_limit",
                f"Basis {basis:.4%} exceeds {self.funding_config.max_basis_pct:.1%}",
            )

        # Exit 3: Max hold time reached
        if hold_duration.days >= self.funding_config.max_hold_days:
            return self._create_exit_signal(
                asset,
                "time_limit",
                f"Held for {hold_duration.days} days (max: {self.funding_config.max_hold_days})",
            )

        return None

    def _check_rebalance_needed(
        self, asset: str, spot_price: Decimal, perp_price: Decimal
    ) -> Optional[TradingSignal]:
        """Check if delta-neutral position needs rebalancing."""
        position = self.arbitrage_positions.get(asset)
        if not position:
            return None

        spot_size = position.get("spot_size", Decimal("0"))
        perp_size = position.get("perp_size", Decimal("0"))

        # Calculate notional values
        spot_notional = spot_size * spot_price
        perp_notional = perp_size * perp_price

        # Calculate delta (should be close to 0)
        # Long spot = positive delta, Short perp = positive delta (offset)
        # For perfect hedge: spot_notional ≈ perp_notional
        delta = spot_notional - perp_notional
        total_notional = (spot_notional + perp_notional) / 2

        if total_notional == 0:
            return None

        delta_deviation = abs(delta) / total_notional

        if delta_deviation > self.funding_config.rebalance_threshold_pct:
            return self._create_rebalance_signal(
                asset, spot_notional, perp_notional, delta
            )

        return None

    def _create_entry_signals(
        self, asset: str, spot_price: Decimal, perp_price: Decimal
    ) -> List[TradingSignal]:
        """Create entry signals for both legs of the arbitrage."""
        signals = []

        # Calculate position size based on allocation
        # Split allocation evenly across assets
        asset_allocation = self.state.current_value / len(self.funding_config.assets)
        position_size = asset_allocation * Decimal(
            "0.5"
        )  # Use 50% of allocation per asset

        # Calculate quantities
        spot_qty = position_size / spot_price
        perp_qty = position_size / perp_price

        predicted = self.predicted_funding_rates.get(asset, Decimal("0"))

        # Spot buy signal (long)
        spot_metadata = {
            "strategy": "FUNDING",
            "leg": "spot_long",
            "pair_asset": asset,
            "quantity": str(spot_qty),
            "price": str(spot_price),
            "predicted_funding": str(predicted),
            "expected_apy": str(predicted * 3 * 365),
        }

        signals.append(
            self._create_signal(
                symbol=f"{asset}USDT",
                signal_type=SignalType.BUY,
                confidence=0.9,
                metadata=spot_metadata,
            )
        )

        # Perp short signal
        perp_metadata = {
            "strategy": "FUNDING",
            "leg": "perp_short",
            "pair_asset": asset,
            "quantity": str(perp_qty),
            "price": str(perp_price),
            "leverage": str(self.funding_config.max_leverage),
            "predicted_funding": str(predicted),
        }

        signals.append(
            self._create_signal(
                symbol=f"{asset}-PERP",
                signal_type=SignalType.SELL,
                confidence=0.9,
                metadata=perp_metadata,
            )
        )

        self.logger.info(
            "funding_engine.entry_signals_created",
            asset=asset,
            spot_qty=str(spot_qty),
            perp_qty=str(perp_qty),
            predicted_funding=str(predicted),
        )

        return signals

    def _create_exit_signal(
        self, asset: str, reason: str, details: str
    ) -> TradingSignal:
        """Create exit signal to close both legs."""
        metadata = {
            "strategy": "FUNDING",
            "action": "close_arbitrage",
            "asset": asset,
            "exit_reason": reason,
            "details": details,
        }

        # Signal on the perp side (primary tracking)
        self.logger.info(
            "funding_engine.exit_signal", asset=asset, reason=reason, details=details
        )

        return self._create_signal(
            symbol=f"{asset}-PERP",
            signal_type=SignalType.CLOSE,
            confidence=1.0,
            metadata=metadata,
        )

    def _create_rebalance_signal(
        self, asset: str, spot_notional: Decimal, perp_notional: Decimal, delta: Decimal
    ) -> TradingSignal:
        """Create rebalancing signal."""
        metadata = {
            "strategy": "FUNDING",
            "action": "rebalance",
            "asset": asset,
            "spot_notional": str(spot_notional),
            "perp_notional": str(perp_notional),
            "delta": str(delta),
            "reason": "delta_neutrality",
        }

        self.logger.info(
            "funding_engine.rebalance_signal",
            asset=asset,
            delta=str(delta),
            spot=str(spot_notional),
            perp=str(perp_notional),
        )

        return self._create_signal(
            symbol=f"{asset}USDT",
            signal_type=SignalType.REBALANCE,
            confidence=0.95,
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
        """Track order fills and update arbitrage positions."""
        # Extract asset from symbol
        asset = None
        for a in self.funding_config.assets:
            if a in symbol:
                asset = a
                break

        if not asset:
            return

        is_spot = "PERP" not in symbol

        # Initialize position tracking
        if asset not in self.arbitrage_positions:
            self.arbitrage_positions[asset] = {
                "spot_size": Decimal("0"),
                "perp_size": Decimal("0"),
                "entry_time": datetime.utcnow(),
                "entry_spot_price": Decimal("0"),
                "entry_perp_price": Decimal("0"),
            }

        position = self.arbitrage_positions[asset]

        if is_spot:
            # Spot leg
            if side == "buy":
                position["spot_size"] += amount
                if position["entry_spot_price"] == 0:
                    position["entry_spot_price"] = price
            else:
                position["spot_size"] -= amount
        else:
            # Perp leg
            if side == "sell":  # Short
                position["perp_size"] += amount
                if position["entry_perp_price"] == 0:
                    position["entry_perp_price"] = price
            else:  # Cover short
                position["perp_size"] -= amount

        # Update delta
        spot_notional = (
            position["spot_size"] * price
            if is_spot
            else position["spot_size"] * position.get("entry_spot_price", price)
        )
        perp_notional = (
            position["perp_size"] * price
            if not is_spot
            else position["perp_size"] * position.get("entry_perp_price", price)
        )
        self.delta_exposure[asset] = spot_notional - perp_notional

        self.signals_executed += 1

        self.logger.info(
            "funding_engine.order_filled",
            asset=asset,
            symbol=symbol,
            side=side,
            amount=str(amount),
            price=str(price),
            spot_size=str(position["spot_size"]),
            perp_size=str(position["perp_size"]),
            delta=str(self.delta_exposure[asset]),
        )

    async def on_position_closed(
        self, symbol: str, pnl: Decimal, pnl_pct: Decimal, close_reason: str = "signal"
    ):
        """Track position close and handle profit distribution."""
        # Extract asset
        asset = None
        for a in self.funding_config.assets:
            if a in symbol:
                asset = a
                break

        # Update PnL
        self.total_pnl += pnl

        # Handle profit distribution
        if pnl > 0:
            self.state.winning_trades += 1

            # Split profits: compound_pct reinvest, rest to TACTICAL
            compound_amount = pnl * self.funding_config.compound_pct
            tactical_amount = pnl * (Decimal("1") - self.funding_config.compound_pct)
            self.pending_tactical_transfer += tactical_amount

            self.logger.info(
                "funding_engine.profit_distribution",
                asset=asset,
                total_pnl=str(pnl),
                compound=str(compound_amount),
                to_tactical=str(tactical_amount),
            )
        else:
            self.state.losing_trades += 1

        # Clean up if both legs closed
        if asset and asset in self.arbitrage_positions:
            position = self.arbitrage_positions[asset]
            if position["spot_size"] <= 0 and position["perp_size"] <= 0:
                del self.arbitrage_positions[asset]
                self.delta_exposure[asset] = Decimal("0")
                self.positions_closed += 1

        self.logger.info(
            "funding_engine.position_closed",
            asset=asset,
            symbol=symbol,
            pnl=str(pnl),
            reason=close_reason,
        )

    def record_funding_payment(self, asset: str, amount: Decimal, timestamp: datetime):
        """Record a funding payment received."""
        self.total_funding_earned += amount
        self.funding_collections += 1

        # Add to history
        self.funding_history[asset].append((timestamp, amount))
        # Keep last 30 days
        cutoff = timestamp - timedelta(days=30)
        self.funding_history[asset] = [
            h for h in self.funding_history[asset] if h[0] > cutoff
        ]

        self.logger.info(
            "funding_engine.payment_received",
            asset=asset,
            amount=str(amount),
            total_earned=str(self.total_funding_earned),
        )

    def get_arbitrage_status(self, asset: str) -> Optional[Dict[str, Any]]:
        """Get current arbitrage position status."""
        if asset not in self.arbitrage_positions:
            return None

        pos = self.arbitrage_positions[asset]
        return {
            "asset": asset,
            "spot_size": str(pos["spot_size"]),
            "perp_size": str(pos["perp_size"]),
            "entry_time": pos["entry_time"].isoformat() if pos["entry_time"] else None,
            "entry_spot_price": str(pos["entry_spot_price"]),
            "entry_perp_price": str(pos["entry_perp_price"]),
            "delta_exposure": str(self.delta_exposure.get(asset, "0")),
            "current_funding": str(self.current_funding_rates.get(asset, "0")),
            "predicted_funding": str(self.predicted_funding_rates.get(asset, "0")),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get FUNDING engine statistics."""
        base_stats = super().get_stats()
        base_stats.update(
            {
                "total_funding_earned": str(self.total_funding_earned),
                "funding_collections": self.funding_collections,
                "pending_tactical_transfer": str(self.pending_tactical_transfer),
                "positions_opened": self.positions_opened,
                "positions_closed": self.positions_closed,
                "active_arbitrages": [
                    self.get_arbitrage_status(a)
                    for a in self.funding_config.assets
                    if a in self.arbitrage_positions
                ],
                "delta_exposure": {k: str(v) for k, v in self.delta_exposure.items()},
            }
        )
        return base_stats

    def get_full_state(self) -> Dict[str, Any]:
        """
        Get complete state for persistence.

        Returns:
            Dictionary with all critical FUNDING state that must survive restarts.
        """
        # Serialize funding history (keep last 100 entries to limit size)
        funding_history_serializable = {}
        for asset, history in self.funding_history.items():
            funding_history_serializable[asset] = [
                {"timestamp": ts.isoformat(), "rate": str(rate)}
                for ts, rate in history[-100:]  # Last 100 entries
            ]

        # Serialize arbitrage positions
        arbitrage_positions_serializable = {}
        for asset, position in self.arbitrage_positions.items():
            arbitrage_positions_serializable[asset] = {
                "spot_size": str(position.get("spot_size", Decimal("0"))),
                "perp_size": str(position.get("perp_size", Decimal("0"))),
                "entry_time": (
                    position.get("entry_time").isoformat()
                    if position.get("entry_time")
                    else None
                ),
                "entry_spot_price": str(position.get("entry_spot_price", Decimal("0"))),
                "entry_perp_price": str(position.get("entry_perp_price", Decimal("0"))),
            }

        return {
            "engine_type": self.engine_type.value,
            "symbols": self.symbols,
            # Funding rate tracking
            "current_funding_rates": {
                k: str(v) for k, v in self.current_funding_rates.items()
            },
            "predicted_funding_rates": {
                k: str(v) for k, v in self.predicted_funding_rates.items()
            },
            "funding_history": funding_history_serializable,
            # Active arbitrage positions
            "arbitrage_positions": arbitrage_positions_serializable,
            # Delta tracking
            "delta_exposure": {k: str(v) for k, v in self.delta_exposure.items()},
            # Profit tracking
            "total_funding_earned": str(self.total_funding_earned),
            "pending_tactical_transfer": str(self.pending_tactical_transfer),
            # Rebalancing tracking
            "last_rebalance_time": {
                k: v.isoformat() if v else None
                for k, v in self.last_rebalance_time.items()
            },
            # Statistics
            "funding_collections": self.funding_collections,
            "positions_opened": self.positions_opened,
            "positions_closed": self.positions_closed,
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
        from decimal import Decimal

        try:
            # Restore funding rate tracking
            for key in ["current_funding_rates", "predicted_funding_rates"]:
                if key in state:
                    for asset, value_str in state[key].items():
                        try:
                            getattr(self, key)[asset] = Decimal(value_str)
                        except (ValueError, TypeError):
                            getattr(self, key)[asset] = Decimal("0")

            # Restore funding history
            if "funding_history" in state:
                for asset, history_list in state["funding_history"].items():
                    restored_history = []
                    for entry in history_list:
                        try:
                            ts = datetime.fromisoformat(entry["timestamp"])
                            rate = Decimal(entry["rate"])
                            restored_history.append((ts, rate))
                        except (ValueError, TypeError, KeyError):
                            continue
                    self.funding_history[asset] = restored_history

            # Restore arbitrage positions
            if "arbitrage_positions" in state:
                for asset, position_data in state["arbitrage_positions"].items():
                    try:
                        position = {
                            "spot_size": Decimal(position_data.get("spot_size", "0")),
                            "perp_size": Decimal(position_data.get("perp_size", "0")),
                            "entry_spot_price": Decimal(
                                position_data.get("entry_spot_price", "0")
                            ),
                            "entry_perp_price": Decimal(
                                position_data.get("entry_perp_price", "0")
                            ),
                        }

                        # Parse entry time
                        entry_time_str = position_data.get("entry_time")
                        if entry_time_str:
                            try:
                                position["entry_time"] = datetime.fromisoformat(
                                    entry_time_str
                                )
                            except (ValueError, TypeError):
                                position["entry_time"] = datetime.utcnow()
                        else:
                            position["entry_time"] = datetime.utcnow()

                        self.arbitrage_positions[asset] = position
                    except (ValueError, TypeError) as e:
                        self.logger.warning(
                            "funding_engine.restore_position_failed",
                            asset=asset,
                            error=str(e),
                        )

            # Restore delta exposure
            if "delta_exposure" in state:
                for asset, value_str in state["delta_exposure"].items():
                    try:
                        self.delta_exposure[asset] = Decimal(value_str)
                    except (ValueError, TypeError):
                        self.delta_exposure[asset] = Decimal("0")

            # Restore profit tracking
            if "total_funding_earned" in state:
                try:
                    self.total_funding_earned = Decimal(state["total_funding_earned"])
                except (ValueError, TypeError):
                    self.total_funding_earned = Decimal("0")

            if "pending_tactical_transfer" in state:
                try:
                    self.pending_tactical_transfer = Decimal(
                        state["pending_tactical_transfer"]
                    )
                except (ValueError, TypeError):
                    self.pending_tactical_transfer = Decimal("0")

            # Restore rebalancing tracking
            if "last_rebalance_time" in state:
                for asset, timestamp_str in state["last_rebalance_time"].items():
                    if timestamp_str:
                        try:
                            self.last_rebalance_time[asset] = datetime.fromisoformat(
                                timestamp_str
                            )
                        except (ValueError, TypeError):
                            pass

            # Restore statistics
            if "funding_collections" in state:
                self.funding_collections = state["funding_collections"]
            if "positions_opened" in state:
                self.positions_opened = state["positions_opened"]
            if "positions_closed" in state:
                self.positions_closed = state["positions_closed"]

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
                "funding_engine.state_restored",
                active_positions=list(self.arbitrage_positions.keys()),
                total_funding_earned=str(self.total_funding_earned),
                total_pnl=str(self.total_pnl),
            )
        except Exception as e:
            self.logger.error("funding_engine.state_restore_error", error=str(e))
            # Continue with default values - don't crash on restore failure
