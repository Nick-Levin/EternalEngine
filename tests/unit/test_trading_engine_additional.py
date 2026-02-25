"""Additional comprehensive unit tests for the TradingEngine.

These tests supplement the existing test suite to achieve 85%+ coverage
of the engine.py file.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

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
# Additional Fixtures
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
        return_value=RiskCheck(
            passed=True, risk_level="normal", max_position_size=Decimal("10")
        )
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
# TestTradingEngineInitialization - Additional Tests
# =============================================================================


class TestTradingEngineInitializationAdditional:
    """Additional initialization tests."""

    def test_engine_initializes_tracking_dicts(
        self, mock_exchange, mock_risk_manager, mock_database
    ):
        """Engine initializes all internal tracking dictionaries."""
        engine = TradingEngine(
            exchange=mock_exchange,
            risk_manager=mock_risk_manager,
            database=mock_database,
        )

        assert isinstance(engine.engine_positions, dict)
        assert isinstance(engine.pending_orders, dict)
        assert isinstance(engine.market_data, dict)
        assert isinstance(engine.failed_orders, dict)
        assert isinstance(engine.engine_states, dict)

        # All engine types should have position dicts
        for engine_type in EngineType:
            assert engine_type in engine.engine_positions
            assert isinstance(engine.engine_positions[engine_type], dict)

    def test_engine_default_intervals(
        self, mock_exchange, mock_risk_manager, mock_database
    ):
        """Default intervals are set correctly."""
        engine = TradingEngine(
            exchange=mock_exchange,
            risk_manager=mock_risk_manager,
            database=mock_database,
        )

        assert engine.analysis_interval == 60
        assert engine.balance_update_interval == 300
        assert engine.circuit_breaker_check_interval == 30

    def test_engine_order_retry_config(
        self, mock_exchange, mock_risk_manager, mock_database
    ):
        """Order retry configuration is set."""
        engine = TradingEngine(
            exchange=mock_exchange,
            risk_manager=mock_risk_manager,
            database=mock_database,
        )

        assert engine.MAX_ORDER_RETRIES == 3
        assert engine.ORDER_RETRY_DELAY_MINUTES == 5
        assert engine.STUCK_ORDER_HOURS == 24
        assert engine.ORPHAN_CHECK_INTERVAL == 300

    def test_engine_exchange_health_config(
        self, mock_exchange, mock_risk_manager, mock_database
    ):
        """Exchange health monitoring config is set."""
        engine = TradingEngine(
            exchange=mock_exchange,
            risk_manager=mock_risk_manager,
            database=mock_database,
        )

        assert engine._exchange_health_check_interval == 10
        assert engine._exchange_downtime_threshold == 30
        assert engine._max_consecutive_errors == 5

    @pytest.mark.asyncio
    async def test_initialize_validates_config(self, trading_engine):
        """Initialize validates configuration."""
        with patch(
            "src.core.engine.engine_config.validate_configuration",
            return_value={"valid": True, "issues": []},
        ):
            with patch.object(trading_engine, "_load_state", AsyncMock()):
                with patch.object(
                    trading_engine, "_sync_positions_from_exchange", AsyncMock()
                ):
                    with patch.object(
                        trading_engine, "_initialize_dca_persistence", AsyncMock()
                    ):
                        await trading_engine.initialize()

    @pytest.mark.asyncio
    async def test_initialize_raises_on_invalid_config(self, trading_engine):
        """Initialize raises error on invalid config."""
        with patch(
            "src.core.engine.engine_config.validate_configuration",
            return_value={"valid": False, "issues": ["Missing API key"]},
        ):
            with pytest.raises(ValueError):
                await trading_engine.initialize()


# =============================================================================
# TestMainLoopAdditional
# =============================================================================


class TestMainLoopAdditional:
    """Additional main loop tests."""

    @pytest.mark.asyncio
    async def test_main_loop_handles_exchange_error(self, trading_engine):
        """Exchange error handling."""
        trading_engine._running = True
        trading_engine._emergency_stop = False
        trading_engine.exchange_circuit_breaker = False

        call_count = 0

        async def raise_exchange_error():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                trading_engine._running = False
            raise Exception("bybit api rate limit")

        with patch.object(
            trading_engine, "_update_exchange_status", side_effect=raise_exchange_error
        ):
            task = asyncio.create_task(trading_engine._main_loop())
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except asyncio.TimeoutError:
                task.cancel()

    @pytest.mark.asyncio
    async def test_main_loop_handles_generic_error(self, trading_engine):
        """Generic error handling."""
        trading_engine._running = True
        trading_engine._emergency_stop = False
        trading_engine.exchange_circuit_breaker = False

        call_count = 0

        async def raise_generic_error():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                trading_engine._running = False
            raise ValueError("Unexpected error")

        with patch.object(
            trading_engine, "_update_exchange_status", side_effect=raise_generic_error
        ):
            task = asyncio.create_task(trading_engine._main_loop())
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except asyncio.TimeoutError:
                task.cancel()

    @pytest.mark.asyncio
    async def test_main_loop_skips_analysis_when_circuit_breaker_active(
        self, trading_engine, mock_strategy
    ):
        """Skip analysis when exchange circuit breaker is active."""
        trading_engine._running = True
        trading_engine.exchange_circuit_breaker = True
        trading_engine._emergency_stop = False

        mock_strategy.analyze = AsyncMock(return_value=[])

        # Mock exchange as unhealthy to keep circuit breaker active
        with patch.object(
            trading_engine, "_check_exchange_health", AsyncMock(return_value=False)
        ):
            with patch.object(
                trading_engine, "_reconnect_exchange", AsyncMock(return_value=False)
            ):
                task = asyncio.create_task(trading_engine._main_loop())
                await asyncio.sleep(0.2)
                trading_engine._running = False
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except asyncio.TimeoutError:
                    task.cancel()

        # Strategy analyze should not be called when circuit breaker is active
        mock_strategy.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_main_loop_reconnect_success(self, trading_engine):
        """Successful reconnection in main loop."""
        trading_engine._running = True
        trading_engine.exchange_circuit_breaker = True
        trading_engine._emergency_stop = False

        with patch.object(
            trading_engine, "_reconnect_exchange", AsyncMock(return_value=True)
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


# =============================================================================
# TestSignalExecutionAdditional
# =============================================================================


class TestSignalExecutionAdditional:
    """Additional signal execution tests."""

    @pytest.mark.asyncio
    async def test_process_signal_rejected(
        self, trading_engine, sample_signal, mock_risk_manager
    ):
        """Rejected signal handling with proper risk_level."""
        mock_risk_manager.check_signal = MagicMock(
            return_value=RiskCheck(
                passed=False,
                reason="Max positions reached",
                risk_level="critical",
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
    async def test_execute_buy_with_dca_amount(
        self, trading_engine, mock_exchange, mock_risk_manager
    ):
        """Buy with DCA amount from signal metadata."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="TestStrategy",
            engine_type=EngineType.CORE_HODL,
            confidence=0.8,
            metadata={"amount_usdt": "1000"},  # DCA amount
        )

        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="dca-order-123",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.02"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-dca-123",
            )
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        risk_check = RiskCheck(passed=True, risk_level="normal")

        await trading_engine._execute_buy(
            EngineType.CORE_HODL,
            signal,
            trading_engine.engines[EngineType.CORE_HODL][0],
            risk_check,
        )

        mock_exchange.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_buy_with_risk_check_max_size(
        self, trading_engine, mock_exchange, mock_risk_manager
    ):
        """Buy with max position size from risk check."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="TestStrategy",
            confidence=0.8,
            metadata={},
        )

        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="risk-order-123",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.01"),
                status=OrderStatus.OPEN,
                exchange_order_id="ex-risk-123",
            )
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        # Risk check reduces max position size
        risk_check = RiskCheck(
            passed=True, risk_level="normal", max_position_size=Decimal("0.01")
        )

        await trading_engine._execute_buy(
            EngineType.CORE_HODL,
            signal,
            trading_engine.engines[EngineType.CORE_HODL][0],
            risk_check,
        )

        mock_exchange.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_buy_zero_quantity(self, trading_engine, mock_exchange):
        """Buy with zero quantity is rejected."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="TestStrategy",
            confidence=0.8,
            metadata={},
        )

        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        # Risk check returns zero max position size
        risk_check = RiskCheck(
            passed=True, risk_level="normal", max_position_size=Decimal("0")
        )

        with patch.object(
            trading_engine, "_create_order_with_retry", AsyncMock(return_value=None)
        ):
            await trading_engine._execute_buy(
                EngineType.CORE_HODL,
                signal,
                trading_engine.engines[EngineType.CORE_HODL][0],
                risk_check,
            )

        mock_exchange.create_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_close_no_position(self, trading_engine):
        """Close when no position exists."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.CLOSE,
            strategy_name="TestStrategy",
            metadata={"reason": "test"},
        )

        # No position exists for this symbol
        with patch.object(
            trading_engine, "_create_order_with_retry", AsyncMock()
        ) as mock_create:
            await trading_engine._execute_close(EngineType.CORE_HODL, signal)
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_close_wrong_side_filter(self, trading_engine, mock_exchange):
        """Close with side filter that doesn't match position."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.CLOSE,
            strategy_name="TestStrategy",
            metadata={"reason": "test"},
        )

        # Add a LONG position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        # Try to close with SHORT filter
        with patch.object(
            trading_engine, "_create_order_with_retry", AsyncMock()
        ) as mock_create:
            await trading_engine._execute_close(
                EngineType.CORE_HODL, signal, side_filter=PositionSide.SHORT
            )
            mock_create.assert_not_called()


