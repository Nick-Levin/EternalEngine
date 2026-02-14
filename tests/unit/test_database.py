"""Unit tests for database operations."""
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime, timedelta

from src.storage.database import Database
from src.core.models import (
    Order, OrderSide, OrderType, OrderStatus,
    Position, PositionSide, Trade, TradeStatus
)


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def test_database():
    """Create an in-memory test database."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return Order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        amount=Decimal("0.1"),
        price=None,
        exchange_order_id="ex_123",
        status=OrderStatus.FILLED,
        filled_amount=Decimal("0.1"),
        average_price=Decimal("50000"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        filled_at=datetime.utcnow(),
        stop_loss_price=Decimal("48500"),
        take_profit_price=Decimal("53000"),
        metadata={"engine_name": "CORE_HODL", "strategy": "DCA"}
    )


@pytest.fixture
def sample_position():
    """Create a sample position for testing."""
    return Position(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        entry_price=Decimal("50000"),
        amount=Decimal("0.5"),
        opened_at=datetime.utcnow(),
        unrealized_pnl=Decimal("2500"),
        realized_pnl=Decimal("0"),
        stop_loss_price=Decimal("48500"),
        take_profit_price=Decimal("53000"),
        metadata={"engine_name": "CORE_HODL"}
    )


@pytest.fixture
def sample_trade():
    """Create a sample trade for testing."""
    return Trade(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        amount=Decimal("0.1"),
        entry_price=Decimal("50000"),
        exit_price=Decimal("51500"),
        entry_time=datetime.utcnow() - timedelta(days=1),
        exit_time=datetime.utcnow(),
        realized_pnl=Decimal("150"),
        realized_pnl_pct=Decimal("3"),
        entry_fee=Decimal("5"),
        exit_fee=Decimal("5.15"),
        strategy_name="TestStrategy",
        close_reason="take_profit",
        status=TradeStatus.CLOSED
    )


# =============================================================================
# Database Initialization Tests
# =============================================================================

class TestDatabaseInitialization:
    """Test database initialization."""
    
    @pytest.mark.asyncio
    async def test_database_initialization(self):
        """Test database initialization creates tables."""
        db = Database("sqlite+aiosqlite:///:memory:")
        await db.initialize()
        
        # If initialization succeeds, tables should exist
        # We can verify by trying to save an order
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1")
        )
        await db.save_order(order)
        
        retrieved = await db.get_order(order.id)
        assert retrieved is not None
        
        await db.close()
    
    @pytest.mark.asyncio
    async def test_database_close(self):
        """Test database connection closing."""
        db = Database("sqlite+aiosqlite:///:memory:")
        await db.initialize()
        
        # Should not raise
        await db.close()


# =============================================================================
# Order CRUD Tests
# =============================================================================

class TestOrderOperations:
    """Test order CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_save_new_order(self, test_database, sample_order):
        """Test saving a new order."""
        saved = await test_database.save_order(sample_order)
        
        assert saved.id == sample_order.id
        assert saved.symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_save_order_with_engine_name(self, test_database, sample_order):
        """Test saving order with engine name."""
        saved = await test_database.save_order(sample_order, engine_name="TEST_ENGINE")
        
        # Retrieve and verify
        retrieved = await test_database.get_order(sample_order.id)
        assert retrieved.metadata.get("engine_name") == "TEST_ENGINE"
    
    @pytest.mark.asyncio
    async def test_update_existing_order(self, test_database, sample_order):
        """Test updating an existing order."""
        # Save initial order
        await test_database.save_order(sample_order)
        
        # Modify and save again
        sample_order.status = OrderStatus.CANCELLED
        sample_order.filled_amount = Decimal("0.05")
        
        updated = await test_database.save_order(sample_order)
        
        # Retrieve and verify
        retrieved = await test_database.get_order(sample_order.id)
        assert retrieved.status == OrderStatus.CANCELLED
        assert retrieved.filled_amount == Decimal("0.05")
    
    @pytest.mark.asyncio
    async def test_get_order(self, test_database, sample_order):
        """Test retrieving an order by ID."""
        await test_database.save_order(sample_order)
        
        retrieved = await test_database.get_order(sample_order.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_order.id
        assert retrieved.symbol == sample_order.symbol
        assert retrieved.side == sample_order.side
        assert retrieved.amount == sample_order.amount
    
    @pytest.mark.asyncio
    async def test_get_order_not_found(self, test_database):
        """Test retrieving a non-existent order."""
        retrieved = await test_database.get_order("nonexistent_id")
        
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_get_open_orders(self, test_database):
        """Test retrieving open orders."""
        # Create orders with different statuses
        open_order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=Decimal("0.1"),
            price=Decimal("49000"),
            status=OrderStatus.OPEN
        )
        
        filled_order = Order(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1"),
            status=OrderStatus.FILLED
        )
        
        await test_database.save_order(open_order)
        await test_database.save_order(filled_order)
        
        open_orders = await test_database.get_open_orders()
        
        assert len(open_orders) == 1
        assert open_orders[0].id == open_order.id
    
    @pytest.mark.asyncio
    async def test_get_open_orders_by_engine(self, test_database):
        """Test retrieving open orders filtered by engine."""
        order1 = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=Decimal("0.1"),
            price=Decimal("49000"),
            status=OrderStatus.OPEN,
            metadata={"engine_name": "CORE_HODL"}
        )
        
        order2 = Order(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=Decimal("1"),
            price=Decimal("2900"),
            status=OrderStatus.OPEN,
            metadata={"engine_name": "TREND"}
        )
        
        await test_database.save_order(order1, engine_name="CORE_HODL")
        await test_database.save_order(order2, engine_name="TREND")
        
        core_orders = await test_database.get_open_orders(engine="CORE_HODL")
        
        assert len(core_orders) == 1
        assert core_orders[0].symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_get_orders_with_filters(self, test_database):
        """Test retrieving orders with filters."""
        order1 = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            status=OrderStatus.FILLED
        )
        
        order2 = Order(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1"),
            status=OrderStatus.CANCELLED
        )
        
        await test_database.save_order(order1)
        await test_database.save_order(order2)
        
        # Filter by symbol
        btc_orders = await test_database.get_orders(symbol="BTCUSDT")
        assert len(btc_orders) == 1
        
        # Filter by status
        filled_orders = await test_database.get_orders(status="filled")
        assert len(filled_orders) == 1


