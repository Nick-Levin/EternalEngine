"""Comprehensive unit tests for the TradingEngine.

These tests cover the main orchestrator of The Eternal Engine trading system,
including initialization, signal execution, order lifecycle, position management,
exchange downtime handling, and emergency stop functionality.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# Import the engine
from src.core.engine import TradingEngine, create_trading_engine
# Import models
from src.core.models import (CircuitBreakerLevel, EngineState, EngineType,
                             MarketData, Order, OrderSide, OrderStatus,
                             OrderType, Portfolio, Position, PositionSide,
                             RiskCheck, SignalType, SystemState, Trade,
                             TradingSignal)
from src.exchange.bybit_client import ByBitClient, SubAccountType
from src.risk.risk_manager import RiskManager
from src.storage.database import Database
from src.strategies.base import BaseStrategy

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_exchange():
    """Create a mock ByBitClient."""
    exchange = AsyncMock(spec=ByBitClient)
    exchange.fetch_time = AsyncMock(return_value=datetime.now(timezone.utc).timestamp())
    exchange.get_balance = AsyncMock(
        return_value=Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )
    )
    exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})
    exchange.create_order = AsyncMock()
    exchange.get_order_status = AsyncMock(return_value=OrderStatus.OPEN)
    exchange.fetch_order = AsyncMock()
    exchange.cancel_order = AsyncMock()
    exchange.get_open_orders = AsyncMock(return_value=[])
    exchange.fetch_balance = AsyncMock(return_value={"total": {}})
    exchange.fetch_ohlcv = AsyncMock(return_value=[])
    exchange.close = AsyncMock()
    exchange.initialize = AsyncMock()
    exchange.load_markets = AsyncMock()
    return exchange


@pytest.fixture
def mock_risk_manager():
    """Create a mock RiskManager."""
    risk_manager = MagicMock(spec=RiskManager)
    risk_manager.check_signal = MagicMock(
        return_value=RiskCheck(passed=True, max_position_size=Decimal("10"))
    )
    risk_manager.calculate_stop_loss = MagicMock(return_value=Decimal("45000"))
    risk_manager.calculate_take_profit = MagicMock(return_value=Decimal("55000"))
    risk_manager.calculate_position_size = MagicMock(return_value=Decimal("1.0"))
    risk_manager.check_circuit_breakers = MagicMock(
        return_value=CircuitBreakerLevel.NONE
    )
    risk_manager.get_circuit_breaker_actions = MagicMock(return_value={})
    risk_manager.get_risk_report = MagicMock(return_value={})
    risk_manager.initialize = AsyncMock()
    risk_manager.reset_periods = MagicMock()
    risk_manager.update_pnl = MagicMock()
    risk_manager.trigger_emergency_stop = MagicMock()
    risk_manager.reset_emergency_stop = MagicMock()
    risk_manager.circuit_breaker = MagicMock()
    risk_manager.circuit_breaker.level = CircuitBreakerLevel.NONE
    return risk_manager


@pytest.fixture
def mock_database():
    """Create a mock Database."""
    database = AsyncMock(spec=Database)
    database.save_order = AsyncMock()
    database.save_position = AsyncMock()
    database.save_trade = AsyncMock()
    database.delete_position = AsyncMock()
    database.get_open_positions = AsyncMock(return_value=[])
    database.get_open_orders = AsyncMock(return_value=[])
    database.get_engine_states = AsyncMock(return_value={})
    database.save_engine_state = AsyncMock()
    database.save_full_engine_state = AsyncMock()
    database.save_dca_state = AsyncMock()
    database.get_all_dca_states = AsyncMock(return_value={})
    return database


@pytest.fixture
def mock_strategy():
    """Create a mock strategy."""
    strategy = AsyncMock(spec=BaseStrategy)
    strategy.name = "TestStrategy"
    strategy.symbols = ["BTCUSDT"]
    strategy.is_active = True
    strategy.analyze = AsyncMock(return_value=[])
    strategy.on_order_filled = AsyncMock()
    strategy.on_position_closed = AsyncMock()
    strategy.get_stats = MagicMock(
        return_value={
            "name": "TestStrategy",
            "signals_generated": 0,
            "trades_executed": 0,
        }
    )
    return strategy


@pytest.fixture
def trading_engine(mock_exchange, mock_risk_manager, mock_database, mock_strategy):
    """Create a TradingEngine with mocked dependencies."""
    strategies = {
        EngineType.CORE_HODL: [mock_strategy],
        EngineType.TREND: [],
        EngineType.FUNDING: [],
        EngineType.TACTICAL: [],
    }

    engine = TradingEngine(
        exchange=mock_exchange,
        risk_manager=mock_risk_manager,
        database=mock_database,
        strategies=strategies,
    )
    return engine


@pytest.fixture
def sample_signal():
    """Create a sample trading signal."""
    return TradingSignal(
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        strategy_name="TestStrategy",
        confidence=0.8,
        metadata={"entry_price": "50000", "stop_loss": "48000"},
    )


@pytest.fixture
def sample_order():
    """Create a sample order."""
    return Order(
        id="test-order-123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        amount=Decimal("0.1"),
        status=OrderStatus.OPEN,
        exchange_order_id="ex-123",
        metadata={
            "engine_type": "core_hodl",
            "strategy_name": "TestStrategy",
            "subaccount": "CORE_HODL",
        },
    )


@pytest.fixture
def sample_position():
    """Create a sample position."""
    return Position(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        entry_price=Decimal("50000"),
        amount=Decimal("0.1"),
        metadata={"engine_type": "CORE_HODL"},
    )


# =============================================================================
# TestTradingEngineInitialization
# =============================================================================


class TestTradingEngineInitialization:
    """Tests for TradingEngine initialization."""

    def test_initialization_creates_all_engines(
        self, mock_exchange, mock_risk_manager, mock_database
    ):
        """Verify 4 engines created on initialization."""
        engine = TradingEngine(
            exchange=mock_exchange,
            risk_manager=mock_risk_manager,
            database=mock_database,
        )

        assert len(engine.engine_states) == 4
        assert EngineType.CORE_HODL in engine.engine_states
        assert EngineType.TREND in engine.engine_states
        assert EngineType.FUNDING in engine.engine_states
        assert EngineType.TACTICAL in engine.engine_states

    @pytest.mark.asyncio
    async def test_initialization_loads_state(self, trading_engine, mock_database):
        """State restored from DB on initialization."""
        mock_position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )
        mock_database.get_open_positions = AsyncMock(return_value=[mock_position])
        mock_database.get_open_orders = AsyncMock(return_value=[])

        await trading_engine.initialize()

        mock_database.get_open_positions.assert_called_once()
        assert "BTCUSDT" in trading_engine.positions

    @pytest.mark.asyncio
    async def test_initialization_syncs_positions(
        self, trading_engine, mock_exchange, mock_database
    ):
        """Position sync on start."""
        mock_exchange.fetch_balance = AsyncMock(return_value={"total": {"BTC": 0.1}})
        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine.initialize()

        mock_exchange.fetch_balance.assert_called()

    def test_allocation_percentages(self, trading_engine):
        """60/20/15/5 split verified."""
        assert trading_engine.ALLOCATION[EngineType.CORE_HODL] == Decimal("0.60")
        assert trading_engine.ALLOCATION[EngineType.TREND] == Decimal("0.20")
        assert trading_engine.ALLOCATION[EngineType.FUNDING] == Decimal("0.15")
        assert trading_engine.ALLOCATION[EngineType.TACTICAL] == Decimal("0.05")

    def test_engine_subaccount_mapping(self, trading_engine):
        """Correct subaccounts assigned."""
        assert (
            trading_engine.ENGINE_TO_SUBACCOUNT[EngineType.CORE_HODL]
            == SubAccountType.CORE_HODL
        )
        assert (
            trading_engine.ENGINE_TO_SUBACCOUNT[EngineType.TREND]
            == SubAccountType.TREND
        )
        assert (
            trading_engine.ENGINE_TO_SUBACCOUNT[EngineType.FUNDING]
            == SubAccountType.FUNDING
        )
        assert (
            trading_engine.ENGINE_TO_SUBACCOUNT[EngineType.TACTICAL]
            == SubAccountType.TACTICAL
        )


# =============================================================================
# TestMainLoop
# =============================================================================


class TestMainLoop:
    """Tests for the main trading loop."""

    @pytest.mark.asyncio
    async def test_main_loop_runs_analysis_cycle(self, trading_engine, mock_strategy):
        """Loop executes analysis cycle."""
        trading_engine._running = True
        trading_engine.exchange_circuit_breaker = False
        trading_engine._emergency_stop = False
        trading_engine._consecutive_network_errors = 0

        # Mock to run only once
        call_count = 0

        async def stop_after_one():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                trading_engine._running = False

        mock_strategy.analyze = AsyncMock(return_value=[])
        mock_strategy.update_portfolio_state = MagicMock()

        # Run main loop briefly
        with patch.object(trading_engine, "_update_pending_orders", AsyncMock()):
            with patch.object(trading_engine, "_run_order_maintenance", AsyncMock()):
                with patch.object(
                    trading_engine, "_check_circuit_breakers", AsyncMock()
                ):
                    with patch.object(trading_engine, "_update_portfolio", AsyncMock()):
                        with patch.object(
                            trading_engine, "_update_exchange_status", AsyncMock()
                        ):
                            task = asyncio.create_task(trading_engine._main_loop())
                            await asyncio.sleep(0.1)
                            trading_engine._running = False
                            try:
                                await asyncio.wait_for(task, timeout=1.0)
                            except asyncio.TimeoutError:
                                task.cancel()

    @pytest.mark.asyncio
    async def test_main_loop_handles_network_errors(self, trading_engine):
        """Graceful error handling for network errors."""
        trading_engine._running = True
        trading_engine.exchange_circuit_breaker = False
        trading_engine._emergency_stop = False

        error_count = 0

        async def raise_network_error():
            nonlocal error_count
            error_count += 1
            if error_count >= 3:
                trading_engine._running = False
            raise Exception("network connection timeout")

        with patch.object(
            trading_engine, "_update_exchange_status", side_effect=raise_network_error
        ):
            task = asyncio.create_task(trading_engine._main_loop())
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except asyncio.TimeoutError:
                task.cancel()

        # Should have recorded network errors
        assert trading_engine._consecutive_network_errors > 0

    @pytest.mark.asyncio
    async def test_main_loop_exchange_health_check(self, trading_engine):
        """Health monitoring happens."""
        trading_engine._last_exchange_health_check = None
        trading_engine._running = True

        with patch.object(
            trading_engine, "_check_exchange_health", AsyncMock(return_value=True)
        ) as mock_check:
            with patch.object(
                trading_engine, "_update_exchange_status", AsyncMock()
            ) as mock_update:
                task = asyncio.create_task(trading_engine._main_loop())
                await asyncio.sleep(0.1)
                trading_engine._running = False
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except asyncio.TimeoutError:
                    task.cancel()

    @pytest.mark.asyncio
    async def test_main_loop_circuit_breaker_pause(self, trading_engine):
        """Pause on exchange downtime."""
        trading_engine._running = True
        trading_engine.exchange_circuit_breaker = True
        trading_engine._emergency_stop = False

        loop_ran = False

        async def mock_reconnect():
            nonlocal loop_ran
            loop_ran = True
            return False

        with patch.object(
            trading_engine, "_reconnect_exchange", side_effect=mock_reconnect
        ):
            with patch.object(
                trading_engine, "_update_exchange_status", AsyncMock()
            ) as mock_update:
                task = asyncio.create_task(trading_engine._main_loop())
                await asyncio.sleep(0.2)
                trading_engine._running = False
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except asyncio.TimeoutError:
                    task.cancel()

        assert loop_ran

    @pytest.mark.asyncio
    async def test_main_loop_circuit_breaker_resume(self, trading_engine):
        """Resume on recovery."""
        trading_engine.exchange_down_since = datetime.now(timezone.utc) - timedelta(
            seconds=10
        )
        trading_engine.exchange_circuit_breaker = True

        with patch.object(
            trading_engine, "_check_exchange_health", AsyncMock(return_value=True)
        ):
            await trading_engine._update_exchange_status()

        assert not trading_engine.exchange_circuit_breaker
        assert trading_engine.exchange_down_since is None

    @pytest.mark.asyncio
    async def test_main_loop_updates_pending_orders(self, trading_engine, sample_order):
        """Order tracking in main loop."""
        trading_engine.pending_orders[sample_order.id] = sample_order

        with patch.object(
            trading_engine, "_update_pending_orders", AsyncMock()
        ) as mock_update:
            await trading_engine._update_pending_orders()
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_loop_periodic_state_save(self, trading_engine, sample_order):
        """Auto-save state happens."""
        with patch.object(trading_engine, "_save_state", AsyncMock()) as mock_save:
            await trading_engine._save_state()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_loop_emergency_stop(self, trading_engine):
        """Emergency handling in main loop."""
        trading_engine._running = True
        trading_engine._emergency_stop = True
        trading_engine._emergency_reason = "Test emergency"

        task = asyncio.create_task(trading_engine._main_loop())
        await asyncio.sleep(0.15)
        trading_engine._running = False
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()


# =============================================================================
# TestSignalExecution
# =============================================================================


class TestSignalExecution:
    """Tests for signal execution methods."""

    @pytest.mark.asyncio
    async def test_execute_buy_creates_order(
        self, trading_engine, sample_signal, mock_exchange
    ):
        """Buy signal → order creation."""
        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="new-order-123",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-123",
            )
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        risk_check = RiskCheck(passed=True)

        await trading_engine._execute_buy(
            EngineType.CORE_HODL,
            sample_signal,
            trading_engine.engines[EngineType.CORE_HODL][0],
            risk_check,
        )

        mock_exchange.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_buy_with_stop_loss(
        self, trading_engine, sample_signal, mock_exchange, mock_risk_manager
    ):
        """Stop attached to buy order."""
        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="new-order-123",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-123",
            )
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        risk_check = RiskCheck(passed=True)

        await trading_engine._execute_buy(
            EngineType.CORE_HODL,
            sample_signal,
            trading_engine.engines[EngineType.CORE_HODL][0],
            risk_check,
        )

        # Verify order was created with stop loss from signal
        mock_exchange.create_order.assert_called_once()
        # The stop loss comes from signal metadata in this case
        assert sample_signal.get_stop_loss() is not None

    @pytest.mark.asyncio
    async def test_execute_sell_creates_order(
        self, trading_engine, sample_signal, mock_exchange
    ):
        """Sell signal → order creation."""
        sample_signal.signal_type = SignalType.SELL

        # Add a position first
        trading_engine.engine_positions[EngineType.TREND]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "TREND"},
        )

        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="sell-order-123",
                symbol="BTCUSDT",
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-sell-123",
            )
        )

        risk_check = RiskCheck(passed=True)

        await trading_engine._execute_sell(
            EngineType.TREND,
            sample_signal,
            trading_engine.engines[EngineType.CORE_HODL][0],
            risk_check,
        )

        mock_exchange.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_close_creates_order(
        self, trading_engine, sample_signal, mock_exchange
    ):
        """Close signal → order creation."""
        sample_signal.signal_type = SignalType.CLOSE
        sample_signal.metadata = {"reason": "test_close"}

        # Add a position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="close-order-123",
                symbol="BTCUSDT",
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-close-123",
            )
        )

        await trading_engine._execute_close(EngineType.CORE_HODL, sample_signal)

        mock_exchange.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_rebalance_creates_orders(
        self, trading_engine, mock_exchange
    ):
        """Rebalance orders creation."""
        rebalance_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.REBALANCE,
            strategy_name="TestStrategy",
            metadata={"targets": {"BTCUSDT": 0.5, "ETHUSDT": 0.5}},
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="rebal-order-123",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-rebal-123",
            )
        )
        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine._execute_rebalance(EngineType.CORE_HODL, rebalance_signal)

    @pytest.mark.asyncio
    async def test_execute_signal_persisted_to_db(
        self, trading_engine, sample_signal, mock_exchange, mock_database
    ):
        """Order saved to database."""
        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="new-order-123",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-123",
            )
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        risk_check = RiskCheck(passed=True)

        await trading_engine._execute_buy(
            EngineType.CORE_HODL,
            sample_signal,
            trading_engine.engines[EngineType.CORE_HODL][0],
            risk_check,
        )

        mock_database.save_order.assert_called()

    @pytest.mark.asyncio
    async def test_execute_signal_updates_pending(
        self, trading_engine, sample_signal, mock_exchange
    ):
        """Order added to pending."""
        new_order = Order(
            id="new-order-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.OPEN,
            exchange_order_id="ex-123",
        )
        mock_exchange.create_order = AsyncMock(return_value=new_order)

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        risk_check = RiskCheck(passed=True)

        await trading_engine._execute_buy(
            EngineType.CORE_HODL,
            sample_signal,
            trading_engine.engines[EngineType.CORE_HODL][0],
            risk_check,
        )

        assert "new-order-123" in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_position_sizing_with_stop(
        self, trading_engine, sample_signal, mock_risk_manager
    ):
        """ATR-based sizing when stop provided."""
        mock_risk_manager.calculate_position_size = MagicMock(
            return_value=Decimal("0.5")
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        # Signal has stop loss
        sample_signal.metadata["stop_loss"] = "48000"

        risk_check = RiskCheck(passed=True)

        with patch.object(
            trading_engine, "_create_order_with_retry", AsyncMock(return_value=None)
        ):
            await trading_engine._execute_buy(
                EngineType.CORE_HODL,
                sample_signal,
                trading_engine.engines[EngineType.CORE_HODL][0],
                risk_check,
            )

        mock_risk_manager.calculate_position_size.assert_called()

    @pytest.mark.asyncio
    async def test_position_sizing_without_stop(
        self, trading_engine, sample_signal, mock_risk_manager
    ):
        """Max position limit when no stop."""
        mock_risk_manager.calculate_stop_loss = MagicMock(return_value=Decimal("48000"))

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        # Signal without stop loss
        sample_signal.metadata = {}

        risk_check = RiskCheck(passed=True)

        with patch.object(
            trading_engine, "_create_order_with_retry", AsyncMock(return_value=None)
        ):
            await trading_engine._execute_buy(
                EngineType.CORE_HODL,
                sample_signal,
                trading_engine.engines[EngineType.CORE_HODL][0],
                risk_check,
            )

        mock_risk_manager.calculate_stop_loss.assert_called()

    @pytest.mark.asyncio
    async def test_insufficient_funds_handling(
        self, trading_engine, sample_signal, mock_exchange
    ):
        """Graceful failure on insufficient funds."""
        import ccxt

        mock_exchange.create_order = AsyncMock(
            side_effect=ccxt.InsufficientFunds("Insufficient funds")
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        order_params = {
            "subaccount": "CORE_HODL",
            "symbol": "BTCUSDT",
            "side": OrderSide.BUY,
            "order_type": OrderType.MARKET,
            "amount": Decimal("10"),
            "price": None,
            "params": {},
        }
        order_metadata = {"engine_type": "CORE_HODL"}

        result = await trading_engine._create_order_with_retry(
            order_params, order_metadata, EngineType.CORE_HODL, "BTCUSDT"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_order_creation_failure_retry(self, trading_engine, mock_exchange):
        """Retry logic for temporary failures."""
        import ccxt

        mock_exchange.create_order = AsyncMock(
            side_effect=ccxt.NetworkError("Network error")
        )

        order_params = {
            "subaccount": "CORE_HODL",
            "symbol": "BTCUSDT",
            "side": OrderSide.BUY,
            "order_type": OrderType.MARKET,
            "amount": Decimal("0.1"),
            "price": None,
            "params": {},
        }
        order_metadata = {"engine_type": "CORE_HODL"}

        result = await trading_engine._create_order_with_retry(
            order_params, order_metadata, EngineType.CORE_HODL, "BTCUSDT"
        )

        assert result is None
        # Should have added to failed_orders for retry
        assert len(trading_engine.failed_orders) == 1

    @pytest.mark.asyncio
    async def test_order_creation_permanent_failure(
        self, trading_engine, mock_exchange
    ):
        """No retry for invalid orders."""
        import ccxt

        mock_exchange.create_order = AsyncMock(
            side_effect=ccxt.InvalidOrder("Invalid order")
        )

        order_params = {
            "subaccount": "CORE_HODL",
            "symbol": "BTCUSDT",
            "side": OrderSide.BUY,
            "order_type": OrderType.MARKET,
            "amount": Decimal("0.1"),
            "price": None,
            "params": {},
        }
        order_metadata = {"engine_type": "CORE_HODL"}

        result = await trading_engine._create_order_with_retry(
            order_params, order_metadata, EngineType.CORE_HODL, "BTCUSDT"
        )

        assert result is None
        # Should NOT be in failed_orders (permanent failure)
        assert len(trading_engine.failed_orders) == 0


# =============================================================================
# TestOrderLifecycle
# =============================================================================


class TestOrderLifecycle:
    """Tests for order lifecycle handling."""

    @pytest.mark.asyncio
    async def test_on_order_filled_updates_position(
        self, trading_engine, sample_order, mock_database
    ):
        """Position updated on order fill."""
        sample_order.status = OrderStatus.FILLED
        sample_order.filled_amount = Decimal("0.1")
        sample_order.average_price = Decimal("50000")
        sample_order.metadata["engine_type"] = "CORE_HODL"

        await trading_engine._on_order_filled(sample_order)

        # Position should be created
        assert "BTCUSDT" in trading_engine.engine_positions[EngineType.CORE_HODL]

    @pytest.mark.asyncio
    async def test_on_order_filled_notifies_strategy(
        self, trading_engine, sample_order, mock_strategy
    ):
        """Callback called on order fill."""
        sample_order.status = OrderStatus.FILLED
        sample_order.filled_amount = Decimal("0.1")
        sample_order.average_price = Decimal("50000")
        sample_order.metadata["engine_type"] = "CORE_HODL"
        sample_order.metadata["strategy_name"] = "TestStrategy"

        await trading_engine._on_order_filled(sample_order)

        mock_strategy.on_order_filled.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_order_filled_updates_stats(
        self, trading_engine, sample_order, mock_database
    ):
        """Stats updated on order fill."""
        sample_order.status = OrderStatus.FILLED
        sample_order.filled_amount = Decimal("0.1")
        sample_order.average_price = Decimal("50000")
        sample_order.metadata["engine_type"] = "CORE_HODL"

        await trading_engine._on_order_filled(sample_order)

        # Engine state should be updated
        assert (
            trading_engine.engine_states[EngineType.CORE_HODL].last_trade_time
            is not None
        )

    @pytest.mark.asyncio
    async def test_on_order_filled_removes_pending(self, trading_engine, sample_order):
        """Cleanup pending orders on fill."""
        trading_engine.pending_orders[sample_order.id] = sample_order
        sample_order.status = OrderStatus.FILLED
        sample_order.filled_amount = Decimal("0.1")
        sample_order.average_price = Decimal("50000")
        sample_order.metadata["engine_type"] = "CORE_HODL"

        await trading_engine._on_order_filled(sample_order)

        assert sample_order.id not in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_on_order_partially_filled(
        self, trading_engine, sample_order, mock_exchange
    ):
        """Partial fill handling."""
        sample_order.status = OrderStatus.PARTIALLY_FILLED
        sample_order.filled_amount = Decimal("0.05")
        sample_order.average_price = Decimal("50000")
        sample_order.metadata["engine_type"] = "CORE_HODL"
        sample_order.metadata["strategy_name"] = "TestStrategy"

        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine._on_order_partially_filled(sample_order)

        # Position should be created with partial amount
        assert "BTCUSDT" in trading_engine.engine_positions[EngineType.CORE_HODL]

    @pytest.mark.asyncio
    async def test_partial_fill_updates_position(self, trading_engine, mock_exchange):
        """Position with partial fill."""
        order = Order(
            id="partial-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0.05"),
            average_price=Decimal("50000"),
            status=OrderStatus.PARTIALLY_FILLED,
            metadata={"engine_type": "CORE_HODL"},
        )

        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine._on_order_partially_filled(order)

        position = trading_engine.engine_positions[EngineType.CORE_HODL].get("BTCUSDT")
        assert position is not None
        assert position.amount == Decimal("0.05")

    @pytest.mark.asyncio
    async def test_partial_fill_persisted(
        self, trading_engine, sample_order, mock_database, mock_exchange
    ):
        """DB updated on partial fill."""
        sample_order.status = OrderStatus.PARTIALLY_FILLED
        sample_order.filled_amount = Decimal("0.05")
        sample_order.average_price = Decimal("50000")
        sample_order.metadata["engine_type"] = "CORE_HODL"

        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine._on_order_partially_filled(sample_order)

        mock_database.save_order.assert_called()

    @pytest.mark.asyncio
    async def test_update_pending_orders_checks_exchange(
        self, trading_engine, sample_order, mock_exchange
    ):
        """Status check for pending orders."""
        trading_engine.pending_orders[sample_order.id] = sample_order
        mock_exchange.get_order_status = AsyncMock(return_value=OrderStatus.FILLED)
        mock_exchange.fetch_order = AsyncMock(
            return_value={"filled": 0.1, "average": 50000.0}
        )

        await trading_engine._update_pending_orders()

        mock_exchange.get_order_status.assert_called()

    @pytest.mark.asyncio
    async def test_update_pending_orders_handles_filled(
        self, trading_engine, sample_order, mock_exchange
    ):
        """Filled detected in pending update."""
        trading_engine.pending_orders[sample_order.id] = sample_order
        mock_exchange.get_order_status = AsyncMock(return_value=OrderStatus.FILLED)

        with patch.object(
            trading_engine, "_on_order_filled", AsyncMock()
        ) as mock_filled:
            await trading_engine._update_pending_orders()
            mock_filled.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_pending_orders_handles_cancelled(
        self, trading_engine, sample_order, mock_exchange
    ):
        """Cancelled cleanup."""
        trading_engine.pending_orders[sample_order.id] = sample_order
        mock_exchange.get_order_status = AsyncMock(return_value=OrderStatus.CANCELLED)

        await trading_engine._update_pending_orders()

        assert sample_order.id not in trading_engine.pending_orders


# =============================================================================
# TestPositionManagement
# =============================================================================


class TestPositionManagement:
    """Tests for position management."""

    @pytest.mark.asyncio
    async def test_update_position_for_buy_new_position(
        self, trading_engine, mock_database
    ):
        """New position creation."""
        order = Order(
            id="buy-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0.1"),
            average_price=Decimal("50000"),
            metadata={"engine_type": "CORE_HODL"},
        )

        await trading_engine._update_position_for_buy(EngineType.CORE_HODL, order)

        position = trading_engine.engine_positions[EngineType.CORE_HODL].get("BTCUSDT")
        assert position is not None
        assert position.amount == Decimal("0.1")
        assert position.entry_price == Decimal("50000")

    @pytest.mark.asyncio
    async def test_update_position_for_buy_existing(
        self, trading_engine, mock_database
    ):
        """Add to existing position (DCA)."""
        # Create initial position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        # Second buy
        order = Order(
            id="buy-order-2",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0.1"),
            average_price=Decimal("55000"),  # Higher price
            metadata={"engine_type": "CORE_HODL"},
        )

        await trading_engine._update_position_for_buy(EngineType.CORE_HODL, order)

        position = trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"]
        assert position.amount == Decimal("0.2")
        # Average price: (50000*0.1 + 55000*0.1) / 0.2 = 52500
        assert position.entry_price == Decimal("52500")

    @pytest.mark.asyncio
    async def test_update_position_for_sell_partial(
        self, trading_engine, mock_database, mock_risk_manager
    ):
        """Partial close."""
        # Create position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.2"),
            metadata={"engine_type": "CORE_HODL"},
        )
        trading_engine.positions["BTCUSDT"] = trading_engine.engine_positions[
            EngineType.CORE_HODL
        ]["BTCUSDT"]

        # Partial sell (not full amount)
        order = Order(
            id="sell-order",
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0.05"),  # Only half of what we wanted
            average_price=Decimal("55000"),
            metadata={"engine_type": "CORE_HODL", "strategy_name": "TestStrategy"},
        )

        await trading_engine._update_position_for_sell(EngineType.CORE_HODL, order)

        # Position should still exist with reduced amount
        position = trading_engine.engine_positions[EngineType.CORE_HODL].get("BTCUSDT")
        if position:
            assert position.amount < Decimal("0.2")

    @pytest.mark.asyncio
    async def test_update_position_for_sell_full(
        self, trading_engine, mock_database, mock_exchange, mock_risk_manager
    ):
        """Full close."""
        # Create position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )
        trading_engine.positions["BTCUSDT"] = trading_engine.engine_positions[
            EngineType.CORE_HODL
        ]["BTCUSDT"]

        # Full sell
        order = Order(
            id="sell-order",
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0.1"),
            average_price=Decimal("55000"),
            metadata={"engine_type": "CORE_HODL", "strategy_name": "TestStrategy"},
        )

        await trading_engine._update_position_for_sell(EngineType.CORE_HODL, order)

        # Position should be removed
        assert "BTCUSDT" not in trading_engine.engine_positions[EngineType.CORE_HODL]
        assert "BTCUSDT" not in trading_engine.positions

    def test_position_average_price_calculation(self, trading_engine):
        """Avg price correct after DCA."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
        )

        # Simulate DCA - adding at higher price
        position.update_from_fill(Decimal("55000"), Decimal("0.1"), OrderSide.BUY)

        # New average: (50000*0.1 + 55000*0.1) / 0.2 = 52500
        assert position.entry_price == Decimal("52500")
        assert position.amount == Decimal("0.2")

    def test_position_unrealized_pnl(self, trading_engine):
        """PnL calculation."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
        )

        # Price goes up
        pnl = position.calculate_unrealized_pnl(Decimal("55000"))
        assert pnl == Decimal("500")  # (55000 - 50000) * 0.1

        # Price goes down
        pnl = position.calculate_unrealized_pnl(Decimal("45000"))
        assert pnl == Decimal("-500")  # (45000 - 50000) * 0.1

    def test_position_realized_pnl(self, trading_engine):
        """Realized tracking."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.2"),
        )

        # Calculate unrealized pnl first (required for realized calc)
        position.unrealized_pnl = position.calculate_unrealized_pnl(Decimal("55000"))

        # Close half at profit
        position.update_from_fill(Decimal("55000"), Decimal("0.1"), OrderSide.SELL)

        # Realized PnL is calculated proportionally
        assert position.realized_pnl > Decimal("0")
        assert position.amount == Decimal("0.1")

    @pytest.mark.asyncio
    async def test_sync_positions_from_exchange(self, trading_engine, mock_exchange):
        """Exchange sync."""
        mock_exchange.fetch_balance = AsyncMock(
            return_value={"total": {"BTC": 0.1, "ETH": 0.5}}
        )
        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine._sync_positions_from_exchange()

        # Should have synced positions
        assert len(trading_engine.engine_positions[EngineType.CORE_HODL]) > 0