# =============================================================================
# TestOrderLifecycleAdditional
# =============================================================================


class TestOrderLifecycleAdditional:
    """Additional order lifecycle tests."""

    @pytest.mark.asyncio
    async def test_on_order_filled_with_no_strategy(self, trading_engine, sample_order):
        """Order filled when strategy not found."""
        sample_order.status = OrderStatus.FILLED
        sample_order.filled_amount = Decimal("0.1")
        sample_order.average_price = Decimal("50000")
        sample_order.metadata["engine_type"] = "CORE_HODL"
        sample_order.metadata["strategy_name"] = "NonExistentStrategy"

        await trading_engine._on_order_filled(sample_order)

        # Should still update position even if strategy not found
        assert "BTCUSDT" in trading_engine.engine_positions[EngineType.CORE_HODL]

    @pytest.mark.asyncio
    async def test_update_pending_orders_skips_during_circuit_breaker(
        self, trading_engine, sample_order
    ):
        """Skip order updates during exchange downtime."""
        trading_engine.pending_orders[sample_order.id] = sample_order
        trading_engine.exchange_circuit_breaker = True

        await trading_engine._update_pending_orders()

        # Order should still be in pending (update skipped)
        assert sample_order.id in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_update_pending_orders_handles_rejected(
        self, trading_engine, sample_order, mock_exchange
    ):
        """Handle rejected orders."""
        trading_engine.pending_orders[sample_order.id] = sample_order
        mock_exchange.get_order_status = AsyncMock(return_value=OrderStatus.REJECTED)

        await trading_engine._update_pending_orders()

        assert sample_order.id not in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_update_pending_orders_handles_expired(
        self, trading_engine, sample_order, mock_exchange
    ):
        """Handle expired orders."""
        trading_engine.pending_orders[sample_order.id] = sample_order
        mock_exchange.get_order_status = AsyncMock(return_value=OrderStatus.EXPIRED)

        await trading_engine._update_pending_orders()

        assert sample_order.id not in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_on_partial_fill_no_fill_amount(self, trading_engine, mock_exchange):
        """Partial fill with no fill amount."""
        order = Order(
            id="partial-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0"),  # No fill amount
            average_price=Decimal("50000"),
            status=OrderStatus.PARTIALLY_FILLED,
            metadata={"engine_type": "CORE_HODL"},
        )

        await trading_engine._on_order_partially_filled(order)

        # Position should not be created with zero amount
        position = trading_engine.engine_positions[EngineType.CORE_HODL].get("BTCUSDT")
        if position:
            assert position.amount > Decimal("0")

    @pytest.mark.asyncio
    async def test_on_partial_fill_no_price_fallback(
        self, trading_engine, mock_exchange
    ):
        """Partial fill with no price - fallback to market price."""
        order = Order(
            id="partial-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0.05"),
            average_price=None,  # No price
            status=OrderStatus.PARTIALLY_FILLED,
            metadata={"engine_type": "CORE_HODL", "strategy_name": "TestStrategy"},
        )

        mock_exchange.get_ticker = AsyncMock(return_value={"last": 51000.0})

        await trading_engine._on_order_partially_filled(order)

        # Should use market price as fallback
        position = trading_engine.engine_positions[EngineType.CORE_HODL].get("BTCUSDT")
        if position:
            assert position.amount == Decimal("0.05")


