"""
The Eternal Engine - Main Entry Point

A 4-strategy autonomous trading system designed for long-term capital compounding.

Usage:
    # Check configuration
    python main.py --check
    
    # Run in paper mode with DEMO keys (testnet)
    python main.py --mode paper --demo
    
    # Run only CORE-HODL engine
    python main.py --engine core
    
    # Run only TREND engine with PROD keys (read-only)
    python main.py --engine trend --prod
    
    # Show system status
    python main.py --status
    
    # Initialize database
    python main.py --init-db
    
    # Run backtest
    python main.py --backtest --engine core
"""

import argparse
import asyncio
import signal
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import structlog

from src.core.config import (bybit_config, database_config, engine_config,
                             notification_config, trading_config)
from src.core.engine import TradingEngine
from src.core.models import EngineType
from src.exchange.bybit_client import ByBitClient, SubAccountType
from src.risk.risk_manager import RiskManager
from src.storage.database import Database
from src.strategies.dca_strategy import DCAStrategy
from src.strategies.grid_strategy import GridStrategy
from src.utils.logging_config import setup_logging

logger = structlog.get_logger(__name__)


class TradingBot:
    """
    Main trading bot application for The Eternal Engine.

    Manages the 4-engine trading system:
    - CORE-HODL (60%): Long-term BTC/ETH accumulation with DCA
    - TREND (20%): Crisis alpha through trend following
    - FUNDING (15%): Market-neutral funding rate arbitrage
    - TACTICAL (5%): Extreme value deployment during crashes
    """

    # Engine name mappings
    ENGINE_NAMES = {
        "core": "CORE-HODL",
        "trend": "TREND",
        "funding": "FUNDING",
        "tactical": "TACTICAL",
        "all": "ALL",
    }

    def __init__(self, engine_filter: Optional[str] = None):
        """
        Initialize the trading bot.

        Args:
            engine_filter: Which engine to run (core, trend, funding, tactical, all)
        """
        self.engine_filter = engine_filter or "all"
        self.engine_name = self.ENGINE_NAMES.get(self.engine_filter, "ALL")

        # Components
        self.engine: Optional[TradingEngine] = None
        self.exchange: Optional[ByBitClient] = None
        self.risk_manager: Optional[RiskManager] = None
        self.database: Optional[Database] = None

        # State
        self._shutdown_event = asyncio.Event()
        self._initialized = False

    async def initialize(self):
        """Initialize all components based on configuration."""
        logger.info(
            "bot.initializing",
            engine_filter=self.engine_filter,
            api_mode=engine_config.bybit.api_mode,
            trading_mode=engine_config.trading_mode.trading_mode,
        )

        # Initialize database
        self.database = Database()
        await self.database.initialize()
        logger.info("bot.database_initialized")

        # Initialize exchange client
        self.exchange = ByBitClient()
        await self.exchange.initialize(testnet=engine_config.bybit.testnet)
        logger.info("bot.exchange_initialized", api_mode=engine_config.bybit.api_mode)

        # Initialize risk manager
        self.risk_manager = RiskManager()
        logger.info("bot.risk_manager_initialized")

        # Initialize strategies based on engine filter
        strategies_by_engine = await self._initialize_strategies()

        if not strategies_by_engine:
            logger.warning("bot.no_strategies_loaded", engine_filter=self.engine_filter)
        else:
            total_strategies = sum(len(s) for s in strategies_by_engine.values())
            logger.info(
                "bot.strategies_loaded",
                count=total_strategies,
                engines=list(strategies_by_engine.keys()),
                names=[
                    s.name
                    for strategies in strategies_by_engine.values()
                    for s in strategies
                ],
            )

        # Create trading engine (orchestrator) with strategies organized by engine
        self.engine = TradingEngine(
            exchange=self.exchange,
            risk_manager=self.risk_manager,
            database=self.database,
            strategies=strategies_by_engine,
        )

        self._initialized = True
        logger.info("bot.initialized")

    async def _initialize_strategies(self) -> Dict[EngineType, List]:
        """
        Initialize strategies based on engine filter.

        Returns:
            Dict mapping EngineType to list of strategy instances
        """
        from src.core.models import EngineType

        strategies_by_engine: Dict[EngineType, List] = {}

        # CORE-HODL Engine (DCAStrategy)
        if self.engine_filter in ("core", "all"):
            if engine_config.core_hodl.enabled:
                dca = DCAStrategy(
                    name="CORE-HODL",
                    symbols=engine_config.trading_mode.core_hodl_symbols,
                    interval_hours=engine_config.core_hodl.dca_interval_hours,
                    amount_usdt=Decimal(str(engine_config.core_hodl.dca_amount_usdt)),
                )
                strategies_by_engine[EngineType.CORE_HODL] = [dca]
                logger.info(
                    "bot.core_hodl_loaded",
                    symbols=dca.symbols,
                    interval=dca.interval_hours,
                    amount=str(dca.base_amount_usdt),
                )
            else:
                logger.info("bot.core_hodl_disabled")

        # TACTICAL Engine (GridStrategy - partial implementation)
        if self.engine_filter in ("tactical", "all"):
            if engine_config.tactical.enabled:
                grid = GridStrategy(
                    name="TACTICAL",
                    symbols=engine_config.trading_mode.default_symbols,
                    grid_levels=engine_config.tactical.grid_levels,
                    grid_spacing_pct=engine_config.tactical.grid_spacing_pct,
                )
                strategies_by_engine[EngineType.TACTICAL] = [grid]
                logger.info(
                    "bot.tactical_loaded",
                    symbols=grid.symbols,
                    levels=grid.grid_levels,
                    spacing=grid.grid_spacing_pct,
                )
            else:
                logger.info("bot.tactical_disabled")

        # TREND Engine (not yet fully implemented - placeholder)
        if self.engine_filter in ("trend", "all"):
            if engine_config.trend.enabled:
                logger.info("bot.trend_enabled_but_not_implemented")
                # TODO: Implement TrendStrategy
            else:
                logger.info("bot.trend_disabled")

        # FUNDING Engine (not yet fully implemented - placeholder)
        if self.engine_filter in ("funding", "all"):
            if engine_config.funding.enabled:
                logger.info("bot.funding_enabled_but_not_implemented")
                # TODO: Implement FundingStrategy
            else:
                logger.info("bot.funding_disabled")

        return strategies_by_engine

    async def run(self):
        """Run the main trading loop."""
        if not self._initialized:
            raise RuntimeError("Bot not initialized. Call initialize() first.")

        logger.info(
            "bot.starting",
            trading_mode=engine_config.trading_mode.trading_mode,
            engine=self.engine_name,
            api_mode=engine_config.bybit.api_mode,
            read_only=engine_config.bybit.is_read_only,
        )

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._signal_handler)

        try:
            # Start the trading engine
            await self.engine.start()

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error("bot.error", error=str(e), exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Perform graceful shutdown."""
        logger.info("bot.shutting_down")

        if self.engine:
            await self.engine.stop()

        if self.exchange:
            await self.exchange.close()

        if self.database:
            await self.database.close()

        logger.info("bot.shutdown_complete")

    def _signal_handler(self):
        """Handle shutdown signals."""
        logger.info("bot.shutdown_signal_received")
        self._shutdown_event.set()

    async def get_status(self) -> Dict:
        """
        Get comprehensive system status.

        Returns:
            Dictionary containing system status information
        """
        if not self._initialized or not self.engine:
            return {"status": "not_initialized"}

        # Get engine status from trading engine
        engine_status = self.engine.get_status()

        # Get circuit breaker status
        cb_status = {
            "level": self.risk_manager.circuit_breaker.level.name,
            "triggered_at": (
                self.risk_manager.circuit_breaker.triggered_at.isoformat()
                if self.risk_manager.circuit_breaker.triggered_at
                else None
            ),
            "emergency_stop": self.risk_manager.emergency_stop,
        }

        # Get recent trades from database
        recent_trades = await self.database.get_trades(limit=5) if self.database else []

        # Get engine states from database
        engine_states = (
            await self.database.get_all_engine_states() if self.database else []
        )

        # Get open positions per engine
        positions = await self.database.get_open_positions() if self.database else []
        positions_by_engine: Dict[str, List] = {}
        for pos in positions:
            engine = (
                pos.metadata.get("engine_name", "unknown")
                if hasattr(pos, "metadata")
                else "unknown"
            )
            if engine not in positions_by_engine:
                positions_by_engine[engine] = []
            positions_by_engine[engine].append(
                {
                    "symbol": pos.symbol,
                    "amount": str(pos.amount),
                    "entry_price": str(pos.entry_price),
                }
            )

        return {
            "status": "running" if engine_status.get("running") else "stopped",
            "timestamp": datetime.utcnow().isoformat(),
            "trading_mode": engine_config.trading_mode.trading_mode,
            "api_mode": engine_config.bybit.api_mode,
            "active_engine": self.engine_name,
            "portfolio": engine_status.get("portfolio", {}),
            "positions": {"total": len(positions), "by_engine": positions_by_engine},
            "pending_orders": engine_status.get("pending_orders", 0),
            "circuit_breaker": cb_status,
            "engine_states": engine_states,
            "recent_trades": [
                {
                    "symbol": t.symbol,
                    "pnl": str(t.realized_pnl),
                    "pnl_pct": str(t.realized_pnl_pct),
                }
                for t in recent_trades
            ],
            "strategies": engine_status.get("strategies", {}),
        }

    async def run_single_engine(self, engine_name: str):
        """
        Run a single engine only.

        Args:
            engine_name: Name of the engine to run (core, trend, funding, tactical)
        """
        if engine_name not in self.ENGINE_NAMES:
            raise ValueError(
                f"Unknown engine: {engine_name}. Valid: {list(self.ENGINE_NAMES.keys())}"
            )

        self.engine_filter = engine_name
        self.engine_name = self.ENGINE_NAMES[engine_name]

        logger.info("bot.running_single_engine", engine=engine_name)

        # Re-initialize with the specific engine
        if self._initialized:
            await self.shutdown()
            self._initialized = False

        await self.initialize()
        await self.run()


def print_banner():
    """Print the startup banner."""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║           🚀 THE ETERNAL ENGINE v1.0.0 🚀                        ║
║                                                                  ║
║     4-Strategy Autonomous Trading System for Bybit              ║
║                                                                  ║
║     CORE-HODL (60%)  |  TREND (20%)  |  FUNDING (15%)  |  TACTICAL (5%)  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def check_configuration() -> Dict:
    """
    Check if configuration is valid.

    Returns:
        Dictionary with validation results
    """
    issues = []
    warnings = []

    # Validate using the new engine_config
    validation = engine_config.validate_configuration()

    if not validation["valid"]:
        issues.extend(validation["issues"])

    # Check trading mode
    if engine_config.is_live_trading:
        warnings.append("⚠️  Running in LIVE trading mode!")
        warnings.append("   Make sure you have:")
        warnings.append("     - Tested thoroughly in paper mode")
        warnings.append("     - Verified API keys have correct permissions")
        warnings.append("     - Set appropriate risk limits in .env")

    # Check API mode
    if engine_config.is_prod_mode:
        warnings.append("⚠️  Using PROD API keys (live environment)")
        if engine_config.bybit.is_read_only:
            warnings.append("   ✓ Read-only mode active")
        else:
            warnings.append("   ⚠️  Trading is ENABLED on live environment!")
    else:
        warnings.append("✓ Using DEMO API keys (testnet)")

    # Check capital allocation
    total_alloc = engine_config.allocation.total_allocation
    if not 0.99 <= total_alloc <= 1.01:
        issues.append(f"Capital allocation sums to {total_alloc:.2%}, should be 100%")

    # Check engine enablement
    enabled_engines = []
    if engine_config.core_hodl.enabled:
        enabled_engines.append("CORE-HODL")
    if engine_config.trend.enabled:
        enabled_engines.append("TREND")
    if engine_config.funding.enabled:
        enabled_engines.append("FUNDING")
    if engine_config.tactical.enabled:
        enabled_engines.append("TACTICAL")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "enabled_engines": enabled_engines,
        "api_mode": engine_config.bybit.api_mode,
        "trading_mode": engine_config.trading_mode.trading_mode,
    }


def print_status(status: Dict):
    """Print formatted status output."""
    print("\n" + "=" * 60)
    print("           THE ETERNAL ENGINE - SYSTEM STATUS")
    print("=" * 60)

    # General status
    print(f"\n📊 System Status: {status.get('status', 'unknown').upper()}")
    print(f"🕐 Timestamp: {status.get('timestamp', 'N/A')}")
    print(f"🎮 Trading Mode: {status.get('trading_mode', 'N/A').upper()}")
    print(f"🔌 API Mode: {status.get('api_mode', 'N/A').upper()}")
    print(f"⚙️  Active Engine: {status.get('active_engine', 'N/A')}")

    # Portfolio
    portfolio = status.get("portfolio", {})
    if portfolio:
        print(f"\n💰 Portfolio:")
        print(f"   Total: {portfolio.get('total', 'N/A')} USDT")
        print(f"   Available: {portfolio.get('available', 'N/A')} USDT")

    # Positions
    positions = status.get("positions", {})
    print(f"\n📈 Positions (Total: {positions.get('total', 0)}):")
    by_engine = positions.get("by_engine", {})
    if by_engine:
        for engine, pos_list in by_engine.items():
            print(f"   {engine}: {len(pos_list)} positions")
            for pos in pos_list:
                print(f"     - {pos['symbol']}: {pos['amount']} @ {pos['entry_price']}")
    else:
        print("   No open positions")

    # Circuit breaker
    cb = status.get("circuit_breaker", {})
    print(f"\n⛔ Circuit Breaker:")
    print(f"   Level: {cb.get('level', 'NONE')}")
    print(f"   Emergency Stop: {cb.get('emergency_stop', False)}")
    if cb.get("triggered_at"):
        print(f"   Triggered At: {cb.get('triggered_at')}")

    # Pending orders
    print(f"\n📝 Pending Orders: {status.get('pending_orders', 0)}")

    # Engine states
    engine_states = status.get("engine_states", [])
    if engine_states:
        print(f"\n🔧 Engine States:")
        for state in engine_states:
            print(
                f"   {state.get('engine_name', 'N/A')}: {state.get('state', 'N/A')} "
                f"({state.get('allocation_pct', 'N/A')}%)"
            )

    # Recent trades
    trades = status.get("recent_trades", [])
    if trades:
        print(f"\n💹 Recent Trades:")
        for trade in trades[:5]:
            pnl = trade.get("pnl", "0")
            print(f"   {trade.get('symbol', 'N/A')}: PnL {pnl} USDT")

    print("\n" + "=" * 60)


async def run_backtest(engine_name: str):
    """
    Run backtest mode for a specific engine.

    Args:
        engine_name: Engine to backtest (core, trend, funding, tactical)
    """
    from src.utils.backtest import BacktestEngine

    logger.info("backtest.starting", engine=engine_name)
    print(f"\n📊 Running backtest for {engine_name.upper()} engine...")
    print("(Note: Backtest functionality is limited in current implementation)")

    # TODO: Implement full backtest logic
    # This is a placeholder showing the structure

    print("\n✓ Backtest complete (placeholder)")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="The Eternal Engine - 4-Strategy Autonomous Trading System"
    )

    # Trading mode
    parser.add_argument(
        "--mode",
        choices=["paper", "demo", "live"],
        help="Trading mode: paper=simulated, demo=Bybit Demo API (fake money), live=real money",
    )

    # API mode
    parser.add_argument(
        "--demo", action="store_true", help="Use DEMO API keys (testnet)"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Use PROD API keys (live, read-only for now)",
    )

    # Engine selection
    parser.add_argument(
        "--engine",
        choices=["core", "trend", "funding", "tactical", "all"],
        default="all",
        help="Run specific engine(s) (default: all)",
    )

    # Actions
    parser.add_argument(
        "--status", action="store_true", help="Show system status and exit"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check configuration and exit"
    )
    parser.add_argument(
        "--init-db", action="store_true", help="Initialize database and exit"
    )
    parser.add_argument("--backtest", action="store_true", help="Run backtest mode")
    parser.add_argument(
        "--reset-emergency",
        action="store_true",
        help="Reset emergency stop (USE WITH CAUTION)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Print banner
    if not args.check and not args.status:
        print_banner()

    # Handle API mode flags
    if args.demo:
        engine_config.bybit.api_mode = "demo"
        engine_config.bybit.testnet = True
        print("✓ DEMO mode selected (testnet)")
    elif args.prod:
        engine_config.bybit.api_mode = "prod"
        engine_config.bybit.testnet = False
        print("✓ PROD mode selected (live environment)")

    # Override trading mode if specified
    if args.mode:
        # Handle demo mode specially
        if args.mode == "demo":
            engine_config.legacy.trading_mode = "live"
            engine_config.trading_mode.trading_mode = "live"
            engine_config.bybit.api_mode = "demo"
            engine_config.bybit.testnet = True
            from src.core.config import trading_config

            trading_config.trading_mode = "live"
            print("✓ DEMO mode selected (live trading on Bybit Demo API)")
            print("  Real market data, fake money - NO REAL FUNDS AT RISK")
        else:
            engine_config.legacy.trading_mode = args.mode
            engine_config.trading_mode.trading_mode = args.mode
            from src.core.config import trading_config

            trading_config.trading_mode = args.mode
            print(f"✓ Trading mode set to: {args.mode.upper()}")

    # Check configuration
    config_check = check_configuration()

    # Print warnings
    for warning in config_check["warnings"]:
        print(warning)

    # Handle --check
    if args.check:
        print("\n" + "=" * 60)
        print("           CONFIGURATION CHECK")
        print("=" * 60)

        if config_check["valid"]:
            print("\n✓ Configuration is valid")
        else:
            print("\n✗ Configuration errors:")
            for issue in config_check["issues"]:
                print(f"   - {issue}")

        print(f"\nAPI Mode: {config_check['api_mode']}")
        print(f"Trading Mode: {config_check['trading_mode']}")
        print(f"Enabled Engines: {', '.join(config_check['enabled_engines'])}")

        print("\n" + "=" * 60)
        return

    # If config is invalid, exit early
    if not config_check["valid"]:
        print("\n✗ Configuration errors:")
        for issue in config_check["issues"]:
            print(f"   - {issue}")
        print("\nPlease check your .env file and try again.")
        return

    # Handle --init-db
    if args.init_db:
        print("\n📦 Initializing database...")
        db = Database()
        await db.initialize()
        print("✓ Database initialized successfully")
        await db.close()
        return

    # Handle --reset-emergency
    if args.reset_emergency:
        print("\n🚨 EMERGENCY STOP RESET")
        print("=" * 60)
        print("WARNING: This will reset the emergency stop state!")
        print("Only do this if you understand why it was triggered.")
        print("=" * 60)

        confirm = input("\nType 'RESET' to confirm: ")
        if confirm != "RESET":
            print("Aborted.")
            return

        # Initialize minimal components to reset
        db = Database()
        await db.initialize()

        # Load and reset risk manager state
        from src.risk.risk_manager import RiskManager

        risk_manager = RiskManager()

        # Get portfolio for initialization
        from src.exchange.bybit_client import ByBitClient

        exchange = ByBitClient()
        await exchange.initialize(testnet=engine_config.bybit.testnet)
        portfolio = await exchange.get_balance()

        await risk_manager.initialize(portfolio)

        # Reset emergency stop
        risk_manager.reset_emergency_stop(authorized_by="manual_cli")

        print("✓ Emergency stop has been reset")
        print("You can now restart the bot normally.")

        await db.close()
        await exchange.close()
        return

    # Handle --backtest
    if args.backtest:
        await run_backtest(args.engine)
        return

    # Create and run the trading bot
    bot = TradingBot(engine_filter=args.engine)

    try:
        await bot.initialize()

        # Handle --status
        if args.status:
            status = await bot.get_status()
            print_status(status)
            return

        # Run the bot
        await bot.run()

    except KeyboardInterrupt:
        print("\n\nShutdown requested by user...")
    except Exception as e:
        logger.error("main.error", error=str(e), exc_info=True)
        print(f"\n✗ Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
