"""Database storage for trading data using SQLAlchemy 2.0 with async support."""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    String, DateTime, Numeric, Integer, JSON, select, and_
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncEngine

from src.core.models import Order, Position, Trade, OrderSide, OrderType, OrderStatus, PositionSide
from src.core.config import database_config


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base."""
    pass


class OrderModel(Base):
    """SQLAlchemy model for orders - history and active orders."""
    __tablename__ = 'orders'
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    engine_name: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    side: Mapped[str] = mapped_column(String, nullable=False)
    order_type: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(36, 18), nullable=True)
    filled_amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    average_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(36, 18), nullable=True)
    stop_loss_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(36, 18), nullable=True)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(36, 18), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class PositionModel(Base):
    """SQLAlchemy model for open positions."""
    __tablename__ = 'positions'
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    engine_name: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    side: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    stop_loss_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(36, 18), nullable=True)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(36, 18), nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class TradeModel(Base):
    """SQLAlchemy model for completed trades."""
    __tablename__ = 'trades'
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    engine_name: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    side: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    realized_pnl_pct: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    entry_fee: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    exit_fee: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    total_fee: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    close_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class PortfolioSnapshotModel(Base):
    """SQLAlchemy model for portfolio value over time."""
    __tablename__ = 'portfolio_snapshots'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    total_equity: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    available_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    engine_allocations: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    positions_value: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    drawdown_from_ath: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class EngineStateModel(Base):
    """SQLAlchemy model for state tracking for each engine."""
    __tablename__ = 'engine_states'
    
    engine_name: Mapped[str] = mapped_column(String, primary_key=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    allocation_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    performance_metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CircuitBreakerEventModel(Base):
    """SQLAlchemy model for circuit breaker triggers."""
    __tablename__ = 'circuit_breaker_events'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    trigger_reason: Mapped[str] = mapped_column(String, nullable=False)
    portfolio_value: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class DailyStatsModel(Base):
    """SQLAlchemy model for daily performance stats per engine."""
    __tablename__ = 'daily_stats'
    
    date: Mapped[str] = mapped_column(String, primary_key=True)
    engine_name: Mapped[str] = mapped_column(String, primary_key=True)
    starting_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    ending_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(36, 18), nullable=True)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    win_count: Mapped[int] = mapped_column(Integer, default=0)
    loss_count: Mapped[int] = mapped_column(Integer, default=0)


class Database:
    """Async database interface for The Eternal Engine."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection.
        
        Args:
            database_url: Database URL. If None, uses config value.
        """
        db_url = database_url or database_config.database_url
        
        # Convert SQLite URL to async version if needed
        if db_url.startswith('sqlite:///') and not db_url.startswith('sqlite+aiosqlite:///'):
            db_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
        
        self.engine: AsyncEngine = create_async_engine(db_url, echo=False)
        self.session_maker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
    
    async def initialize(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self):
        """Close database connection and cleanup resources."""
        await self.engine.dispose()
    
    # Order operations
    async def save_order(self, order: Order, engine_name: Optional[str] = None) -> Order:
        """
        Save or update an order.
        
        Args:
            order: Order object to save
            engine_name: Optional engine name for tracking
            
        Returns:
            The saved Order object
        """
        async with self.session_maker() as session:
            db_order = await session.get(OrderModel, order.id)
            
            if db_order is None:
                db_order = OrderModel(
                    id=order.id,
                    exchange_order_id=order.exchange_order_id,
                    engine_name=engine_name or order.metadata.get('engine_name'),
                    symbol=order.symbol,
                    side=order.side.value,
                    order_type=order.order_type.value,
                    amount=order.amount,
                    price=order.price,
                    status=order.status.value,
                    filled_amount=order.filled_amount,
                    average_price=order.average_price,
                    stop_loss_price=order.stop_loss_price,
                    take_profit_price=order.take_profit_price,
                    created_at=order.created_at,
                    updated_at=order.updated_at,
                    filled_at=order.filled_at,
                    metadata_json=order.metadata
                )
                session.add(db_order)
            else:
                db_order.status = order.status.value
                db_order.filled_amount = order.filled_amount
                db_order.average_price = order.average_price
                db_order.updated_at = order.updated_at or datetime.now(timezone.utc)
                db_order.filled_at = order.filled_at
                if engine_name:
                    db_order.engine_name = engine_name
            
            await session.commit()
            return order
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get an order by ID.
        
        Args:
            order_id: The order ID to look up
            
        Returns:
            Order object or None if not found
        """
        async with self.session_maker() as session:
            db_order = await session.get(OrderModel, order_id)
            
            if db_order is None:
                return None
            
            return self._order_from_model(db_order)
    
    async def get_open_orders(self, engine: Optional[str] = None) -> List[Order]:
        """
        Get all open (active) orders.
        
        Args:
            engine: Optional engine name filter
            
        Returns:
            List of active Order objects
        """
        async with self.session_maker() as session:
            active_statuses = ['pending', 'open', 'partially_filled']
            query = select(OrderModel).where(OrderModel.status.in_(active_statuses))
            
            if engine:
                query = query.where(OrderModel.engine_name == engine)
            
            query = query.order_by(OrderModel.created_at.desc())
            result = await session.execute(query)
            db_orders = result.scalars().all()
            
            return [self._order_from_model(o) for o in db_orders]
    
    async def get_orders(
        self, 
        symbol: Optional[str] = None, 
        status: Optional[str] = None,
        engine: Optional[str] = None,
        limit: int = 100
    ) -> List[Order]:
        """
        Get orders with optional filters.
        
        Args:
            symbol: Filter by symbol
            status: Filter by status
            engine: Filter by engine name
            limit: Maximum number of results
            
        Returns:
            List of Order objects
        """
        async with self.session_maker() as session:
            query = select(OrderModel).order_by(OrderModel.created_at.desc()).limit(limit)
            
            if symbol:
                query = query.where(OrderModel.symbol == symbol)
            if status:
                query = query.where(OrderModel.status == status)
            if engine:
                query = query.where(OrderModel.engine_name == engine)
            
            result = await session.execute(query)
            db_orders = result.scalars().all()
            
            return [self._order_from_model(o) for o in db_orders]
    
    # Position operations
    async def save_position(self, position: Position, engine_name: Optional[str] = None) -> Position:
        """
        Save or update a position.
        
        Args:
            position: Position object to save
            engine_name: Optional engine name for tracking
            
        Returns:
            The saved Position object
        """
        async with self.session_maker() as session:
            db_position = await session.get(PositionModel, position.id)
            
            if db_position is None:
                db_position = PositionModel(
                    id=position.id,
                    engine_name=engine_name or position.metadata.get('engine_name'),
                    symbol=position.symbol,
                    side=position.side.value,
                    entry_price=position.entry_price,
                    amount=position.amount,
                    opened_at=position.opened_at,
                    unrealized_pnl=position.unrealized_pnl,
                    realized_pnl=position.realized_pnl,
                    stop_loss_price=position.stop_loss_price,
                    take_profit_price=position.take_profit_price,
                    metadata_json=position.metadata
                )
                session.add(db_position)
            else:
                db_position.amount = position.amount
                db_position.entry_price = position.entry_price
                db_position.unrealized_pnl = position.unrealized_pnl
                db_position.realized_pnl = position.realized_pnl
                if engine_name:
                    db_position.engine_name = engine_name
            
            await session.commit()
            return position
    
    async def get_position(self, symbol: str, engine: Optional[str] = None) -> Optional[Position]:
        """
        Get position for a symbol.
        
        Args:
            symbol: Trading pair symbol
            engine: Optional engine name filter
            
        Returns:
            Position object or None if not found
        """
        async with self.session_maker() as session:
            query = select(PositionModel).where(PositionModel.symbol == symbol)
            
            if engine:
                query = query.where(PositionModel.engine_name == engine)
            
            result = await session.execute(query)
            db_position = result.scalar_one_or_none()
            
            if db_position is None:
                return None
            
            return self._position_from_model(db_position)
    
    async def get_open_positions(self, engine: Optional[str] = None) -> List[Position]:
        """
        Get all open positions.
        
        Args:
            engine: Optional engine name filter
            
        Returns:
            List of open Position objects
        """
        async with self.session_maker() as session:
            query = select(PositionModel)
            
            if engine:
                query = query.where(PositionModel.engine_name == engine)
            
            result = await session.execute(query)
            db_positions = result.scalars().all()
            
            return [self._position_from_model(p) for p in db_positions]
    
    async def delete_position(self, symbol: str, engine: Optional[str] = None):
        """
        Delete a position.
        
        Args:
            symbol: Trading pair symbol
            engine: Optional engine name filter
        """
        async with self.session_maker() as session:
            query = select(PositionModel).where(PositionModel.symbol == symbol)
            
            if engine:
                query = query.where(PositionModel.engine_name == engine)
            
            result = await session.execute(query)
            db_position = result.scalar_one_or_none()
            
            if db_position:
                await session.delete(db_position)
                await session.commit()
    
    # Trade operations
    async def save_trade(self, trade: Trade, engine_name: Optional[str] = None) -> Trade:
        """
        Save a completed trade.
        
        Args:
            trade: Trade object to save
            engine_name: Optional engine name for tracking
            
        Returns:
            The saved Trade object
        """
        async with self.session_maker() as session:
            db_trade = TradeModel(
                id=trade.id,
                engine_name=engine_name or trade.strategy_name or trade.close_reason,
                symbol=trade.symbol,
                side=trade.side.value,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                amount=trade.amount,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time or datetime.now(timezone.utc),
                realized_pnl=trade.realized_pnl,
                realized_pnl_pct=trade.realized_pnl_pct,
                entry_fee=trade.entry_fee,
                exit_fee=trade.exit_fee,
                total_fee=trade.total_fee,
                close_reason=trade.close_reason,
                metadata_json=getattr(trade, 'metadata', {})
            )
            session.add(db_trade)
            await session.commit()
            return trade
    
    async def get_trades(
        self, 
        engine: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        """
        Get completed trades.
        
        Args:
            engine: Filter by engine name
            symbol: Filter by symbol
            limit: Maximum number of results
            
        Returns:
            List of Trade objects
        """
        async with self.session_maker() as session:
            query = select(TradeModel).order_by(TradeModel.exit_time.desc()).limit(limit)
            
            if engine:
                query = query.where(TradeModel.engine_name == engine)
            if symbol:
                query = query.where(TradeModel.symbol == symbol)
            
            result = await session.execute(query)
            db_trades = result.scalars().all()
            
            return [self._trade_from_model(t) for t in db_trades]
    
    # Portfolio snapshot operations
    async def save_portfolio_snapshot(
        self,
        total_equity: Decimal,
        available_balance: Decimal,
        engine_allocations: Dict[str, Any],
        positions_value: Decimal = Decimal("0"),
        drawdown_from_ath: Decimal = Decimal("0"),
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Save a portfolio snapshot.
        
        Args:
            total_equity: Total portfolio equity
            available_balance: Available cash balance
            engine_allocations: JSON dict of engine allocations
            positions_value: Total value of open positions
            drawdown_from_ath: Current drawdown from all-time high
            metadata: Additional metadata
            
        Returns:
            Snapshot ID
        """
        async with self.session_maker() as session:
            snapshot = PortfolioSnapshotModel(
                total_equity=total_equity,
                available_balance=available_balance,
                engine_allocations=engine_allocations,
                positions_value=positions_value,
                drawdown_from_ath=drawdown_from_ath,
                metadata=metadata or {}
            )
            session.add(snapshot)
            await session.commit()
            return snapshot.id
    
    async def get_latest_portfolio_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent portfolio snapshot.
        
        Returns:
            Snapshot data as dict or None
        """
        async with self.session_maker() as session:
            query = select(PortfolioSnapshotModel).order_by(PortfolioSnapshotModel.timestamp.desc()).limit(1)
            result = await session.execute(query)
            snapshot = result.scalar_one_or_none()
            
            if snapshot is None:
                return None
            
            return {
                'id': snapshot.id,
                'timestamp': snapshot.timestamp,
                'total_equity': snapshot.total_equity,
                'available_balance': snapshot.available_balance,
                'engine_allocations': snapshot.engine_allocations,
                'positions_value': snapshot.positions_value,
                'drawdown_from_ath': snapshot.drawdown_from_ath,
                'metadata': snapshot.metadata
            }
    
    # Engine state operations
    async def save_engine_state(
        self,
        engine_name: str,
        state: str,
        allocation_pct: Decimal,
        performance_metrics: Optional[Dict[str, Any]] = None
    ):
        """
        Save or update engine state.
        
        Args:
            engine_name: Engine identifier (e.g., 'CORE-HODL', 'TREND')
            state: Engine state (e.g., 'active', 'paused', 'stopped')
            allocation_pct: Capital allocation percentage
            performance_metrics: JSON dict of performance metrics
        """
        async with self.session_maker() as session:
            db_state = await session.get(EngineStateModel, engine_name)
            
            if db_state is None:
                db_state = EngineStateModel(
                    engine_name=engine_name,
                    state=state,
                    allocation_pct=allocation_pct,
                    performance_metrics=performance_metrics or {}
                )
                session.add(db_state)
            else:
                db_state.state = state
                db_state.allocation_pct = allocation_pct
                db_state.performance_metrics = performance_metrics or db_state.performance_metrics
                db_state.last_updated = datetime.now(timezone.utc)
            
            await session.commit()
    
    async def get_engine_state(self, engine_name: str) -> Optional[Dict[str, Any]]:
        """
        Get state for a specific engine.
        
        Args:
            engine_name: Engine identifier
            
        Returns:
            Engine state as dict or None
        """
        async with self.session_maker() as session:
            db_state = await session.get(EngineStateModel, engine_name)
            
            if db_state is None:
                return None
            
            return {
                'engine_name': db_state.engine_name,
                'state': db_state.state,
                'allocation_pct': db_state.allocation_pct,
                'performance_metrics': db_state.performance_metrics,
                'last_updated': db_state.last_updated
            }
    
    async def get_all_engine_states(self) -> List[Dict[str, Any]]:
        """
        Get states for all engines.
        
        Returns:
            List of engine state dicts
        """
        async with self.session_maker() as session:
            query = select(EngineStateModel)
            result = await session.execute(query)
            db_states = result.scalars().all()
            
            return [
                {
                    'engine_name': s.engine_name,
                    'state': s.state,
                    'allocation_pct': s.allocation_pct,
                    'performance_metrics': s.performance_metrics,
                    'last_updated': s.last_updated
                }
                for s in db_states
            ]
    
    # Circuit breaker operations
    async def record_circuit_breaker(
        self,
        level: int,
        reason: str,
        portfolio_value: Decimal,
        drawdown_pct: Decimal
    ) -> int:
        """
        Record a circuit breaker event.
        
        Args:
            level: Circuit breaker level (1-4)
            reason: Trigger reason description
            portfolio_value: Portfolio value at trigger time
            drawdown_pct: Drawdown percentage
            
        Returns:
            Event ID
        """
        async with self.session_maker() as session:
            event = CircuitBreakerEventModel(
                level=level,
                trigger_reason=reason,
                portfolio_value=portfolio_value,
                drawdown_pct=drawdown_pct
            )
            session.add(event)
            await session.commit()
            return event.id
    
    async def resolve_circuit_breaker(self, event_id: int):
        """
        Mark a circuit breaker event as resolved.
        
        Args:
            event_id: The circuit breaker event ID
        """
        async with self.session_maker() as session:
            event = await session.get(CircuitBreakerEventModel, event_id)
            if event:
                event.resolved_at = datetime.now(timezone.utc)
                await session.commit()
    
    async def get_active_circuit_breakers(self) -> List[Dict[str, Any]]:
        """
        Get all unresolved circuit breaker events.
        
        Returns:
            List of active circuit breaker events
        """
        async with self.session_maker() as session:
            query = select(CircuitBreakerEventModel).where(CircuitBreakerEventModel.resolved_at.is_(None))
            result = await session.execute(query)
            events = result.scalars().all()
            
            return [
                {
                    'id': e.id,
                    'level': e.level,
                    'timestamp': e.timestamp,
                    'trigger_reason': e.trigger_reason,
                    'portfolio_value': e.portfolio_value,
                    'drawdown_pct': e.drawdown_pct
                }
                for e in events
            ]
    
    # Daily stats operations
    async def save_daily_stats(
        self,
        date: str,
        engine_name: str,
        starting_balance: Decimal,
        ending_balance: Optional[Decimal] = None,
        total_pnl: Decimal = Decimal("0"),
        trade_count: int = 0,
        win_count: int = 0,
        loss_count: int = 0
    ):
        """
        Save or update daily statistics.
        
        Args:
            date: Date string (YYYY-MM-DD)
            engine_name: Engine identifier
            starting_balance: Starting balance for the day
            ending_balance: Ending balance for the day
            total_pnl: Total PnL for the day
            trade_count: Number of trades
            win_count: Number of winning trades
            loss_count: Number of losing trades
        """
        async with self.session_maker() as session:
            # Use composite key lookup
            query = select(DailyStatsModel).where(
                and_(DailyStatsModel.date == date, DailyStatsModel.engine_name == engine_name)
            )
            result = await session.execute(query)
            db_stats = result.scalar_one_or_none()
            
            if db_stats is None:
                db_stats = DailyStatsModel(
                    date=date,
                    engine_name=engine_name,
                    starting_balance=starting_balance,
                    ending_balance=ending_balance,
                    total_pnl=total_pnl,
                    trade_count=trade_count,
                    win_count=win_count,
                    loss_count=loss_count
                )
                session.add(db_stats)
            else:
                if ending_balance is not None:
                    db_stats.ending_balance = ending_balance
                db_stats.total_pnl = total_pnl
                db_stats.trade_count = trade_count
                db_stats.win_count = win_count
                db_stats.loss_count = loss_count
            
            await session.commit()
    
    async def get_daily_stats(
        self,
        engine: Optional[str] = None,
        date: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily statistics.
        
        Args:
            engine: Filter by engine name
            date: Filter by specific date
            limit: Maximum number of results
            
        Returns:
            List of daily stats dicts
        """
        async with self.session_maker() as session:
            query = select(DailyStatsModel).order_by(DailyStatsModel.date.desc()).limit(limit)
            
            if engine:
                query = query.where(DailyStatsModel.engine_name == engine)
            if date:
                query = query.where(DailyStatsModel.date == date)
            
            result = await session.execute(query)
            db_stats = result.scalars().all()
            
            return [
                {
                    'date': s.date,
                    'engine_name': s.engine_name,
                    'starting_balance': s.starting_balance,
                    'ending_balance': s.ending_balance,
                    'total_pnl': s.total_pnl,
                    'trade_count': s.trade_count,
                    'win_count': s.win_count,
                    'loss_count': s.loss_count
                }
                for s in db_stats
            ]
    
    # Helpers
    def _order_from_model(self, model: OrderModel) -> Order:
        """Convert DB model to Order object."""
        return Order(
            id=model.id,
            symbol=model.symbol,
            side=OrderSide(model.side),
            order_type=OrderType(model.order_type),
            amount=model.amount,
            price=model.price,
            exchange_order_id=model.exchange_order_id,
            status=OrderStatus(model.status),
            filled_amount=model.filled_amount,
            average_price=model.average_price,
            stop_loss_price=model.stop_loss_price,
            take_profit_price=model.take_profit_price,
            created_at=model.created_at,
            updated_at=model.updated_at,
            filled_at=model.filled_at,
            metadata={**(model.metadata_json or {}), 'engine_name': model.engine_name}
        )
    
    def _position_from_model(self, model: PositionModel) -> Position:
        """Convert DB model to Position object."""
        return Position(
            id=model.id,
            symbol=model.symbol,
            side=PositionSide(model.side),
            entry_price=model.entry_price,
            amount=model.amount,
            opened_at=model.opened_at,
            unrealized_pnl=model.unrealized_pnl,
            realized_pnl=model.realized_pnl,
            stop_loss_price=model.stop_loss_price,
            take_profit_price=model.take_profit_price,
            metadata={**(model.metadata_json or {}), 'engine_name': model.engine_name}
        )
    
    def _trade_from_model(self, model: TradeModel) -> Trade:
        """Convert DB model to Trade object."""
        return Trade(
            id=model.id,
            symbol=model.symbol,
            side=OrderSide(model.side),
            amount=model.amount,
            entry_price=model.entry_price,
            exit_price=model.exit_price,
            entry_time=model.entry_time,
            exit_time=model.exit_time,
            realized_pnl=model.realized_pnl,
            realized_pnl_pct=model.realized_pnl_pct,
            entry_fee=model.entry_fee,
            exit_fee=model.exit_fee,
            total_fee=model.total_fee,
            strategy_name=model.engine_name or "",
            close_reason=model.close_reason or ""
        )