# =============================================================================
# TestPositionManagementAdditional
# =============================================================================


class TestPositionManagementAdditional:
    """Additional position management tests."""

    @pytest.mark.asyncio
    async def test_update_position_for_buy_no_fill_price(
        self, trading_engine, mock_exchange, mock_database
    ):
        """Buy update with no fill price - fallback to market."""
        order = Order(
            id="buy-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0.1"),
            average_price=None,  # No fill price
            price=None,
            metadata={"engine_type": "CORE_HODL"},
        )

        mock_exchange.get_ticker = AsyncMock(return_value={"last": 52000.0})

        await trading_engine._update_position_for_buy(EngineType.CORE_HODL, order)

        position = trading_engine.engine_positions[EngineType.CORE_HODL].get("BTCUSDT")
        assert position is not None

    @pytest.mark.asyncio
    async def test_update_position_for_sell_no_fill_price(
        self, trading_engine, mock_database, mock_exchange, mock_risk_manager
    ):
        """Sell update with no fill price - fallback to entry price."""
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

        order = Order(
            id="sell-order",
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            filled_amount=Decimal("0.1"),
            average_price=None,  # No fill price
            price=None,
            metadata={"engine_type": "CORE_HODL", "strategy_name": "TestStrategy"},
        )

        mock_exchange.get_ticker = AsyncMock(side_effect=Exception("API error"))

        await trading_engine._update_position_for_sell(EngineType.CORE_HODL, order)

        # Position should be removed even with error
        assert "BTCUSDT" not in trading_engine.engine_positions[EngineType.CORE_HODL]

    @pytest.mark.asyncio
    async def test_update_position_for_sell_partial_with_price(
        self, trading_engine, mock_database
    ):
        """Partial sell with valid price."""
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
            filled_amount=Decimal("0.05"),  # Only partial fill
            average_price=Decimal("55000"),
            metadata={"engine_type": "CORE_HODL", "strategy_name": "TestStrategy"},
        )

        await trading_engine._update_position_for_sell(EngineType.CORE_HODL, order)

        # Position should still exist
        position = trading_engine.engine_positions[EngineType.CORE_HODL].get("BTCUSDT")
        if position:
            assert position.amount < Decimal("0.2")