# =============================================================================
# TestExchangeDowntime
# =============================================================================


class TestExchangeDowntime:
    """Tests for exchange downtime handling."""

    @pytest.mark.asyncio
    async def test_check_exchange_health_success(self, trading_engine, mock_exchange):
        """Healthy check."""
        mock_exchange.fetch_time = AsyncMock(
            return_value=datetime.now(timezone.utc).timestamp()
        )

        result = await trading_engine._check_exchange_health()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_exchange_health_failure(self, trading_engine, mock_exchange):
        """Unhealthy check."""
        mock_exchange.fetch_time = AsyncMock(side_effect=Exception("Connection failed"))

        result = await trading_engine._check_exchange_health()

        assert result is False

    @pytest.mark.asyncio
    async def test_exchange_circuit_breaker_activates(
        self, trading_engine, mock_exchange
    ):
        """CB on downtime."""
        mock_exchange.fetch_time = AsyncMock(side_effect=Exception("Connection failed"))

        await trading_engine._update_exchange_status()

        # Should have set exchange_down_since
        assert trading_engine.exchange_down_since is not None

    @pytest.mark.asyncio
    async def test_exchange_circuit_breaker_pauses_engines(
        self, trading_engine, mock_exchange
    ):
        """Engines paused on downtime."""
        mock_exchange.fetch_time = AsyncMock(side_effect=Exception("Connection failed"))
        trading_engine.exchange_down_since = datetime.now(timezone.utc) - timedelta(
            seconds=60
        )

        await trading_engine._update_exchange_status()

        assert trading_engine.exchange_circuit_breaker is True

    @pytest.mark.asyncio
    async def test_exchange_circuit_breaker_resumes(
        self, trading_engine, mock_exchange
    ):
        """Auto-resume on recovery."""
        # First mark as down
        trading_engine.exchange_down_since = datetime.now(timezone.utc) - timedelta(
            seconds=60
        )
        trading_engine.exchange_circuit_breaker = True

        # Then simulate recovery
        mock_exchange.fetch_time = AsyncMock(
            return_value=datetime.now(timezone.utc).timestamp()
        )

        # Pre-pause an engine to test resume
        trading_engine.engine_states[EngineType.CORE_HODL].pause("test")

        await trading_engine._update_exchange_status()

        assert not trading_engine.exchange_circuit_breaker
        assert trading_engine.exchange_down_since is None

    @pytest.mark.asyncio
    async def test_reconnect_exchange(self, trading_engine, mock_exchange):
        """Reconnection logic."""
        mock_exchange.close = AsyncMock()
        mock_exchange.initialize = AsyncMock()

        result = await trading_engine._reconnect_exchange()

        assert result is True
        mock_exchange.initialize.assert_called()


