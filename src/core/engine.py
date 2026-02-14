"""Main trading engine - orchestrates all components."""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import structlog

from src.core.models import (
    Order, Position, Portfolio, TradingSignal, 
    SignalType, OrderSide, OrderType, OrderStatus
)
from src.core.config import trading_config
from src.exchange.bybit_client import ByBitClient
from src.risk.risk_manager import RiskManager
from src.strategies.base import BaseStrategy
from src.storage.database import Database

logger = structlog.get_logger(__name__)


class TradingEngine:
    """
    Main trading engine that orchestrates all components.
    
    Responsibilities:
    - Manages strategy lifecycle
    - Processes signals through risk manager
    - Executes orders via exchange client
    - Tracks positions and portfolio
    - Handles errors and recovery
    """
    
    def __init__(
        self,
        exchange: ByBitClient,
        risk_manager: RiskManager,
        database: Database,
        strategies: List[BaseStrategy]
    ):
        self.exchange = exchange
        self.risk_manager = risk_manager
        self.database = database
        self.strategies = {s.name: s for s in strategies}
        
        # State
        self.portfolio: Optional[Portfolio] = None
        self.positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, Order] = {}
        self.market_data: Dict[str, List] = {}
        
        # Control
        self._running = False
        self._main_task: Optional[asyncio.Task] = None
        
        # Intervals
        self.analysis_interval = 60  # seconds
        self.balance_update_interval = 300  # seconds
        
    async def start(self):
        """Start the trading engine."""
        logger.info("engine.starting")
        
        self._running = True
        
        # Initialize portfolio
        self.portfolio = await self.exchange.get_balance()
        await self.risk_manager.initialize(self.portfolio)
        
        # Load positions from database
        await self._load_state()
        
        # Start main loop
        self._main_task = asyncio.create_task(self._main_loop())
        
        logger.info(
            "engine.started",
            balance=str(self.portfolio.total_balance),
            strategies=list(self.strategies.keys())
        )
    
    async def stop(self):
        """Stop the trading engine gracefully."""
        logger.info("engine.stopping")
        self._running = False
        
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
        
        # Save state
        await self._save_state()
        
        logger.info("engine.stopped")
    
    async def _main_loop(self):
        """Main trading loop."""
        last_analysis = datetime.min
        last_balance_update = datetime.min
        
        while self._running:
            try:
                now = datetime.utcnow()
                
                # Update balance periodically
                if now - last_balance_update >= timedelta(seconds=self.balance_update_interval):
                    self.portfolio = await self.exchange.get_balance()
                    await self.risk_manager.reset_periods(self.portfolio)
                    last_balance_update = now
                    
                    logger.info(
                        "engine.balance_update",
                        total=str(self.portfolio.total_balance),
                        available=str(self.portfolio.available_balance),
                        exposure_pct=str(self.portfolio.exposure_pct)
                    )
                
                # Run analysis periodically
                if now - last_analysis >= timedelta(seconds=self.analysis_interval):
                    await self._run_analysis()
                    last_analysis = now
                
                # Check pending orders
                await self._update_pending_orders()
                
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error("engine.loop_error", error=str(e))
                await asyncio.sleep(5)
    
    async def _run_analysis(self):
        """Run all strategies and process signals."""
        # Fetch market data for all symbols
        symbols = set()
        for strategy in self.strategies.values():
            symbols.update(strategy.symbols)
        
        for symbol in symbols:
            try:
                # Fetch OHLCV data
                ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
                self.market_data[symbol] = ohlcv
            except Exception as e:
                logger.error("engine.data_fetch_error", symbol=symbol, error=str(e))
        
        # Run each strategy
        for name, strategy in self.strategies.items():
            if not strategy.is_active:
                continue
            
            try:
                # Get relevant data for this strategy
                strategy_data = {
                    s: self.market_data.get(s, [])
                    for s in strategy.symbols
                }
                
                # Generate signals
                signals = await strategy.analyze(strategy_data)
                
                # Process each signal
                for signal in signals:
                    await self._process_signal(signal, strategy)
                    
            except Exception as e:
                logger.error("engine.strategy_error", strategy=name, error=str(e))
    
    async def _process_signal(self, signal: TradingSignal, strategy: BaseStrategy):
        """Process a trading signal through risk checks."""
        logger.info(
            "engine.signal_received",
            strategy=signal.strategy_name,
            symbol=signal.symbol,
            signal=signal.signal_type.value,
            confidence=signal.confidence
        )
        
        # Risk check
        risk_check = self.risk_manager.check_signal(
            signal, self.portfolio, self.positions
        )
        
        if not risk_check.passed:
            logger.warning(
                "engine.signal_rejected",
                symbol=signal.symbol,
                reason=risk_check.reason,
                risk_level=risk_check.risk_level
            )
            return
        
        # Execute based on signal type
        if signal.signal_type == SignalType.BUY:
            await self._execute_buy(signal, strategy)
        elif signal.signal_type == SignalType.SELL:
            await self._execute_sell(signal, strategy)
        elif signal.signal_type == SignalType.CLOSE:
            await self._execute_close(signal)
    
    async def _execute_buy(self, signal: TradingSignal, strategy: BaseStrategy):
        """Execute a buy signal."""
        symbol = signal.symbol
        
        # Get current price
        ticker = await self.exchange.get_ticker(symbol)
        current_price = ticker['last']
        
        # Calculate position size
        quantity = self.risk_manager.calculate_position_size(
            self.portfolio, current_price
        )
        
        if quantity <= 0:
            logger.warning("engine.zero_quantity", symbol=symbol)
            return
        
        # Calculate stop loss and take profit
        stop_loss = None
        take_profit = None
        
        if trading_config.enable_stop_loss:
            stop_loss = self.risk_manager.calculate_stop_loss(current_price, "long")
        if trading_config.enable_take_profit:
            take_profit = self.risk_manager.calculate_take_profit(current_price, "long")
        
        # Create order
        order = await self.exchange.create_order(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=quantity,
            price=None
        )
        
        # Add risk management
        order.stop_loss_price = stop_loss
        order.take_profit_price = take_profit
        
        # Track order
        self.pending_orders[order.id] = order
        
        # Save to database
        await self.database.save_order(order)
        
        logger.info(
            "engine.buy_order_created",
            order_id=order.id,
            symbol=symbol,
            quantity=str(quantity),
            stop_loss=str(stop_loss) if stop_loss else None,
            take_profit=str(take_profit) if take_profit else None
        )
    
    async def _execute_sell(self, signal: TradingSignal, strategy: BaseStrategy):
        """Execute a sell signal."""
        symbol = signal.symbol
        
        # Check if we have a position
        if symbol not in self.positions:
            logger.warning("engine.no_position", symbol=symbol)
            return
        
        position = self.positions[symbol]
        
        # Create sell order
        order = await self.exchange.create_order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            amount=position.amount,
            price=None
        )
        
        self.pending_orders[order.id] = order
        await self.database.save_order(order)
        
        logger.info(
            "engine.sell_order_created",
            order_id=order.id,
            symbol=symbol,
            amount=str(position.amount)
        )
    
    async def _execute_close(self, signal: TradingSignal):
        """Close an existing position."""
        await self._execute_sell(signal, None)
    
    async def _update_pending_orders(self):
        """Check and update status of pending orders."""
        for order_id, order in list(self.pending_orders.items()):
            try:
                # Get current status from exchange
                status = await self.exchange.get_order_status(
                    order.exchange_order_id or order.id,
                    order.symbol
                )
                
                if status != order.status:
                    order.status = status
                    order.updated_at = datetime.utcnow()
                    
                    if status == OrderStatus.FILLED:
                        await self._on_order_filled(order)
                    elif status in (OrderStatus.CANCELLED, OrderStatus.REJECTED):
                        del self.pending_orders[order_id]
                        
            except Exception as e:
                logger.error("engine.order_update_error", order_id=order_id, error=str(e))
    
    async def _on_order_filled(self, order: Order):
        """Handle filled order."""
        order.filled_at = datetime.utcnow()
        
        # Notify strategy
        strategy = self.strategies.get(order.metadata.get('strategy_name', ''))
        if strategy:
            await strategy.on_order_filled(
                order.symbol,
                order.side.value,
                order.filled_amount,
                order.average_price or order.price or Decimal("0")
            )
        
        # Update position
        if order.side == OrderSide.BUY:
            await self._update_position_for_buy(order)
        else:
            await self._update_position_for_sell(order)
        
        # Update database
        await self.database.update_order(order)
        
        # Remove from pending
        if order.id in self.pending_orders:
            del self.pending_orders[order.id]
        
        logger.info(
            "engine.order_filled",
            order_id=order.id,
            symbol=order.symbol,
            side=order.side.value,
            amount=str(order.filled_amount),
            price=str(order.average_price) if order.average_price else None
        )
    
    async def _update_position_for_buy(self, order: Order):
        """Update position after buy order."""
        symbol = order.symbol
        
        if symbol not in self.positions:
            # Create new position
            self.positions[symbol] = Position(
                symbol=symbol,
                side=PositionSide.LONG,
                entry_price=order.average_price or order.price or Decimal("0"),
                amount=order.filled_amount,
                stop_loss_price=order.stop_loss_price,
                take_profit_price=order.take_profit_price
            )
        else:
            # Update existing position (DCA)
            position = self.positions[symbol]
            total_cost = (position.entry_price * position.amount) + \
                        (order.average_price or order.price or Decimal("0")) * order.filled_amount
            total_amount = position.amount + order.filled_amount
            
            position.entry_price = total_cost / total_amount
            position.amount = total_amount
        
        await self.database.save_position(self.positions[symbol])
    
    async def _update_position_for_sell(self, order: Order):
        """Update position after sell order."""
        symbol = order.symbol
        
        if symbol in self.positions:
            position = self.positions[symbol]
            
            # Calculate PnL
            realized_pnl = position.calculate_pnl(order.average_price or order.price or Decimal("0"))
            
            # Update risk manager
            self.risk_manager.update_pnl(realized_pnl)
            
            # Notify strategy
            strategy = self.strategies.get(order.metadata.get('strategy_name', ''))
            if strategy:
                await strategy.on_position_closed(
                    symbol, realized_pnl, position.calculate_pnl_pct(order.average_price or order.price or Decimal("0"))
                )
            
            # Remove position
            del self.positions[symbol]
            await self.database.delete_position(symbol)
    
    async def _load_state(self):
        """Load state from database."""
        # Load positions
        positions = await self.database.get_open_positions()
        for pos in positions:
            self.positions[pos.symbol] = pos
        
        logger.info("engine.state_loaded", positions=len(positions))
    
    async def _save_state(self):
        """Save state to database."""
        # Positions are saved on update
        logger.info("engine.state_saved")
    
    def get_status(self) -> Dict:
        """Get current engine status."""
        return {
            'running': self._running,
            'portfolio': {
                'total': str(self.portfolio.total_balance) if self.portfolio else None,
                'available': str(self.portfolio.available_balance) if self.portfolio else None,
            },
            'positions': {
                symbol: {
                    'side': pos.side.value,
                    'amount': str(pos.amount),
                    'entry_price': str(pos.entry_price)
                }
                for symbol, pos in self.positions.items()
            },
            'pending_orders': len(self.pending_orders),
            'strategies': {
                name: strategy.get_stats()
                for name, strategy in self.strategies.items()
            }
        }