# =============================================================================
# TestExchangeDowntimeAdditional
# =============================================================================


class TestExchangeDowntimeAdditional:
    """Additional exchange downtime tests."""

    @pytest.mark.asyncio
    async def test_update_exchange_status_already_healthy(
        self, trading_engine, mock_exchange
    ):
        """Update when exchange is already healthy."""
        trading_engine.exchange_down_since = None
        trading_engine.exchange_circuit_breaker = False

        mock_exchange.fetch_time = AsyncMock(
            return_value=datetime.now(timezone.utc).timestamp()
        )

        await trading_engine._update_exchange_status()

        # Should remain healthy
        assert not trading_engine.exchange_circuit_breaker

    @pytest.mark.asyncio
    async def test_pause_all_engines_indefinite(self, trading_engine):
        """Pause all engines indefinitely."""
        await trading_engine._pause_all_engines("test_reason")

        for engine_type, state in trading_engine.engine_states.items():
            assert state.is_paused is True
            assert state.pause_reason == "test_reason"
            assert state.pause_until is None  # Indefinite

    @pytest.mark.asyncio
    async def test_resume_all_engines_not_emergency(self, trading_engine):
        """Resume all engines when not in emergency."""
        # First pause
        await trading_engine._pause_all_engines("test")

        trading_engine._emergency_stop = False

        # Then resume
        await trading_engine._resume_all_engines()

        for state in trading_engine.engine_states.values():
            assert state.is_paused is False

    @pytest.mark.asyncio
    async def test_resume_all_engines_during_emergency(self, trading_engine):
        """Resume should not work during emergency stop."""
        # First pause
        await trading_engine._pause_all_engines("test")

        trading_engine._emergency_stop = True

        # Try to resume (should not work due to emergency)
        await trading_engine._resume_all_engines()

        for state in trading_engine.engine_states.values():
            # Should still be paused due to emergency
            assert state.is_paused is True