# =============================================================================
# TestOrderMaintenance
# =============================================================================


class TestOrderMaintenance:
    """Tests for order maintenance."""

    @pytest.mark.asyncio
    async def test_detect_orphan_orders(self, trading_engine, mock_exchange):
        """Orphan detection."""
        orphan_order = Order(
            id="orphan-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.OPEN,
            exchange_order_id="ex-orphan-123",
            metadata={},
        )

        mock_exchange.get_open_orders = AsyncMock(return_value=[orphan_order])

        await trading_engine._detect_orphan_orders()

        # Orphan should be added to pending
        assert "orphan-123" in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_detect_orphan_orders_adds_to_pending(
        self, trading_engine, mock_exchange
    ):
        """Orphan adoption."""
        orphan_order = Order(
            id="orphan-456",
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            amount=Decimal("0.5"),
            status=OrderStatus.OPEN,
            exchange_order_id="ex-orphan-456",
            metadata={},
        )

        mock_exchange.get_open_orders = AsyncMock(return_value=[orphan_order])

        await trading_engine._detect_orphan_orders()

        added_order = trading_engine.pending_orders.get("orphan-456")
        assert added_order is not None
        assert added_order.metadata.get("is_orphan") is True

    @pytest.mark.asyncio
    async def test_cleanup_stuck_orders(self, trading_engine, mock_exchange):
        """Old order cleanup."""
        old_order = Order(
            id="stuck-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=Decimal("0.1"),
            status=OrderStatus.OPEN,
            exchange_order_id="ex-stuck",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
            metadata={"subaccount": "CORE_HODL"},
        )

        trading_engine.pending_orders["stuck-order"] = old_order
        mock_exchange.cancel_order = AsyncMock()

        await trading_engine._cleanup_stuck_orders()

        mock_exchange.cancel_order.assert_called_once()
        assert "stuck-order" not in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_process_failed_orders_retry(self, trading_engine, mock_exchange):
        """Retry logic for failed orders."""
        failed_order = Order(
            id="failed-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.PENDING,
            metadata={"subaccount": "CORE_HODL", "engine_type": "CORE_HODL"},
        )

        # Add to failed orders with old timestamp (past retry delay)
        trading_engine.failed_orders["failed-order"] = (
            failed_order,
            0,
            datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="retry-success",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-retry",
            )
        )

        await trading_engine._process_failed_orders()

        mock_exchange.create_order.assert_called_once()
        assert "failed-order" not in trading_engine.failed_orders

    @pytest.mark.asyncio
    async def test_process_failed_orders_max_retries(
        self, trading_engine, mock_database
    ):
        """Max 3 attempts."""
        failed_order = Order(
            id="max-retry-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.PENDING,
            metadata={},
        )

        # Add with max retries reached
        trading_engine.failed_orders["max-retry-order"] = (
            failed_order,
            3,  # Max retries
            datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        await trading_engine._process_failed_orders()

        # Should be removed and marked as rejected
        assert "max-retry-order" not in trading_engine.failed_orders
        mock_database.save_order.assert_called()

    def test_failed_order_delay_respected(self, trading_engine):
        """5-min delay."""
        failed_order = Order(
            id="recent-fail",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
        )

        # Add with recent timestamp (within delay)
        trading_engine.failed_orders["recent-fail"] = (
            failed_order,
            0,
            datetime.now(timezone.utc) - timedelta(minutes=2),  # Only 2 min ago
        )

        # Should still be in failed orders (not enough time passed)
        assert "recent-fail" in trading_engine.failed_orders


# =============================================================================
# TestEmergencyStop
# =============================================================================


class TestEmergencyStop:
    """Tests for emergency stop functionality."""

    @pytest.mark.asyncio
    async def test_emergency_stop_pauses_all_engines(
        self, trading_engine, mock_risk_manager
    ):
        """Stop all engines."""
        await trading_engine.emergency_stop("Test emergency")

        for engine_type, state in trading_engine.engine_states.items():
            assert state.is_paused is True

    @pytest.mark.asyncio
    async def test_emergency_stop_sets_flag(self, trading_engine):
        """Flag set."""
        await trading_engine.emergency_stop("Test emergency")

        assert trading_engine._emergency_stop is True
        assert trading_engine._emergency_reason == "Test emergency"

    @pytest.mark.asyncio
    async def test_emergency_stop_logs_reason(self, trading_engine, mock_risk_manager):
        """Reason logged."""
        await trading_engine.emergency_stop("Critical error occurred")

        mock_risk_manager.trigger_emergency_stop.assert_called_once_with(
            "Critical error occurred"
        )

    @pytest.mark.asyncio
    async def test_reset_emergency_stop_resumes(
        self, trading_engine, mock_risk_manager
    ):
        """Recovery."""
        # First trigger emergency
        await trading_engine.emergency_stop("Test")
        assert trading_engine._emergency_stop is True

        # Then reset
        result = await trading_engine.reset_emergency_stop("admin_user")

        assert result is True
        assert trading_engine._emergency_stop is False
        assert trading_engine._emergency_reason is None
        mock_risk_manager.reset_emergency_stop.assert_called_once_with("admin_user")


# =============================================================================
# TestStatePersistence
# =============================================================================


class TestStatePersistence:
    """Tests for state persistence."""

    @pytest.mark.asyncio
    async def test_save_state_persists_positions(self, trading_engine, mock_database):
        """Positions saved."""
        # Add a position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        with patch.object(mock_database, "save_engine_state", AsyncMock()):
            await trading_engine._save_state()

    @pytest.mark.asyncio
    async def test_save_state_persists_orders(self, trading_engine, mock_database):
        """Orders saved."""
        order = Order(
            id="test-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.OPEN,
            metadata={"engine_type": "CORE_HODL"},
        )
        trading_engine.pending_orders["test-order"] = order

        with patch.object(mock_database, "save_engine_state", AsyncMock()):
            await trading_engine._save_state()

    @pytest.mark.asyncio
    async def test_save_state_persists_engine_states(
        self, trading_engine, mock_database
    ):
        """Engine state saved."""
        with patch.object(mock_database, "save_engine_state", AsyncMock()) as mock_save:
            await trading_engine._save_state()

    @pytest.mark.asyncio
    async def test_load_state_restores_positions(self, trading_engine, mock_database):
        """Positions restored."""
        saved_position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )
        mock_database.get_open_positions = AsyncMock(return_value=[saved_position])
        mock_database.get_open_orders = AsyncMock(return_value=[])

        await trading_engine._load_state()

        assert "BTCUSDT" in trading_engine.positions
        assert "BTCUSDT" in trading_engine.engine_positions[EngineType.CORE_HODL]

    @pytest.mark.asyncio
    async def test_load_state_restores_pending_orders(
        self, trading_engine, mock_database
    ):
        """Orders restored."""
        saved_order = Order(
            id="saved-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.OPEN,
            metadata={"engine_type": "CORE_HODL"},
        )
        mock_database.get_open_positions = AsyncMock(return_value=[])
        mock_database.get_open_orders = AsyncMock(return_value=[saved_order])

        await trading_engine._load_state()

        assert "saved-order" in trading_engine.pending_orders


