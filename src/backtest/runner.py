"""
Backtest Runner - CLI and programmatic interface.

Usage:
    python -m src.backtest.runner --engine TREND --start 2020-01-01 --end 2023-12-31
    python -m src.backtest.runner --all-engines --years 3
"""

import argparse
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

import structlog

from src.backtest.data_loader import HistoricalDataLoader
from src.backtest.engine import BacktestResult, EternalEngineBacktest
from src.backtest.market_regime import MarketRegimeAnalyzer
from src.backtest.report import BacktestReport
from src.core.models import EngineType

logger = structlog.get_logger(__name__)


class BacktestRunner:
    """High-level backtest runner interface."""

    def __init__(self, cache_dir: str = "data/historical"):
        self.data_loader = HistoricalDataLoader(cache_dir=cache_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def run_full_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        initial_capital: Decimal = Decimal("100000"),
        symbols: list = None,
        timeframe: str = "1h",
    ) -> BacktestResult:
        """
        Run complete backtest for all 4 engines.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Starting capital
            symbols: List of symbols to trade (default: BTC, ETH)
            timeframe: OHLCV timeframe

        Returns:
            BacktestResult with all metrics
        """
        if symbols is None:
            symbols = ["BTC/USDT", "ETH/USDT"]

        logger.info(
            "backtest_runner.starting",
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            capital=str(initial_capital),
        )

        # Load historical data
        market_data = await self._load_data(symbols, timeframe, start_date, end_date)

        if not market_data:
            raise ValueError("No market data loaded")

        # Create and run backtest engine
        engine = EternalEngineBacktest(
            initial_capital=initial_capital,
            fee_rate=Decimal("0.001"),  # 0.1% taker fee
            slippage_pct=Decimal("0.05"),  # 0.05% slippage
        )

        result = await engine.run(market_data, start_date, end_date)

        # Analyze market regimes
        analyzer = MarketRegimeAnalyzer()
        btc_data = market_data.get("BTC/USDT", [])
        regimes = analyzer.identify_regimes(btc_data)
        result.regime_performance = analyzer.calculate_regime_performance(
            regimes, engine.engine_states
        )

        logger.info(
            "backtest_runner.complete",
            total_return=f"{result.total_return_pct:.2f}%",
            sharpe=result.sharpe_ratio,
        )

        return result

    async def run_single_engine(
        self,
        engine_type: EngineType,
        start_date: datetime,
        end_date: datetime,
        initial_capital: Decimal = Decimal("100000"),
    ) -> BacktestResult:
        """
        Run backtest for a single engine.

        Args:
            engine_type: Which engine to test
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Starting capital

        Returns:
            BacktestResult
        """
        # Run full backtest but filter results to single engine
        result = await self.run_full_backtest(start_date, end_date, initial_capital)

        # Filter to single engine (simplified - in production would run just that engine)
        if engine_type in result.engine_results:
            engine_data = result.engine_results[engine_type]
            result.total_return_pct = engine_data["return_pct"]

        return result

    async def run_multi_year_comparison(self, years: list = [3, 5, 8]) -> dict:
        """
        Run backtests for multiple time periods for comparison.

        Args:
            years: List of year periods to test

        Returns:
            Dictionary of results by period
        """
        end_date = datetime.utcnow()
        results = {}

        for period in years:
            start_date = end_date - timedelta(days=365 * period)

            logger.info(
                "backtest_runner.period_start",
                period_years=period,
                start=start_date.isoformat(),
            )

            try:
                result = await self.run_full_backtest(start_date, end_date)
                results[f"{period}y"] = result
            except Exception as e:
                logger.error(
                    "backtest_runner.period_failed", period=period, error=str(e)
                )
                results[f"{period}y"] = None

        return results

    async def _load_data(
        self, symbols: list, timeframe: str, start_date: datetime, end_date: datetime
    ) -> dict:
        """Load historical data for all symbols."""
        market_data = {}

        for symbol in symbols:
            try:
                data = await self.data_loader.load_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                )

                if data is not None and not data.empty:
                    from src.backtest.data_loader import HistoricalDataLoader

                    market_data[symbol] = HistoricalDataLoader._convert_to_market_data(
                        data
                    )
                    logger.info(
                        "backtest_runner.data_loaded", symbol=symbol, records=len(data)
                    )
                else:
                    logger.warning("backtest_runner.no_data", symbol=symbol)

            except Exception as e:
                logger.error("backtest_runner.load_failed", symbol=symbol, error=str(e))

        return market_data


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="The Eternal Engine - Backtest Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full system backtest for 3 years
  python -m src.backtest.runner --years 3
  
  # Run specific date range
  python -m src.backtest.runner --start 2020-01-01 --end 2023-12-31
  
  # Run single engine
  python -m src.backtest.runner --engine TREND --years 5
  
  # Multi-period comparison
  python -m src.backtest.runner --multi-year --years 3 5 8
        """,
    )

    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")

    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")

    parser.add_argument(
        "--years", type=int, default=3, help="Number of years to backtest (default: 3)"
    )

    parser.add_argument(
        "--engine",
        type=str,
        choices=["CORE_HODL", "TREND", "FUNDING", "TACTICAL", "ALL"],
        default="ALL",
        help="Engine to backtest (default: ALL)",
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100000,
        help="Initial capital (default: 100000)",
    )

    parser.add_argument(
        "--multi-year",
        action="store_true",
        help="Run comparison across multiple periods",
    )

    parser.add_argument("--output", type=str, help="Output file for report (markdown)")

    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        default=["BTC/USDT", "ETH/USDT"],
        help="Symbols to trade (default: BTC/USDT ETH/USDT)",
    )

    parser.add_argument(
        "--timeframe", type=str, default="1h", help="OHLCV timeframe (default: 1h)"
    )

    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()

    # Parse dates
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        start_date = datetime.utcnow() - timedelta(days=365 * args.years)

    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d")
    else:
        end_date = datetime.utcnow()

    runner = BacktestRunner()

    if args.multi_year:
        # Multi-year comparison
        results = await runner.run_multi_year_comparison([3, 5, 8])

        print("\n" + "=" * 80)
        print("MULTI-YEAR COMPARISON")
        print("=" * 80)

        for period, result in results.items():
            if result:
                print(f"\n{period}:")
                print(f"  Return: {result.total_return_pct:+.2f}%")
                print(f"  Max DD: {result.max_drawdown_pct:.2f}%")
                print(f"  Sharpe: {result.sharpe_ratio:.2f}")
    else:
        # Single backtest
        if args.engine == "ALL":
            result = await runner.run_full_backtest(
                start_date=start_date,
                end_date=end_date,
                initial_capital=Decimal(str(args.capital)),
                symbols=args.symbols,
                timeframe=args.timeframe,
            )
        else:
            engine_type = EngineType(args.engine)
            result = await runner.run_single_engine(
                engine_type=engine_type,
                start_date=start_date,
                end_date=end_date,
                initial_capital=Decimal(str(args.capital)),
            )

        # Generate report
        report = BacktestReport(result)
        report.print_full_report()

        # Save to file if requested
        if args.output:
            markdown = report.generate_markdown_report()
            Path(args.output).write_text(markdown)
            print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