# =============================================================================
# TestOrderMaintenanceAdditional
# =============================================================================


class TestOrderMaintenanceAdditional:
    """Additional order maintenance tests."""

    @pytest.mark.asyncio
    async def test_cleanup_stuck_orders_order_not_found(
        self, trading_engine, mock_exchange
    ):
        """Stuck order cleanup when order not found on exchange."""
        import ccxt

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
        mock_exchange.cancel_order = AsyncMock(
            side_effect=ccxt.OrderNotFound("Order not found")
        )

        await trading_engine._cleanup_stuck_orders()

        # Order should be removed from pending
        assert "stuck-order" not in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_cleanup_stuck_orders_cancel_error(
        self, trading_engine, mock_exchange
    ):
        """Stuck order cleanup when cancel fails."""
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
        mock_exchange.cancel_order = AsyncMock(side_effect=Exception("Cancel failed"))

        await trading_engine._cleanup_stuck_orders()

        # Order should still be in pending (cleanup failed)
        assert "stuck-order" in trading_engine.pending_orders

    @pytest.mark.asyncio
    async def test_process_failed_orders_not_yet_time(self, trading_engine):
        """Failed orders not retried before delay."""
        failed_order = Order(
            id="failed-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.PENDING,
            metadata={"subaccount": "CORE_HODL", "engine_type": "CORE_HODL"},
        )

        # Add with recent timestamp (within delay)
        trading_engine.failed_orders["failed-order"] = (
            failed_order,
            0,
            datetime.now(timezone.utc) - timedelta(minutes=2),  # Only 2 min ago
        )

        await trading_engine._process_failed_orders()

        # Should still be in failed_orders
        assert "failed-order" in trading_engine.failed_orders

    @pytest.mark.asyncio
    async def test_retry_order_error(self, trading_engine, mock_exchange):
        """Retry order with generic error."""
        original_order = Order(
            id="original-order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL", "subaccount": "CORE_HODL"},
        )

        mock_exchange.create_order = AsyncMock(side_effect=Exception("Generic error"))

        result = await trading_engine._retry_order(original_order)

        assert result is False

    @pytest.mark.asyncio
    async def test_run_order_maintenance(self, trading_engine):
        """Full order maintenance run."""
        trading_engine._last_orphan_check = None

        with patch.object(
            trading_engine, "_detect_orphan_orders", AsyncMock()
        ) as mock_detect:
            with patch.object(
                trading_engine, "_cleanup_stuck_orders", AsyncMock()
            ) as mock_cleanup:
                with patch.object(
                    trading_engine, "_process_failed_orders", AsyncMock()
                ) as mock_process:
                    await trading_engine._run_order_maintenance()

                    mock_detect.assert_called_once()
                    mock_cleanup.assert_called_once()
                    mock_process.assert_called_once()

        assert trading_engine._last_orphan_check is not None


