"""
Eternal Engine Backtest Module.

Professional-grade backtesting system for The Eternal Engine.

Usage:
    from src.backtest.runner import BacktestRunner
    
    runner = BacktestRunner()
    result = await runner.run_full_backtest(
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2023, 12, 31),
        initial_capital=Decimal("100000")
    )
    
    report = BacktestReport(result)
    report.print_full_report()
"""

from src.backtest.data_loader import HistoricalDataLoader
from src.backtest.engine import (BacktestResult, EngineBacktestState,
                                 EternalEngineBacktest)
from src.backtest.market_regime import (MarketRegime, MarketRegimeAnalyzer,
                                        RegimePeriod)
from src.backtest.report import BacktestReport
from src.backtest.runner import BacktestRunner

__all__ = [
    "EternalEngineBacktest",
    "BacktestResult",
    "EngineBacktestState",
    "HistoricalDataLoader",
    "BacktestReport",
    "BacktestRunner",
    "MarketRegime",
    "MarketRegimeAnalyzer",
    "RegimePeriod",
]
