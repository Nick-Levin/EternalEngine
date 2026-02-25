#!/usr/bin/env python3
"""
DCA Purchase Utility - Manually trigger or simulate DCA purchases.

This utility helps with:
- Simulating what the next DCA purchase would look like
- Testing configuration changes
- Manual purchase triggering (with caution)

Usage:
    # Simulate purchases (dry run - no actual orders)
    python scripts/trigger_dca_purchase.py
    
    # Show help
    python scripts/trigger_dca_purchase.py --help
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.core.config import bybit_config, engine_config
    from src.exchange.bybit_client import ByBitClient
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Make sure you're running from the project root with venv activated.")
    sys.exit(1)


async def simulate_dca_purchase(symbols=None, amount=None):
    """
    Simulate a DCA purchase to show what would be bought.

    This is a SAFE dry-run that doesn't place any orders.
    """
    print("=" * 70)
    print("DCA Purchase Simulator (DRY RUN - No orders will be placed)")
    print("=" * 70)
    print()

    # Initialize exchange connection
    print("Connecting to exchange...")
    try:
        exchange = ByBitClient(
            api_key=bybit_config.api_key,
            api_secret=bybit_config.api_secret,
            testnet=(bybit_config.api_mode == "testnet"),
            demo_trading=(bybit_config.api_mode == "demo"),
        )
        await exchange.initialize()
        print("✓ Connected")
    except Exception as e:
        print(f"✗ Could not connect: {e}")
        return

    # Get symbols
    if symbols is None:
        symbols = engine_config.trading_mode.default_symbols

    # Get amount
    if amount is None:
        amount = Decimal(str(engine_config.core_hodl.dca_amount_usdt))
    else:
        amount = Decimal(str(amount))

    print(f"\nConfiguration:")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Amount per symbol: ${amount} USDT")
    print(f"  Total: ${amount * len(symbols)} USDT")
    print()

    # Get prices and calculate
    print("Fetching current prices...")
    print("-" * 70)

    total_cost = Decimal("0")
    purchases = []

    for symbol in symbols:
        try:
            ticker = await exchange.get_ticker(symbol)
            price = Decimal(str(ticker.get("last", 0)))

            if price <= 0:
                print(f"  ⚠️  {symbol}: Could not get price")
                continue

            qty = amount / price
            cost = qty * price
            total_cost += cost

            purchases.append(
                {"symbol": symbol, "price": price, "qty": qty, "cost": cost}
            )

            print(f"  {symbol:12} @ ${price:12,.2f} x {qty:14.8f} = ${cost:10,.2f}")

        except Exception as e:
            print(f"  ⚠️  {symbol}: Error - {e}")

    print("-" * 70)
    print(f"  {'TOTAL':12} {'':12} {'':14} = ${total_cost:10,.2f}")
    print()

    print("=" * 70)
    print("NOTE: This was a simulation. No orders were placed.")
    print("=" * 70)
    print()
    print("To actually execute DCA purchases:")
    print("  1. Ensure the bot is running: make run-paper")
    print("  2. The bot will automatically purchase based on schedule")
    print("  3. Or modify last_purchase time in database to trigger sooner")

    await exchange.close()


def main():
    parser = argparse.ArgumentParser(
        description="DCA Purchase Simulator - Preview what would be bought",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Simulate with default settings
    python scripts/trigger_dca_purchase.py
    
    # Simulate with custom symbols
    python scripts/trigger_dca_purchase.py --symbols BTCUSDT,ETHUSDT
    
    # Simulate with custom amount
    python scripts/trigger_dca_purchase.py --amount 500
        """,
    )

    parser.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated list of symbols (default: from config)",
    )
    parser.add_argument(
        "--amount", type=float, help="Amount per symbol in USDT (default: from config)"
    )

    args = parser.parse_args()

    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]

    # Run simulation
    try:
        asyncio.run(simulate_dca_purchase(symbols=symbols, amount=args.amount))
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