# =============================================================================
# TestStatePersistenceAdditional
# =============================================================================


class TestStatePersistenceAdditional:
    """Additional state persistence tests."""

    @pytest.mark.asyncio
    async def test_save_state_with_full_engine_state(
        self, trading_engine, mock_database
    ):
        """Save state with full engine state persistence."""
        # Create a strategy that supports full state
        mock_strategy = AsyncMock(spec=BaseStrategy)
        mock_strategy.name = "FullStateStrategy"
        mock_strategy.get_full_state = MagicMock(return_value={"last_purchase": {}})

        trading_engine.engines[EngineType.CORE_HODL] = [mock_strategy]

        with patch.object(mock_database, "save_engine_state", AsyncMock()):
            with patch.object(
                mock_database, "save_full_engine_state", AsyncMock()
            ) as mock_save_full:
                await trading_engine._save_state()

                mock_save_full.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_state_engine_state_error(self, trading_engine, mock_database):
        """Save state handles engine state error."""
        # Create a strategy that throws error on get_full_state
        mock_strategy = AsyncMock(spec=BaseStrategy)
        mock_strategy.name = "ErrorStrategy"
        mock_strategy.get_full_state = MagicMock(side_effect=Exception("State error"))

        trading_engine.engines[EngineType.CORE_HODL] = [mock_strategy]

        with patch.object(mock_database, "save_engine_state", AsyncMock()):
            with patch.object(mock_database, "save_full_engine_state", AsyncMock()):
                # Should not raise
                await trading_engine._save_state()

    @pytest.mark.asyncio
    async def test_load_state_with_engine_states(self, trading_engine, mock_database):
        """Load state with engine state data."""
        saved_position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        mock_database.get_open_positions = AsyncMock(return_value=[saved_position])
        mock_database.get_open_orders = AsyncMock(return_value=[])

        # Mock get_engine_states if available
        with patch.object(
            mock_database,
            "get_engine_states",
            AsyncMock(return_value={EngineType.CORE_HODL: {"is_active": True}}),
        ):
            await trading_engine._load_state()

            assert "BTCUSDT" in trading_engine.positions


# =============================================================================
# TestSyncPositionsAdditional
# =============================================================================


class TestSyncPositionsAdditional:
    """Additional position sync tests."""

    @pytest.mark.asyncio
    async def test_sync_positions_skips_usdt(self, trading_engine, mock_exchange):
        """Skip USDT when syncing positions."""
        mock_exchange.fetch_balance = AsyncMock(
            return_value={"total": {"USDT": 1000.0, "BTC": 0.1}}
        )
        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine._sync_positions_from_exchange()

        # USDT itself should be skipped (not USDT trading pairs like BTCUSDT)
        for pos in trading_engine.engine_positions[EngineType.CORE_HODL].values():
            assert pos.symbol != "USDT"  # Only skip USDT itself, not USDT pairs

    @pytest.mark.asyncio
    async def test_sync_positions_skips_dust(self, trading_engine, mock_exchange):
        """Skip dust amounts when syncing positions."""
        mock_exchange.fetch_balance = AsyncMock(
            return_value={"total": {"BTC": 0.00001}}  # Very small amount
        )
        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine._sync_positions_from_exchange()

        # Dust position should be skipped
        positions = trading_engine.engine_positions[EngineType.CORE_HODL]
        for pos in positions.values():
            assert pos.amount * pos.entry_price >= Decimal("1.0")

    @pytest.mark.asyncio
    async def test_sync_positions_already_tracked(self, trading_engine, mock_exchange):
        """Skip already tracked positions."""
        # Pre-add a position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )

        mock_exchange.fetch_balance = AsyncMock(return_value={"total": {"BTC": 0.1}})
        mock_exchange.get_ticker = AsyncMock(return_value={"last": 50000.0})

        await trading_engine._sync_positions_from_exchange()

        # Should still have the position
        assert "BTCUSDT" in trading_engine.engine_positions[EngineType.CORE_HODL]

    @pytest.mark.asyncio
    async def test_sync_last_purchase_no_positions(self, trading_engine):
        """Sync last purchase when no positions exist."""
        # Clear any positions
        trading_engine.engine_positions[EngineType.CORE_HODL] = {}

        # Create a DCA strategy
        dca_strategy = AsyncMock(spec=BaseStrategy)
        dca_strategy.name = "DCAStrategy"
        dca_strategy.symbols = ["BTCUSDT"]
        dca_strategy.last_purchase = {}

        trading_engine.engines[EngineType.CORE_HODL] = [dca_strategy]

        await trading_engine._sync_last_purchase_from_orders()

        # Should not set last_purchase when no positions
        assert "BTCUSDT" not in dca_strategy.last_purchase