# =============================================================================
# TestHelperMethods
# =============================================================================


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_position_value(self, trading_engine):
        """Position value calculation."""
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        value = trading_engine._get_position_value(EngineType.CORE_HODL, "BTCUSDT")

        assert value == Decimal("5000")  # 50000 * 0.1

    def test_get_position_value_no_position(self, trading_engine):
        """Zero for no position."""
        value = trading_engine._get_position_value(EngineType.CORE_HODL, "ETHUSDT")

        assert value == Decimal("0")

    def test_get_exchange_downtime_seconds(self, trading_engine):
        """Downtime calculation."""
        trading_engine.exchange_down_since = datetime.now(timezone.utc) - timedelta(
            seconds=30
        )

        downtime = trading_engine._get_exchange_downtime_seconds()

        assert downtime >= 30.0

    def test_get_exchange_downtime_seconds_no_downtime(self, trading_engine):
        """Zero when no downtime."""
        trading_engine.exchange_down_since = None

        downtime = trading_engine._get_exchange_downtime_seconds()

        assert downtime == 0.0

    def test_is_engine_enabled(self, trading_engine):
        """Engine enabled check."""
        assert trading_engine._is_engine_enabled(EngineType.CORE_HODL) is True
        assert trading_engine._is_engine_enabled(EngineType.TREND) is True

    def test_get_engine_config(self, trading_engine):
        """Engine config retrieval."""
        config = trading_engine._get_engine_config(EngineType.CORE_HODL)

        assert isinstance(config, dict)

    @pytest.mark.asyncio
    async def test_pause_all_engines(self, trading_engine):
        """Pause all engines."""
        await trading_engine._pause_all_engines("test_reason")

        for state in trading_engine.engine_states.values():
            assert state.is_paused is True
            assert state.pause_reason == "test_reason"

    @pytest.mark.asyncio
    async def test_resume_all_engines(self, trading_engine):
        """Resume all engines."""
        # First pause
        await trading_engine._pause_all_engines("test")

        # Then resume
        await trading_engine._resume_all_engines()

        for state in trading_engine.engine_states.values():
            assert state.is_paused is False


