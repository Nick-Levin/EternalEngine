#!/usr/bin/env python3
"""
Script to manually trigger a DCA purchase for CORE-HODL engine.

This is useful when:
- The bot missed a scheduled purchase due to downtime
- You want to manually accelerate the deployment phase
- Testing the purchase flow

Usage:
    python scripts/trigger_dca_purchase.py [--symbols BTCUSDT,ETHUSDT] [--amount 100]
"""
import asyncio
import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.exchange.bybit_client import ByBitClient
from src.risk.risk_manager import RiskManager
from src.storage.database import Database
from src.core.engine import TradingEngine, EngineType
from src.strategies.dca_strategy import DCAStrategy
from src.core.config import engine_config, bybit_config, database_config


async def trigger_dca_purchase(symbols=None, amount=None, dry_run=True):
    """
    Manually trigger a DCA purchase.
    
    Args:
        symbols: List of symbols to buy (default: from config)
        amount: Amount to buy per symbol in USDT (default: from config)
        dry_run: If True, only show what would be bought without executing
    """
    
    print("=" * 70)
    print("DCA Manual Purchase Trigger")
    print("=" * 70)
    print()
    
    # Initialize components
    print("Initializing...")
    exchange = ByBitClient(
        api_key=bybit_config.api_key,
        api_secret=bybit_config.api_secret,
        testnet=(bybit_config.api_mode == 'testnet'),
        demo_trading=(bybit_config.api_mode == 'demo')
    )
    await exchange.initialize()
    
    risk_manager = RiskManager()
    database = Database()
    await database.initialize()
    
    # Get symbols to buy
    if symbols is None:
        symbols = engine_config.trading_mode.default_symbols
    
    # Get amount per symbol
    if amount is None:
        amount = Decimal(str(engine_config.core_hodl.dca_amount_usdt))
    else:
        amount = Decimal(str(amount))
    
    # Get current prices
    print(f"\nFetching current prices for {len(symbols)} symbols...")
    print("-" * 70)
    
    total_cost = Decimal("0")
    purchases = []
    
    for symbol in symbols:
        try:
            ticker = await exchange.get_ticker(symbol)
            price = Decimal(str(ticker.get('last', 0)))
            
            if price <= 0:
                print(f"  ⚠️  {symbol}: Could not get price")
                continue
            
            # Calculate quantity
            qty = amount / price
            cost = qty * price
            total_cost += cost
            
            purchases.append({
                'symbol': symbol,
                'price': price,
                'qty': qty,
                'cost': cost
            })
            
            print(f"  {symbol:12} @ ${price:10.2f} x {qty:12.8f} = ${cost:10.2f}")
            
        except Exception as e:
            print(f"  ⚠️  {symbol}: Error - {e}")
    
    print("-" * 70)
    print(f"  {'TOTAL':12} {'':12} {'':12} = ${total_cost:10.2f}")
    print()
    
    if dry_run:
        print("=" * 70)
        print("DRY RUN MODE - No orders were placed")
        print("=" * 70)
        print()
        print("To execute the purchase, restart the bot normally.")
        print("The bot will trigger the purchase based on the DCA schedule.")
        print()
        print("If you want to force an immediate purchase:")
        print("1. Stop the bot if running")
        print("2. Run: python scripts/fix_dca_missed_purchase.py")
        print("3. Start the bot - it will purchase on next cycle")
        print()
        print("Or modify the last_purchase time in the database to be")
        print("more than 7 days ago, then restart the bot.")
        
    else:
        print("=" * 70)
        print("LIVE MODE - Orders would be placed here")
        print("=" * 70)
        print()
        print("NOTE: This script currently only supports dry-run mode.")
        print("To execute purchases, use the normal bot operation.")
    
    await exchange.close()
    await database.close()


def main():
    parser = argparse.ArgumentParser(
        description="Manually trigger or simulate DCA purchases"
    )
    parser.add_argument(
        '--symbols',
        type=str,
        help='Comma-separated list of symbols (default: from config)'
    )
    parser.add_argument(
        '--amount',
        type=float,
        help='Amount per symbol in USDT (default: from config)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually execute orders (default: dry run only)'
    )
    
    args = parser.parse_args()
    
    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
    
    # Run
    asyncio.run(trigger_dca_purchase(
        symbols=symbols,
        amount=args.amount,
        dry_run=not args.execute
    ))


if __name__ == "__main__":
    main()