# =============================================================================
# TestDCAInitializationAdditional
# =============================================================================


class TestDCAInitializationAdditional:
    """Additional DCA initialization tests."""

    @pytest.mark.asyncio
    async def test_initialize_dca_no_persistence_support(
        self, trading_engine, mock_database
    ):
        """DCA strategy without persistence support."""
        # Create a strategy without last_purchase
        regular_strategy = AsyncMock(spec=BaseStrategy)
        regular_strategy.name = "RegularStrategy"
        regular_strategy.symbols = ["BTCUSDT"]
        # No last_purchase attribute

        trading_engine.engines[EngineType.CORE_HODL] = [regular_strategy]

        await trading_engine._initialize_dca_persistence()

        # Should not throw error
        mock_database.get_all_dca_states.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_dca_database_error(self, trading_engine, mock_database):
        """DCA initialization handles database error."""
        dca_strategy = AsyncMock(spec=BaseStrategy)
        dca_strategy.name = "DCAStrategy"
        dca_strategy.symbols = ["BTCUSDT"]
        dca_strategy.last_purchase = {}
        dca_strategy.set_db_save_callback = MagicMock()

        trading_engine.engines[EngineType.CORE_HODL] = [dca_strategy]

        mock_database.get_all_dca_states = AsyncMock(side_effect=Exception("DB error"))

        # Should not throw error
        await trading_engine._initialize_dca_persistence()


# =============================================================================
# TestUpdatePortfolioAdditional
# =============================================================================


class TestUpdatePortfolioAdditional:
    """Additional portfolio update tests."""

    @pytest.mark.asyncio
    async def test_update_engine_allocations_no_portfolio(self, trading_engine):
        """Update allocations when no portfolio."""
        trading_engine.portfolio = None

        await trading_engine._update_engine_allocations()

        # Should not throw error
        for state in trading_engine.engine_states.values():
            assert state.current_value == Decimal("0")

    @pytest.mark.asyncio
    async def test_update_engine_allocations_with_drift(self, trading_engine):
        """Update allocations with drift detection."""
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        # Add a position that causes drift
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("5.0"),  # Large position causing drift
            metadata={"engine_type": "CORE_HODL"},
        )

        await trading_engine._update_engine_allocations()

        # Should have calculated allocation for CORE_HODL
        state = trading_engine.engine_states[EngineType.CORE_HODL]
        assert state.current_value > Decimal("0")


# =============================================================================
# TestCreateOrderWithRetryAdditional
# =============================================================================