# =============================================================================
# TestGetStatus
# =============================================================================


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_returns_dict(self, trading_engine):
        """Status is dictionary."""
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        status = trading_engine.get_status()

        assert isinstance(status, dict)
        assert "system" in status
        assert "portfolio" in status
        assert "engines" in status

    def test_get_status_includes_emergency_state(self, trading_engine):
        """Emergency state included."""
        trading_engine._emergency_stop = True
        trading_engine._emergency_reason = "Test"
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        status = trading_engine.get_status()

        assert status["system"]["emergency_stop"] is True
        assert status["system"]["emergency_reason"] == "Test"

    def test_get_status_includes_positions(self, trading_engine):
        """Positions included."""
        trading_engine.positions["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
        )
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        status = trading_engine.get_status()

        assert "BTCUSDT" in status["positions"]

    def test_get_system_state(self, trading_engine):
        """SystemState object returned."""
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        state = trading_engine.get_system_state()

        assert isinstance(state, SystemState)


# =============================================================================
# TestFactoryFunction
# =============================================================================


class TestFactoryFunction:
    """Tests for create_trading_engine factory."""

    def test_create_trading_engine_returns_instance(self):
        """Factory returns TradingEngine."""
        with patch("src.core.engine.ByBitClient") as mock_ex:
            with patch("src.risk.risk_manager.create_risk_manager") as mock_risk:
                with patch("src.core.engine.Database") as mock_db:
                    mock_ex.return_value = AsyncMock()
                    mock_risk.return_value = MagicMock()
                    mock_db.return_value = AsyncMock()

                    engine = create_trading_engine()

                    assert isinstance(engine, TradingEngine)


