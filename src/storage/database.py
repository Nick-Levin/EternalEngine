"""Database storage for trading data."""
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    create_engine, Column, String, DateTime, 
    Numeric, Integer, JSON, ForeignKey, select
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import AsyncEngine

from src.core.models import Order, Position, Trade, OrderSide, OrderType, OrderStatus, PositionSide
from src.core.config import database_config

Base = declarative_base()


class OrderModel(Base):
    """SQLAlchemy model for orders."""
    __tablename__ = 'orders'
    
    id = Column(String, primary_key=True)
    exchange_order_id = Column(String, nullable=True)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    order_type = Column(String, nullable=False)
    amount = Column(Numeric(36, 18), nullable=False)
    price = Column(Numeric(36, 18), nullable=True)
    status = Column(String, nullable=False)
    filled_amount = Column(Numeric(36, 18), default=0)
    average_price = Column(Numeric(36, 18), nullable=True)
    stop_loss_price = Column(Numeric(36, 18), nullable=True)
    take_profit_price = Column(Numeric(36, 18), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, default=dict)


class PositionModel(Base):
    """SQLAlchemy model for positions."""
    __tablename__ = 'positions'
    
    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False, unique=True)
    side = Column(String, nullable=False)
    entry_price = Column(Numeric(36, 18), nullable=False)
    amount = Column(Numeric(36, 18), nullable=False)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    unrealized_pnl = Column(Numeric(36, 18), default=0)
    realized_pnl = Column(Numeric(36, 18), default=0)
    stop_loss_price = Column(Numeric(36, 18), nullable=True)
    take_profit_price = Column(Numeric(36, 18), nullable=True)
    metadata_json = Column(JSON, default=dict)


class TradeModel(Base):
    """SQLAlchemy model for completed trades."""
    __tablename__ = 'trades'
    
    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    amount = Column(Numeric(36, 18), nullable=False)
    entry_price = Column(Numeric(36, 18), nullable=False)
    exit_price = Column(Numeric(36, 18), nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    realized_pnl = Column(Numeric(36, 18), nullable=False)
    realized_pnl_pct = Column(Numeric(36, 18), nullable=False)
    entry_fee = Column(Numeric(36, 18), default=0)
    exit_fee = Column(Numeric(36, 18), default=0)
    total_fee = Column(Numeric(36, 18), default=0)
    strategy_name = Column(String, nullable=True)
    close_reason = Column(String, nullable=True)


class DailyStatsModel(Base):
    """SQLAlchemy model for daily statistics."""
    __tablename__ = 'daily_stats'
    
    date = Column(String, primary_key=True)  # YYYY-MM-DD
    starting_balance = Column(Numeric(36, 18), nullable=False)
    ending_balance = Column(Numeric(36, 18), nullable=True)
    total_pnl = Column(Numeric(36, 18), default=0)
    trade_count = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)


class Database:
    """Async database interface."""
    
    def __init__(self):
        # Convert SQLite URL to async version if needed
        db_url = database_config.database_url
        if db_url.startswith('sqlite:///') and not db_url.startswith('sqlite+aiosqlite:///'):
            db_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
        
        self.engine: AsyncEngine = create_async_engine(db_url, echo=False)
        self.session_maker = async_sessionmaker(self.engine, class_=AsyncSession)
    
    async def initialize(self):
        """Create tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self):
        """Close database connection."""
        await self.engine.dispose()
    
    # Order operations
    async def save_order(self, order: Order):
        """Save or update an order."""
        async with self.session_maker() as session:
            db_order = await session.get(OrderModel, order.id)
            
            if db_order is None:
                db_order = OrderModel(
                    id=order.id,
                    exchange_order_id=order.exchange_order_id,
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
                db_order.updated_at = order.updated_at
                db_order.filled_at = order.filled_at
            
            await session.commit()
    
    async def update_order(self, order: Order):
        """Update an existing order."""
        await self.save_order(order)
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        async with self.session_maker() as session:
            db_order = await session.get(OrderModel, order_id)
            
            if db_order is None:
                return None
            
            return self._order_from_model(db_order)
    
    async def get_orders(
        self, 
        symbol: Optional[str] = None, 
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get orders with optional filters."""
        async with self.session_maker() as session:
            query = select(OrderModel).order_by(OrderModel.created_at.desc()).limit(limit)
            
            if symbol:
                query = query.where(OrderModel.symbol == symbol)
            if status:
                query = query.where(OrderModel.status == status)
            
            result = await session.execute(query)
            db_orders = result.scalars().all()
            
            return [self._order_from_model(o) for o in db_orders]
    
    # Position operations
    async def save_position(self, position: Position):
        """Save or update a position."""
        async with self.session_maker() as session:
            db_position = await session.get(PositionModel, position.id)
            
            if db_position is None:
                db_position = PositionModel(
                    id=position.id,
                    symbol=position.symbol,
                    side=position.side.value,
                    entry_price=position.entry_price,
                    amount=position.amount,
                    opened_at=position.opened_at,
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
            
            await session.commit()
    
    async def delete_position(self, symbol: str):
        """Delete a position."""
        async with self.session_maker() as session:
            result = await session.execute(
                select(PositionModel).where(PositionModel.symbol == symbol)
            )
            db_position = result.scalar_one_or_none()
            
            if db_position:
                await session.delete(db_position)
                await session.commit()
    
    async def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        async with self.session_maker() as session:
            result = await session.execute(
                select(PositionModel).where(PositionModel.closed_at.is_(None))
            )
            db_positions = result.scalars().all()
            
            return [self._position_from_model(p) for p in db_positions]
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        async with self.session_maker() as session:
            result = await session.execute(
                select(PositionModel).where(PositionModel.symbol == symbol)
            )
            db_position = result.scalar_one_or_none()
            
            if db_position is None:
                return None
            
            return self._position_from_model(db_position)
    
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
            metadata=model.metadata_json or {}
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
            closed_at=model.closed_at,
            unrealized_pnl=model.unrealized_pnl,
            realized_pnl=model.realized_pnl,
            stop_loss_price=model.stop_loss_price,
            take_profit_price=model.take_profit_price,
            metadata=model.metadata_json or {}
        )
