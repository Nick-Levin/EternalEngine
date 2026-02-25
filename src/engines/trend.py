"""
TREND Engine (20% Allocation)

Trend-following strategy for perpetual futures.
Captures large directional moves while protecting capital in bear markets.

Strategy:
- Assets: BTC-PERP, ETH-PERP
- Entry: Price > 200SMA, 50SMA > 200SMA, ADX > 25
- Exit: Price closes below 200SMA
- Max leverage: 2x (liquidation buffer >50%)
- Risk per trade: 1% of engine capital
- Trailing stop: 3x ATR

Risk Level: MODERATE
Market: Perpetual Futures
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import structlog

from src.core.models import (EngineType, MarketData, Position, PositionSide,
                             SignalType, TradingSignal)
from src.engines.base import BaseEngine, EngineConfig

logger = structlog.get_logger(__name__)


@dataclass
class TrendEngineConfig(EngineConfig):
    """Configuration for TREND engine.

    Attributes:
        ema_fast_period: Fast EMA period (default: 50)
        ema_slow_period: Slow EMA/SMA period (default: 200)
        adx_period: ADX calculation period (default: 14)
        adx_threshold: Minimum ADX for trend confirmation (default: 25)
        atr_period: ATR calculation period (default: 14)
        atr_multiplier: ATR multiplier for stops (default: 3.0)
        max_leverage: Maximum allowed leverage (default: 2.0)
        risk_per_trade: Risk per trade as % of capital (default: 1%)
        trailing_stop_enabled: Enable trailing stops (default: True)
        trailing_activation_r: R-multiple to activate trailing (default: 1.0)
        trailing_distance_atr: ATR multiple for trailing distance (default: 3.0)
        btc_allocation: BTC-PERP allocation % (default: 60%)
        eth_allocation: ETH-PERP allocation % (default: 40%)
    """

    ema_fast_period: int = 50
    ema_slow_period: int = 200
    adx_period: int = 14
    adx_threshold: Decimal = Decimal("25.0")
    atr_period: int = 14
    atr_multiplier: Decimal = Decimal("2.0")
    max_leverage: Decimal = Decimal("2.0")
    risk_per_trade: Decimal = Decimal("0.01")  # 1%
    trailing_stop_enabled: bool = True
    trailing_activation_r: Decimal = Decimal("1.0")
    trailing_distance_atr: Decimal = Decimal("3.0")
    btc_allocation: Decimal = Decimal("0.60")
    eth_allocation: Decimal = Decimal("0.40")

    def __post_init__(self):
        if not hasattr(self, "engine_type"):
            self.engine_type = EngineType.TREND


class TrendEngine(BaseEngine):
    """
    TREND Engine - Systematic trend following on perpetual futures.

    This engine generates "crisis alpha" by capturing large directional
    moves and moving to cash/stables during bear markets.

    Key Behaviors:
    1. Long-only when trend is up (200 SMA filter)
    2. Early trend confirmation (50 EMA > 200 SMA)
    3. Trend strength filter (ADX > 25)
    4. ATR-based position sizing and stops
    5. Automatic exit when trend reverses

    Technical Indicators:
    - 50 EMA: Early trend detection
    - 200 SMA: Major trend filter
    - ADX(14): Trend strength measurement
    - ATR(14): Volatility-based position sizing

    References:
    - See docs/04-trading-strategies/01-strategy-specifications.md
    - AGENTS.md section 2.2
    """

    def __init__(
        self,
        symbols: List[str] = None,
        config: Optional[TrendEngineConfig] = None,
        risk_manager=None,
    ):
        # Default symbols: BTC and ETH perpetuals
        if symbols is None:
            symbols = ["BTC-PERP", "ETH-PERP"]

        self.trend_config = config or TrendEngineConfig(
            engine_type=EngineType.TREND, allocation_pct=Decimal("0.20")
        )

        super().__init__(
            config=self.trend_config,
            engine_type=EngineType.TREND,
            symbols=symbols,
            risk_manager=risk_manager,
        )

        # Technical indicator state
        self.ema_fast: Dict[str, Decimal] = {}
        self.ema_slow: Dict[str, Decimal] = {}
        self.adx: Dict[str, Decimal] = {}
        self.atr: Dict[str, Decimal] = {}

        # Position tracking with entry details
        self.entry_prices: Dict[str, Decimal] = {}
        self.stop_losses: Dict[str, Decimal] = {}
        self.trailing_stops: Dict[str, Decimal] = {}
        self.position_risk: Dict[str, Decimal] = {}  # Risk amount per position

        # Trade statistics
        self.trend_entries: Dict[str, int] = {s: 0 for s in symbols}
        self.trend_exits: Dict[str, int] = {s: 0 for s in symbols}
        self.winning_trades_by_symbol: Dict[str, int] = {s: 0 for s in symbols}
        self.losing_trades_by_symbol: Dict[str, int] = {s: 0 for s in symbols}

        self.logger.info(
            "trend_engine.initialized",
            ema_fast=self.trend_config.ema_fast_period,
            ema_slow=self.trend_config.ema_slow_period,
            adx_threshold=str(self.trend_config.adx_threshold),
            max_leverage=str(self.trend_config.max_leverage),
        )

    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """
        Analyze trends and generate entry/exit signals.

        Entry Conditions (ALL must be met):
        1. Price > 200 SMA (major trend up)
        2. 50 EMA > 200 SMA (early trend confirmation)
        3. ADX > 25 (trend has strength)

        Exit Conditions (ANY triggers exit):
        1. Price closes below 200 SMA (trend reversal)
        2. Stop loss hit (ATR-based)
        3. Trailing stop activated and hit
        """
        signals = []

        if not self.is_active:
            return signals

        for symbol in self.symbols:
            if (
                symbol not in data
                or len(data[symbol]) < self.trend_config.ema_slow_period
            ):
                continue

            bars = data[symbol]
            current_price = bars[-1].close

            # Calculate indicators
            self._calculate_indicators(symbol, bars)

            # Check if we have a position
            has_position = symbol in self.positions and self.positions[symbol].is_open

            if has_position:
                # Check exit conditions
                exit_signal = self._check_exit_conditions(symbol, current_price, bars)
                if exit_signal:
                    signals.append(exit_signal)
            else:
                # Check entry conditions
                if self._check_entry_conditions(symbol, current_price):
                    signal = self._create_entry_signal(symbol, current_price)
                    signals.append(signal)

        return signals

    def _calculate_indicators(self, symbol: str, bars: List[MarketData]):
        """Calculate EMA, SMA, ADX, and ATR for the symbol."""
        closes = [bar.close for bar in bars]
        highs = [bar.high for bar in bars]
        lows = [bar.low for bar in bars]

        # Calculate EMAs
        self.ema_fast[symbol] = self._calculate_ema(
            closes, self.trend_config.ema_fast_period
        )

        # Calculate SMA (200)
        self.ema_slow[symbol] = self._calculate_sma(
            closes, self.trend_config.ema_slow_period
        )

        # Calculate ADX
        self.adx[symbol] = self._calculate_adx(
            highs, lows, closes, self.trend_config.adx_period
        )

        # Calculate ATR
        self.atr[symbol] = self._calculate_atr(
            highs, lows, closes, self.trend_config.atr_period
        )

    def _calculate_ema(self, prices: List[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return prices[-1] if prices else Decimal("0")

        multiplier = Decimal("2") / (Decimal(str(period)) + Decimal("1"))
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (Decimal("1") - multiplier))

        return ema

    def _calculate_sma(self, prices: List[Decimal], period: int) -> Decimal:
        """Calculate Simple Moving Average."""
        if len(prices) < period:
            return prices[-1] if prices else Decimal("0")

        return sum(prices[-period:]) / period

    def _calculate_adx(
        self,
        highs: List[Decimal],
        lows: List[Decimal],
        closes: List[Decimal],
        period: int,
    ) -> Decimal:
        """Calculate Average Directional Index (ADX)."""
        if len(closes) < period + 1:
            return Decimal("0")

        # Calculate True Range and Directional Movement
        tr_values = []
        plus_dm_values = []
        minus_dm_values = []

        for i in range(1, len(closes)):
            # True Range
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i - 1])
            tr3 = abs(lows[i] - closes[i - 1])
            tr = max(tr1, tr2, tr3)
            tr_values.append(tr)

            # Directional Movement
            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]

            if up_move > down_move and up_move > 0:
                plus_dm_values.append(up_move)
            else:
                plus_dm_values.append(Decimal("0"))

            if down_move > up_move and down_move > 0:
                minus_dm_values.append(down_move)
            else:
                minus_dm_values.append(Decimal("0"))

        if len(tr_values) < period:
            return Decimal("25")  # Neutral ADX

        # Calculate smoothed averages
        atr = sum(tr_values[-period:]) / period
        plus_di = (
            100 * (sum(plus_dm_values[-period:]) / period) / atr
            if atr > 0
            else Decimal("0")
        )
        minus_di = (
            100 * (sum(minus_dm_values[-period:]) / period) / atr
            if atr > 0
            else Decimal("0")
        )

        # Calculate DX and ADX
        dx = (
            100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            if (plus_di + minus_di) > 0
            else Decimal("0")
        )

        return dx  # Simplified - real ADX requires smoothing

    def _calculate_atr(
        self,
        highs: List[Decimal],
        lows: List[Decimal],
        closes: List[Decimal],
        period: int,
    ) -> Decimal:
        """Calculate Average True Range."""
        if len(closes) < period + 1:
            return Decimal("0")

        tr_values = []
        for i in range(1, len(closes)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i - 1])
            tr3 = abs(lows[i] - closes[i - 1])
            tr_values.append(max(tr1, tr2, tr3))

        if len(tr_values) < period:
            return tr_values[-1] if tr_values else Decimal("0")

        return sum(tr_values[-period:]) / period

    def _check_entry_conditions(self, symbol: str, current_price: Decimal) -> bool:
        """Check if all entry conditions are met."""
        # Get indicator values
        ema_50 = self.ema_fast.get(symbol, Decimal("0"))
        sma_200 = self.ema_slow.get(symbol, Decimal("0"))
        adx = self.adx.get(symbol, Decimal("0"))

        # Condition 1: Price > 200 SMA
        price_above_sma = current_price > sma_200

        # Condition 2: 50 EMA > 200 SMA
        ema_above_sma = ema_50 > sma_200

        # Condition 3: ADX > threshold
        adx_strong = adx > self.trend_config.adx_threshold

        # Log status
        self.logger.debug(
            "trend_engine.entry_check",
            symbol=symbol,
            price=str(current_price),
            sma_200=str(sma_200),
            ema_50=str(ema_50),
            adx=str(adx),
            price_above_sma=price_above_sma,
            ema_above_sma=ema_above_sma,
            adx_strong=adx_strong,
        )

        return price_above_sma and ema_above_sma and adx_strong

    def _check_exit_conditions(
        self, symbol: str, current_price: Decimal, bars: List[MarketData]
    ) -> Optional[TradingSignal]:
        """Check if position should be exited."""
        position = self.positions.get(symbol)
        if not position or not position.is_open:
            return None

        sma_200 = self.ema_slow.get(symbol, Decimal("0"))
        atr = self.atr.get(symbol, Decimal("0"))
        entry_price = self.entry_prices.get(symbol, position.entry_price)

        # Exit 1: Price closes below 200 SMA
        if current_price < sma_200:
            return self._create_exit_signal(
                symbol, current_price, "trend_reversal", "Price below 200 SMA"
            )

        # Exit 2: Stop loss hit
        stop_loss = self.stop_losses.get(symbol)
        if stop_loss and current_price <= stop_loss:
            return self._create_exit_signal(
                symbol, current_price, "stop_loss", f"Stop at {stop_loss}"
            )

        # Exit 3: Trailing stop
        if self.trend_config.trailing_stop_enabled:
            trailing_stop = self._update_trailing_stop(
                symbol, current_price, entry_price, atr
            )
            if trailing_stop and current_price <= trailing_stop:
                return self._create_exit_signal(
                    symbol,
                    current_price,
                    "trailing_stop",
                    f"Trailing stop at {trailing_stop}",
                )

        return None

    def _update_trailing_stop(
        self, symbol: str, current_price: Decimal, entry_price: Decimal, atr: Decimal
    ) -> Optional[Decimal]:
        """Update trailing stop if profit target reached."""
        if atr == 0:
            return None

        # Calculate profit in R-multiples
        risk_per_r = atr * self.trend_config.atr_multiplier
        if risk_per_r == 0:
            return None

        current_r = (current_price - entry_price) / risk_per_r

        # Activate trailing stop after 1R profit
        if current_r >= self.trend_config.trailing_activation_r:
            # Set trailing stop at 3x ATR below current price
            trailing_distance = atr * self.trend_config.trailing_distance_atr
            new_stop = current_price - trailing_distance

            # Only move stop up, never down
            current_trailing = self.trailing_stops.get(symbol)
            if current_trailing is None or new_stop > current_trailing:
                self.trailing_stops[symbol] = new_stop
                self.logger.info(
                    "trend_engine.trailing_stop_updated",
                    symbol=symbol,
                    new_stop=str(new_stop),
                    current_r=str(current_r),
                )

            return self.trailing_stops[symbol]

        return None

    def _create_entry_signal(
        self, symbol: str, current_price: Decimal
    ) -> TradingSignal:
        """Create a trend entry signal."""
        # Calculate position size based on risk
        atr = self.atr.get(symbol, Decimal("0"))
        stop_distance = atr * self.trend_config.atr_multiplier

        if stop_distance > 0:
            risk_amount = self.state.current_value * self.trend_config.risk_per_trade
            position_size = risk_amount / stop_distance
        else:
            position_size = Decimal("0")

        stop_price = current_price - stop_distance

        # Determine allocation
        if "BTC" in symbol:
            allocation = self.trend_config.btc_allocation
        else:
            allocation = self.trend_config.eth_allocation

        metadata = {
            "strategy": "TREND",
            "entry_price": str(current_price),
            "stop_loss": str(stop_price),
            "atr": str(atr),
            "ema_50": str(self.ema_fast.get(symbol)),
            "sma_200": str(self.ema_slow.get(symbol)),
            "adx": str(self.adx.get(symbol)),
            "position_size": str(position_size),
            "leverage": str(self.trend_config.max_leverage),
            "allocation": str(allocation),
        }

        self.logger.info(
            "trend_engine.entry_signal",
            symbol=symbol,
            price=str(current_price),
            stop=str(stop_price),
            adx=str(self.adx.get(symbol)),
        )

        return self._create_signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            confidence=0.85,
            metadata=metadata,
        )

    def _create_exit_signal(
        self, symbol: str, current_price: Decimal, reason: str, details: str
    ) -> TradingSignal:
        """Create an exit signal."""
        metadata = {
            "strategy": "TREND",
            "exit_price": str(current_price),
            "exit_reason": reason,
            "details": details,
            "sma_200": str(self.ema_slow.get(symbol)),
            "entry_price": str(self.entry_prices.get(symbol, "0")),
        }

        self.logger.info(
            "trend_engine.exit_signal",
            symbol=symbol,
            price=str(current_price),
            reason=reason,
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
        """Track order fills and update position state."""
        if side == "buy":
            # Entry
            self.entry_prices[symbol] = price
            self.trend_entries[symbol] = self.trend_entries.get(symbol, 0) + 1

            # Set initial stop loss
            atr = self.atr.get(symbol, Decimal("0"))
            stop_distance = atr * self.trend_config.atr_multiplier
            self.stop_losses[symbol] = price - stop_distance
            self.trailing_stops[symbol] = None  # Reset trailing stop

            # Record position
            if symbol not in self.positions:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    entry_price=price,
                    amount=amount,
                    leverage=self.trend_config.max_leverage,
                )

            self.signals_executed += 1
            self.state.total_trades += 1

            self.logger.info(
                "trend_engine.entry_filled",
                symbol=symbol,
                price=str(price),
                amount=str(amount),
                stop_loss=str(self.stop_losses[symbol]),
            )

        elif side == "sell":
            # Exit - will trigger on_position_closed
            self.logger.info(
                "trend_engine.exit_filled",
                symbol=symbol,
                price=str(price),
                amount=str(amount),
            )

    async def on_position_closed(
        self, symbol: str, pnl: Decimal, pnl_pct: Decimal, close_reason: str = "signal"
    ):
        """Track position close and update statistics."""
        self.total_pnl += pnl
        self.trend_exits[symbol] = self.trend_exits.get(symbol, 0) + 1

        # Update win/loss tracking
        if pnl > 0:
            self.state.winning_trades += 1
            self.winning_trades_by_symbol[symbol] = (
                self.winning_trades_by_symbol.get(symbol, 0) + 1
            )
        else:
            self.state.losing_trades += 1
            self.losing_trades_by_symbol[symbol] = (
                self.losing_trades_by_symbol.get(symbol, 0) + 1
            )

        # Cleanup
        if symbol in self.positions:
            del self.positions[symbol]
        if symbol in self.entry_prices:
            del self.entry_prices[symbol]
        if symbol in self.stop_losses:
            del self.stop_losses[symbol]
        if symbol in self.trailing_stops:
            del self.trailing_stops[symbol]

        self.logger.info(
            "trend_engine.position_closed",
            symbol=symbol,
            pnl=str(pnl),
            pnl_pct=str(pnl_pct),
            reason=close_reason,
            total_entries=self.trend_entries.get(symbol, 0),
            total_exits=self.trend_exits.get(symbol, 0),
        )

    def get_trend_status(self, symbol: str) -> Dict[str, Any]:
        """Get current trend status for a symbol."""
        return {
            "ema_50": str(self.ema_fast.get(symbol, "N/A")),
            "sma_200": str(self.ema_slow.get(symbol, "N/A")),
            "adx": str(self.adx.get(symbol, "N/A")),
            "atr": str(self.atr.get(symbol, "N/A")),
            "has_position": symbol in self.positions and self.positions[symbol].is_open,
            "entry_price": str(self.entry_prices.get(symbol, "N/A")),
            "stop_loss": str(self.stop_losses.get(symbol, "N/A")),
            "trailing_stop": str(self.trailing_stops.get(symbol, "N/A")),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get TREND engine statistics."""
        base_stats = super().get_stats()
        base_stats.update(
            {
                "entries_by_symbol": self.trend_entries,
                "exits_by_symbol": self.trend_exits,
                "winners_by_symbol": self.winning_trades_by_symbol,
                "losers_by_symbol": self.losing_trades_by_symbol,
                "trend_status": {s: self.get_trend_status(s) for s in self.symbols},
            }
        )
        return base_stats

    def get_full_state(self) -> Dict[str, Any]:
        """
        Get complete state for persistence.

        Returns:
            Dictionary with all critical TREND state that must survive restarts.
        """
        return {
            "engine_type": self.engine_type.value,
            "symbols": self.symbols,
            # Technical indicator state (will be recalculated, but useful for reference)
            "ema_fast": {k: str(v) for k, v in self.ema_fast.items()},
            "ema_slow": {k: str(v) for k, v in self.ema_slow.items()},
            "adx": {k: str(v) for k, v in self.adx.items()},
            "atr": {k: str(v) for k, v in self.atr.items()},
            # Position tracking with entry details
            "entry_prices": {k: str(v) for k, v in self.entry_prices.items()},
            "stop_losses": {k: str(v) for k, v in self.stop_losses.items()},
            "trailing_stops": {
                k: str(v) if v is not None else None
                for k, v in self.trailing_stops.items()
            },
            "position_risk": {k: str(v) for k, v in self.position_risk.items()},
            # Trade statistics
            "trend_entries": self.trend_entries,
            "trend_exits": self.trend_exits,
            "winning_trades_by_symbol": self.winning_trades_by_symbol,
            "losing_trades_by_symbol": self.losing_trades_by_symbol,
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
            # Restore technical indicator state
            for key in ["ema_fast", "ema_slow", "adx", "atr"]:
                if key in state:
                    for symbol, value_str in state[key].items():
                        try:
                            getattr(self, key)[symbol] = Decimal(value_str)
                        except (ValueError, TypeError):
                            getattr(self, key)[symbol] = Decimal("0")

            # Restore position tracking
            for key in ["entry_prices", "stop_losses", "position_risk"]:
                if key in state:
                    for symbol, value_str in state[key].items():
                        try:
                            getattr(self, key)[symbol] = Decimal(value_str)
                        except (ValueError, TypeError):
                            getattr(self, key)[symbol] = Decimal("0")

            # Restore trailing stops (can be None)
            if "trailing_stops" in state:
                for symbol, value_str in state["trailing_stops"].items():
                    if value_str is None:
                        self.trailing_stops[symbol] = None
                    else:
                        try:
                            self.trailing_stops[symbol] = Decimal(value_str)
                        except (ValueError, TypeError):
                            self.trailing_stops[symbol] = None

            # Restore trade statistics
            for key in [
                "trend_entries",
                "trend_exits",
                "winning_trades_by_symbol",
                "losing_trades_by_symbol",
            ]:
                if key in state:
                    getattr(self, key).update(state[key])

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
                "trend_engine.state_restored",
                active_positions=list(self.entry_prices.keys()),
                total_trades=self.state.total_trades,
                total_pnl=str(self.total_pnl),
            )
        except Exception as e:
            self.logger.error("trend_engine.state_restore_error", error=str(e))
            # Continue with default values - don't crash on restore failure