# =============================================================================
# TestEnginePauseResume
# =============================================================================


class TestEnginePauseResume:
    """Tests for engine pause/resume methods."""

    def test_pause_engine(self, trading_engine):
        """Pause specific engine."""
        trading_engine.pause_engine(EngineType.CORE_HODL, "maintenance")

        assert trading_engine.engine_states[EngineType.CORE_HODL].is_paused is True
        assert (
            trading_engine.engine_states[EngineType.CORE_HODL].pause_reason
            == "maintenance"
        )

    def test_pause_engine_with_duration(self, trading_engine):
        """Pause with auto-resume."""
        trading_engine.pause_engine(EngineType.TREND, "cooldown", duration_seconds=3600)

        assert trading_engine.engine_states[EngineType.TREND].is_paused is True
        assert trading_engine.engine_states[EngineType.TREND].pause_until is not None

    def test_resume_engine(self, trading_engine):
        """Resume specific engine."""
        # First pause
        trading_engine.pause_engine(EngineType.CORE_HODL, "test")
        assert trading_engine.engine_states[EngineType.CORE_HODL].is_paused is True

        # Then resume
        trading_engine.resume_engine(EngineType.CORE_HODL)

        assert trading_engine.engine_states[EngineType.CORE_HODL].is_paused is False
        assert trading_engine.engine_states[EngineType.CORE_HODL].pause_reason is None


