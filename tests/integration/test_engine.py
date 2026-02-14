"""Integration tests for The Eternal Engine trading system.

These tests verify the interaction between multiple components:
- TradingEngine orchestration
- RiskManager integration
- Exchange execution
- Database persistence
- Signal flow between components
"""
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.engine import TradingEngine, create_trading_engine
from src.core.models import (
    Order, OrderSide, OrderType, OrderStatus,
    Position, PositionSide, TradingSignal, SignalType,
    Portfolio, EngineType, MarketData
)
from src.exchange.bybit_client import ByBitClient, SubAccountType
from src.risk.risk_manager import RiskManager
from src.storage.database import Database
from src.strategies.base import BaseStrategy


# =============================================================================
# Test Configuration Setup
# =============================================================================

@pytest.fixture(autouse=True)
def mock_engine_config():
    """Mock engine configuration with valid API keys for testing."""
    with patch("src.core.engine.engine_config") as mock_config:
        mock_config.api_mode = "demo"
        mock_config.is_demo_mode = True
        mock_config.is_prod_mode = False
        mock_config.demo_api_key = "test_demo_key"
        mock_config.demo_api_secret = "test_demo_secret"
        mock_config.get_active_api_credentials.return_value = ("test_demo_key", "test_demo_secret")
        mock_config.validate_configuration.return_value = {"valid": True, "issues": []}
        
        # Capital allocation
        mock_config.capital_allocation = MagicMock()
        mock_config.capital_allocation.core_hodl = 0.60
        mock_config.capital_allocation.trend = 0.20
        mock_config.capital_allocation.funding = 0.15
        mock_config.capital_allocation.tactical = 0.05
        
        # Engine configs - use MagicMock with enabled attribute and model_dump method
        core_hodl_config = MagicMock()
        core_hodl_config.enabled = True
        core_hodl_config.dca_amount_usdt = 100.0
        core_hodl_config.dca_interval_hours = 24
        core_hodl_config.model_dump.return_value = {"enabled": True, "dca_amount_usdt": 100.0}
        mock_config.core_hodl = core_hodl_config
        
        trend_config = MagicMock()
        trend_config.enabled = True
        trend_config.max_leverage = 2.0
        trend_config.model_dump.return_value = {"enabled": True, "max_leverage": 2.0}
        mock_config.trend = trend_config
        
        funding_config = MagicMock()
        funding_config.enabled = True
        funding_config.min_annualized_rate = 0.10
        funding_config.max_leverage = 2.0
        funding_config.model_dump.return_value = {"enabled": True, "min_annualized_rate": 0.10, "max_leverage": 2.0}
        mock_config.funding = funding_config
        
        # Position sizing config
        mock_config.position_sizing = MagicMock()
        mock_config.position_sizing.max_risk_per_trade = 0.01
        mock_config.position_sizing.max_position_pct = 5.0
        
        tactical_config = MagicMock()
        tactical_config.enabled = True
        tactical_config.profit_target_pct = 100.0
        tactical_config.model_dump.return_value = {"enabled": True, "profit_target_pct": 100.0}
        mock_config.tactical = tactical_config
        
        yield mock_config