# =============================================================================
# Position CRUD Tests
# =============================================================================

class TestPositionOperations:
    """Test position CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_save_new_position(self, test_database, sample_position):
        """Test saving a new position."""
        saved = await test_database.save_position(sample_position)
        
        assert saved.id == sample_position.id
        assert saved.symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_update_existing_position(self, test_database, sample_position):
        """Test updating an existing position."""
        await test_database.save_position(sample_position)
        
        # Modify position
        sample_position.amount = Decimal("0.7")
        sample_position.unrealized_pnl = Decimal("3500")
        
        await test_database.save_position(sample_position)
        
        # Retrieve and verify
        retrieved = await test_database.get_position("BTCUSDT")
        assert retrieved.amount == Decimal("0.7")
        assert retrieved.unrealized_pnl == Decimal("3500")
    
    @pytest.mark.asyncio
    async def test_get_position(self, test_database, sample_position):
        """Test retrieving a position by symbol."""
        await test_database.save_position(sample_position)
        
        retrieved = await test_database.get_position("BTCUSDT")
        
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"
        assert retrieved.side == PositionSide.LONG
        assert retrieved.entry_price == Decimal("50000")
    
    @pytest.mark.asyncio
    async def test_get_position_not_found(self, test_database):
        """Test retrieving a non-existent position."""
        retrieved = await test_database.get_position("NONEXISTENT")
        
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_get_open_positions(self, test_database):
        """Test retrieving all open positions."""
        pos1 = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5")
        )
        
        pos2 = Position(
            symbol="ETHUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("3000"),
            amount=Decimal("5")
        )
        
        await test_database.save_position(pos1)
        await test_database.save_position(pos2)
        
        positions = await test_database.get_open_positions()
        
        assert len(positions) == 2
    
    @pytest.mark.asyncio
    async def test_get_open_positions_by_engine(self, test_database):
        """Test retrieving positions filtered by engine."""
        pos1 = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5"),
            metadata={"engine_name": "CORE_HODL"}
        )
        
        pos2 = Position(
            symbol="BTC-PERP",
            side=PositionSide.LONG,
            entry_price=Decimal("51000"),
            amount=Decimal("0.3"),
            metadata={"engine_name": "TREND"}
        )
        
        await test_database.save_position(pos1, engine_name="CORE_HODL")
        await test_database.save_position(pos2, engine_name="TREND")
        
        core_positions = await test_database.get_open_positions(engine="CORE_HODL")
        
        assert len(core_positions) == 1
        assert core_positions[0].symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_delete_position(self, test_database, sample_position):
        """Test deleting a position."""
        await test_database.save_position(sample_position)
        
        # Verify position exists
        retrieved = await test_database.get_position("BTCUSDT")
        assert retrieved is not None
        
        # Delete position
        await test_database.delete_position("BTCUSDT")
        
        # Verify position is deleted
        retrieved = await test_database.get_position("BTCUSDT")
        assert retrieved is None


# =============================================================================
# Trade CRUD Tests
# =============================================================================

class TestTradeOperations:
    """Test trade CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_save_trade(self, test_database, sample_trade):
        """Test saving a trade."""
        saved = await test_database.save_trade(sample_trade)
        
        assert saved.id == sample_trade.id
        assert saved.symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_save_trade_with_engine_name(self, test_database, sample_trade):
        """Test saving trade with engine name."""
        saved = await test_database.save_trade(sample_trade, engine_name="CORE_HODL")
        
        # Verify by retrieving trades
        trades = await test_database.get_trades(engine="CORE_HODL")
        assert len(trades) == 1
    
    @pytest.mark.asyncio
    async def test_get_trades(self, test_database):
        """Test retrieving trades."""
        trade1 = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.1"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("51500"),
            entry_time=datetime.utcnow() - timedelta(days=2),
            exit_time=datetime.utcnow() - timedelta(days=1),
            realized_pnl=Decimal("150"),
            realized_pnl_pct=Decimal("3"),
            strategy_name="Strategy1"
        )
        
        trade2 = Trade(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            amount=Decimal("1"),
            entry_price=Decimal("3000"),
            exit_price=Decimal("3150"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("150"),
            realized_pnl_pct=Decimal("5"),
            strategy_name="Strategy2"
        )
        
        await test_database.save_trade(trade1)
        await test_database.save_trade(trade2)
        
        trades = await test_database.get_trades()
        
        assert len(trades) == 2
        # Should be ordered by exit_time desc, so ETH first
        assert trades[0].symbol == "ETHUSDT"
    
    @pytest.mark.asyncio
    async def test_get_trades_by_symbol(self, test_database):
        """Test retrieving trades filtered by symbol."""
        trade1 = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.1"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("51500"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("150"),
            realized_pnl_pct=Decimal("3")
        )
        
        trade2 = Trade(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            amount=Decimal("1"),
            entry_price=Decimal("3000"),
            exit_price=Decimal("3150"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("150"),
            realized_pnl_pct=Decimal("5")
        )
        
        await test_database.save_trade(trade1)
        await test_database.save_trade(trade2)
        
        btc_trades = await test_database.get_trades(symbol="BTCUSDT")
        
        assert len(btc_trades) == 1
        assert btc_trades[0].symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_get_trades_with_limit(self, test_database):
        """Test retrieving trades with limit."""
        for i in range(10):
            trade = Trade(
                symbol=f"COIN{i}",
                side=OrderSide.BUY,
                amount=Decimal("1"),
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                entry_time=datetime.utcnow() - timedelta(days=1),
                exit_time=datetime.utcnow() - timedelta(hours=i),
                realized_pnl=Decimal("10"),
                realized_pnl_pct=Decimal("10")
            )
            await test_database.save_trade(trade)
        
        trades = await test_database.get_trades(limit=5)
        
        assert len(trades) == 5


# =============================================================================
# Portfolio Snapshot Tests
# =============================================================================

class TestPortfolioSnapshotOperations:
    """Test portfolio snapshot operations."""
    
    @pytest.mark.asyncio
    async def test_save_portfolio_snapshot(self, test_database):
        """Test saving a portfolio snapshot."""
        snapshot_id = await test_database.save_portfolio_snapshot(
            total_equity=Decimal("100000"),
            available_balance=Decimal("80000"),
            engine_allocations={
                "CORE_HODL": 60000,
                "TREND": 20000,
                "FUNDING": 15000,
                "TACTICAL": 5000
            },
            positions_value=Decimal("20000"),
            drawdown_from_ath=Decimal("2.5")
        )
        
        assert isinstance(snapshot_id, int)
        assert snapshot_id > 0
    
    @pytest.mark.asyncio
    async def test_get_latest_portfolio_snapshot(self, test_database):
        """Test retrieving the latest portfolio snapshot."""
        # Save first snapshot
        await test_database.save_portfolio_snapshot(
            total_equity=Decimal("100000"),
            available_balance=Decimal("80000"),
            engine_allocations={},
            positions_value=Decimal("20000"),
            drawdown_from_ath=Decimal("0")
        )
        
        # Save second snapshot (more recent)
        await test_database.save_portfolio_snapshot(
            total_equity=Decimal("105000"),
            available_balance=Decimal("85000"),
            engine_allocations={},
            positions_value=Decimal("20000"),
            drawdown_from_ath=Decimal("0")
        )
        
        latest = await test_database.get_latest_portfolio_snapshot()
        
        assert latest is not None
        assert latest['total_equity'] == Decimal("105000")
        assert latest['available_balance'] == Decimal("85000")
    
    @pytest.mark.asyncio
    async def test_get_latest_portfolio_snapshot_empty(self, test_database):
        """Test retrieving latest snapshot when none exist."""
        latest = await test_database.get_latest_portfolio_snapshot()
        
        assert latest is None


# =============================================================================
# Engine State Tests
# =============================================================================

class TestEngineStateOperations:
    """Test engine state operations."""
    
    @pytest.mark.asyncio
    async def test_save_engine_state(self, test_database):
        """Test saving engine state."""
        await test_database.save_engine_state(
            engine_name="CORE_HODL",
            state="active",
            allocation_pct=Decimal("60"),
            performance_metrics={
                "total_trades": 100,
                "win_rate": 0.65,
                "profit_factor": 2.5
            }
        )
        
        # Verify by retrieving
        state = await test_database.get_engine_state("CORE_HODL")
        assert state is not None
        assert state['state'] == "active"
        assert state['allocation_pct'] == Decimal("60")
    
    @pytest.mark.asyncio
    async def test_update_engine_state(self, test_database):
        """Test updating engine state."""
        await test_database.save_engine_state(
            engine_name="TREND",
            state="active",
            allocation_pct=Decimal("20"),
            performance_metrics={}
        )
        
        # Update state
        await test_database.save_engine_state(
            engine_name="TREND",
            state="paused",
            allocation_pct=Decimal("20"),
            performance_metrics={"pause_reason": "circuit_breaker"}
        )
        
        state = await test_database.get_engine_state("TREND")
        assert state['state'] == "paused"
    
    @pytest.mark.asyncio
    async def test_get_engine_state_not_found(self, test_database):
        """Test retrieving non-existent engine state."""
        state = await test_database.get_engine_state("NONEXISTENT")
        
        assert state is None
    
    @pytest.mark.asyncio
    async def test_get_all_engine_states(self, test_database):
        """Test retrieving all engine states."""
        await test_database.save_engine_state("CORE_HODL", "active", Decimal("60"), {})
        await test_database.save_engine_state("TREND", "active", Decimal("20"), {})
        await test_database.save_engine_state("FUNDING", "active", Decimal("15"), {})
        
        states = await test_database.get_all_engine_states()
        
        assert len(states) == 3


# =============================================================================
# Circuit Breaker Event Tests
# =============================================================================

class TestCircuitBreakerOperations:
    """Test circuit breaker event operations."""
    
    @pytest.mark.asyncio
    async def test_record_circuit_breaker(self, test_database):
        """Test recording a circuit breaker event."""
        event_id = await test_database.record_circuit_breaker(
            level=2,
            reason="Daily loss limit reached",
            portfolio_value=Decimal("95000"),
            drawdown_pct=Decimal("5")
        )
        
        assert isinstance(event_id, int)
        assert event_id > 0
    
    @pytest.mark.asyncio
    async def test_resolve_circuit_breaker(self, test_database):
        """Test resolving a circuit breaker event."""
        event_id = await test_database.record_circuit_breaker(
            level=1,
            reason="Test trigger",
            portfolio_value=Decimal("100000"),
            drawdown_pct=Decimal("2")
        )
        
        await test_database.resolve_circuit_breaker(event_id)
        
        # Verify it's resolved
        active_events = await test_database.get_active_circuit_breakers()
        assert len(active_events) == 0
    
    @pytest.mark.asyncio
    async def test_get_active_circuit_breakers(self, test_database):
        """Test retrieving active circuit breaker events."""
        # Create active event
        await test_database.record_circuit_breaker(
            level=1,
            reason="Active trigger",
            portfolio_value=Decimal("100000"),
            drawdown_pct=Decimal("2")
        )
        
        # Create and resolve another event
        resolved_id = await test_database.record_circuit_breaker(
            level=1,
            reason="Resolved trigger",
            portfolio_value=Decimal("100000"),
            drawdown_pct=Decimal("2")
        )
        await test_database.resolve_circuit_breaker(resolved_id)
        
        active = await test_database.get_active_circuit_breakers()
        
        assert len(active) == 1
        assert active[0]['trigger_reason'] == "Active trigger"


# =============================================================================
# Daily Stats Tests
# =============================================================================

class TestDailyStatsOperations:
    """Test daily statistics operations."""
    
    @pytest.mark.asyncio
    async def test_save_daily_stats(self, test_database):
        """Test saving daily statistics."""
        await test_database.save_daily_stats(
            date="2024-01-01",
            engine_name="CORE_HODL",
            starting_balance=Decimal("100000"),
            ending_balance=Decimal("101000"),
            total_pnl=Decimal("1000"),
            trade_count=5,
            win_count=4,
            loss_count=1
        )
        
        # Verify by retrieving
        stats = await test_database.get_daily_stats(
            engine="CORE_HODL",
            date="2024-01-01"
        )
        
        assert len(stats) == 1
        assert stats[0]['total_pnl'] == Decimal("1000")
    
    @pytest.mark.asyncio
    async def test_update_daily_stats(self, test_database):
        """Test updating daily statistics."""
        await test_database.save_daily_stats(
            date="2024-01-01",
            engine_name="TREND",
            starting_balance=Decimal("20000"),
            ending_balance=None,
            total_pnl=Decimal("0"),
            trade_count=0
        )
        
        # Update with end-of-day values
        await test_database.save_daily_stats(
            date="2024-01-01",
            engine_name="TREND",
            starting_balance=Decimal("20000"),
            ending_balance=Decimal("20500"),
            total_pnl=Decimal("500"),
            trade_count=3,
            win_count=2,
            loss_count=1
        )
        
        stats = await test_database.get_daily_stats(
            engine="TREND",
            date="2024-01-01"
        )
        
        assert stats[0]['ending_balance'] == Decimal("20500")
        assert stats[0]['total_pnl'] == Decimal("500")
        assert stats[0]['trade_count'] == 3
    
    @pytest.mark.asyncio
    async def test_get_daily_stats_with_limit(self, test_database):
        """Test retrieving daily stats with limit."""
        for i in range(10):
            date = f"2024-01-{i+1:02d}"
            await test_database.save_daily_stats(
                date=date,
                engine_name="CORE_HODL",
                starting_balance=Decimal("100000"),
                ending_balance=Decimal("101000"),
                total_pnl=Decimal("1000"),
                trade_count=5
            )
        
        stats = await test_database.get_daily_stats(
            engine="CORE_HODL",
            limit=5
        )
        
        assert len(stats) == 5


# =============================================================================
# Model Conversion Tests
# =============================================================================

class TestModelConversion:
    """Test conversion between domain models and database models."""
    
    @pytest.mark.asyncio
    async def test_order_round_trip(self, test_database, sample_order):
        """Test that orders are correctly saved and retrieved."""
        await test_database.save_order(sample_order)
        retrieved = await test_database.get_order(sample_order.id)
        
        assert retrieved.id == sample_order.id
        assert retrieved.symbol == sample_order.symbol
        assert retrieved.side == sample_order.side
        assert retrieved.order_type == sample_order.order_type
        assert retrieved.amount == sample_order.amount
        assert retrieved.status == sample_order.status
        assert retrieved.stop_loss_price == sample_order.stop_loss_price
        assert retrieved.take_profit_price == sample_order.take_profit_price
    
    @pytest.mark.asyncio
    async def test_position_round_trip(self, test_database, sample_position):
        """Test that positions are correctly saved and retrieved."""
        await test_database.save_position(sample_position)
        retrieved = await test_database.get_position(sample_position.symbol)
        
        assert retrieved.id == sample_position.id
        assert retrieved.symbol == sample_position.symbol
        assert retrieved.side == sample_position.side
        assert retrieved.entry_price == sample_position.entry_price
        assert retrieved.amount == sample_position.amount
        assert retrieved.unrealized_pnl == sample_position.unrealized_pnl
        assert retrieved.realized_pnl == sample_position.realized_pnl
    
    @pytest.mark.asyncio
    async def test_trade_round_trip(self, test_database, sample_trade):
        """Test that trades are correctly saved and retrieved."""
        await test_database.save_trade(sample_trade)
        retrieved = await test_database.get_trades(limit=1)
        
        assert len(retrieved) == 1
        assert retrieved[0].id == sample_trade.id
        assert retrieved[0].symbol == sample_trade.symbol
        assert retrieved[0].entry_price == sample_trade.entry_price
        assert retrieved[0].exit_price == sample_trade.exit_price
        assert retrieved[0].realized_pnl == sample_trade.realized_pnl