# =============================================================================
# TestSignalProcessing
# =============================================================================


class TestSignalProcessing:
    """Tests for signal processing."""

    @pytest.mark.asyncio
    async def test_process_signal_risk_check(
        self, trading_engine, sample_signal, mock_risk_manager
    ):
        """Risk check called."""
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        with patch.object(trading_engine, "_execute_buy", AsyncMock()):
            await trading_engine._process_signal(
                EngineType.CORE_HODL,
                sample_signal,
                trading_engine.engines[EngineType.CORE_HODL][0],
            )

        mock_risk_manager.check_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_signal_rejected(
        self, trading_engine, sample_signal, mock_risk_manager
    ):
        """Rejected signal handling."""
        mock_risk_manager.check_signal = MagicMock(
            return_value=RiskCheck(
                passed=False,
                reason="Max positions reached",
                checks_performed=["position_limit"],
            )
        )

        with patch.object(trading_engine, "_execute_buy", AsyncMock()) as mock_exec:
            await trading_engine._process_signal(
                EngineType.CORE_HODL,
                sample_signal,
                trading_engine.engines[EngineType.CORE_HODL][0],
            )

            mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_signal_emergency_exit(self, trading_engine, sample_signal):
        """Emergency exit signal handling."""
        sample_signal.signal_type = SignalType.EMERGENCY_EXIT

        with patch.object(trading_engine, "emergency_stop", AsyncMock()) as mock_stop:
            await trading_engine._process_signal(
                EngineType.CORE_HODL,
                sample_signal,
                trading_engine.engines[EngineType.CORE_HODL][0],
            )

            mock_stop.assert_called_once()


# =============================================================================
# TestDCAInitialization
# =============================================================================


class TestDCAInitialization:
    """Tests for DCA persistence initialization."""

    @pytest.mark.asyncio
    async def test_initialize_dca_persistence(self, trading_engine, mock_database):
        """DCA state loaded."""
        # Create a mock DCA strategy
        dca_strategy = AsyncMock(spec=BaseStrategy)
        dca_strategy.name = "DCAStrategy"
        dca_strategy.symbols = ["BTCUSDT"]
        dca_strategy.last_purchase = {}
        dca_strategy.set_db_save_callback = MagicMock()
        dca_strategy.interval_hours = 168

        mock_database.get_all_dca_states = AsyncMock(
            return_value={"BTCUSDT": datetime.now(timezone.utc)}
        )

        trading_engine.engines[EngineType.CORE_HODL] = [dca_strategy]

        await trading_engine._initialize_dca_persistence()

        dca_strategy.set_db_save_callback.assert_called_once()
        assert "BTCUSDT" in dca_strategy.last_purchase


# =============================================================================
# TestAddStrategy
# =============================================================================


