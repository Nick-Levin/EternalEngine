"""
Historical Data Loader for Backtesting.

Downloads and caches real historical OHLCV data from Bybit via CCXT.
Supports multiple timeframes and symbols.
"""

import asyncio
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ccxt.async_support as ccxt
import pandas as pd
import structlog

from src.core.models import MarketData

logger = structlog.get_logger(__name__)


class HistoricalDataLoader:
    """
    Load historical market data for backtesting.

    Features:
    - Downloads from Bybit via CCXT
    - Caches data locally (CSV format)
    - Handles rate limiting
    - Supports multiple timeframes
    """

    def __init__(
        self,
        cache_dir: str = "data/backtests",
        exchange_id: str = "bybit",
        timeframe: str = "1h",
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.exchange_id = exchange_id
        self.timeframe = timeframe
        self.exchange = None

    async def initialize(self):
        """Initialize exchange connection."""
        if self.exchange is None:
            self.exchange = getattr(ccxt, self.exchange_id)(
                {
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "spot",
                    },
                }
            )
            await self.exchange.load_markets()
            logger.info("data_loader.exchange_initialized", exchange=self.exchange_id)

    async def close(self):
        """Close exchange connection."""
        if self.exchange:
            await self.exchange.close()
            self.exchange = None

    async def load_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True,
    ) -> List[MarketData]:
        """
        Load historical data for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            start_date: Start of data range
            end_date: End of data range
            use_cache: Whether to use cached data

        Returns:
            List of MarketData objects
        """
        cache_file = self._get_cache_path(symbol, start_date, end_date)

        # Try cache first
        if use_cache and cache_file.exists():
            logger.info("data_loader.using_cache", symbol=symbol, file=str(cache_file))
            return self._load_from_cache(cache_file)

        # Download from exchange
        logger.info(
            "data_loader.downloading",
            symbol=symbol,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )

        await self.initialize()

        # Fetch OHLCV data
        since = int(start_date.timestamp() * 1000)
        limit = 1000  # Max per request

        all_ohlcv = []
        current_since = since

        while True:
            try:
                ohlcv = await self.exchange.fetch_ohlcv(
                    symbol, timeframe=self.timeframe, since=current_since, limit=limit
                )

                if not ohlcv:
                    break

                all_ohlcv.extend(ohlcv)

                # Check if we've reached end date
                last_timestamp = ohlcv[-1][0]
                last_date = datetime.fromtimestamp(last_timestamp / 1000)

                if last_date >= end_date:
                    break

                # Move to next batch
                current_since = last_timestamp + 1

                # Rate limit protection
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error("data_loader.fetch_error", symbol=symbol, error=str(e))
                break

        # Convert to MarketData
        market_data = self._ohlcv_to_market_data(all_ohlcv, symbol)

        # Cache for future use
        if market_data:
            self._save_to_cache(market_data, cache_file)

        logger.info(
            "data_loader.complete",
            symbol=symbol,
            records=len(market_data),
            date_range=(
                f"{market_data[0].timestamp} to {market_data[-1].timestamp}"
                if market_data
                else "N/A"
            ),
        )

        return market_data

    async def load_multi_symbol(
        self, symbols: List[str], start_date: datetime, end_date: datetime
    ) -> Dict[str, List[MarketData]]:
        """
        Load data for multiple symbols.

        Args:
            symbols: List of trading pairs
            start_date: Start of data range
            end_date: End of data range

        Returns:
            Dict mapping symbol to MarketData list
        """
        results = {}

        for symbol in symbols:
            try:
                data = await self.load_data(symbol, start_date, end_date)
                results[symbol] = data
            except Exception as e:
                logger.error("data_loader.symbol_failed", symbol=symbol, error=str(e))
                results[symbol] = []

        return results

    def _ohlcv_to_market_data(self, ohlcv: List[List], symbol: str) -> List[MarketData]:
        """Convert CCXT OHLCV format to MarketData objects."""
        market_data = []

        for candle in ohlcv:
            # OHLCV format: [timestamp, open, high, low, close, volume]
            timestamp = datetime.fromtimestamp(candle[0] / 1000)

            market_data.append(
                MarketData(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=Decimal(str(candle[1])),
                    high=Decimal(str(candle[2])),
                    low=Decimal(str(candle[3])),
                    close=Decimal(str(candle[4])),
                    volume=Decimal(str(candle[5])),
                )
            )

        return market_data

    def _get_cache_path(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> Path:
        """Generate cache file path."""
        # Normalize symbol for filename
        safe_symbol = symbol.replace("/", "_")
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        filename = f"{safe_symbol}_{self.timeframe}_{start_str}_{end_str}.csv"
        return self.cache_dir / filename

    def _save_to_cache(self, data: List[MarketData], filepath: Path):
        """Save data to cache file."""
        if not data:
            return

        records = []
        for md in data:
            records.append(
                {
                    "timestamp": md.timestamp.isoformat(),
                    "symbol": md.symbol,
                    "open": float(md.open),
                    "high": float(md.high),
                    "low": float(md.low),
                    "close": float(md.close),
                    "volume": float(md.volume),
                }
            )

        df = pd.DataFrame(records)
        df.to_csv(filepath, index=False)
        logger.info("data_loader.cached", file=str(filepath), records=len(records))

    def _load_from_cache(self, filepath: Path) -> List[MarketData]:
        """Load data from cache file."""
        df = pd.read_csv(filepath)

        market_data = []
        for _, row in df.iterrows():
            market_data.append(
                MarketData(
                    symbol=row["symbol"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])),
                )
            )

        return market_data

    @staticmethod
    def get_available_date_range(symbol: str = "BTC/USDT") -> Tuple[datetime, datetime]:
        """
        Get the available date range for a symbol on Bybit.

        Bybit spot data generally available from ~2020.
        """
        # Bybit spot trading started around 2020
        start = datetime(2020, 1, 1)
        end = datetime.now()

        return start, end
