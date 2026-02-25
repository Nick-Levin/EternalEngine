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
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Type

# Import ccxt for exception handling
import ccxt.async_support as ccxt
import structlog

from src.core.config import engine_config
from src.core.models import (CircuitBreakerLevel, EngineState, EngineType,
                             Order, OrderSide, OrderStatus, OrderType,
                             Portfolio, Position, PositionSide, RiskCheck,
                             SignalType, SystemState, Trade, TradingSignal)
from src.exchange.bybit_client import ByBitClient, SubAccountType
from src.risk.risk_manager import RiskManager
from src.storage.database import Database
from src.strategies.base import BaseStrategy

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
        strategies: Optional[Dict[EngineType, List[BaseStrategy]]] = None,
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

        # Order retry configuration
        self.MAX_ORDER_RETRIES = 3
        self.ORDER_RETRY_DELAY_MINUTES = 5
        self.STUCK_ORDER_HOURS = 24
        self.ORPHAN_CHECK_INTERVAL = 300  # 5 minutes

        # Failed orders queue: order_id -> (order, retry_count, failed_at)
        self.failed_orders: Dict[str, Tuple[Order, int, datetime]] = {}

        # Last orphan check timestamp
        self._last_orphan_check: Optional[datetime] = None

        # Exchange health monitoring
        self.exchange_down_since: Optional[datetime] = None
        self.exchange_circuit_breaker: bool = False
        self._last_exchange_health_check: Optional[datetime] = None
        self._exchange_health_check_interval = 10  # seconds
        self._exchange_downtime_threshold = 30  # seconds before pausing engines
        self._consecutive_network_errors = 0
        self._max_consecutive_errors = 5

        # Initialize engine states
        self._initialize_engine_states()

        logger.info(
            "trading_engine.initialized",
            allocations={k.value: float(v) for k, v in self.ALLOCATION.items()},
        )

    def _initialize_engine_states(self):
        """Initialize state tracking for all 4 engines."""
        for engine_type in EngineType:
            self.engine_states[engine_type] = EngineState(
                engine_type=engine_type,
                current_allocation_pct=self.ALLOCATION[engine_type],
                is_active=self._is_engine_enabled(engine_type),
                config=self._get_engine_config(engine_type),
            )
            self._last_analysis[engine_type] = datetime.min.replace(tzinfo=timezone.utc)

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

        # Initialize DCA persistence for all strategies
        await self._initialize_dca_persistence()

        # Sync positions from exchange (catches positions not in database)
        await self._sync_positions_from_exchange()

        logger.info(
            "trading_engine.initialized",
            total_balance=str(self.portfolio.total_balance),
            engines=list(self.engine_states.keys()),
            enabled_engines=[
                e.value for e, s in self.engine_states.items() if s.is_active
            ],
        )

    async def _initialize_dca_persistence(self):
        """
        Initialize DCA persistence for all DCA strategies.

        Sets up database callbacks and loads last_purchase times from database.
        This ensures DCA timing survives bot restarts.
        """
        for engine_type, strategies in self.engines.items():
            for strategy in strategies:
                # Check if this is a DCA strategy with persistence support
                if hasattr(strategy, "last_purchase") and hasattr(
                    strategy, "set_db_save_callback"
                ):
                    try:
                        # Set callback for saving to database
                        strategy.set_db_save_callback(self.database.save_dca_state)

                        # Load existing last_purchase times from database
                        loaded_times = await self.database.get_all_dca_states(
                            strategy.name
                        )
                        if loaded_times:
                            for symbol, timestamp in loaded_times.items():
                                strategy.last_purchase[symbol] = timestamp
                            logger.info(
                                "trading_engine.dca_state_loaded",
                                strategy=strategy.name,
                                symbols=list(loaded_times.keys()),
                                count=len(loaded_times),
                            )
                    except Exception as e:
                        logger.warning(
                            "trading_engine.dca_persistence_init_failed",
                            strategy=strategy.name,
                            error=str(e),
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
            paper_mode=engine_config.is_paper_trading,
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
        3. Check exchange health status
        4. For each active engine:
           - Run analysis cycle
           - Process signals through risk manager
           - Execute approved orders
        5. Update pending orders
        6. Sleep and repeat

        Handles network errors and exchange downtime gracefully with automatic
        retry logic and circuit breaker activation.
        """
        while self._running:
            try:
                now = datetime.now(timezone.utc)

                # Check for emergency stop
                if self._emergency_stop:
                    logger.warning(
                        "trading_engine.emergency_stop_active",
                        reason=self._emergency_reason,
                    )
                    await asyncio.sleep(5)
                    continue

                # Check exchange health periodically
                if (
                    self._last_exchange_health_check is None
                    or now - self._last_exchange_health_check
                    >= timedelta(seconds=self._exchange_health_check_interval)
                ):
                    await self._update_exchange_status()
                    self._last_exchange_health_check = now

                # If exchange circuit breaker is active, skip trading operations
                if self.exchange_circuit_breaker:
                    logger.debug(
                        "trading_engine.exchange_circuit_breaker_active",
                        downtime_seconds=self._get_exchange_downtime_seconds(),
                    )
                    # Try to reconnect periodically
                    if await self._reconnect_exchange():
                        await self._update_exchange_status()
                    await asyncio.sleep(5)
                    continue

                # Update portfolio periodically
                if (
                    self._last_balance_update is None
                    or now - self._last_balance_update
                    >= timedelta(seconds=self.balance_update_interval)
                ):
                    await self._update_portfolio()
                    self._last_balance_update = now

                # Check circuit breakers
                if (
                    self._last_circuit_breaker_check is None
                    or now - self._last_circuit_breaker_check
                    >= timedelta(seconds=self.circuit_breaker_check_interval)
                ):
                    await self._check_circuit_breakers()
                    self._last_circuit_breaker_check = now

                # Run analysis for each engine
                for engine_type in EngineType:
                    engine_state = self.engine_states[engine_type]

                    # Skip if engine cannot trade
                    if not engine_state.can_trade:
                        continue

                    # Check analysis interval
                    last_analysis = self._last_analysis.get(
                        engine_type, datetime.min.replace(tzinfo=timezone.utc)
                    )
                    if now - last_analysis >= timedelta(seconds=self.analysis_interval):
                        await self._run_analysis_cycle(engine_type)
                        self._last_analysis[engine_type] = now

                # Update pending orders
                await self._update_pending_orders()

                # Run order maintenance (orphan detection, stuck order cleanup, retry)
                await self._run_order_maintenance()

                # Reset consecutive error counter on successful iteration
                self._consecutive_network_errors = 0

                # Small sleep to prevent CPU spinning
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("trading_engine.loop_cancelled")
                break
            except Exception as e:
                # Handle specific network/exchange errors
                error_str = str(e).lower()

                # Check for network-related errors
                if any(
                    err in error_str
                    for err in [
                        "network",
                        "connection",
                        "timeout",
                        "unavailable",
                        "refused",
                        "dns",
                    ]
                ):
                    self._consecutive_network_errors += 1
                    logger.warning(
                        "trading_engine.network_error",
                        error=str(e),
                        consecutive_errors=self._consecutive_network_errors,
                    )

                    # Progressive backoff based on consecutive errors
                    if self._consecutive_network_errors <= 1:
                        await asyncio.sleep(1)
                    elif self._consecutive_network_errors <= 3:
                        await asyncio.sleep(5)
                    elif self._consecutive_network_errors <= 5:
                        await asyncio.sleep(10)
                    else:
                        logger.error(
                            "trading_engine.too_many_network_errors",
                            consecutive_errors=self._consecutive_network_errors,
                        )
                        # Activate exchange circuit breaker after max errors
                        if not self.exchange_circuit_breaker:
                            await self._pause_all_engines("too_many_network_errors")
                            self.exchange_circuit_breaker = True
                        await asyncio.sleep(30)
                    continue

                # Check for exchange-specific errors
                if any(
                    err in error_str
                    for err in ["exchange", "bybit", "api", "rate limit"]
                ):
                    logger.warning("trading_engine.exchange_error", error=str(e))
                    await asyncio.sleep(10)
                    continue

                # Generic error handling
                logger.error("trading_engine.loop_error", error=str(e), exc_info=True)
                await asyncio.sleep(5)

    async def _check_exchange_health(self) -> bool:
        """
        Check if exchange is reachable by fetching server time.

        Uses a lightweight endpoint to minimize overhead while
        verifying connectivity to the exchange.

        Returns:
            True if exchange is healthy, False otherwise
        """
        try:
            await self.exchange.fetch_time()
            return True
        except Exception as e:
            logger.debug("trading_engine.exchange_health_check_failed", error=str(e))
            return False

    async def _update_exchange_status(self):
        """
        Monitor exchange health and pause/resume engines accordingly.

        Tracks exchange downtime and activates circuit breaker after
        a threshold period. Automatically resumes engines when exchange
        recovers.
        """
        is_healthy = await self._check_exchange_health()
        now = datetime.now(timezone.utc)

        if not is_healthy:
            if not self.exchange_down_since:
                self.exchange_down_since = now
                logger.warning("trading_engine.exchange_down_detected")

            # Calculate downtime
            downtime = (now - self.exchange_down_since).total_seconds()

            # Pause all engines after threshold of downtime
            if (
                downtime > self._exchange_downtime_threshold
                and not self.exchange_circuit_breaker
            ):
                self.exchange_circuit_breaker = True
                await self._pause_all_engines("exchange_down")
                logger.warning(
                    "trading_engine.exchange_circuit_breaker_activated",
                    downtime_seconds=int(downtime),
                )
        else:
            # Exchange is healthy
            if self.exchange_down_since:
                downtime = (now - self.exchange_down_since).total_seconds()
                logger.info(
                    "trading_engine.exchange_recovered", downtime_seconds=int(downtime)
                )
                self.exchange_down_since = None

            if self.exchange_circuit_breaker:
                self.exchange_circuit_breaker = False
                await self._resume_all_engines()
                logger.info("trading_engine.exchange_circuit_breaker_deactivated")

    def _get_exchange_downtime_seconds(self) -> float:
        """Get current exchange downtime in seconds."""
        if not self.exchange_down_since:
            return 0.0
        return (datetime.now(timezone.utc) - self.exchange_down_since).total_seconds()

    async def _pause_all_engines(self, reason: str):
        """
        Pause all engines during exchange downtime.

        Args:
            reason: Reason for pausing engines
        """
        logger.warning("trading_engine.pausing_all_engines", reason=reason)

        for engine_type in EngineType:
            state = self.engine_states[engine_type]
            if state.can_trade:
                state.pause(reason, duration_seconds=None)  # Indefinite

    async def _resume_all_engines(self):
        """Resume all engines after exchange recovery."""
        logger.info("trading_engine.resuming_all_engines")

        for engine_type in EngineType:
            state = self.engine_states[engine_type]
            if state.is_paused and not self._emergency_stop:
                state.resume()

    async def _reconnect_exchange(self) -> bool:
        """
        Attempt to reconnect to exchange.

        Closes existing connection and reinitializes.
        Called periodically when exchange circuit breaker is active.

        Returns:
            True if reconnection was successful, False otherwise
        """
        try:
            logger.debug("trading_engine.attempting_reconnect")

            # Close existing connection if possible
            try:
                if hasattr(self.exchange, "close"):
                    await self.exchange.close()
            except Exception as e:
                logger.debug("trading_engine.close_connection_error", error=str(e))

            # Wait before reconnecting
            await asyncio.sleep(1)

            # Reinitialize connection
            if hasattr(self.exchange, "initialize"):
                await self.exchange.initialize()
            elif hasattr(self.exchange, "load_markets"):
                await self.exchange.load_markets(reload=True)

            logger.info("trading_engine.exchange_reconnected")
            return True

        except Exception as e:
            logger.debug("trading_engine.reconnect_failed", error=str(e))
            return False

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
                    ohlcv = await self.exchange.fetch_ohlcv(
                        symbol, timeframe="1h", limit=100
                    )
                    self.market_data[symbol] = ohlcv
                engine_data[symbol] = self.market_data.get(symbol, [])
            except Exception as e:
                logger.error(
                    "trading_engine.data_fetch_error",
                    engine=engine_type.value,
                    symbol=symbol,
                    error=str(e),
                )

        # Run each strategy for this engine
        for strategy in strategies:
            if not strategy.is_active:
                continue

            try:
                # Update portfolio state for CORE-HODL strategy
                if hasattr(strategy, "update_portfolio_state"):
                    # Calculate position values for each symbol
                    position_values = {}
                    for symbol in strategy.symbols:
                        position = self.engine_positions.get(engine_type, {}).get(
                            symbol
                        )
                        if position:
                            position_values[symbol] = (
                                position.amount * position.entry_price
                            )
                        else:
                            position_values[symbol] = Decimal("0")

                    strategy.update_portfolio_state(
                        portfolio_value=(
                            self.portfolio.total_balance
                            if self.portfolio
                            else Decimal("0")
                        ),
                        positions=position_values,
                    )

                # Get relevant data for this strategy
                strategy_data = {s: engine_data.get(s, []) for s in strategy.symbols}

                # Generate signals
                signals = await strategy.analyze(strategy_data)

                # Process each signal
                for signal in signals:
                    # Add engine type to signal
                    signal.engine_type = engine_type
                    await self._process_signal(engine_type, signal, strategy)

            except Exception as e:
                logger.error(
                    "trading_engine.strategy_error",
                    engine=engine_type.value,
                    strategy=strategy.name,
                    error=str(e),
                )
                engine_state.record_error(str(e))

    async def _process_signal(
        self, engine_type: EngineType, signal: TradingSignal, strategy: BaseStrategy
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
            confidence=signal.confidence,
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
                risk_level=risk_check.risk_level,
            )
            self.engine_states[engine_type].record_error(
                f"Signal rejected: {risk_check.reason}"
            )
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
                await self._execute_close(
                    engine_type, signal, side_filter=PositionSide.LONG
                )
            elif signal.signal_type == SignalType.CLOSE_SHORT:
                await self._execute_close(
                    engine_type, signal, side_filter=PositionSide.SHORT
                )
            elif signal.signal_type == SignalType.REBALANCE:
                await self._execute_rebalance(engine_type, signal)
            elif signal.signal_type == SignalType.EMERGENCY_EXIT:
                await self.emergency_stop(
                    f"Emergency exit signal from {engine_type.value}"
                )

        except Exception as e:
            logger.error(
                "trading_engine.execution_error", engine=engine_type.value, error=str(e)
            )

    async def _execute_buy(
        self,
        engine_type: EngineType,
        signal: TradingSignal,
        strategy: BaseStrategy,
        risk_check: RiskCheck,
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
        current_price = Decimal(str(ticker["last"]))

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

        # For CORE-HODL (DCA strategy), use the DCA amount from signal metadata
        if (
            engine_type == EngineType.CORE_HODL
            and signal.metadata
            and "amount_usdt" in signal.metadata
        ):
            dca_amount_usdt = Decimal(str(signal.metadata["amount_usdt"]))
            quantity = dca_amount_usdt / current_price
            logger.info(
                "trading_engine.dca_amount",
                engine=engine_type.value,
                symbol=symbol,
                amount_usdt=str(dca_amount_usdt),
                price=str(current_price),
                quantity=str(quantity),
                order_value=str(quantity * current_price),
            )
        else:
            quantity = self.risk_manager.calculate_position_size(
                portfolio=self.portfolio,
                entry_price=current_price,
                stop_loss_price=stop_loss,
                risk_pct=risk_per_trade,
                strategy_type=engine_type.value.lower().replace("_", ""),
            )

        # Adjust for max position size
        # max_position_pct is already stored as a decimal (e.g., 0.05 = 5%)
        max_position_value = engine_allocation * Decimal(
            str(engine_config.position_sizing.max_position_pct)
        )
        max_quantity = (max_position_value * max_leverage) / current_price
        original_quantity = quantity
        quantity = min(quantity, max_quantity)

        if quantity < original_quantity:
            logger.warning(
                "trading_engine.quantity_capped_by_max_position",
                engine=engine_type.value,
                symbol=symbol,
                original=str(original_quantity),
                capped=str(quantity),
                max_position_value=str(max_position_value),
            )

        # Risk check adjusted size
        risk_check_max_size = getattr(risk_check, "max_position_size", None)
        if risk_check_max_size and isinstance(risk_check_max_size, Decimal):
            quantity = min(quantity, risk_check_max_size)
            logger.info(
                "trading_engine.quantity_adjusted_by_risk_check",
                engine=engine_type.value,
                symbol=symbol,
                risk_check_max=str(risk_check_max_size),
                final_quantity=str(quantity),
            )

        if quantity <= 0:
            logger.warning(
                "trading_engine.zero_quantity", engine=engine_type.value, symbol=symbol
            )
            return

        # Calculate take profit
        take_profit = (
            signal.get_take_profit()
            or self.risk_manager.calculate_take_profit(current_price, "long")
        )

        # Get subaccount for this engine
        subaccount = self.ENGINE_TO_SUBACCOUNT.get(
            engine_type, SubAccountType.CORE_HODL
        ).value

        # Prepare order parameters
        order_params = {
            "subaccount": subaccount,
            "symbol": symbol,
            "side": OrderSide.BUY,
            "order_type": OrderType.MARKET,
            "amount": quantity,
            "price": None,
            "params": {
                "engine_type": engine_type.value,
                "strategy_name": strategy.name,
                "leverage": (
                    float(max_leverage)
                    if engine_type in (EngineType.TREND, EngineType.FUNDING)
                    else None
                ),
            },
        }

        # Prepare order metadata for retry
        order_metadata = {
            "engine_type": engine_type.value,
            "strategy_name": strategy.name,
            "signal_confidence": signal.confidence,
            "leverage": float(max_leverage),
            "stop_loss_price": float(stop_loss) if stop_loss else None,
            "take_profit_price": float(take_profit) if take_profit else None,
            "subaccount": subaccount,
        }

        # Create order with retry handling
        order = await self._create_order_with_retry(
            order_params, order_metadata, engine_type, symbol
        )

        if order is None:
            # Order failed and was added to retry queue or rejected
            return

        # Add metadata
        order.stop_loss_price = stop_loss
        order.take_profit_price = take_profit
        order.metadata = {
            "engine_type": engine_type.value,
            "strategy_name": strategy.name,
            "signal_confidence": signal.confidence,
            "leverage": float(max_leverage),
        }

        # Track order
        self.pending_orders[order.id] = order

        # Save to database
        await self.database.save_order(order)

        # Update engine state
        self.engine_states[engine_type].last_signal_time = datetime.now(timezone.utc)

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
            leverage=float(max_leverage),
        )

    async def _execute_sell(
        self,
        engine_type: EngineType,
        signal: TradingSignal,
        strategy: BaseStrategy,
        risk_check: RiskCheck,
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
                logger.warning(
                    "trading_engine.no_position",
                    engine=engine_type.value,
                    symbol=symbol,
                )
                return

        position = engine_positions.get(symbol)
        if position:
            amount = position.amount
        else:
            size = signal.metadata.get("size", Decimal("0"))
            amount = Decimal(str(size)) if size else Decimal("0")

        if amount <= 0:
            logger.warning(
                "trading_engine.zero_sell_amount",
                engine=engine_type.value,
                symbol=symbol,
            )
            return

        # Get subaccount for this engine
        subaccount = self.ENGINE_TO_SUBACCOUNT.get(
            engine_type, SubAccountType.CORE_HODL
        ).value

        # Prepare order parameters
        order_params = {
            "subaccount": subaccount,
            "symbol": symbol,
            "side": OrderSide.SELL,
            "order_type": OrderType.MARKET,
            "amount": amount,
            "price": None,
            "params": {
                "engine_type": engine_type.value,
                "strategy_name": strategy.name,
            },
        }

        # Prepare order metadata for retry
        order_metadata = {
            "engine_type": engine_type.value,
            "strategy_name": strategy.name,
            "signal_confidence": signal.confidence,
            "subaccount": subaccount,
        }

        # Create order with retry handling
        order = await self._create_order_with_retry(
            order_params, order_metadata, engine_type, symbol
        )

        if order is None:
            # Order failed and was added to retry queue or rejected
            return

        order.metadata = {
            "engine_type": engine_type.value,
            "strategy_name": strategy.name,
            "signal_confidence": signal.confidence,
        }

        self.pending_orders[order.id] = order
        await self.database.save_order(order)

        logger.info(
            "trading_engine.sell_order_created",
            engine=engine_type.value,
            order_id=order.id,
            symbol=symbol,
            amount=str(amount),
        )

    async def _execute_close(
        self,
        engine_type: EngineType,
        signal: TradingSignal,
        side_filter: Optional[PositionSide] = None,
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
            logger.warning(
                "trading_engine.no_position_to_close",
                engine=engine_type.value,
                symbol=symbol,
            )
            return

        position = engine_positions[symbol]

        # Check side filter
        if side_filter and position.side != side_filter:
            logger.debug(
                "trading_engine.side_filter_skip",
                engine=engine_type.value,
                symbol=symbol,
                position_side=position.side.value,
                filter=side_filter.value,
            )
            return

        # Determine close side
        close_side = (
            OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        )

        # Get subaccount for this engine
        subaccount = self.ENGINE_TO_SUBACCOUNT.get(
            engine_type, SubAccountType.CORE_HODL
        ).value

        # Prepare order parameters
        order_params = {
            "subaccount": subaccount,
            "symbol": symbol,
            "side": close_side,
            "order_type": OrderType.MARKET,
            "amount": position.amount,
            "price": None,
            "params": {"engine_type": engine_type.value, "close_position": True},
        }

        # Prepare order metadata for retry
        order_metadata = {
            "engine_type": engine_type.value,
            "close_reason": signal.metadata.get("reason", "signal"),
            "signal_confidence": signal.confidence,
            "subaccount": subaccount,
        }

        # Create order with retry handling
        order = await self._create_order_with_retry(
            order_params, order_metadata, engine_type, symbol
        )

        if order is None:
            # Order failed and was added to retry queue or rejected
            return

        order.metadata = {
            "engine_type": engine_type.value,
            "close_reason": signal.metadata.get("reason", "signal"),
            "signal_confidence": signal.confidence,
        }

        self.pending_orders[order.id] = order
        await self.database.save_order(order)

        logger.info(
            "trading_engine.close_order_created",
            engine=engine_type.value,
            order_id=order.id,
            symbol=symbol,
            side=close_side.value,
            amount=str(position.amount),
        )

    async def _execute_rebalance(self, engine_type: EngineType, signal: TradingSignal):
        """
        Execute a portfolio rebalance for an engine.

        Args:
            engine_type: The engine to rebalance
            signal: The rebalance signal with target allocations
        """
        logger.info(
            "trading_engine.rebalance_signal",
            engine=engine_type.value,
            metadata=signal.metadata,
        )

        # Rebalance logic is engine-specific
        # CORE-HODL: BTC/ETH ratio adjustment
        # FUNDING: Spot/perp ratio adjustment

        targets = signal.metadata.get("targets", {})

        for symbol, target_pct in targets.items():
            # Calculate current vs target
            current_value = self._get_position_value(engine_type, symbol)
            target_value = (
                self.portfolio.total_balance
                * self.ALLOCATION[engine_type]
                * Decimal(str(target_pct))
            )

            diff = target_value - current_value

            if abs(diff) < Decimal("1.0"):  # Minimum $1 difference
                continue

            # Create rebalance order
            ticker = await self.exchange.get_ticker(symbol)
            price = Decimal(str(ticker["last"]))

            # Get subaccount for this engine
            subaccount = self.ENGINE_TO_SUBACCOUNT.get(
                engine_type, SubAccountType.CORE_HODL
            ).value

            # Prepare order parameters
            if diff > 0:
                # Need to buy
                amount = diff / price
                order_side = OrderSide.BUY
            else:
                # Need to sell
                amount = abs(diff) / price
                order_side = OrderSide.SELL

            order_params = {
                "subaccount": subaccount,
                "symbol": symbol,
                "side": order_side,
                "order_type": OrderType.MARKET,
                "amount": amount,
                "price": None,
                "params": {"engine_type": engine_type.value, "rebalance": True},
            }

            order_metadata = {
                "engine_type": engine_type.value,
                "rebalance": True,
                "subaccount": subaccount,
            }

            # Create order with retry handling
            order = await self._create_order_with_retry(
                order_params, order_metadata, engine_type, symbol
            )

            if order is None:
                # Order failed and was added to retry queue or rejected
                continue

            self.pending_orders[order.id] = order
            await self.database.save_order(order)

            logger.info(
                "trading_engine.rebalance_order",
                engine=engine_type.value,
                symbol=symbol,
                diff=str(diff),
                order_id=order.id,
            )

    def _get_position_value(self, engine_type: EngineType, symbol: str) -> Decimal:
        """Get the current value of a position for an engine."""
        engine_positions = self.engine_positions.get(engine_type, {})
        if symbol in engine_positions:
            pos = engine_positions[symbol]
            return pos.entry_price * pos.amount
        return Decimal("0")

    async def _update_pending_orders(self):
        """
        Check and update status of pending orders.

        Skips updating during exchange downtime to avoid errors
        and preserves order tracking state.
        """
        # Skip order updates during exchange downtime
        if self.exchange_circuit_breaker:
            logger.debug(
                "trading_engine.skipping_order_updates",
                reason="exchange_circuit_breaker_active",
                pending_orders=len(self.pending_orders),
            )
            return

        for order_id, order in list(self.pending_orders.items()):
            try:
                # Get subaccount from order metadata
                subaccount = order.metadata.get("subaccount", "CORE_HODL")

                # Get current status from exchange
                status = await self.exchange.get_order_status(
                    subaccount=subaccount,
                    order_id=order.exchange_order_id or order.id,
                    symbol=order.symbol,
                )

                if status != order.status:
                    order.status = status
                    order.updated_at = datetime.now(timezone.utc)

                    if status == OrderStatus.FILLED:
                        await self._on_order_filled(order)
                    elif status == OrderStatus.PARTIALLY_FILLED:
                        # Fetch full order details to get filled amount and average price
                        try:
                            order_info = await self.exchange.fetch_order(
                                order_id=order.exchange_order_id or order.id,
                                symbol=order.symbol,
                                params={"subaccount": subaccount},
                            )
                            if order_info:
                                # Update order with partial fill info
                                filled_amount = order_info.get("filled")
                                average_price = order_info.get("average")
                                if filled_amount is not None:
                                    order.filled_amount = Decimal(str(filled_amount))
                                if average_price is not None:
                                    order.average_price = Decimal(str(average_price))
                                await self._on_order_partially_filled(order)
                        except Exception as fetch_error:
                            logger.warning(
                                "trading_engine.partial_fill_fetch_error",
                                order_id=order_id,
                                error=str(fetch_error),
                            )
                    elif status in (
                        OrderStatus.CANCELLED,
                        OrderStatus.REJECTED,
                        OrderStatus.EXPIRED,
                    ):
                        del self.pending_orders[order_id]

            except Exception as e:
                # Log but don't crash - order tracking is not critical
                logger.warning(
                    "trading_engine.order_update_error", order_id=order_id, error=str(e)
                )

    async def _on_order_partially_filled(self, order: Order):
        """Handle partial fill - update position but keep order pending.

        Args:
            order: The partially filled order
        """
        # Get engine type from metadata
        engine_type_str = order.metadata.get("engine_type", "CORE_HODL")
        try:
            engine_type = EngineType(engine_type_str.lower().replace("_", "_"))
        except ValueError:
            engine_type = EngineType.CORE_HODL

        # Calculate the newly filled amount (delta since last update)
        # We need to track what we've already processed, so check position
        engine_positions = self.engine_positions.get(engine_type, {})
        position = engine_positions.get(order.symbol)

        # Get the fill details for this partial fill
        fill_amount = order.filled_amount
        fill_price = order.average_price

        if fill_amount is None or fill_amount <= 0:
            logger.warning(
                "trading_engine.partial_fill_no_amount",
                order_id=order.id,
                symbol=order.symbol,
            )
            return

        if fill_price is None or fill_price <= 0:
            # Try to get current market price as fallback
            try:
                ticker = await self.exchange.get_ticker(order.symbol)
                fill_price = Decimal(str(ticker["last"]))
                logger.warning(
                    "trading_engine.partial_fill_using_market_price",
                    order_id=order.id,
                    symbol=order.symbol,
                    price=str(fill_price),
                )
            except Exception as e:
                logger.error(
                    "trading_engine.partial_fill_no_price",
                    order_id=order.id,
                    symbol=order.symbol,
                    error=str(e),
                )
                return

        # Update position tracking for the partial fill
        if order.side == OrderSide.BUY:
            await self._update_position_for_partial_buy(
                engine_type, order, fill_amount, fill_price
            )
        else:
            await self._update_position_for_partial_sell(
                engine_type, order, fill_amount, fill_price
            )

        # Notify strategy of partial fill
        strategy_name = order.metadata.get("strategy_name", "")
        for s in self.engines.get(engine_type, []):
            if s.name == strategy_name:
                try:
                    # Calculate the amount filled in this update (delta)
                    # We pass the total filled amount and let strategy handle it
                    await s.on_order_filled(
                        order.symbol,
                        order.side.value,
                        fill_amount,  # Total filled amount so far
                        fill_price,
                    )
                except Exception as e:
                    logger.warning(
                        "trading_engine.strategy_partial_fill_notify_failed",
                        strategy=strategy_name,
                        error=str(e),
                    )
                break

        # Persist partial fill state to database
        await self.database.save_order(order)

        # Also save position to reflect partial fill
        position = self.engine_positions.get(engine_type, {}).get(order.symbol)
        if position:
            await self.database.save_position(position)

        # Keep order in pending_orders - it will be removed when fully filled
        logger.info(
            "trading_engine.order_partially_filled",
            engine=engine_type.value,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side.value,
            filled_amount=str(fill_amount),
            total_amount=str(order.amount),
            fill_percentage=float(order.fill_percentage),
            price=str(fill_price),
        )

    async def _update_position_for_partial_buy(
        self,
        engine_type: EngineType,
        order: Order,
        fill_amount: Decimal,
        fill_price: Decimal,
    ):
        """Update position tracking after a partial buy fill.

        Args:
            engine_type: The engine type
            order: The order being partially filled
            fill_amount: Amount filled in this update
            fill_price: Price of the fill
        """
        symbol = order.symbol
        engine_positions = self.engine_positions[engine_type]

        if symbol not in engine_positions:
            # Create new position with partial fill amount
            engine_positions[symbol] = Position(
                symbol=symbol,
                side=PositionSide.LONG,
                entry_price=fill_price,
                amount=fill_amount,
                stop_loss_price=order.stop_loss_price,
                take_profit_price=order.take_profit_price,
                metadata={"engine_type": engine_type.value, "partial_fill": True},
            )
        else:
            # Update existing position
            position = engine_positions[symbol]
            total_cost = (position.entry_price * position.amount) + (
                fill_price * fill_amount
            )
            total_amount = position.amount + fill_amount

            position.entry_price = total_cost / total_amount
            position.amount = total_amount
            if order.stop_loss_price:
                position.stop_loss_price = order.stop_loss_price

        # Also update global positions
        self.positions[symbol] = engine_positions[symbol]

    async def _update_position_for_partial_sell(
        self,
        engine_type: EngineType,
        order: Order,
        fill_amount: Decimal,
        fill_price: Decimal,
    ):
        """Update position tracking after a partial sell fill.

        Args:
            engine_type: The engine type
            order: The order being partially filled
            fill_amount: Amount filled in this update
            fill_price: Price of the fill
        """
        symbol = order.symbol
        engine_positions = self.engine_positions[engine_type]

        if symbol not in engine_positions:
            # No existing position - nothing to update for a sell
            logger.warning(
                "trading_engine.partial_sell_no_position",
                symbol=symbol,
                engine=engine_type.value,
            )
            return

        position = engine_positions[symbol]

        # Calculate realized PnL for the partial close
        realized_pnl = position.calculate_unrealized_pnl(fill_price) * (
            fill_amount / position.amount
        )

        # Update position amount
        position.amount -= fill_amount
        position.realized_pnl += realized_pnl

        # If position is now fully closed, remove it
        if position.amount <= 0:
            position.amount = Decimal("0")
            position.side = PositionSide.NONE
            position.closed_at = datetime.now(timezone.utc)

            # Create trade record for the full position close
            pnl_pct = position.calculate_pnl_percentage(fill_price)
            trade = Trade(
                symbol=symbol,
                side=(
                    OrderSide.BUY
                    if position.side == PositionSide.LONG
                    else OrderSide.SELL
                ),
                amount=fill_amount,
                entry_price=position.entry_price,
                exit_price=fill_price,
                realized_pnl=realized_pnl,
                realized_pnl_pct=pnl_pct,
                strategy_name=order.metadata.get("strategy_name", ""),
                engine_type=engine_type,
                close_reason="partial_fill_complete",
            )
            self._trades.append(trade)
            await self.database.save_trade(trade)

            # Remove position
            del engine_positions[symbol]
            if symbol in self.positions:
                del self.positions[symbol]
            await self.database.delete_position(symbol)

        # Update risk manager with realized PnL
        self.risk_manager.update_pnl(realized_pnl)

    async def _on_order_filled(self, order: Order):
        """Handle filled order."""
        order.filled_at = datetime.now(timezone.utc)

        # Get engine type from metadata
        engine_type_str = order.metadata.get("engine_type", "CORE_HODL")
        try:
            engine_type = EngineType(engine_type_str.lower().replace("_", "_"))
        except ValueError:
            engine_type = EngineType.CORE_HODL

        # Notify strategy
        strategy_name = order.metadata.get("strategy_name", "")
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
                order.average_price or order.price or Decimal("0"),
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
        self.engine_states[engine_type].last_trade_time = datetime.now(timezone.utc)

        # Save state after significant event (order fill)
        await self._save_state()

        logger.info(
            "trading_engine.order_filled",
            engine=engine_type.value,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side.value,
            amount=str(order.filled_amount or order.amount),
            price=str(order.average_price) if order.average_price else None,
        )

    async def _update_position_for_buy(self, engine_type: EngineType, order: Order):
        """Update position tracking after a buy order."""
        symbol = order.symbol
        engine_positions = self.engine_positions[engine_type]

        # Get fill price - use average_price first, then price, then fetch current market price
        fill_price = order.average_price or order.price
        if not fill_price or fill_price <= 0:
            # Fallback: fetch current market price from exchange
            try:
                ticker = await self.exchange.get_ticker(symbol)
                fill_price = Decimal(str(ticker["last"]))
                logger.warning(
                    "trading_engine.using_market_price_fallback",
                    symbol=symbol,
                    order_id=order.id,
                    fill_price=str(fill_price),
                )
            except Exception as e:
                logger.error(
                    "trading_engine.failed_to_get_fill_price",
                    symbol=symbol,
                    order_id=order.id,
                    error=str(e),
                )
                # Cannot create/update position without a valid price
                return

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
                metadata={"engine_type": engine_type.value},
            )
        else:
            # Update existing position (DCA)
            position = engine_positions[symbol]
            total_cost = (position.entry_price * position.amount) + (
                fill_price * fill_amount
            )
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

        # Get fill price - use average_price first, then price, then fetch current market price
        fill_price = order.average_price or order.price
        if not fill_price or fill_price <= 0:
            # Fallback: fetch current market price from exchange
            try:
                ticker = await self.exchange.get_ticker(symbol)
                fill_price = Decimal(str(ticker["last"]))
                logger.warning(
                    "trading_engine.using_market_price_fallback",
                    symbol=symbol,
                    order_id=order.id,
                    fill_price=str(fill_price),
                )
            except Exception as e:
                logger.error(
                    "trading_engine.failed_to_get_fill_price",
                    symbol=symbol,
                    order_id=order.id,
                    error=str(e),
                )
                # Cannot calculate PnL without a valid price - use position's entry price
                # (this will result in 0 PnL, which is safer than using 0)
                fill_price = position.entry_price

        # Calculate PnL
        realized_pnl = position.calculate_unrealized_pnl(fill_price)
        pnl_pct = position.calculate_pnl_percentage(fill_price)

        # Update risk manager
        self.risk_manager.update_pnl(realized_pnl)

        # Create trade record
        trade = Trade(
            symbol=symbol,
            side=(
                OrderSide.BUY if position.side == PositionSide.LONG else OrderSide.SELL
            ),
            amount=position.amount,
            entry_price=position.entry_price,
            exit_price=fill_price,
            realized_pnl=realized_pnl,
            realized_pnl_pct=pnl_pct,
            strategy_name=order.metadata.get("strategy_name", ""),
            engine_type=engine_type,
            close_reason=order.metadata.get("close_reason", "signal"),
        )
        self._trades.append(trade)
        await self.database.save_trade(trade)

        # Notify strategy
        strategy_name = order.metadata.get("strategy_name", "")
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
                exposure_pct=str(self.portfolio.exposure_pct),
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
            state.current_allocation_pct = (
                (position_value / total * 100) if total > 0 else Decimal("0")
            )

            # Check for significant drift (potential rebalance needed)
            actual_pct = position_value / total if total > 0 else Decimal("0")
            drift = (
                abs(actual_pct - target_allocation) / target_allocation
                if target_allocation > 0
                else Decimal("0")
            )

            if drift > Decimal("0.20"):  # 20% drift from target
                logger.warning(
                    "trading_engine.allocation_drift",
                    engine=engine_type.value,
                    target=float(target_allocation),
                    actual=float(actual_pct),
                    drift=float(drift),
                )

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
                engine_type_str = pos.metadata.get("engine_type", "CORE_HODL")
                try:
                    engine_type = EngineType(engine_type_str)
                except ValueError:
                    engine_type = EngineType.CORE_HODL

                self.engine_positions[engine_type][pos.symbol] = pos

            # Load pending orders (critical for partial fill recovery on restart)
            pending_orders = await self.database.get_open_orders()
            for order in pending_orders:
                # Only load orders that are still active
                if order.status in (
                    OrderStatus.PENDING,
                    OrderStatus.OPEN,
                    OrderStatus.PARTIALLY_FILLED,
                ):
                    self.pending_orders[order.id] = order
                    logger.debug(
                        "trading_engine.pending_order_loaded",
                        order_id=order.id,
                        symbol=order.symbol,
                        status=order.status.value,
                        filled_amount=str(order.filled_amount),
                    )

            # Load engine states if available (optional)
            if hasattr(self.database, "get_engine_states"):
                saved_states = await self.database.get_engine_states()
                for engine_type, state_data in saved_states.items():
                    if engine_type in self.engine_states:
                        # Update with saved values
                        for key, value in state_data.items():
                            if hasattr(self.engine_states[engine_type], key):
                                setattr(self.engine_states[engine_type], key, value)

            logger.info(
                "trading_engine.state_loaded",
                positions=len(positions),
                pending_orders=len(self.pending_orders),
                engines=len(self.engine_states),
            )
        except Exception as e:
            logger.error("trading_engine.state_load_error", error=str(e))

    async def _sync_positions_from_exchange(self):
        """
        Sync positions from Bybit exchange to catch positions not in database.

        This is critical when:
        - Database was cleared but positions exist on exchange
        - Positions were created manually or by another instance
        - Restarting after a crash

        Also updates strategy's last_purchase time from order history.
        """
        logger.info("trading_engine.syncing_positions_from_exchange")

        try:
            # Get balance for CORE_HODL subaccount
            balance = await self.exchange.fetch_balance("CORE_HODL")

            for symbol, amount in balance.get("total", {}).items():
                # Skip USDT (quote currency) and zero balances
                if symbol == "USDT" or not amount or amount <= 0:
                    continue

                # Convert amount to Decimal immediately
                amount_decimal = Decimal(str(amount))

                # Convert symbol format if needed (BTC -> BTCUSDT)
                trading_symbol = f"{symbol}USDT"

                # Check if we already track this position
                if trading_symbol in self.engine_positions[EngineType.CORE_HODL]:
                    logger.debug(
                        "trading_engine.position_already_tracked",
                        symbol=trading_symbol,
                        amount=amount,
                    )
                    continue

                # Get current price to calculate position value
                try:
                    ticker = await self.exchange.get_ticker(trading_symbol)
                    current_price = Decimal(str(ticker.get("last", 0)))

                    if current_price <= 0:
                        logger.warning(
                            "trading_engine.sync_no_price", symbol=trading_symbol
                        )
                        continue

                    # Calculate position value for dust check
                    position_value = amount_decimal * current_price

                    # Skip dust amounts (less than $1.0 worth)
                    if position_value < Decimal("1.0"):
                        logger.debug(
                            "trading_engine.skipping_dust_amount",
                            symbol=trading_symbol,
                            amount=str(amount_decimal),
                            value_usd=str(position_value),
                        )
                        continue

                    # Create position record
                    from src.core.models import Position, PositionSide

                    position = Position(
                        symbol=trading_symbol,
                        side=PositionSide.LONG,
                        entry_price=current_price,  # Use current price as estimate
                        amount=amount_decimal,
                        opened_at=datetime.now(timezone.utc),
                        metadata={
                            "engine_type": "CORE_HODL",
                            "synced_from_exchange": True,
                        },
                    )

                    # Add to engine positions
                    self.engine_positions[EngineType.CORE_HODL][
                        trading_symbol
                    ] = position
                    self.positions[trading_symbol] = position

                    # Save to database
                    await self.database.save_position(position)

                    logger.info(
                        "trading_engine.position_synced",
                        symbol=trading_symbol,
                        amount=str(amount_decimal),
                        value=float(position_value),
                    )

                except Exception as e:
                    logger.warning(
                        "trading_engine.sync_position_error",
                        symbol=trading_symbol,
                        error=str(e),
                    )

            # Try to get last order time for DCA strategies
            await self._sync_last_purchase_from_orders()

        except Exception as e:
            logger.error("trading_engine.sync_positions_error", error=str(e))

    async def _sync_last_purchase_from_orders(self):
        """
        Fetch recent orders from exchange to set last_purchase times for DCA strategies.

        This prevents immediate re-buying when positions already exist.
        Only sets last_purchase if there are actual positions synced from exchange.
        """
        try:
            # Check if we have any positions synced from exchange
            core_hodl_positions = self.engine_positions.get(EngineType.CORE_HODL, {})

            if not core_hodl_positions:
                # No positions exist - this is a fresh start
                # Don't set last_purchase, let strategy generate initial buy signals
                logger.info(
                    "trading_engine.no_positions_fresh_start",
                    message="No existing positions, allowing immediate buy signals",
                )
                return

            # We have existing positions - set last_purchase to prevent immediate rebuy
            for engine_type, strategies in self.engines.items():
                for strategy in strategies:
                    if hasattr(strategy, "last_purchase"):
                        # Set last_purchase to now so DCA waits proper interval
                        from datetime import datetime

                        for symbol in strategy.symbols:
                            if symbol not in strategy.last_purchase:
                                # Only set if not already set (from database)
                                # Only set if we have a position for this symbol
                                if symbol in core_hodl_positions:
                                    strategy.last_purchase[symbol] = datetime.now(
                                        timezone.utc
                                    )
                                    logger.info(
                                        "trading_engine.last_purchase_synced",
                                        symbol=symbol,
                                        strategy=strategy.name,
                                        next_purchase_in_hours=strategy.interval_hours,
                                    )

        except Exception as e:
            logger.warning("trading_engine.sync_orders_error", error=str(e))

    async def _save_state(self):
        """Save state to database."""
        import json
        from datetime import datetime
        from decimal import Decimal

        def custom_encoder(obj):
            """JSON encoder that handles Decimal and datetime types."""
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        try:
            # Save engine states (optional)
            if hasattr(self.database, "save_engine_state"):
                for engine_type, state in self.engine_states.items():
                    await self.database.save_engine_state(
                        engine_name=engine_type.value,
                        state=json.dumps(state.model_dump(), default=custom_encoder),
                        allocation_pct=float(state.current_allocation_pct),
                    )

            # Save full engine states for all engines with strategies
            for engine_type, engines in self.engines.items():
                for engine in engines:
                    # Check if engine supports full state persistence
                    if hasattr(engine, "get_full_state"):
                        try:
                            full_state = engine.get_full_state()
                            await self.database.save_full_engine_state(
                                engine_name=engine_type.value, state=full_state
                            )
                            logger.debug(
                                "trading_engine.engine_state_saved",
                                engine=engine_type.value,
                            )
                        except Exception as e:
                            logger.error(
                                "trading_engine.engine_state_save_failed",
                                engine=engine_type.value,
                                error=str(e),
                            )

            logger.info("trading_engine.state_saved")
        except Exception as e:
            logger.error("trading_engine.state_save_error", error=str(e))

    async def _process_failed_orders(self):
        """
        Retry failed orders after delay.

        Processes the failed_orders queue and attempts to retry orders
        that have exceeded the retry delay. Orders are retried up to
        MAX_ORDER_RETRIES times before being permanently failed.
        """
        now = datetime.now(timezone.utc)

        for order_id, (order, retry_count, failed_at) in list(
            self.failed_orders.items()
        ):
            # Check if max retries exceeded
            if retry_count >= self.MAX_ORDER_RETRIES:
                logger.error(
                    "trading_engine.order_max_retries",
                    order_id=order_id,
                    symbol=order.symbol,
                    retries=retry_count,
                )
                # Update order status to rejected
                order.status = OrderStatus.REJECTED
                order.updated_at = now
                await self.database.save_order(order)
                del self.failed_orders[order_id]
                continue

            # Check if retry delay has passed
            delay_minutes = (now - failed_at).total_seconds() / 60
            if delay_minutes >= self.ORDER_RETRY_DELAY_MINUTES:
                logger.info(
                    "trading_engine.retrying_order",
                    order_id=order_id,
                    symbol=order.symbol,
                    attempt=retry_count + 1,
                    max_retries=self.MAX_ORDER_RETRIES,
                )

                success = await self._retry_order(order)

                if success:
                    logger.info(
                        "trading_engine.order_retry_success",
                        order_id=order_id,
                        symbol=order.symbol,
                    )
                    del self.failed_orders[order_id]
                else:
                    # Update retry count and timestamp
                    self.failed_orders[order_id] = (order, retry_count + 1, now)
                    logger.warning(
                        "trading_engine.order_retry_failed",
                        order_id=order_id,
                        symbol=order.symbol,
                        next_attempt=(
                            retry_count + 2
                            if retry_count + 1 < self.MAX_ORDER_RETRIES
                            else None
                        ),
                    )

    async def _retry_order(self, order: Order) -> bool:
        """
        Attempt to retry a failed order.

        Args:
            order: The order to retry

        Returns:
            True if retry was successful, False otherwise
        """
        try:
            # Get subaccount from metadata
            subaccount = order.metadata.get("subaccount")
            if not subaccount:
                # Try to get from engine_type mapping
                engine_type_str = order.metadata.get("engine_type", "CORE_HODL")
                try:
                    engine_type = EngineType(engine_type_str)
                    subaccount = self.ENGINE_TO_SUBACCOUNT.get(
                        engine_type, SubAccountType.CORE_HODL
                    ).value
                except ValueError:
                    subaccount = SubAccountType.CORE_HODL.value

            # Create the order again
            new_order = await self.exchange.create_order(
                subaccount=subaccount,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                amount=order.amount,
                price=order.price,
                params={
                    "engine_type": order.metadata.get("engine_type"),
                    "strategy_name": order.metadata.get("strategy_name"),
                    "retry_of": order.id,
                },
            )

            # Copy metadata from original order
            new_order.stop_loss_price = order.stop_loss_price
            new_order.take_profit_price = order.take_profit_price
            new_order.metadata = order.metadata.copy()
            new_order.metadata["is_retry"] = True
            new_order.metadata["original_order_id"] = order.id

            # Track the new order
            self.pending_orders[new_order.id] = new_order
            await self.database.save_order(new_order)

            logger.info(
                "trading_engine.order_retry_created",
                original_order_id=order.id,
                new_order_id=new_order.id,
                symbol=order.symbol,
            )

            return True

        except ccxt.InsufficientFunds as e:
            logger.error(
                "trading_engine.retry_insufficient_funds",
                order_id=order.id,
                symbol=order.symbol,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "trading_engine.retry_error",
                order_id=order.id,
                symbol=order.symbol,
                error=str(e),
            )
            return False

    async def _detect_orphan_orders(self):
        """
        Find orders on exchange not tracked by bot.

        Orphan orders can occur when:
        - Orders were created before bot restart
        - Orders failed to save to database
        - Orders were created manually on exchange

        Orphan orders are added to pending_orders for tracking.
        """
        for engine_type in EngineType:
            subaccount = self.ENGINE_TO_SUBACCOUNT[engine_type].value

            try:
                # Fetch open orders from exchange
                exchange_orders = await self.exchange.get_open_orders(
                    subaccount=subaccount
                )

                # Get set of tracked order IDs
                tracked_ids = set(self.pending_orders.keys())

                for ex_order in exchange_orders:
                    # Check if this order is already tracked
                    order_id = ex_order.id
                    exchange_order_id = ex_order.exchange_order_id

                    # Skip if already tracked by internal ID
                    if order_id in tracked_ids:
                        continue

                    # Skip if already tracked by exchange order ID
                    if exchange_order_id and any(
                        po.exchange_order_id == exchange_order_id
                        for po in self.pending_orders.values()
                    ):
                        continue

                    logger.warning(
                        "trading_engine.orphan_order_detected",
                        order_id=order_id,
                        exchange_order_id=exchange_order_id,
                        symbol=ex_order.symbol,
                        side=ex_order.side.value,
                        amount=str(ex_order.amount),
                        subaccount=subaccount,
                    )

                    # Add to pending orders for tracking
                    ex_order.metadata["is_orphan"] = True
                    ex_order.metadata["detected_at"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                    ex_order.metadata["subaccount"] = subaccount
                    ex_order.metadata["engine_type"] = engine_type.value

                    self.pending_orders[order_id] = ex_order
                    await self.database.save_order(ex_order)

                    logger.info(
                        "trading_engine.orphan_order_tracked",
                        order_id=order_id,
                        symbol=ex_order.symbol,
                    )

            except Exception as e:
                logger.error(
                    "trading_engine.orphan_detection_failed",
                    engine=engine_type.value,
                    subaccount=subaccount,
                    error=str(e),
                )

    async def _cleanup_stuck_orders(self):
        """
        Cancel orders stuck for too long.

        Orders that remain open for longer than STUCK_ORDER_HOURS
        are considered "stuck" and will be cancelled to free up capital.
        """
        now = datetime.now(timezone.utc)

        for order_id, order in list(self.pending_orders.items()):
            # Calculate order age
            created_at = order.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            age_hours = (now - created_at).total_seconds() / 3600

            if age_hours > self.STUCK_ORDER_HOURS:
                logger.warning(
                    "trading_engine.canceling_stuck_order",
                    order_id=order_id,
                    symbol=order.symbol,
                    age_hours=round(age_hours, 2),
                    max_hours=self.STUCK_ORDER_HOURS,
                )

                try:
                    # Get subaccount from order metadata
                    subaccount = order.metadata.get("subaccount", "CORE_HODL")

                    # Cancel the order
                    await self.exchange.cancel_order(
                        order_id=order.exchange_order_id or order_id,
                        subaccount=subaccount,
                        symbol=order.symbol,
                    )

                    # Update order status
                    order.status = OrderStatus.CANCELLED
                    order.updated_at = now
                    await self.database.save_order(order)

                    # Remove from pending
                    del self.pending_orders[order_id]

                    logger.info(
                        "trading_engine.stuck_order_cancelled",
                        order_id=order_id,
                        symbol=order.symbol,
                        age_hours=round(age_hours, 2),
                    )

                except ccxt.OrderNotFound:
                    # Order already cancelled or filled
                    logger.warning(
                        "trading_engine.stuck_order_not_found",
                        order_id=order_id,
                        symbol=order.symbol,
                    )
                    # Update status and remove
                    order.status = OrderStatus.CANCELLED
                    order.updated_at = now
                    await self.database.save_order(order)
                    del self.pending_orders[order_id]

                except Exception as e:
                    logger.error(
                        "trading_engine.stuck_order_cleanup_failed",
                        order_id=order_id,
                        symbol=order.symbol,
                        error=str(e),
                    )

    async def _create_order_with_retry(
        self,
        order_params: dict,
        order_metadata: dict,
        engine_type: EngineType,
        symbol: str,
    ) -> Optional[Order]:
        """
        Create an order with retry logic for temporary failures.

        Args:
            order_params: Parameters for exchange.create_order()
            order_metadata: Metadata to store with the order
            engine_type: The engine creating the order
            symbol: The trading symbol

        Returns:
            Order object if successful, None if failed/retry queued
        """
        try:
            # Attempt to create the order
            order = await self.exchange.create_order(**order_params)
            return order

        except ccxt.InsufficientFunds as e:
            # Permanent failure - don't retry
            logger.error(
                "trading_engine.insufficient_funds",
                engine=engine_type.value,
                symbol=symbol,
                error=str(e),
            )
            # Don't add to retry queue - this is a permanent failure
            return None

        except ccxt.InvalidOrder as e:
            # Permanent failure - bad order parameters
            logger.error(
                "trading_engine.invalid_order",
                engine=engine_type.value,
                symbol=symbol,
                error=str(e),
            )
            return None

        except (ccxt.NetworkError, ccxt.ExchangeError, ccxt.RequestTimeout) as e:
            # Temporary failure - add to retry queue
            logger.warning(
                "trading_engine.order_failed_temporarily",
                engine=engine_type.value,
                symbol=symbol,
                error_type=type(e).__name__,
                error=str(e),
            )

            # Create a placeholder order for retry tracking
            placeholder_order = Order(
                symbol=symbol,
                side=order_params["side"],
                order_type=order_params["order_type"],
                amount=order_params["amount"],
                price=order_params["price"],
                status=OrderStatus.PENDING,
                metadata=order_metadata,
            )

            # Add to retry queue
            self.failed_orders[placeholder_order.id] = (
                placeholder_order,
                0,
                datetime.now(timezone.utc),
            )

            logger.info(
                "trading_engine.order_queued_for_retry",
                order_id=placeholder_order.id,
                engine=engine_type.value,
                symbol=symbol,
                retry_delay_minutes=self.ORDER_RETRY_DELAY_MINUTES,
            )

            return None

        except Exception as e:
            # Unknown error - log and don't retry
            logger.error(
                "trading_engine.order_failed",
                engine=engine_type.value,
                symbol=symbol,
                error_type=type(e).__name__,
                error=str(e),
            )
            return None

    async def _run_order_maintenance(self):
        """
        Run periodic order maintenance tasks.

        This includes:
        - Detecting orphan orders
        - Cleaning up stuck orders
        - Processing failed orders for retry
        """
        now = datetime.now(timezone.utc)

        # Check if it's time for orphan detection
        if (
            self._last_orphan_check is None
            or (now - self._last_orphan_check).total_seconds()
            >= self.ORPHAN_CHECK_INTERVAL
        ):

            logger.debug("trading_engine.running_order_maintenance")

            await self._detect_orphan_orders()
            await self._cleanup_stuck_orders()
            await self._process_failed_orders()

            self._last_orphan_check = now

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

        logger.warning(
            "trading_engine.resetting_emergency_stop", authorized_by=authorized_by
        )

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
        # Calculate exchange health info
        exchange_downtime = self._get_exchange_downtime_seconds()

        status = {
            "system": {
                "running": self._running,
                "emergency_stop": self._emergency_stop,
                "emergency_reason": self._emergency_reason,
                "paper_mode": engine_config.is_paper_trading,
                "demo_mode": engine_config.is_demo_mode,
                "exchange_health": {
                    "circuit_breaker": self.exchange_circuit_breaker,
                    "down_since": (
                        self.exchange_down_since.isoformat()
                        if self.exchange_down_since
                        else None
                    ),
                    "downtime_seconds": int(exchange_downtime),
                    "consecutive_errors": self._consecutive_network_errors,
                },
            },
            "portfolio": (
                {
                    "total": (
                        str(self.portfolio.total_balance) if self.portfolio else None
                    ),
                    "available": (
                        str(self.portfolio.available_balance)
                        if self.portfolio
                        else None
                    ),
                    "exposure_pct": (
                        str(self.portfolio.exposure_pct) if self.portfolio else None
                    ),
                    "all_time_high": (
                        str(self.portfolio.all_time_high) if self.portfolio else None
                    ),
                    "current_drawdown_pct": (
                        str(self.portfolio.current_drawdown_pct)
                        if self.portfolio
                        else None
                    ),
                }
                if self.portfolio
                else None
            ),
            "engines": {},
            "positions": {
                symbol: {
                    "side": pos.side.value,
                    "amount": str(pos.amount),
                    "entry_price": str(pos.entry_price),
                    "unrealized_pnl": str(pos.unrealized_pnl),
                }
                for symbol, pos in self.positions.items()
            },
            "pending_orders": len(self.pending_orders),
            "circuit_breaker": (
                self.risk_manager.get_circuit_breaker_actions()
                if self.risk_manager
                else None
            ),
            "risk": (
                self.risk_manager.get_risk_report(self.portfolio)
                if self.risk_manager and self.portfolio
                else None
            ),
            "performance": {
                "signals_processed": self._signals_processed,
                "signals_executed": self._signals_executed,
                "execution_rate": (
                    self._signals_executed / self._signals_processed * 100
                    if self._signals_processed > 0
                    else 0
                ),
                "total_trades": len(self._trades),
                "recent_trades": [
                    {
                        "symbol": t.symbol,
                        "pnl": str(t.net_pnl),
                        "pnl_pct": str(t.realized_pnl_pct),
                        "engine": t.engine_type.value if t.engine_type else None,
                    }
                    for t in self._trades[-10:]
                ],
            },
        }

        # Add engine-specific status
        for engine_type, state in self.engine_states.items():
            engine_strategies = self.engines.get(engine_type, [])
            status["engines"][engine_type.value] = {
                "is_active": state.is_active,
                "can_trade": state.can_trade,
                "is_paused": state.is_paused,
                "pause_reason": state.pause_reason,
                "allocation_pct": float(self.ALLOCATION[engine_type]),
                "current_value": str(state.current_value),
                "current_allocation_pct": str(state.current_allocation_pct),
                "total_trades": state.total_trades,
                "winning_trades": state.winning_trades,
                "losing_trades": state.losing_trades,
                "win_rate": float(state.win_rate),
                "total_pnl": str(state.total_pnl),
                "max_drawdown_pct": str(state.max_drawdown_pct),
                "circuit_breaker_level": state.circuit_breaker_level.value,
                "strategies": [
                    {
                        "name": s.name,
                        "is_active": s.is_active,
                        "symbols": s.symbols,
                        "stats": s.get_stats(),
                    }
                    for s in engine_strategies
                ],
                "positions": [
                    {
                        "symbol": pos.symbol,
                        "side": pos.side.value,
                        "amount": str(pos.amount),
                        "entry_price": str(pos.entry_price),
                    }
                    for pos in self.engine_positions.get(engine_type, {}).values()
                ],
            }

        return status

    def get_system_state(self) -> SystemState:
        """
        Get complete system state snapshot.

        Returns:
            SystemState model with all current state
        """
        return SystemState(
            timestamp=datetime.now(timezone.utc),
            portfolio=self.portfolio
            or Portfolio(total_balance=Decimal("0"), available_balance=Decimal("0")),
            engines=self.engine_states,
            positions=self.positions,
            orders=list(self.pending_orders.values()),
            circuit_breaker_level=(
                self.risk_manager.circuit_breaker.level
                if self.risk_manager
                else CircuitBreakerLevel.NONE
            ),
            is_trading_halted=self._emergency_stop,
        )

    def pause_engine(
        self,
        engine_type: EngineType,
        reason: str,
        duration_seconds: Optional[int] = None,
    ):
        """
        Pause a specific engine.

        Args:
            engine_type: The engine to pause
            reason: Why the engine is being paused
            duration_seconds: Auto-resume duration (None for indefinite)
        """
        if engine_type in self.engine_states:
            self.engine_states[engine_type].pause(reason, duration_seconds)
            logger.info(
                "trading_engine.engine_paused",
                engine=engine_type.value,
                reason=reason,
                duration=duration_seconds,
            )

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
        logger.info(
            "trading_engine.strategy_added",
            engine=engine_type.value,
            strategy=strategy.name,
        )


# =============================================================================
# Factory Functions
# =============================================================================


def create_trading_engine(
    exchange: Optional[ByBitClient] = None,
    risk_manager: Optional[RiskManager] = None,
    database: Optional[Database] = None,
    strategies: Optional[Dict[EngineType, List[BaseStrategy]]] = None,
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
        strategies=strategies or {},
    )