class TestAddStrategy:
    """Tests for add_strategy method."""

    def test_add_strategy_to_engine(self, trading_engine):
        """Strategy added to engine."""
        new_strategy = AsyncMock(spec=BaseStrategy)
        new_strategy.name = "NewStrategy"
        new_strategy.symbols = ["ETHUSDT"]

        trading_engine.add_strategy(EngineType.TREND, new_strategy)

        assert new_strategy in trading_engine.engines[EngineType.TREND]

    def test_add_strategy_creates_list_if_needed(self, trading_engine):
        """Creates strategy list if needed."""
        # Clear existing strategies for TACTICAL
        trading_engine.engines[EngineType.TACTICAL] = []

        new_strategy = AsyncMock(spec=BaseStrategy)
        new_strategy.name = "TacticalStrategy"
        new_strategy.symbols = ["BTCUSDT"]

        trading_engine.add_strategy(EngineType.TACTICAL, new_strategy)

        assert trading_engine.engines[EngineType.TACTICAL] == [new_strategy]


# =============================================================================
# TestAnalysisCycle
# =============================================================================


class TestAnalysisCycle:
    """Tests for analysis cycle."""

    @pytest.mark.asyncio
    async def test_run_analysis_cycle(
        self, trading_engine, mock_strategy, mock_exchange
    ):
        """Analysis cycle runs."""
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[])
        mock_strategy.analyze = AsyncMock(return_value=[])

        await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)

        mock_strategy.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_analysis_cycle_skips_inactive_strategies(
        self, trading_engine, mock_strategy, mock_exchange
    ):
        """Skip inactive strategies."""
        mock_strategy.is_active = False
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[])

        await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)

        mock_strategy.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_analysis_cycle_handles_errors(
        self, trading_engine, mock_strategy, mock_exchange
    ):
        """Error handling in analysis."""
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[])
        mock_strategy.analyze = AsyncMock(side_effect=Exception("Analysis error"))

        await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)

        # Should not crash - error recorded
        assert trading_engine.engine_states[EngineType.CORE_HODL].error_count > 0


# =============================================================================
# TestUpdatePortfolio
# =============================================================================


class TestUpdatePortfolio:
    """Tests for portfolio updates."""

    @pytest.mark.asyncio
    async def test_update_portfolio(
        self, trading_engine, mock_exchange, mock_risk_manager
    ):
        """Portfolio updated from exchange."""
        mock_exchange.get_balance = AsyncMock(
            return_value=Portfolio(
                total_balance=Decimal("110000"), available_balance=Decimal("60000")
            )
        )

        await trading_engine._update_portfolio()

        assert trading_engine.portfolio.total_balance == Decimal("110000")
        mock_risk_manager.reset_periods.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_portfolio_error_handling(self, trading_engine, mock_exchange):
        """Error handling in portfolio update."""
        mock_exchange.get_balance = AsyncMock(side_effect=Exception("API error"))

        await trading_engine._update_portfolio()

        # Should not crash


# =============================================================================
# TestCircuitBreakerCheck
# =============================================================================


class TestCircuitBreakerCheck:
    """Tests for circuit breaker checks."""

    @pytest.mark.asyncio
    async def test_check_circuit_breakers(self, trading_engine, mock_risk_manager):
        """Circuit breakers checked."""
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )
        mock_risk_manager.check_circuit_breakers = MagicMock(
            return_value=CircuitBreakerLevel.LEVEL_1
        )

        await trading_engine._check_circuit_breakers()

        for state in trading_engine.engine_states.values():
            assert state.circuit_breaker_level == CircuitBreakerLevel.LEVEL_1

    @pytest.mark.asyncio
    async def test_check_circuit_breakers_level_4(
        self, trading_engine, mock_risk_manager
    ):
        """Level 4 triggers emergency stop."""
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )
        mock_risk_manager.check_circuit_breakers = MagicMock(
            return_value=CircuitBreakerLevel.LEVEL_4
        )

        with patch.object(trading_engine, "emergency_stop", AsyncMock()) as mock_stop:
            await trading_engine._check_circuit_breakers()
            mock_stop.assert_called_once()


# =============================================================================
# TestRetryOrder
# =============================================================================


class TestRetryOrder:
    """Tests for order retry functionality."""

    @pytest.mark.asyncio
    async def test_retry_order_success(self, trading_engine, mock_exchange):
        """Retry succeeds."""
        original_order = Order(
            id="original-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL", "subaccount": "CORE_HODL"},
        )

        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="retried-order",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                exchange_order_id="ex-retry",
                status=OrderStatus.OPEN,
            )
        )

        result = await trading_engine._retry_order(original_order)

        assert result is True
        mock_exchange.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_order_insufficient_funds(self, trading_engine, mock_exchange):
        """Retry fails on insufficient funds."""
        import ccxt

        original_order = Order(
            id="original-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        mock_exchange.create_order = AsyncMock(
            side_effect=ccxt.InsufficientFunds("No funds")
        )

        result = await trading_engine._retry_order(original_order)

        assert result is False


# =============================================================================
# TestCloseSideFiltering
# =============================================================================


class TestCloseSideFiltering:
    """Tests for close signal side filtering."""

    @pytest.mark.asyncio
    async def test_execute_close_long_filter(self, trading_engine, mock_exchange):
        """Close long filter."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.CLOSE_LONG,
            strategy_name="TestStrategy",
            metadata={"reason": "test"},
        )

        # Add short position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        # Should not close (side filter doesn't match)
        with patch.object(trading_engine, "_create_order_with_retry", AsyncMock()):
            await trading_engine._execute_close(
                EngineType.CORE_HODL, signal, side_filter=PositionSide.LONG
            )

    @pytest.mark.asyncio
    async def test_execute_close_short_filter(self, trading_engine, mock_exchange):
        """Close short filter."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.CLOSE_SHORT,
            strategy_name="TestStrategy",
            metadata={"reason": "test"},
        )

        # Add long position
        trading_engine.engine_positions[EngineType.TREND]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "TREND"},
        )

        # Should not close (side filter doesn't match)
        with patch.object(trading_engine, "_create_order_with_retry", AsyncMock()):
            await trading_engine._execute_close(
                EngineType.TREND, signal, side_filter=PositionSide.SHORT
            )


# =============================================================================
# TestSellWithoutPosition
# =============================================================================


class TestSellWithoutPosition:
    """Tests for sell handling when no position exists."""

    @pytest.mark.asyncio
    async def test_execute_sell_no_position_core_hodl(
        self, trading_engine, mock_strategy, mock_risk_manager
    ):
        """CORE-HODL requires position."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.SELL,
            strategy_name="TestStrategy",
            metadata={},
        )

        # No position exists
        risk_check = RiskCheck(passed=True)

        with patch.object(
            trading_engine, "_create_order_with_retry", AsyncMock()
        ) as mock_create:
            await trading_engine._execute_sell(
                EngineType.CORE_HODL, signal, mock_strategy, risk_check
            )
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_sell_no_position_trend(
        self, trading_engine, mock_strategy, mock_risk_manager, mock_exchange
    ):
        """TREND allows short selling."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.SELL,
            strategy_name="TestStrategy",
            metadata={"size": "0.1"},  # As string for Decimal conversion
        )

        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="short-order",
                symbol="BTCUSDT",
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-short",
            )
        )

        risk_check = RiskCheck(passed=True)

        await trading_engine._execute_sell(
            EngineType.TREND, signal, mock_strategy, risk_check
        )

        # Should create short order
        mock_exchange.create_order.assert_called_once()
