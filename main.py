"""
ByBit Conservative Trading Bot - Main Entry Point

A fully automated trading bot focused on conservative, low-risk strategies.

Usage:
    python main.py --mode paper    # Run in paper trading mode
    python main.py --mode live     # Run in live trading mode (requires API keys)
    python main.py --status        # Show current status
    python main.py --stop          # Stop the bot
"""
import asyncio
import argparse
import signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logging_config import setup_logging
from src.core.config import trading_config, bybit_config, strategy_config
from src.core.engine import TradingEngine
from src.exchange.bybit_client import ByBitClient
from src.risk.risk_manager import RiskManager
from src.storage.database import Database
from src.strategies.dca_strategy import DCAStrategy
from src.strategies.grid_strategy import GridStrategy

import structlog

logger = structlog.get_logger(__name__)


class TradingBot:
    """Main trading bot application."""
    
    def __init__(self):
        self.engine: TradingEngine = None
        self.exchange: ByBitClient = None
        self.risk_manager: RiskManager = None
        self.database: Database = None
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize all components."""
        logger.info("bot.initializing")
        
        # Initialize database
        self.database = Database()
        await self.database.initialize()
        
        # Initialize exchange
        self.exchange = ByBitClient()
        await self.exchange.initialize()
        
        # Initialize risk manager
        self.risk_manager = RiskManager()
        
        # Initialize strategies
        strategies = []
        
        # DCA Strategy
        if strategy_config.default_strategy == "dca":
            dca = DCAStrategy(
                symbols=trading_config.default_symbols,
                interval_hours=strategy_config.dca_interval_hours,
                amount_usdt=strategy_config.dca_amount_usdt
            )
            strategies.append(dca)
            logger.info(
                "bot.dca_strategy_loaded",
                symbols=dca.symbols,
                interval=dca.interval_hours,
                amount=dca.amount_usdt
            )
        
        # Grid Strategy (can run alongside DCA)
        grid = GridStrategy(
            symbols=trading_config.default_symbols,
            grid_levels=strategy_config.grid_levels,
            grid_spacing_pct=strategy_config.grid_spacing_pct
        )
        strategies.append(grid)
        logger.info(
            "bot.grid_strategy_loaded",
            symbols=grid.symbols,
            levels=grid.grid_levels,
            spacing=grid.grid_spacing_pct
        )
        
        # Create trading engine
        self.engine = TradingEngine(
            exchange=self.exchange,
            risk_manager=self.risk_manager,
            database=self.database,
            strategies=strategies
        )
        
        logger.info("bot.initialized")
    
    async def run(self):
        """Run the trading bot."""
        logger.info("bot.starting", mode=trading_config.trading_mode)
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._signal_handler)
        
        try:
            # Start engine
            await self.engine.start()
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error("bot.error", error=str(e))
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown."""
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
    
    async def get_status(self) -> dict:
        """Get current bot status."""
        if not self.engine:
            return {"status": "not_initialized"}
        
        return self.engine.get_status()


def check_config():
    """Check if configuration is valid."""
    errors = []
    
    if not bybit_config.api_key or bybit_config.api_key == "your_api_key_here":
        errors.append("BYBIT_API_KEY not set in .env file")
    
    if not bybit_config.api_secret or bybit_config.api_secret == "your_api_secret_here":
        errors.append("BYBIT_API_SECRET not set in .env file")
    
    if trading_config.trading_mode == "live":
        print("⚠️  WARNING: Running in LIVE trading mode!")
        print("Make sure you have:")
        print("  - Tested thoroughly in paper mode")
        print("  - Verified API keys have correct permissions")
        print("  - Set appropriate risk limits in .env")
        print()
    
    if errors:
        print("Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease copy .env.example to .env and fill in your API credentials.")
        return False
    
    return True


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ByBit Conservative Trading Bot")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        help="Trading mode (overrides .env setting)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current status and exit"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check configuration and exit"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Check config
    if args.check:
        if check_config():
            print("✓ Configuration valid")
        return
    
    if not check_config():
        return
    
    # Override mode if specified
    if args.mode:
        trading_config.trading_mode = args.mode
    
    # Create and run bot
    bot = TradingBot()
    
    try:
        await bot.initialize()
        
        if args.status:
            status = await bot.get_status()
            print("\n=== Bot Status ===")
            print(f"Running: {status['running']}")
            print(f"Portfolio: {status['portfolio']}")
            print(f"Positions: {status['positions']}")
            print(f"Pending Orders: {status['pending_orders']}")
            print(f"Strategies: {list(status['strategies'].keys())}")
            return
        
        await bot.run()
        
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        logger.error("main.error", error=str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
