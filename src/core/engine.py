"""Main trading engine orchestrator for The Eternal Engine.

Coordinates all 4 engines (CORE-HODL, TREND, FUNDING, TACTICAL) with proper
capital allocation, risk management, and signal execution.

Architecture:
    TradingEngine
    ├── BybitClient (multi-subaccount)
    ├── RiskManager (circuit breakers, position sizing)
    ├── Database (state persistence)
    ├── Portfolio (portfolio tracking)
    ├── CORE-HODL Engine (60% allocation)
    ├── TREND Engine (20% allocation)
    ├── FUNDING Engine (15% allocation)
    └── TACTICAL Engine (5% allocation)
"""
import asyncio
from typing import Dict, List, Optional, Type
from datetime import datetime, timedelta
from decimal import Decimal
import structlog

from src.core.models import (
    Order, Position, Portfolio, TradingSignal, 
    SignalType, OrderSide, OrderType, OrderStatus,
    PositionSide, EngineType, EngineState, SystemState,
    CircuitBreakerLevel, RiskCheck, Trade
)
from src.core.config import engine_config
from src.exchange.bybit_client import ByBitClient, SubAccountType
from src.risk.risk_manager import RiskManager
from src.strategies.base import BaseStrategy
from src.storage.database import Database

logger = structlog.get_logger(__name__)