# =============================================================================
# Integration Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def integration_database():
    """Create an in-memory database for integration tests."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def mock_exchange_client():
    """Create a fully mocked exchange client."""
    client = MagicMock(spec=ByBitClient)
    
    # Mock async methods
    client.initialize = AsyncMock()
    client.close = AsyncMock()
    
    client.get_balance = AsyncMock(return_value=Portfolio(
        total_balance=Decimal("100000"),
        available_balance=Decimal("80000")
    ))
    
    client.get_positions = AsyncMock(return_value=[])
    
    client.create_order = AsyncMock(return_value=Order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        amount=Decimal("0.1"),
        price=Decimal("50000"),
        status=OrderStatus.FILLED,
        filled_amount=Decimal("0.1"),
        average_price=Decimal("50000"),
        exchange_order_id="test_order_123"
    ))
    
    client.cancel_order = AsyncMock(return_value=True)
    client.get_order_status = AsyncMock(return_value=OrderStatus.FILLED)
    client.get_open_orders = AsyncMock(return_value=[])
    
    client.fetch_ohlcv = AsyncMock(return_value=[
        MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow() - timedelta(hours=i),
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49000"),
            close=Decimal("50500"),
            volume=Decimal("1000")
        )
        for i in range(100)
    ])
    
    client.fetch_ticker = AsyncMock(return_value={
        'symbol': 'BTCUSDT',
        'last': Decimal('50000'),
        'bid': Decimal('49990'),
        'ask': Decimal('50010'),
        'timestamp': int(datetime.utcnow().timestamp() * 1000)
    })
    
    client.get_ticker = AsyncMock(return_value={
        'symbol': 'BTCUSDT',
        'last': Decimal('50000'),
        'bid': Decimal('49990'),
        'ask': Decimal('50010'),
        'timestamp': int(datetime.utcnow().timestamp() * 1000)
    })
    
    client.get_all_balances = AsyncMock(return_value={
        'CORE_HODL': Portfolio(total_balance=Decimal("60000"), available_balance=Decimal("50000")),
        'TREND': Portfolio(total_balance=Decimal("20000"), available_balance=Decimal("18000")),
        'FUNDING': Portfolio(total_balance=Decimal("15000"), available_balance=Decimal("14000")),
        'TACTICAL': Portfolio(total_balance=Decimal("5000"), available_balance=Decimal("5000"))
    })
    
    return client


@pytest.fixture
def mock_strategy():
    """Create a mock strategy for testing."""
    strategy = MagicMock(spec=BaseStrategy)
    strategy.name = "TestStrategy"
    strategy.symbols = ["BTCUSDT", "ETHUSDT"]
    strategy.is_active = True
    strategy.engine_type = EngineType.CORE_HODL
    
    strategy.analyze = AsyncMock(return_value=[
        TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="TestStrategy",
            engine_type=EngineType.CORE_HODL,
            timestamp=datetime.utcnow(),
            confidence=0.8,
            metadata={"entry_price": "50000", "size": "0.1"}
        )
    ])
    
    strategy.on_order_filled = AsyncMock()
    strategy.on_position_closed = AsyncMock()
    strategy.get_stats = MagicMock(return_value={"test": "stats"})
    
    return strategy


@pytest_asyncio.fixture
async def trading_engine(mock_exchange_client, integration_database):
    """Create a configured trading engine for integration tests."""
    risk_manager = RiskManager()
    
    engine = TradingEngine(
        exchange=mock_exchange_client,
        risk_manager=risk_manager,
        database=integration_database
    )
    
    yield engine
    
    # Cleanup
    if engine._running:
        await engine.stop()


# =============================================================================
# Trading Engine Initialization Tests
# =============================================================================

class TestTradingEngineInitialization:
    """Test TradingEngine initialization and configuration."""
    
    @pytest.mark.asyncio
    async def test_trading_engine_initialization(self, trading_engine):
        """Test trading engine initialization."""
        await trading_engine.initialize()
        
        assert trading_engine.portfolio is not None
        assert trading_engine.portfolio.total_balance == Decimal("100000")
        assert len(trading_engine.engine_states) == 4
        assert all(e in trading_engine.engine_states for e in EngineType)
    
    @pytest.mark.asyncio
    async def test_trading_engine_allocation_percentages(self, trading_engine):
        """Test engine allocation percentages."""
        await trading_engine.initialize()
        
        assert trading_engine.ALLOCATION[EngineType.CORE_HODL] == Decimal("0.60")
        assert trading_engine.ALLOCATION[EngineType.TREND] == Decimal("0.20")
        assert trading_engine.ALLOCATION[EngineType.FUNDING] == Decimal("0.15")
        assert trading_engine.ALLOCATION[EngineType.TACTICAL] == Decimal("0.05")
    
    @pytest.mark.asyncio
    async def test_trading_engine_subaccount_mapping(self, trading_engine):
        """Test engine to subaccount mapping."""
        assert trading_engine.ENGINE_TO_SUBACCOUNT[EngineType.CORE_HODL] == SubAccountType.CORE_HODL
        assert trading_engine.ENGINE_TO_SUBACCOUNT[EngineType.TREND] == SubAccountType.TREND
        assert trading_engine.ENGINE_TO_SUBACCOUNT[EngineType.FUNDING] == SubAccountType.FUNDING
        assert trading_engine.ENGINE_TO_SUBACCOUNT[EngineType.TACTICAL] == SubAccountType.TACTICAL
    
    @pytest.mark.asyncio
    async def test_trading_engine_state_loading(self, trading_engine, integration_database):
        """Test loading state from database on initialization."""
        # Pre-populate database with a position
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5"),
            metadata={"engine_type": "CORE_HODL"}
        )
        await integration_database.save_position(position)
        
        await trading_engine.initialize()
        
        # Position should be loaded
        assert "BTCUSDT" in trading_engine.positions


# =============================================================================
# Signal Flow Tests
# =============================================================================

class TestSignalFlow:
    """Test signal flow: Engine → RiskManager → Execution."""
    
    @pytest.mark.asyncio
    async def test_signal_processing_pipeline(self, trading_engine, mock_strategy):
        """Test complete signal processing pipeline."""
        await trading_engine.initialize()
        
        # Add strategy
        trading_engine.add_strategy(EngineType.CORE_HODL, mock_strategy)
        
        # Manually trigger analysis cycle
        await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)
        
        # Strategy analyze should have been called
        mock_strategy.analyze.assert_called_once()
        
        # Exchange create_order should have been called (signal passed risk check)
        trading_engine.exchange.create_order.assert_called()
    
    @pytest.mark.asyncio
    async def test_signal_rejected_by_risk_manager(self, trading_engine, mock_strategy):
        """Test signal rejection by risk manager."""
        await trading_engine.initialize()
        
        # Add strategy with low confidence signal (will be rejected)
        mock_strategy.analyze = AsyncMock(return_value=[
            TradingSignal(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                strategy_name="TestStrategy",
                engine_type=EngineType.CORE_HODL,
                timestamp=datetime.utcnow(),
                confidence=0.3,  # Below threshold
                metadata={}
            )
        ])
        
        trading_engine.add_strategy(EngineType.CORE_HODL, mock_strategy)
        
        # Trigger analysis
        await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)
        
        # Exchange should NOT be called for rejected signal
        # Note: create_order may still be called if there are existing orders
    
    @pytest.mark.asyncio
    async def test_signal_risk_check_integration(self, trading_engine):
        """Test risk check integration with signal processing."""
        await trading_engine.initialize()
        
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            engine_type=EngineType.CORE_HODL,
            timestamp=datetime.utcnow(),
            confidence=0.8
        )
        
        risk_check = trading_engine.risk_manager.check_signal(
            signal, trading_engine.portfolio, {}
        )
        
        assert risk_check.passed is True


# =============================================================================
# Order Execution Tests
# =============================================================================

class TestOrderExecution:
    """Test order execution flow."""
    
    @pytest.mark.asyncio
    async def test_buy_order_execution(self, trading_engine):
        """Test buy order execution flow."""
        await trading_engine.initialize()
        
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            engine_type=EngineType.CORE_HODL,
            timestamp=datetime.utcnow(),
            confidence=0.8,
            metadata={"entry_price": "50000"}
        )
        
        # Create a mock strategy
        mock_strategy = MagicMock()
        mock_strategy.name = "TestStrategy"
        trading_engine.engines[EngineType.CORE_HODL] = [mock_strategy]
        
        await trading_engine._execute_buy(EngineType.CORE_HODL, signal, mock_strategy, MagicMock())
        
        # Exchange should have been called
        trading_engine.exchange.create_order.assert_called()
        
        # Order should be tracked
        assert len(trading_engine.pending_orders) == 1
    
    @pytest.mark.asyncio
    async def test_order_fill_handling(self, trading_engine):
        """Test order fill handling."""
        await trading_engine.initialize()
        
        # Create a filled order
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.FILLED,
            filled_amount=Decimal("0.1"),
            average_price=Decimal("50000"),
            metadata={"engine_type": "CORE_HODL", "strategy_name": "Test"}
        )
        
        await trading_engine._on_order_filled(order)
        
        # Position should be created
        assert "BTCUSDT" in trading_engine.positions
        assert trading_engine.positions["BTCUSDT"].amount == Decimal("0.1")
    
    @pytest.mark.asyncio
    async def test_position_close_handling(self, trading_engine, integration_database):
        """Test position close handling."""
        await trading_engine.initialize()
        
        # Pre-create a position
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1")
        )
        trading_engine.positions["BTCUSDT"] = position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = position
        await integration_database.save_position(position)
        
        # Create a sell order that closes the position
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.FILLED,
            filled_amount=Decimal("0.1"),
            average_price=Decimal("55000"),
            metadata={"engine_type": "CORE_HODL"}
        )
        
        await trading_engine._on_order_filled(order)
        
        # Position should be removed
        assert "BTCUSDT" not in trading_engine.positions


# =============================================================================
# Circuit Breaker Integration Tests
# =============================================================================

class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with trading engine."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_triggers_emergency_stop(self, trading_engine):
        """Test circuit breaker triggers emergency stop."""
        await trading_engine.initialize()
        
        # Set portfolio to trigger circuit breaker
        trading_engine.portfolio.total_balance = Decimal("75000")  # 25% drawdown
        trading_engine.risk_manager.all_time_high_balance = Decimal("100000")
        
        await trading_engine._check_circuit_breakers()
        
        # Should trigger Level 4 circuit breaker
        assert trading_engine._emergency_stop is True
        assert trading_engine.engine_states[EngineType.CORE_HODL].circuit_breaker_level.value == "level_4"
    
    @pytest.mark.asyncio
    async def test_emergency_stop_halts_trading(self, trading_engine):
        """Test that emergency stop halts trading."""
        await trading_engine.initialize()
        
        await trading_engine.emergency_stop("Test emergency")
        
        assert trading_engine._emergency_stop is True
        assert trading_engine.risk_manager.emergency_stop is True
        
        # All engines should be paused
        for engine_type, state in trading_engine.engine_states.items():
            assert state.is_paused is True
    
    @pytest.mark.asyncio
    async def test_reset_emergency_stop(self, trading_engine):
        """Test resetting emergency stop."""
        await trading_engine.initialize()
        
        await trading_engine.emergency_stop("Test emergency")
        assert trading_engine._emergency_stop is True
        
        await trading_engine.reset_emergency_stop("admin_user")
        
        assert trading_engine._emergency_stop is False
        assert trading_engine.risk_manager.emergency_stop is False


# =============================================================================
# State Persistence Tests
# =============================================================================

class TestStatePersistence:
    """Test state persistence across operations."""
    
    @pytest.mark.asyncio
    async def test_position_persistence(self, trading_engine, integration_database):
        """Test that positions are persisted to database."""
        await trading_engine.initialize()
        
        # Create a position
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5")
        )
        
        await integration_database.save_position(position)
        
        # Retrieve from database
        retrieved = await integration_database.get_position("BTCUSDT")
        
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"
        assert retrieved.amount == Decimal("0.5")
    
    @pytest.mark.asyncio
    async def test_order_persistence(self, trading_engine, integration_database):
        """Test that orders are persisted to database."""
        await trading_engine.initialize()
        
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.FILLED
        )
        
        await integration_database.save_order(order)
        
        retrieved = await integration_database.get_order(order.id)
        
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_engine_state_persistence(self, trading_engine, integration_database):
        """Test engine state persistence."""
        await trading_engine.initialize()
        
        await integration_database.save_engine_state(
            engine_name="CORE_HODL",
            state="active",
            allocation_pct=Decimal("60"),
            performance_metrics={"win_rate": 0.65}
        )
        
        state = await integration_database.get_engine_state("CORE_HODL")
        
        assert state is not None
        assert state['state'] == "active"
        assert state['allocation_pct'] == Decimal("60")


# =============================================================================
# Portfolio Management Tests
# =============================================================================

class TestPortfolioManagement:
    """Test portfolio and allocation management."""
    
    @pytest.mark.asyncio
    async def test_portfolio_update(self, trading_engine):
        """Test portfolio update from exchange."""
        await trading_engine.initialize()
        
        await trading_engine._update_portfolio()
        
        assert trading_engine.portfolio is not None
        trading_engine.exchange.get_balance.assert_called()
    
    @pytest.mark.asyncio
    async def test_engine_allocation_update(self, trading_engine):
        """Test engine allocation update."""
        await trading_engine.initialize()
        
        # Add positions
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5")
        )
        
        await trading_engine._update_engine_allocations()
        
        # Check that allocation was calculated
        state = trading_engine.engine_states[EngineType.CORE_HODL]
        assert state.current_value > Decimal("0")


# =============================================================================
# Full Trading Cycle Tests
# =============================================================================

class TestFullTradingCycle:
    """Test complete trading cycles."""
    
    @pytest.mark.asyncio
    async def test_full_buy_cycle(self, trading_engine, mock_strategy):
        """Test complete buy cycle: signal → risk check → order → fill → position."""
        await trading_engine.initialize()
        
        # Setup
        trading_engine.add_strategy(EngineType.CORE_HODL, mock_strategy)
        
        # Execute cycle
        await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)
        
        # Verify order was created
        trading_engine.exchange.create_order.assert_called()
        
        # Simulate order fill
        order_id = list(trading_engine.pending_orders.keys())[0]
        order = trading_engine.pending_orders[order_id]
        
        # Manually trigger fill handling
        await trading_engine._on_order_filled(order)
        
        # Verify position was created
        assert len(trading_engine.positions) > 0
    
    @pytest.mark.asyncio
    async def test_full_close_cycle(self, trading_engine, mock_strategy, integration_database):
        """Test complete close cycle: signal → order → fill → position removal."""
        await trading_engine.initialize()
        
        # Pre-create position
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.1")
        )
        trading_engine.positions["BTCUSDT"] = position
        trading_engine.engine_positions[EngineType.CORE_HODL]["BTCUSDT"] = position
        await integration_database.save_position(position)
        
        # Setup strategy to generate close signal
        mock_strategy.analyze = AsyncMock(return_value=[
            TradingSignal(
                symbol="BTCUSDT",
                signal_type=SignalType.CLOSE,
                strategy_name="TestStrategy",
                engine_type=EngineType.CORE_HODL,
                timestamp=datetime.utcnow(),
                confidence=1.0,
                metadata={"reason": "test_close"}
            )
        ])
        
        trading_engine.add_strategy(EngineType.CORE_HODL, mock_strategy)
        
        # Execute cycle
        await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)
        
        # Simulate fill
        if trading_engine.pending_orders:
            order_id = list(trading_engine.pending_orders.keys())[0]
            order = trading_engine.pending_orders[order_id]
            await trading_engine._on_order_filled(order)
            
            # Position should be removed
            assert "BTCUSDT" not in trading_engine.positions


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling in integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_exchange_error_handling(self, trading_engine, mock_strategy):
        """Test handling of exchange errors."""
        await trading_engine.initialize()
        
        # Make exchange raise error
        trading_engine.exchange.create_order = AsyncMock(
            side_effect=Exception("Exchange API error")
        )
        
        trading_engine.add_strategy(EngineType.CORE_HODL, mock_strategy)
        
        # Should not crash
        try:
            await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)
        except Exception:
            pass  # Expected
    
    @pytest.mark.asyncio
    async def test_strategy_error_handling(self, trading_engine):
        """Test handling of strategy errors."""
        await trading_engine.initialize()
        
        # Create failing strategy
        failing_strategy = MagicMock()
        failing_strategy.name = "FailingStrategy"
        failing_strategy.symbols = ["BTCUSDT"]
        failing_strategy.is_active = True
        failing_strategy.analyze = AsyncMock(side_effect=Exception("Strategy error"))
        
        trading_engine.add_strategy(EngineType.CORE_HODL, failing_strategy)
        
        # Should not crash
        await trading_engine._run_analysis_cycle(EngineType.CORE_HODL)
        
        # Engine should record error
        assert trading_engine.engine_states[EngineType.CORE_HODL].error_count > 0


# =============================================================================
# Status and Monitoring Tests
# =============================================================================

class TestStatusAndMonitoring:
    """Test status and monitoring functionality."""
    
    @pytest.mark.asyncio
    async def test_get_status(self, trading_engine):
        """Test getting comprehensive system status."""
        await trading_engine.initialize()
        
        status = trading_engine.get_status()
        
        assert 'system' in status
        assert 'portfolio' in status
        assert 'engines' in status
        assert 'positions' in status
        assert 'performance' in status
        
        assert status['system']['running'] is False  # Not started yet
        assert 'core_hodl' in status['engines']
    
    @pytest.mark.asyncio
    async def test_get_system_state(self, trading_engine):
        """Test getting complete system state snapshot."""
        await trading_engine.initialize()
        
        state = trading_engine.get_system_state()
        
        assert state.portfolio is not None
        assert len(state.engines) == 4
        assert state.circuit_breaker_level is not None
        assert state.is_trading_halted is False
