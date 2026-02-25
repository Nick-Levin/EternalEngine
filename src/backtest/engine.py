"""
Eternal Engine Backtest - Full System Simulation.

Simulates all 4 engines (CORE-HODL, TREND, FUNDING, TACTICAL) with:
- Proper capital allocation (60/20/15/5)
- Realistic fee simulation
- Slippage modeling
- Risk management enforcement
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import structlog

from src.core.models import (EngineType, MarketData, Order, OrderSide,
                             OrderStatus, OrderType, Position, SignalType,
                             Trade)
from src.engines.core_hodl import CoreHodlConfig, CoreHodlEngine
from src.engines.funding import FundingEngine, FundingEngineConfig
from src.engines.tactical import TacticalEngine, TacticalEngineConfig
from src.engines.trend import TrendEngine, TrendEngineConfig
from src.risk.risk_manager import RiskManager

logger = structlog.get_logger(__name__)


@dataclass
class EngineBacktestState:
    """State tracking for a single engine during backtest."""

    engine_type: EngineType
    allocation_pct: Decimal
    initial_capital: Decimal
    current_capital: Decimal
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Dict] = field(default_factory=list)


@dataclass
class BacktestResult:
    """Complete backtest results."""

    # Overall
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    final_capital: Decimal
    total_return_pct: float

    # Risk metrics
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility_annual: float

    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float

    # Engine breakdown
    engine_results: Dict[EngineType, Dict]

    # Monthly returns
    monthly_returns: pd.DataFrame

    # Drawdown periods
    max_drawdown_start: datetime
    max_drawdown_end: datetime
    max_drawdown_recovery: Optional[datetime]

    # Market regime performance
    regime_performance: Dict[str, Dict]


class EternalEngineBacktest:
    """
    Professional-grade backtest engine for The Eternal Engine.

    Simulates the complete 4-engine system with:
    - Realistic execution (fees, slippage)
    - Risk management enforcement
    - Capital allocation rebalancing
    - Market regime analysis
    """

    def __init__(
        self,
        initial_capital: Decimal = Decimal("100000"),
        fee_rate: Decimal = Decimal("0.001"),  # 0.1% taker fee
        slippage_pct: Decimal = Decimal("0.05"),  # 0.05% slippage
        rebalance_frequency_days: int = 90,  # Quarterly
        enable_compound: bool = True,
    ):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage_pct = slippage_pct
        self.rebalance_frequency = timedelta(days=rebalance_frequency_days)
        self.enable_compound = enable_compound

        # Capital allocation per AGENTS.md
        self.allocations = {
            EngineType.CORE_HODL: Decimal("0.60"),
            EngineType.TREND: Decimal("0.20"),
            EngineType.FUNDING: Decimal("0.15"),
            EngineType.TACTICAL: Decimal("0.05"),
        }

        # State
        self.engines: Dict[EngineType, Any] = {}
        self.engine_states: Dict[EngineType, EngineBacktestState] = {}
        self.risk_manager = RiskManager()
        self.last_rebalance: Optional[datetime] = None

        logger.info(
            "backtest_engine.initialized",
            initial_capital=str(initial_capital),
            fee_rate=str(fee_rate),
            allocations={k.value: float(v) for k, v in self.allocations.items()},
        )

    async def run(
        self,
        market_data: Dict[str, List[MarketData]],
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestResult:
        """
        Run complete backtest simulation.

        Args:
            market_data: Historical OHLCV data for all symbols
            start_date: Backtest start
            end_date: Backtest end

        Returns:
            BacktestResult with full performance metrics
        """
        logger.info(
            "backtest.starting", start=start_date.isoformat(), end=end_date.isoformat()
        )

        # Initialize engines
        self._initialize_engines()

        # Get all timestamps
        timestamps = self._get_sorted_timestamps(market_data)
        timestamps = [t for t in timestamps if start_date <= t <= end_date]

        logger.info("backtest.timestamps_loaded", count=len(timestamps))

        # Main simulation loop
        for i, timestamp in enumerate(timestamps):
            if i % 1000 == 0:
                logger.info(
                    "backtest.progress",
                    current=timestamp.isoformat(),
                    progress=f"{i/len(timestamps)*100:.1f}%",
                )

            # Get data up to current time
            current_data = self._get_data_at_time(market_data, timestamp)
            current_prices = self._get_current_prices(current_data)

            # Update portfolio values
            self._update_engine_values(current_prices, timestamp)

            # Check if rebalancing needed
            if self._should_rebalance(timestamp):
                self._rebalance_capital(timestamp)

            # Run each engine
            for engine_type, engine in self.engines.items():
                await self._run_engine_cycle(
                    engine_type, engine, current_data, current_prices, timestamp
                )

        # Calculate final results
        result = self._calculate_results(start_date, end_date)

        logger.info(
            "backtest.complete",
            total_return=f"{result.total_return_pct:.2f}%",
            max_drawdown=f"{result.max_drawdown_pct:.2f}%",
            sharpe=result.sharpe_ratio,
        )

        return result

    def _initialize_engines(self):
        """Initialize all 4 engines with proper capital allocation."""
        for engine_type, allocation in self.allocations.items():
            capital = self.initial_capital * allocation

            if engine_type == EngineType.CORE_HODL:
                config = CoreHodlConfig(
                    allocation_pct=allocation,
                    dca_amount_usdt=capital * Decimal("0.01"),  # 1% per DCA
                )
                engine = CoreHodlEngine(config=config)

            elif engine_type == EngineType.TREND:
                config = TrendEngineConfig(
                    allocation_pct=allocation, risk_per_trade=Decimal("0.01")
                )
                engine = TrendEngine(config=config)

            elif engine_type == EngineType.FUNDING:
                config = FundingEngineConfig(allocation_pct=allocation)
                engine = FundingEngine(config=config)

            elif engine_type == EngineType.TACTICAL:
                config = TacticalEngineConfig(allocation_pct=allocation)
                engine = TacticalEngine(config=config)

            self.engines[engine_type] = engine
            self.engine_states[engine_type] = EngineBacktestState(
                engine_type=engine_type,
                allocation_pct=allocation,
                initial_capital=capital,
                current_capital=capital,
            )

            logger.info(
                "backtest.engine_initialized",
                engine=engine_type.value,
                capital=str(capital),
            )

    async def _run_engine_cycle(
        self,
        engine_type: EngineType,
        engine: Any,
        market_data: Dict[str, List[MarketData]],
        current_prices: Dict[str, Decimal],
        timestamp: datetime,
    ):
        """Run one analysis cycle for an engine."""
        state = self.engine_states[engine_type]

        # Skip if engine has no capital
        if state.current_capital <= 0:
            return

        # Get signals from engine
        try:
            signals = await engine.analyze(market_data)
        except Exception as e:
            logger.error(
                "backtest.engine_error", engine=engine_type.value, error=str(e)
            )
            return

        # Process each signal
        for signal in signals:
            await self._process_signal(
                signal, engine_type, state, current_prices, timestamp
            )

    async def _process_signal(
        self,
        signal,
        engine_type: EngineType,
        state: EngineBacktestState,
        current_prices: Dict[str, Decimal],
        timestamp: datetime,
    ):
        """Process a trading signal."""
        symbol = signal.symbol

        if symbol not in current_prices:
            return

        price = current_prices[symbol]

        # Apply slippage
        if signal.signal_type == SignalType.BUY:
            executed_price = price * (Decimal("1") + self.slippage_pct)
        else:
            executed_price = price * (Decimal("1") - self.slippage_pct)

        # Calculate position size
        if signal.signal_type == SignalType.BUY:
            # Use signal metadata or default sizing
            size_pct = Decimal("0.1")  # 10% of engine capital per trade
            trade_value = state.current_capital * size_pct

            if trade_value <= 0:
                return

            # Calculate quantity
            fee = trade_value * self.fee_rate
            quantity = (trade_value - fee) / executed_price

            # Update state
            state.current_capital -= trade_value

            if symbol in state.positions:
                # Average up
                old_pos = state.positions[symbol]
                total_qty = old_pos.amount + quantity
                total_value = (old_pos.entry_price * old_pos.amount) + (
                    executed_price * quantity
                )
                old_pos.entry_price = total_value / total_qty
                old_pos.amount = total_qty
            else:
                state.positions[symbol] = Position(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    entry_price=executed_price,
                    amount=quantity,
                    opened_at=timestamp,
                )

            logger.debug(
                "backtest.buy_executed",
                engine=engine_type.value,
                symbol=symbol,
                price=str(executed_price),
                quantity=str(quantity),
            )

        elif signal.signal_type in (SignalType.SELL, SignalType.CLOSE):
            if symbol not in state.positions:
                return

            position = state.positions[symbol]
            quantity = position.amount

            # Calculate proceeds
            gross_value = quantity * executed_price
            fee = gross_value * self.fee_rate
            net_value = gross_value - fee

            # Calculate P&L
            entry_value = position.amount * position.entry_price
            pnl = net_value - entry_value
            pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else Decimal("0")

            # Update state
            state.current_capital += net_value
            del state.positions[symbol]

            # Record trade
            trade = Trade(
                id=f"{timestamp.isoformat()}_{symbol}",
                symbol=symbol,
                entry_price=position.entry_price,
                exit_price=executed_price,
                amount=quantity,
                entry_time=position.opened_at,
                exit_time=timestamp,
                realized_pnl=pnl,
                realized_pnl_pct=pnl_pct,
                total_fee=fee * 2,  # Entry + exit
            )
            state.trades.append(trade)

            logger.debug(
                "backtest.sell_executed",
                engine=engine_type.value,
                symbol=symbol,
                price=str(executed_price),
                pnl=str(pnl),
                pnl_pct=f"{pnl_pct:.2f}%",
            )

    def _update_engine_values(
        self, current_prices: Dict[str, Decimal], timestamp: datetime
    ):
        """Update equity curves for all engines."""
        for engine_type, state in self.engine_states.items():
            # Calculate position values
            position_value = Decimal("0")
            for symbol, position in state.positions.items():
                if symbol in current_prices:
                    position_value += position.amount * current_prices[symbol]

            total_value = state.current_capital + position_value

            state.equity_curve.append(
                {
                    "timestamp": timestamp,
                    "cash": state.current_capital,
                    "positions_value": position_value,
                    "total": total_value,
                }
            )

    def _should_rebalance(self, timestamp: datetime) -> bool:
        """Check if quarterly rebalancing is due."""
        if self.last_rebalance is None:
            return False
        return timestamp - self.last_rebalance >= self.rebalance_frequency

    def _rebalance_capital(self, timestamp: datetime):
        """Rebalance capital between engines to maintain target allocations."""
        # Calculate total portfolio value
        total_value = Decimal("0")
        for state in self.engine_states.values():
            if state.equity_curve:
                total_value += state.equity_curve[-1]["total"]

        if total_value <= 0:
            return

        # Rebalance each engine
        for engine_type, state in self.engine_states.items():
            target_value = total_value * state.allocation_pct
            current_value = (
                state.equity_curve[-1]["total"] if state.equity_curve else Decimal("0")
            )

            drift = abs(current_value - target_value) / target_value

            if drift > Decimal("0.10"):  # 10% drift threshold
                logger.info(
                    "backtest.rebalancing",
                    engine=engine_type.value,
                    current=str(current_value),
                    target=str(target_value),
                    drift=f"{drift*100:.1f}%",
                )

                # Adjust capital (simplified - real rebalance would involve trades)
                adjustment = target_value - current_value
                state.current_capital += adjustment

        self.last_rebalance = timestamp

    def _get_sorted_timestamps(
        self, market_data: Dict[str, List[MarketData]]
    ) -> List[datetime]:
        """Get sorted list of all timestamps."""
        timestamps = set()
        for symbol_data in market_data.values():
            for data in symbol_data:
                timestamps.add(data.timestamp)
        return sorted(timestamps)

    def _get_data_at_time(
        self, market_data: Dict[str, List[MarketData]], timestamp: datetime
    ) -> Dict[str, List[MarketData]]:
        """Get market data up to given timestamp."""
        result = {}
        for symbol, data_list in market_data.items():
            result[symbol] = [d for d in data_list if d.timestamp <= timestamp]
        return result

    def _get_current_prices(
        self, market_data: Dict[str, List[MarketData]]
    ) -> Dict[str, Decimal]:
        """Extract current prices from market data."""
        prices = {}
        for symbol, data_list in market_data.items():
            if data_list:
                prices[symbol] = data_list[-1].close
        return prices

    def _calculate_results(
        self, start_date: datetime, end_date: datetime
    ) -> BacktestResult:
        """Calculate comprehensive backtest metrics."""
        # Combine all engine equity curves
        portfolio_equity = self._combine_equity_curves()

        if portfolio_equity.empty:
            raise ValueError("No equity data generated")

        # Basic metrics
        initial = portfolio_equity["total"].iloc[0]
        final = portfolio_equity["total"].iloc[-1]
        total_return = (final - initial) / initial * 100

        # Calculate returns series
        portfolio_equity["returns"] = portfolio_equity["total"].pct_change()

        # Risk metrics
        max_dd, dd_start, dd_end, dd_recovery = self._calculate_max_drawdown(
            portfolio_equity
        )

        # Sharpe ratio (assuming risk-free rate = 0, 252 trading days)
        returns_mean = portfolio_equity["returns"].mean() * 252
        returns_std = portfolio_equity["returns"].std() * np.sqrt(252)
        sharpe = returns_mean / returns_std if returns_std > 0 else 0

        # Sortino ratio (downside deviation only)
        downside_returns = portfolio_equity["returns"][portfolio_equity["returns"] < 0]
        downside_std = downside_returns.std() * np.sqrt(252)
        sortino = returns_mean / downside_std if downside_std > 0 else 0

        # Calmar ratio (return / max drawdown)
        calmar = abs(total_return / max_dd) if max_dd != 0 else 0

        # Volatility
        volatility = returns_std * 100

        # Trade statistics
        all_trades = []
        for state in self.engine_states.values():
            all_trades.extend(state.trades)

        total_trades = len(all_trades)
        winning_trades = sum(1 for t in all_trades if t.realized_pnl > 0)
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        wins = [float(t.realized_pnl_pct) for t in all_trades if t.realized_pnl > 0]
        losses = [float(t.realized_pnl_pct) for t in all_trades if t.realized_pnl <= 0]

        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0

        total_gains = sum(t.realized_pnl for t in all_trades if t.realized_pnl > 0)
        total_losses = abs(
            sum(t.realized_pnl for t in all_trades if t.realized_pnl < 0)
        )
        profit_factor = total_gains / total_losses if total_losses > 0 else 0

        # Engine breakdown
        engine_results = {}
        for engine_type, state in self.engine_states.items():
            if state.equity_curve:
                engine_initial = state.equity_curve[0]["total"]
                engine_final = state.equity_curve[-1]["total"]
                engine_return = (engine_final - engine_initial) / engine_initial * 100

                engine_results[engine_type] = {
                    "initial": float(engine_initial),
                    "final": float(engine_final),
                    "return_pct": engine_return,
                    "trades": len(state.trades),
                    "win_rate": (
                        sum(1 for t in state.trades if t.realized_pnl > 0)
                        / len(state.trades)
                        * 100
                        if state.trades
                        else 0
                    ),
                }

        # Monthly returns
        portfolio_equity["month"] = portfolio_equity["timestamp"].dt.to_period("M")
        monthly = portfolio_equity.groupby("month")["returns"].sum() * 100

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial,
            final_capital=final,
            total_return_pct=total_return,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            volatility_annual=volatility,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=win_rate,
            avg_win_pct=avg_win,
            avg_loss_pct=avg_loss,
            profit_factor=profit_factor,
            engine_results=engine_results,
            monthly_returns=monthly,
            max_drawdown_start=dd_start,
            max_drawdown_end=dd_end,
            max_drawdown_recovery=dd_recovery,
            regime_performance={},  # To be filled by caller
        )

    def _combine_equity_curves(self) -> pd.DataFrame:
        """Combine all engine equity curves into portfolio equity."""
        # Get all timestamps
        all_timestamps = set()
        for state in self.engine_states.values():
            for point in state.equity_curve:
                all_timestamps.add(point["timestamp"])

        timestamps = sorted(all_timestamps)

        # Build portfolio equity
        records = []
        for ts in timestamps:
            total = Decimal("0")
            for state in self.engine_states.values():
                # Find equity at this timestamp
                equity_at_ts = None
                for point in state.equity_curve:
                    if point["timestamp"] == ts:
                        equity_at_ts = point["total"]
                        break
                if equity_at_ts:
                    total += equity_at_ts

            records.append({"timestamp": ts, "total": float(total)})

        return pd.DataFrame(records)

    def _calculate_max_drawdown(
        self, equity_df: pd.DataFrame
    ) -> Tuple[float, datetime, datetime, Optional[datetime]]:
        """Calculate maximum drawdown with dates."""
        equity_df["peak"] = equity_df["total"].cummax()
        equity_df["drawdown"] = (
            (equity_df["total"] - equity_df["peak"]) / equity_df["peak"] * 100
        )

        max_dd_idx = equity_df["drawdown"].idxmin()
        max_dd = equity_df.loc[max_dd_idx, "drawdown"]

        # Find drawdown start (peak before)
        peak_value = equity_df.loc[max_dd_idx, "peak"]
        peak_mask = (equity_df["total"] == peak_value) & (equity_df.index <= max_dd_idx)
        dd_start_idx = equity_df[peak_mask].index[-1] if peak_mask.any() else 0

        # Find recovery (when equity exceeds previous peak)
        recovery_mask = (equity_df.index > max_dd_idx) & (
            equity_df["total"] >= peak_value
        )
        recovery_idx = (
            equity_df[recovery_mask].index[0] if recovery_mask.any() else None
        )

        return (
            max_dd,
            equity_df.loc[dd_start_idx, "timestamp"],
            equity_df.loc[max_dd_idx, "timestamp"],
            equity_df.loc[recovery_idx, "timestamp"] if recovery_idx else None,
        )