class TradingEngine:
    """
    Main orchestrator for The Eternal Engine 4-strategy trading system.
    
    Responsibilities:
    - Initialize and manage 4 engines (CORE-HODL, TREND, FUNDING, TACTICAL)
    - Coordinate capital allocation (60/20/15/5)
    - Run analysis loop for each engine
    - Route signals through RiskManager
    - Execute orders via BybitClient
    - Track positions and portfolio state
    - Handle circuit breakers and emergency stops
    - Provide status and monitoring
    
    Capital Allocation:
    - CORE-HODL: 60% - Spot BTC/ETH accumulation with DCA and rebalancing
    - TREND: 20% - Perpetual futures trend following (max 2x leverage)
    - FUNDING: 15% - Delta-neutral funding rate arbitrage
    - TACTICAL: 5% - Crisis deployment strategy
    """
    
    # Capital allocation percentages
    ALLOCATION = {
        EngineType.CORE_HODL: Decimal("0.60"),
        EngineType.TREND: Decimal("0.20"),
        EngineType.FUNDING: Decimal("0.15"),
        EngineType.TACTICAL: Decimal("0.05"),
    }
    
    # Subaccount mapping
    ENGINE_TO_SUBACCOUNT = {
        EngineType.CORE_HODL: SubAccountType.CORE_HODL,
        EngineType.TREND: SubAccountType.TREND,
        EngineType.FUNDING: SubAccountType.FUNDING,
        EngineType.TACTICAL: SubAccountType.TACTICAL,
    }
    
    def __init__(
        self,
        exchange: ByBitClient,
        risk_manager: RiskManager,
        database: Database,
        strategies: Optional[Dict[EngineType, List[BaseStrategy]]] = None
    ):
        self.exchange = exchange
        self.risk_manager = risk_manager
        self.database = database
        
        # Engine management
        self.engines: Dict[EngineType, List[BaseStrategy]] = strategies or {}
        self.engine_states: Dict[EngineType, EngineState] = {}
        
        # Portfolio and positions
        self.portfolio: Optional[Portfolio] = None
        self.positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, Order] = {}
        self.market_data: Dict[str, List] = {}
        
        # Engine-specific positions tracking
        self.engine_positions: Dict[EngineType, Dict[str, Position]] = {
            engine: {} for engine in EngineType
        }
        
        # Control state
        self._running = False
        self._main_task: Optional[asyncio.Task] = None
        self._emergency_stop = False
        self._emergency_reason: Optional[str] = None
        
        # Intervals (configurable)
        self.analysis_interval = 60  # seconds
        self.balance_update_interval = 300  # seconds
        self.circuit_breaker_check_interval = 30  # seconds
        
        # Tracking
        self._last_analysis: Dict[EngineType, datetime] = {}
        self._last_balance_update: Optional[datetime] = None
        self._last_circuit_breaker_check: Optional[datetime] = None
        
        # Performance tracking
        self._trades: List[Trade] = []
        self._signals_processed = 0
        self._signals_executed = 0
        
        # Initialize engine states
        self._initialize_engine_states()
        
        logger.info("trading_engine.initialized", 
                   allocations={k.value: float(v) for k, v in self.ALLOCATION.items()})
    
    def _initialize_engine_states(self):
        """Initialize state tracking for all 4 engines."""
        for engine_type in EngineType:
            self.engine_states[engine_type] = EngineState(
                engine_type=engine_type,
                current_allocation_pct=self.ALLOCATION[engine_type],
                is_active=self._is_engine_enabled(engine_type),
                config=self._get_engine_config(engine_type)
            )
            self._last_analysis[engine_type] = datetime.min
    
    def _is_engine_enabled(self, engine_type: EngineType) -> bool:
        """Check if an engine is enabled in configuration."""
        config_map = {
            EngineType.CORE_HODL: engine_config.core_hodl.enabled,
            EngineType.TREND: engine_config.trend.enabled,
            EngineType.FUNDING: engine_config.funding.enabled,
            EngineType.TACTICAL: engine_config.tactical.enabled,
        }
        return config_map.get(engine_type, True)
    
    def _get_engine_config(self, engine_type: EngineType) -> dict:
        """Get configuration for a specific engine."""
        config_map = {
            EngineType.CORE_HODL: engine_config.core_hodl.model_dump(),
            EngineType.TREND: engine_config.trend.model_dump(),
            EngineType.FUNDING: engine_config.funding.model_dump(),
            EngineType.TACTICAL: engine_config.tactical.model_dump(),
        }
        return config_map.get(engine_type, {})
    
    async def initialize(self):
        """
        Initialize the trading engine.
        
        Sets up all engines, connections, and initial state.
        Must be called before start().
        """
        logger.info("trading_engine.initializing")
        
        # Validate configuration
        validation = engine_config.validate_configuration()
        if not validation["valid"]:
            for issue in validation["issues"]:
                logger.error("trading_engine.config_issue", issue=issue)
            raise ValueError(f"Invalid configuration: {validation['issues']}")
        
        # Initialize portfolio
        self.portfolio = await self.exchange.get_balance()
        await self.risk_manager.initialize(self.portfolio)
        
        # Calculate engine allocations
        await self._update_engine_allocations()
        
        # Load state from database
        await self._load_state()
        
        logger.info(
            "trading_engine.initialized",
            total_balance=str(self.portfolio.total_balance),
            engines=list(self.engine_states.keys()),
            enabled_engines=[e.value for e, s in self.engine_states.items() if s.is_active]
        )
    
    async def start(self):
        """
        Start the trading engine main loop.
        
        Begins the orchestration of all 4 engines with proper
        capital allocation and risk management.
        """
        if self._running:
            logger.warning("trading_engine.already_running")
            return
        
        if self.portfolio is None:
            await self.initialize()
        
        logger.info("trading_engine.starting")
        self._running = True
        
        # Start main loop
        self._main_task = asyncio.create_task(self._main_loop())
        
        logger.info(
            "trading_engine.started",
            engines_active=sum(1 for s in self.engine_states.values() if s.can_trade),
            paper_mode=engine_config.is_paper_trading
        )
    
    async def stop(self):
        """
        Stop the trading engine gracefully.
        
        Completes pending operations, saves state, and shuts down.
        """
        logger.info("trading_engine.stopping")
        self._running = False
        
        # Cancel main task
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
        
        # Save state
        await self._save_state()
        
        logger.info("trading_engine.stopped")
    
    async def _main_loop(self):
        """
        Main trading orchestration loop.
        
        Loop:
        1. Update portfolio and balance
        2. Check circuit breakers
        3. For each active engine:
           - Run analysis cycle
           - Process signals through risk manager
           - Execute approved orders
        4. Update pending orders
        5. Sleep and repeat
        """
        while self._running:
            try:
                now = datetime.utcnow()
                
                # Check for emergency stop
                if self._emergency_stop:
                    logger.warning("trading_engine.emergency_stop_active", 
                                 reason=self._emergency_reason)
                    await asyncio.sleep(5)
                    continue
                
                # Update portfolio periodically
                if (self._last_balance_update is None or 
                    now - self._last_balance_update >= timedelta(seconds=self.balance_update_interval)):
                    await self._update_portfolio()
                    self._last_balance_update = now
                
                # Check circuit breakers
                if (self._last_circuit_breaker_check is None or
                    now - self._last_circuit_breaker_check >= timedelta(seconds=self.circuit_breaker_check_interval)):
                    await self._check_circuit_breakers()
                    self._last_circuit_breaker_check = now
                
                # Run analysis for each engine
                for engine_type in EngineType:
                    engine_state = self.engine_states[engine_type]
                    
                    # Skip if engine cannot trade
                    if not engine_state.can_trade:
                        continue
                    
                    # Check analysis interval
                    last_analysis = self._last_analysis.get(engine_type, datetime.min)
                    if now - last_analysis >= timedelta(seconds=self.analysis_interval):
                        await self._run_analysis_cycle(engine_type)
                        self._last_analysis[engine_type] = now
                
                # Update pending orders
                await self._update_pending_orders()
                
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                logger.info("trading_engine.loop_cancelled")
                break
            except Exception as e:
                logger.error("trading_engine.loop_error", error=str(e), exc_info=True)
                await asyncio.sleep(5)
    
    async def _run_analysis_cycle(self, engine_type: EngineType):
        """
        Run analysis cycle for a specific engine.
        
        Args:
            engine_type: The engine to run analysis for
        """
        engine_state = self.engine_states[engine_type]
        strategies = self.engines.get(engine_type, [])
        
        if not strategies:
            return
        
        logger.debug("trading_engine.running_analysis", engine=engine_type.value)
        
        # Collect all symbols needed by this engine
        symbols = set()
        for strategy in strategies:
            symbols.update(strategy.symbols)
        
        # Fetch market data
        engine_data = {}
        for symbol in symbols:
            try:
                if symbol not in self.market_data:
                    ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
                    self.market_data[symbol] = ohlcv
                engine_data[symbol] = self.market_data.get(symbol, [])
            except Exception as e:
                logger.error("trading_engine.data_fetch_error", 
                           engine=engine_type.value, symbol=symbol, error=str(e))
        
        # Run each strategy for this engine
        for strategy in strategies:
            if not strategy.is_active:
                continue
            
            try:
                # Get relevant data for this strategy
                strategy_data = {
                    s: engine_data.get(s, []) for s in strategy.symbols
                }
                
                # Generate signals
                signals = await strategy.analyze(strategy_data)
                
                # Process each signal
                for signal in signals:
                    # Add engine type to signal
                    signal.engine_type = engine_type
                    await self._process_signal(engine_type, signal, strategy)
                    
            except Exception as e:
                logger.error("trading_engine.strategy_error", 
                           engine=engine_type.value, strategy=strategy.name, error=str(e))
                engine_state.record_error(str(e))
    
    async def _process_signal(
        self, 
        engine_type: EngineType, 
        signal: TradingSignal, 
        strategy: BaseStrategy
    ):
        """
        Process a trading signal through risk validation.
        
        Args:
            engine_type: The engine that generated the signal
            signal: The trading signal to process
            strategy: The strategy that generated the signal
        """
        self._signals_processed += 1
        
        logger.info(
            "trading_engine.signal_received",
            engine=engine_type.value,
            strategy=signal.strategy_name,
            symbol=signal.symbol,
            signal=signal.signal_type.value,
            confidence=signal.confidence
        )
        
        # Get engine-specific positions
        engine_positions = self.engine_positions.get(engine_type, {})
        
        # Risk check with engine context
        risk_check = self.risk_manager.check_signal(
            signal, self.portfolio, {**self.positions, **engine_positions}
        )
        
        if not risk_check.passed:
            logger.warning(
                "trading_engine.signal_rejected",
                engine=engine_type.value,
                symbol=signal.symbol,
                reason=risk_check.reason,
                risk_level=risk_check.risk_level
            )
            self.engine_states[engine_type].record_error(f"Signal rejected: {risk_check.reason}")
            return
        
        # Execute based on signal type
        try:
            if signal.signal_type == SignalType.BUY:
                await self._execute_buy(engine_type, signal, strategy, risk_check)
            elif signal.signal_type == SignalType.SELL:
                await self._execute_sell(engine_type, signal, strategy, risk_check)
            elif signal.signal_type == SignalType.CLOSE:
                await self._execute_close(engine_type, signal)
            elif signal.signal_type == SignalType.CLOSE_LONG:
                await self._execute_close(engine_type, signal, side_filter=PositionSide.LONG)
            elif signal.signal_type == SignalType.CLOSE_SHORT:
                await self._execute_close(engine_type, signal, side_filter=PositionSide.SHORT)
            elif signal.signal_type == SignalType.REBALANCE:
                await self._execute_rebalance(engine_type, signal)
            elif signal.signal_type == SignalType.EMERGENCY_EXIT:
                await self.emergency_stop(f"Emergency exit signal from {engine_type.value}")
                
        except Exception as e:
            logger.error("trading_engine.execution_error", 
                       engine=engine_type.value, error=str(e))
    
    async def _execute_buy(
        self, 
        engine_type: EngineType, 
        signal: TradingSignal, 
        strategy: BaseStrategy,
        risk_check: RiskCheck
    ):
        """
        Execute a buy order for an engine.
        
        Args:
            engine_type: The engine executing the buy
            signal: The buy signal
            strategy: The source strategy
            risk_check: The risk check result
        """
        symbol = signal.symbol
        
        # Get current price
        ticker = await self.exchange.get_ticker(symbol)
        current_price = Decimal(str(ticker['last']))
        
        # Calculate position size with engine constraints
        stop_loss = signal.get_stop_loss() or self.risk_manager.calculate_stop_loss(
            current_price, "long"
        )
        
        # Get engine-specific max leverage
        leverage_map = {
            EngineType.CORE_HODL: Decimal("1.0"),
            EngineType.TREND: Decimal(str(engine_config.trend.max_leverage)),
            EngineType.FUNDING: Decimal(str(engine_config.funding.max_leverage)),
            EngineType.TACTICAL: Decimal("1.0"),
        }
        max_leverage = leverage_map.get(engine_type, Decimal("1.0"))
        
        # Calculate position size
        engine_allocation = self.portfolio.total_balance * self.ALLOCATION[engine_type]
        risk_per_trade = Decimal(str(engine_config.position_sizing.max_risk_per_trade))
        
        quantity = self.risk_manager.calculate_position_size(
            portfolio=self.portfolio,
            entry_price=current_price,
            stop_loss_price=stop_loss,
            risk_pct=risk_per_trade,
            strategy_type=engine_type.value.lower().replace("_", "")
        )
        
        # Adjust for max position size
        max_position_value = engine_allocation * Decimal(str(engine_config.position_sizing.max_position_pct)) / 100
        max_quantity = (max_position_value * max_leverage) / current_price
        quantity = min(quantity, max_quantity)
        
        # Risk check adjusted size
        if risk_check.max_position_size:
            quantity = min(quantity, risk_check.max_position_size)
        
        if quantity <= 0:
            logger.warning("trading_engine.zero_quantity", 
                         engine=engine_type.value, symbol=symbol)
            return
        
        # Calculate take profit
        take_profit = signal.get_take_profit() or self.risk_manager.calculate_take_profit(
            current_price, "long"
        )
        
        # Create order
        order = await self.exchange.create_order(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=quantity,
            price=None,
            params={
                'engine_type': engine_type.value,
                'strategy_name': strategy.name,
                'leverage': float(max_leverage) if engine_type in (EngineType.TREND, EngineType.FUNDING) else None
            }
        )
        
        # Add metadata
        order.stop_loss_price = stop_loss
        order.take_profit_price = take_profit
        order.metadata = {
            'engine_type': engine_type.value,
            'strategy_name': strategy.name,
            'signal_confidence': signal.confidence,
            'leverage': float(max_leverage)
        }
        
        # Track order
        self.pending_orders[order.id] = order
        
        # Save to database
        await self.database.save_order(order)
        
        # Update engine state
        self.engine_states[engine_type].last_signal_time = datetime.utcnow()
        
        self._signals_executed += 1
        
        logger.info(
            "trading_engine.buy_order_created",
            engine=engine_type.value,
            order_id=order.id,
            symbol=symbol,
            quantity=str(quantity),
            price=str(current_price),
            stop_loss=str(stop_loss),
            take_profit=str(take_profit),
            leverage=float(max_leverage)
        )
    
    async def _execute_sell(
        self, 
        engine_type: EngineType, 
        signal: TradingSignal, 
        strategy: BaseStrategy,
        risk_check: RiskCheck
    ):
        """
        Execute a sell/short order for an engine.
        
        Args:
            engine_type: The engine executing the sell
            signal: The sell signal
            strategy: The source strategy
            risk_check: The risk check result
        """
        symbol = signal.symbol
        
        # Check if we have a position
        engine_positions = self.engine_positions.get(engine_type, {})
        if symbol not in engine_positions:
            # For short positions, we don't need existing position
            if engine_type in (EngineType.TREND, EngineType.FUNDING):
                # Short selling allowed
                pass
            else:
                logger.warning("trading_engine.no_position", 
                             engine=engine_type.value, symbol=symbol)
                return
        
        position = engine_positions.get(symbol)
        amount = position.amount if position else signal.metadata.get('size', Decimal("0"))
        
        if amount <= 0:
            logger.warning("trading_engine.zero_sell_amount", 
                         engine=engine_type.value, symbol=symbol)
            return
        
        # Create sell order
        order = await self.exchange.create_order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            amount=amount,
            price=None,
            params={
                'engine_type': engine_type.value,
                'strategy_name': strategy.name
            }
        )
        
        order.metadata = {
            'engine_type': engine_type.value,
            'strategy_name': strategy.name,
            'signal_confidence': signal.confidence
        }
        
        self.pending_orders[order.id] = order
        await self.database.save_order(order)
        
        logger.info(
            "trading_engine.sell_order_created",
            engine=engine_type.value,
            order_id=order.id,
            symbol=symbol,
            amount=str(amount)
        )
    
    async def _execute_close(
        self, 
        engine_type: EngineType, 
        signal: TradingSignal,
        side_filter: Optional[PositionSide] = None
    ):
        """
        Close a position for an engine.
        
        Args:
            engine_type: The engine closing the position
            signal: The close signal
            side_filter: Optional side filter (long/short only)
        """
        symbol = signal.symbol
        engine_positions = self.engine_positions.get(engine_type, {})
        
        if symbol not in engine_positions:
            logger.warning("trading_engine.no_position_to_close", 
                         engine=engine_type.value, symbol=symbol)
            return
        
        position = engine_positions[symbol]
        
        # Check side filter
        if side_filter and position.side != side_filter:
            logger.debug("trading_engine.side_filter_skip",
                        engine=engine_type.value, symbol=symbol,
                        position_side=position.side.value, filter=side_filter.value)
            return
        
        # Determine close side
        close_side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        
        # Create close order
        order = await self.exchange.create_order(
            symbol=symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            amount=position.amount,
            price=None,
            params={
                'engine_type': engine_type.value,
                'close_position': True
            }
        )
        
        order.metadata = {
            'engine_type': engine_type.value,
            'close_reason': signal.metadata.get('reason', 'signal'),
            'signal_confidence': signal.confidence
        }
        
        self.pending_orders[order.id] = order
        await self.database.save_order(order)
        
        logger.info(
            "trading_engine.close_order_created",
            engine=engine_type.value,
            order_id=order.id,
            symbol=symbol,
            side=close_side.value,
            amount=str(position.amount)
        )
    
    async def _execute_rebalance(self, engine_type: EngineType, signal: TradingSignal):
        """
        Execute a portfolio rebalance for an engine.
        
        Args:
            engine_type: The engine to rebalance
            signal: The rebalance signal with target allocations
        """
        logger.info("trading_engine.rebalance_signal", 
                   engine=engine_type.value, metadata=signal.metadata)
        
        # Rebalance logic is engine-specific
        # CORE-HODL: BTC/ETH ratio adjustment
        # FUNDING: Spot/perp ratio adjustment
        
        targets = signal.metadata.get('targets', {})
        
        for symbol, target_pct in targets.items():
            # Calculate current vs target
            current_value = self._get_position_value(engine_type, symbol)
            target_value = self.portfolio.total_balance * self.ALLOCATION[engine_type] * Decimal(str(target_pct))
            
            diff = target_value - current_value
            
            if abs(diff) < Decimal("1.0"):  # Minimum $1 difference
                continue
            
            # Create rebalance order
            ticker = await self.exchange.get_ticker(symbol)
            price = Decimal(str(ticker['last']))
            
            if diff > 0:
                # Need to buy
                amount = diff / price
                order = await self.exchange.create_order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    amount=amount,
                    price=None,
                    params={'engine_type': engine_type.value, 'rebalance': True}
                )
            else:
                # Need to sell
                amount = abs(diff) / price
                order = await self.exchange.create_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    amount=amount,
                    price=None,
                    params={'engine_type': engine_type.value, 'rebalance': True}
                )
            
            self.pending_orders[order.id] = order
            await self.database.save_order(order)
            
            logger.info("trading_engine.rebalance_order",
                       engine=engine_type.value, symbol=symbol, 
                       diff=str(diff), order_id=order.id)
    
    def _get_position_value(self, engine_type: EngineType, symbol: str) -> Decimal:
        """Get the current value of a position for an engine."""
        engine_positions = self.engine_positions.get(engine_type, {})
        if symbol in engine_positions:
            pos = engine_positions[symbol]
            return pos.entry_price * pos.amount
        return Decimal("0")
    
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
                    elif status in (OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED):
                        del self.pending_orders[order_id]
                        
            except Exception as e:
                logger.error("trading_engine.order_update_error", 
                           order_id=order_id, error=str(e))
    
    async def _on_order_filled(self, order: Order):
        """Handle filled order."""
        order.filled_at = datetime.utcnow()
        
        # Get engine type from metadata
        engine_type_str = order.metadata.get('engine_type', 'CORE_HODL')
        try:
            engine_type = EngineType(engine_type_str.lower().replace('_', '_'))
        except ValueError:
            engine_type = EngineType.CORE_HODL
        
        # Notify strategy
        strategy_name = order.metadata.get('strategy_name', '')
        strategy = None
        for s in self.engines.get(engine_type, []):
            if s.name == strategy_name:
                strategy = s
                break
        
        if strategy:
            await strategy.on_order_filled(
                order.symbol,
                order.side.value,
                order.filled_amount or order.amount,
                order.average_price or order.price or Decimal("0")
            )
        
        # Update position
        if order.side == OrderSide.BUY:
            await self._update_position_for_buy(engine_type, order)
        else:
            await self._update_position_for_sell(engine_type, order)
        
        # Update database
        await self.database.save_order(order)
        
        # Remove from pending
        if order.id in self.pending_orders:
            del self.pending_orders[order.id]
        
        # Update engine state
        self.engine_states[engine_type].last_trade_time = datetime.utcnow()
        
        logger.info(
            "trading_engine.order_filled",
            engine=engine_type.value,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side.value,
            amount=str(order.filled_amount or order.amount),
            price=str(order.average_price) if order.average_price else None
        )
    
    async def _update_position_for_buy(self, engine_type: EngineType, order: Order):
        """Update position tracking after a buy order."""
        symbol = order.symbol
        engine_positions = self.engine_positions[engine_type]
        
        fill_price = order.average_price or order.price or Decimal("0")
        fill_amount = order.filled_amount or order.amount
        
        if symbol not in engine_positions:
            # Create new position
            engine_positions[symbol] = Position(
                symbol=symbol,
                side=PositionSide.LONG,
                entry_price=fill_price,
                amount=fill_amount,
                stop_loss_price=order.stop_loss_price,
                take_profit_price=order.take_profit_price,
                metadata={'engine_type': engine_type.value}
            )
        else:
            # Update existing position (DCA)
            position = engine_positions[symbol]
            total_cost = (position.entry_price * position.amount) + (fill_price * fill_amount)
            total_amount = position.amount + fill_amount
            
            position.entry_price = total_cost / total_amount
            position.amount = total_amount
            if order.stop_loss_price:
                position.stop_loss_price = order.stop_loss_price
        
        # Also update global positions
        self.positions[symbol] = engine_positions[symbol]
        await self.database.save_position(engine_positions[symbol])
    
    async def _update_position_for_sell(self, engine_type: EngineType, order: Order):
        """Update position tracking after a sell order."""
        symbol = order.symbol
        engine_positions = self.engine_positions[engine_type]
        
        if symbol not in engine_positions:
            return
        
        position = engine_positions[symbol]
        fill_price = order.average_price or order.price or Decimal("0")
        
        # Calculate PnL
        realized_pnl = position.calculate_unrealized_pnl(fill_price)
        pnl_pct = position.calculate_pnl_percentage(fill_price)
        
        # Update risk manager
        self.risk_manager.update_pnl(realized_pnl)
        
        # Create trade record
        trade = Trade(
            symbol=symbol,
            side=OrderSide.BUY if position.side == PositionSide.LONG else OrderSide.SELL,
            amount=position.amount,
            entry_price=position.entry_price,
            exit_price=fill_price,
            realized_pnl=realized_pnl,
            realized_pnl_pct=pnl_pct,
            strategy_name=order.metadata.get('strategy_name', ''),
            engine_type=engine_type,
            close_reason=order.metadata.get('close_reason', 'signal')
        )
        self._trades.append(trade)
        await self.database.save_trade(trade)
        
        # Notify strategy
        strategy_name = order.metadata.get('strategy_name', '')
        for s in self.engines.get(engine_type, []):
            if s.name == strategy_name:
                await s.on_position_closed(symbol, realized_pnl, pnl_pct)
                break
        
        # Update engine state
        self.engine_states[engine_type].record_trade(trade)
        
        # Remove position
        del engine_positions[symbol]
        if symbol in self.positions:
            del self.positions[symbol]
        await self.database.delete_position(symbol)
    
    async def _update_portfolio(self):
        """Update portfolio state from exchange."""
        try:
            self.portfolio = await self.exchange.get_balance()
            self.risk_manager.reset_periods(self.portfolio)
            
            # Update engine values
            await self._update_engine_allocations()
            
            logger.info(
                "trading_engine.portfolio_update",
                total=str(self.portfolio.total_balance),
                available=str(self.portfolio.available_balance),
                exposure_pct=str(self.portfolio.exposure_pct)
            )
        except Exception as e:
            logger.error("trading_engine.portfolio_update_error", error=str(e))
    
    async def _update_engine_allocations(self):
        """Update current value allocations for each engine."""
        if not self.portfolio:
            return
        
        total = self.portfolio.total_balance
        
        for engine_type, state in self.engine_states.items():
            # Calculate current value for this engine
            engine_positions = self.engine_positions.get(engine_type, {})
            position_value = sum(
                pos.entry_price * pos.amount for pos in engine_positions.values()
            )
            
            target_allocation = self.ALLOCATION[engine_type]
            target_value = total * target_allocation
            
            state.current_value = position_value
            state.current_allocation_pct = (position_value / total * 100) if total > 0 else Decimal("0")
            
            # Check for significant drift (potential rebalance needed)
            actual_pct = position_value / total if total > 0 else Decimal("0")
            drift = abs(actual_pct - target_allocation) / target_allocation if target_allocation > 0 else Decimal("0")
            
            if drift > Decimal("0.20"):  # 20% drift from target
                logger.warning("trading_engine.allocation_drift",
                             engine=engine_type.value,
                             target=float(target_allocation),
                             actual=float(actual_pct),
                             drift=float(drift))
    
    async def _check_circuit_breakers(self):
        """Check and handle circuit breaker conditions."""
        if not self.portfolio:
            return
        
        level = self.risk_manager.check_circuit_breakers(self.portfolio)
        
        if level != CircuitBreakerLevel.NONE:
            logger.warning("trading_engine.circuit_breaker_active", level=level.value)
            
            # Update all engine states
            for engine_type, state in self.engine_states.items():
                state.circuit_breaker_level = level
            
            # Handle level-specific actions
            if level == CircuitBreakerLevel.LEVEL_4:
                await self.emergency_stop("Circuit breaker LEVEL_4 triggered")
    
    async def _load_state(self):
        """Load state from database."""
        try:
            # Load positions
            positions = await self.database.get_open_positions()
            for pos in positions:
                self.positions[pos.symbol] = pos
                
                # Assign to engine based on metadata
                engine_type_str = pos.metadata.get('engine_type', 'CORE_HODL')
                try:
                    engine_type = EngineType(engine_type_str)
                except ValueError:
                    engine_type = EngineType.CORE_HODL
                
                self.engine_positions[engine_type][pos.symbol] = pos
            
            # Load engine states if available (optional)
            if hasattr(self.database, 'get_engine_states'):
                saved_states = await self.database.get_engine_states()
                for engine_type, state_data in saved_states.items():
                    if engine_type in self.engine_states:
                        # Update with saved values
                        for key, value in state_data.items():
                            if hasattr(self.engine_states[engine_type], key):
                                setattr(self.engine_states[engine_type], key, value)
            
            logger.info("trading_engine.state_loaded", 
                       positions=len(positions),
                       engines=len(self.engine_states))
        except Exception as e:
            logger.error("trading_engine.state_load_error", error=str(e))
    
    async def _save_state(self):
        """Save state to database."""
        try:
            # Save engine states (optional)
            if hasattr(self.database, 'save_engine_state'):
                for engine_type, state in self.engine_states.items():
                    await self.database.save_engine_state(engine_type, state)
            
            logger.info("trading_engine.state_saved")
        except Exception as e:
            logger.error("trading_engine.state_save_error", error=str(e))
    
    async def emergency_stop(self, reason: str):
        """
        Trigger emergency stop - halt all trading immediately.
        
        Args:
            reason: Explanation for the emergency stop
        """
        if self._emergency_stop:
            return
        
        logger.critical("trading_engine.emergency_stop", reason=reason)
        
        self._emergency_stop = True
        self._emergency_reason = reason
        
        # Pause all engines
        for engine_type, state in self.engine_states.items():
            state.pause(reason, duration_seconds=None)  # Indefinite
        
        # Trigger risk manager emergency stop
        self.risk_manager.trigger_emergency_stop(reason)
        
        # Save state
        await self._save_state()
    
    async def reset_emergency_stop(self, authorized_by: str) -> bool:
        """
        Reset emergency stop after verification.
        
        Args:
            authorized_by: Identifier of person authorizing the reset
            
        Returns:
            True if reset was successful
        """
        if not self._emergency_stop:
            return False
        
        logger.warning("trading_engine.resetting_emergency_stop", authorized_by=authorized_by)
        
        # Reset risk manager
        self.risk_manager.reset_emergency_stop(authorized_by)
        
        # Resume all engines
        for engine_type, state in self.engine_states.items():
            if state.is_paused and state.pause_reason == self._emergency_reason:
                state.resume()
        
        self._emergency_stop = False
        self._emergency_reason = None
        
        logger.info("trading_engine.emergency_stop_reset", authorized_by=authorized_by)
        return True
    
    def get_status(self) -> Dict:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary with complete system state
        """
        status = {
            'system': {
                'running': self._running,
                'emergency_stop': self._emergency_stop,
                'emergency_reason': self._emergency_reason,
                'paper_mode': engine_config.is_paper_trading,
                'demo_mode': engine_config.is_demo_mode,
            },
            'portfolio': {
                'total': str(self.portfolio.total_balance) if self.portfolio else None,
                'available': str(self.portfolio.available_balance) if self.portfolio else None,
                'exposure_pct': str(self.portfolio.exposure_pct) if self.portfolio else None,
                'all_time_high': str(self.portfolio.all_time_high) if self.portfolio else None,
                'current_drawdown_pct': str(self.portfolio.current_drawdown_pct) if self.portfolio else None,
            } if self.portfolio else None,
            'engines': {},
            'positions': {
                symbol: {
                    'side': pos.side.value,
                    'amount': str(pos.amount),
                    'entry_price': str(pos.entry_price),
                    'unrealized_pnl': str(pos.unrealized_pnl)
                }
                for symbol, pos in self.positions.items()
            },
            'pending_orders': len(self.pending_orders),
            'circuit_breaker': self.risk_manager.get_circuit_breaker_actions() if self.risk_manager else None,
            'risk': self.risk_manager.get_risk_report(self.portfolio) if self.risk_manager and self.portfolio else None,
            'performance': {
                'signals_processed': self._signals_processed,
                'signals_executed': self._signals_executed,
                'execution_rate': (
                    self._signals_executed / self._signals_processed * 100 
                    if self._signals_processed > 0 else 0
                ),
                'total_trades': len(self._trades),
                'recent_trades': [
                    {
                        'symbol': t.symbol,
                        'pnl': str(t.net_pnl),
                        'pnl_pct': str(t.realized_pnl_pct),
                        'engine': t.engine_type.value if t.engine_type else None
                    }
                    for t in self._trades[-10:]
                ]
            }
        }
        
        # Add engine-specific status
        for engine_type, state in self.engine_states.items():
            engine_strategies = self.engines.get(engine_type, [])
            status['engines'][engine_type.value] = {
                'is_active': state.is_active,
                'can_trade': state.can_trade,
                'is_paused': state.is_paused,
                'pause_reason': state.pause_reason,
                'allocation_pct': float(self.ALLOCATION[engine_type]),
                'current_value': str(state.current_value),
                'current_allocation_pct': str(state.current_allocation_pct),
                'total_trades': state.total_trades,
                'winning_trades': state.winning_trades,
                'losing_trades': state.losing_trades,
                'win_rate': float(state.win_rate),
                'total_pnl': str(state.total_pnl),
                'max_drawdown_pct': str(state.max_drawdown_pct),
                'circuit_breaker_level': state.circuit_breaker_level.value,
                'strategies': [
                    {
                        'name': s.name,
                        'is_active': s.is_active,
                        'symbols': s.symbols,
                        'stats': s.get_stats()
                    }
                    for s in engine_strategies
                ],
                'positions': [
                    {
                        'symbol': pos.symbol,
                        'side': pos.side.value,
                        'amount': str(pos.amount),
                        'entry_price': str(pos.entry_price)
                    }
                    for pos in self.engine_positions.get(engine_type, {}).values()
                ]
            }
        
        return status
    
    def get_system_state(self) -> SystemState:
        """
        Get complete system state snapshot.
        
        Returns:
            SystemState model with all current state
        """
        return SystemState(
            timestamp=datetime.utcnow(),
            portfolio=self.portfolio or Portfolio(total_balance=Decimal("0"), available_balance=Decimal("0")),
            engines=self.engine_states,
            positions=self.positions,
            orders=list(self.pending_orders.values()),
            circuit_breaker_level=self.risk_manager.circuit_breaker.level if self.risk_manager else CircuitBreakerLevel.NONE,
            is_trading_halted=self._emergency_stop
        )
    
    def pause_engine(self, engine_type: EngineType, reason: str, duration_seconds: Optional[int] = None):
        """
        Pause a specific engine.
        
        Args:
            engine_type: The engine to pause
            reason: Why the engine is being paused
            duration_seconds: Auto-resume duration (None for indefinite)
        """
        if engine_type in self.engine_states:
            self.engine_states[engine_type].pause(reason, duration_seconds)
            logger.info("trading_engine.engine_paused", 
                       engine=engine_type.value, reason=reason, duration=duration_seconds)
    
    def resume_engine(self, engine_type: EngineType):
        """
        Resume a specific engine.
        
        Args:
            engine_type: The engine to resume
        """
        if engine_type in self.engine_states:
            self.engine_states[engine_type].resume()
            logger.info("trading_engine.engine_resumed", engine=engine_type.value)
    
    def add_strategy(self, engine_type: EngineType, strategy: BaseStrategy):
        """
        Add a strategy to an engine.
        
        Args:
            engine_type: The engine to add the strategy to
            strategy: The strategy to add
        """
        if engine_type not in self.engines:
            self.engines[engine_type] = []
        
        self.engines[engine_type].append(strategy)
        logger.info("trading_engine.strategy_added", 
                   engine=engine_type.value, strategy=strategy.name)


# =============================================================================
# Factory Functions
# =============================================================================

def create_trading_engine(
    exchange: Optional[ByBitClient] = None,
    risk_manager: Optional[RiskManager] = None,
    database: Optional[Database] = None,
    strategies: Optional[Dict[EngineType, List[BaseStrategy]]] = None
) -> TradingEngine:
    """
    Factory function to create a configured TradingEngine.
    
    Args:
        exchange: ByBitClient instance (created if None)
        risk_manager: RiskManager instance (created if None)
        database: Database instance (created if None)
        strategies: Dictionary of strategies by engine type
        
    Returns:
        Configured TradingEngine instance
    """
    from src.exchange.bybit_client import ByBitClient
    from src.risk.risk_manager import create_risk_manager
    from src.storage.database import Database
    
    exchange = exchange or ByBitClient()
    risk_manager = risk_manager or create_risk_manager()
    database = database or Database()
    
    return TradingEngine(
        exchange=exchange,
        risk_manager=risk_manager,
        database=database,
        strategies=strategies or {}
    )