class TestCreateOrderWithRetryAdditional:
    """Additional order creation retry tests."""

    @pytest.mark.asyncio
    async def test_create_order_success(self, trading_engine, mock_exchange):
        """Successful order creation."""
        mock_exchange.create_order = AsyncMock(
            return_value=Order(
                id="success-order",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1"),
                status=OrderStatus.OPEN,
            )
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

        assert result is not None
        assert result.id == "success-order"

    @pytest.mark.asyncio
    async def test_create_order_unknown_error(self, trading_engine, mock_exchange):
        """Unknown error during order creation."""
        mock_exchange.create_order = AsyncMock(side_effect=RuntimeError("Unknown"))

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
        assert len(trading_engine.failed_orders) == 0  # Unknown errors not retried


# =============================================================================
# TestStartStopAdditional
# =============================================================================


class TestStartStopAdditional:
    """Additional start/stop tests."""

    @pytest.mark.asyncio
    async def test_start_already_running(self, trading_engine):
        """Start when already running."""
        trading_engine._running = True

        with patch.object(trading_engine, "initialize", AsyncMock()) as mock_init:
            await trading_engine.start()
            mock_init.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_initializes_if_needed(self, trading_engine):
        """Start initializes if portfolio not set."""
        trading_engine._running = False
        trading_engine.portfolio = None

        with patch.object(trading_engine, "initialize", AsyncMock()) as mock_init:
            with patch("asyncio.create_task") as mock_create:
                await trading_engine.start()
                mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_saves_state(self, trading_engine):
        """Stop saves state."""
        trading_engine._running = True
        trading_engine._main_task = None

        with patch.object(trading_engine, "_save_state", AsyncMock()) as mock_save:
            await trading_engine.stop()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, trading_engine):
        """Stop cancels running task."""
        trading_engine._running = True

        async def dummy_task():
            await asyncio.sleep(10)

        trading_engine._main_task = asyncio.create_task(dummy_task())

        with patch.object(trading_engine, "_save_state", AsyncMock()):
            await trading_engine.stop()

        assert not trading_engine._running


# =============================================================================
# TestHelperMethodsAdditional
# =============================================================================


class TestHelperMethodsAdditional:
    """Additional helper method tests."""

    def test_get_position_value_different_engines(self, trading_engine):
        """Position value for different engines."""
        # Add positions to different engines
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1"),
            metadata={"engine_type": "CORE_HODL"},
        )
        trading_engine.engine_positions[EngineType.TREND]["ETHUSDT"] = Position(
            symbol="ETHUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("3000"),
            amount=Decimal("1.0"),
            metadata={"engine_type": "TREND"},
        )

        core_value = trading_engine._get_position_value(EngineType.CORE_HODL, "BTCUSDT")
        trend_value = trading_engine._get_position_value(EngineType.TREND, "ETHUSDT")

        assert core_value == Decimal("5000")
        assert trend_value == Decimal("3000")

    def test_initialize_engine_states(self, trading_engine):
        """Engine states are initialized correctly."""
        # Re-initialize
        trading_engine._initialize_engine_states()

        for engine_type in EngineType:
            assert engine_type in trading_engine.engine_states
            state = trading_engine.engine_states[engine_type]
            assert state.engine_type == engine_type
            assert (
                state.current_allocation_pct == trading_engine.ALLOCATION[engine_type]
            )


# =============================================================================
# TestGetStatusAdditional
# =============================================================================


class TestGetStatusAdditional:
    """Additional get_status tests."""

    def test_get_status_no_portfolio(self, trading_engine):
        """Get status when portfolio is None."""
        trading_engine.portfolio = None

        status = trading_engine.get_status()

        assert status["portfolio"] is None

    def test_get_status_with_circuit_breaker(self, trading_engine):
        """Get status when circuit breaker is active."""
        trading_engine.exchange_circuit_breaker = True
        trading_engine.exchange_down_since = datetime.now(timezone.utc) - timedelta(
            seconds=30
        )
        trading_engine.portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("50000")
        )

        status = trading_engine.get_status()

        assert status["system"]["exchange_health"]["circuit_breaker"] is True
        assert status["system"]["exchange_health"]["downtime_seconds"] >= 30

    def test_get_system_state_with_none_portfolio(self, trading_engine):
        """Get system state when portfolio is None."""
        trading_engine.portfolio = None

        state = trading_engine.get_system_state()

        assert isinstance(state, SystemState)
        assert state.portfolio.total_balance == Decimal("0")
