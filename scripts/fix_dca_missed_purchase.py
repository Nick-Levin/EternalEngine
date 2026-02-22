#!/usr/bin/env python3
"""
Script to fix the missed DCA purchase on Feb 22, 2026.

The issue was that the bot was restarted on Feb 20, which reset the 
last_purchase timer to Feb 20 instead of keeping the Feb 15 timestamp.

This script:
1. Sets the last_purchase time in the database to Feb 15, 2026
2. Triggers an immediate DCA purchase if desired
"""
import asyncio
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.database import Database
from src.core.config import database_config


async def fix_dca_last_purchase():
    """Fix the DCA last_purchase timestamps in the database."""
    
    # Initialize database
    db = Database()
    await db.initialize()
    
    print("=" * 60)
    print("DCA Missed Purchase Fix Script")
    print("=" * 60)
    print()
    
    # Strategy name
    strategy_name = "CORE-HODL"
    
    # Symbols to fix
    symbols = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
        "DOGEUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT", "LINKUSDT"
    ]
    
    # The original purchase date (Feb 15, 2026)
    # Setting to Feb 15, 00:00:00 UTC to ensure the next purchase 
    # (Feb 22) would have been triggered
    original_purchase_date = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
    
    print(f"Setting last_purchase times to: {original_purchase_date}")
    print(f"Strategy: {strategy_name}")
    print(f"Symbols: {', '.join(symbols)}")
    print()
    
    # Save the last_purchase times to database
    for symbol in symbols:
        await db.save_dca_state(
            strategy_name=strategy_name,
            symbol=symbol,
            last_purchase=original_purchase_date
        )
        print(f"  ✓ Updated {symbol}")
    
    print()
    print("=" * 60)
    print("Verification - Loading saved states:")
    print("=" * 60)
    
    # Verify by loading back
    saved_states = await db.get_all_dca_states(strategy_name)
    for symbol in symbols:
        saved_time = saved_states.get(symbol)
        if saved_time:
            print(f"  {symbol}: {saved_time}")
        else:
            print(f"  {symbol}: NOT FOUND!")
    
    print()
    
    # Calculate when next purchase should happen
    interval_hours = 168  # 7 days
    next_purchase = original_purchase_date + timedelta(hours=interval_hours)
    now = datetime.now(timezone.utc)
    
    print("=" * 60)
    print("Next Purchase Schedule:")
    print("=" * 60)
    print(f"  Original purchase: {original_purchase_date}")
    print(f"  Next scheduled:    {next_purchase}")
    print(f"  Current time:      {now}")
    print()
    
    if now >= next_purchase:
        hours_overdue = (now - next_purchase).total_seconds() / 3600
        print(f"  ⚠️  Purchase is overdue by {hours_overdue:.1f} hours!")
        print(f"     The bot should trigger the purchase on next analysis cycle.")
    else:
        hours_remaining = (next_purchase - now).total_seconds() / 3600
        print(f"  ⏰ Next purchase in {hours_remaining:.1f} hours")
    
    print()
    print("=" * 60)
    print("Fix Complete!")
    print("=" * 60)
    print()
    print("IMPORTANT: Restart the bot for changes to take effect.")
    print("The bot will now correctly calculate the next purchase time")
    print("based on Feb 15 instead of the restart date.")
    print()
    print("To manually trigger the purchase immediately, run:")
    print("  python scripts/trigger_dca_purchase.py")
    
    await db.close()


if __name__ == "__main__":
    asyncio.run(fix_dca_last_purchase())
