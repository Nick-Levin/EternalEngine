"""
Backtest Report Generator.

Produces professional-grade backtest reports with:
- Performance metrics
- Risk analysis
- Engine breakdown
- Trade statistics
- Visual equity curves (ASCII/text-based)
"""

from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult, EngineBacktestState
from src.backtest.market_regime import MarketRegime, RegimePeriod
from src.core.models import EngineType


class BacktestReport:
    """Generate professional backtest reports."""

    def __init__(self, result: BacktestResult):
        self.result = result

    def print_full_report(self):
        """Print complete backtest report to console."""
        self._print_header()
        self._print_performance_summary()
        self._print_risk_metrics()
        self._print_engine_breakdown()
        self._print_trade_statistics()
        self._print_monthly_returns()
        self._print_drawdown_analysis()
        self._print_conclusion()

    def generate_markdown_report(self) -> str:
        """Generate markdown formatted report."""
        lines = []

        lines.append("# Eternal Engine Backtest Report")
        lines.append("")
        lines.append(
            f"**Test Period:** {self.result.start_date.strftime('%Y-%m-%d')} to {self.result.end_date.strftime('%Y-%m-%d')}"
        )
        lines.append(f"**Initial Capital:** ${self.result.initial_capital:,.2f}")
        lines.append(f"**Final Capital:** ${self.result.final_capital:,.2f}")
        lines.append("")

        lines.append("## Performance Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Return | {self.result.total_return_pct:+.2f}% |")
        lines.append(
            f"| Annualized Return | {self._calculate_annualized_return():.2f}% |"
        )
        lines.append(f"| Max Drawdown | {self.result.max_drawdown_pct:.2f}% |")
        lines.append(f"| Sharpe Ratio | {self.result.sharpe_ratio:.2f} |")
        lines.append(f"| Sortino Ratio | {self.result.sortino_ratio:.2f} |")
        lines.append("")

        lines.append("## Engine Performance")
        lines.append("")
        lines.append(f"| Engine | Allocation | Return | Trades | Win Rate |")
        lines.append(f"|--------|------------|--------|--------|----------|")
        for engine_type, data in self.result.engine_results.items():
            lines.append(
                f"| {engine_type.value} | {data['initial']/self.result.initial_capital*100:.0f}% | {data['return_pct']:+.2f}% | {data['trades']} | {data['win_rate']:.1f}% |"
            )
        lines.append("")

        return "\n".join(lines)

    def _print_header(self):
        """Print report header."""
        print("\n" + "=" * 80)
        print("THE ETERNAL ENGINE - BACKTEST REPORT")
        print("=" * 80)
        print(
            f"\nTest Period: {self.result.start_date.strftime('%Y-%m-%d')} to {self.result.end_date.strftime('%Y-%m-%d')}"
        )
        print(f"Initial Capital: ${self.result.initial_capital:,.2f}")
        print(f"Final Capital:   ${self.result.final_capital:,.2f}")
        duration_days = (self.result.end_date - self.result.start_date).days
        print(f"Duration:        {duration_days} days ({duration_days/365:.1f} years)")

    def _print_performance_summary(self):
        """Print performance summary."""
        print("\n" + "-" * 80)
        print("PERFORMANCE SUMMARY")
        print("-" * 80)

        annualized = self._calculate_annualized_return()

        print(f"\n  Total Return:          {self.result.total_return_pct:+.2f}%")
        print(f"  Annualized Return:     {annualized:+.2f}%")
        print(f"  Final Portfolio Value: ${self.result.final_capital:,.2f}")

        # Color code the result
        if self.result.total_return_pct > 100:
            print(f"  Status:                🟢 EXCEPTIONAL (>100% return)")
        elif self.result.total_return_pct > 50:
            print(f"  Status:                🟢 OUTPERFORMING (>50% return)")
        elif self.result.total_return_pct > 0:
            print(f"  Status:                🟡 PROFITABLE (positive return)")
        else:
            print(f"  Status:                🔴 LOSS (negative return)")

    def _print_risk_metrics(self):
        """Print risk metrics."""
        print("\n" + "-" * 80)
        print("RISK METRICS")
        print("-" * 80)

        print(f"\n  Max Drawdown:          {self.result.max_drawdown_pct:.2f}%")
        print(f"  Sharpe Ratio:          {self.result.sharpe_ratio:.2f}")
        print(f"  Sortino Ratio:         {self.result.sortino_ratio:.2f}")
        print(f"  Calmar Ratio:          {self.result.calmar_ratio:.2f}")
        print(f"  Volatility (Annual):   {self.result.volatility_annual:.2f}%")

        # Risk assessment
        print("\n  Risk Assessment:")
        if self.result.max_drawdown_pct > -25:
            print(f"    ✅ Drawdown controlled (< 25%)")
        else:
            print(f"    ⚠️  High drawdown (> 25%)")

        if self.result.sharpe_ratio > 1.0:
            print(f"    ✅ Good risk-adjusted returns (Sharpe > 1.0)")
        elif self.result.sharpe_ratio > 0.5:
            print(f"    🟡 Moderate risk-adjusted returns")
        else:
            print(f"    ⚠️  Poor risk-adjusted returns")

    def _print_engine_breakdown(self):
        """Print performance breakdown by engine."""
        print("\n" + "-" * 80)
        print("ENGINE PERFORMANCE BREAKDOWN")
        print("-" * 80)

        print(
            f"\n  {'Engine':<15} {'Alloc':<8} {'Return':<12} {'Trades':<8} {'Win Rate':<10}"
        )
        print("  " + "-" * 60)

        for engine_type in [
            EngineType.CORE_HODL,
            EngineType.TREND,
            EngineType.FUNDING,
            EngineType.TACTICAL,
        ]:
            if engine_type in self.result.engine_results:
                data = self.result.engine_results[engine_type]
                alloc = data["initial"] / self.result.initial_capital * 100

                print(
                    f"  {engine_type.value:<15} {alloc:>6.0f}%  {data['return_pct']:>+9.2f}%   {data['trades']:>6}    {data['win_rate']:>7.1f}%"
                )

        print("\n  Notes:")
        print("    • CORE-HODL: Long-term accumulation, lower trade frequency")
        print("    • TREND: Trend following, moderate frequency")
        print("    • FUNDING: Funding arbitrage, regular small profits")
        print("    • TACTICAL: Crisis deployment, rare but significant")

    def _print_trade_statistics(self):
        """Print trade statistics."""
        print("\n" + "-" * 80)
        print("TRADE STATISTICS")
        print("-" * 80)

        print(f"\n  Total Trades:          {self.result.total_trades}")
        print(
            f"  Winning Trades:        {self.result.winning_trades} ({self.result.win_rate_pct:.1f}%)"
        )
        print(
            f"  Losing Trades:         {self.result.losing_trades} ({100-self.result.win_rate_pct:.1f}%)"
        )
        print(f"\n  Average Win:           {self.result.avg_win_pct:+.2f}%")
        print(f"  Average Loss:          {self.result.avg_loss_pct:.2f}%")
        print(f"  Profit Factor:         {self.result.profit_factor:.2f}")

        if self.result.profit_factor > 2.0:
            print(f"  Win/Loss Quality:      ✅ Excellent (PF > 2.0)")
        elif self.result.profit_factor > 1.5:
            print(f"  Win/Loss Quality:      🟢 Good (PF > 1.5)")
        elif self.result.profit_factor > 1.0:
            print(f"  Win/Loss Quality:      🟡 Marginal (PF > 1.0)")
        else:
            print(f"  Win/Loss Quality:      🔴 Poor (PF < 1.0)")

    def _print_monthly_returns(self):
        """Print monthly returns heatmap."""
        print("\n" + "-" * 80)
        print("MONTHLY RETURNS (%)")
        print("-" * 80)

        if self.result.monthly_returns.empty:
            print("\n  No monthly data available")
            return

        # Pivot to year/month format
        monthly = self.result.monthly_returns.copy()
        monthly.index = pd.to_datetime(monthly.index.astype(str))

        years = sorted(set(monthly.index.year))
        months = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        print(f"\n  {'Year':<6} {' '.join(f'{m:>6}' for m in months)}   {'Total':>7}")
        print("  " + "-" * 90)

        for year in years:
            year_data = monthly[monthly.index.year == year]
            row_values = []
            for month in range(1, 13):
                month_data = year_data[year_data.index.month == month]
                if not month_data.empty:
                    val = month_data.values[0]
                    row_values.append(f"{val:+6.1f}")
                else:
                    row_values.append("     -")

            year_total = year_data.sum()
            print(f"  {year:<6} {' '.join(row_values)}   {year_total:+7.1f}")

        # Best and worst months
        best_month = monthly.idxmax()
        worst_month = monthly.idxmin()
        print(f"\n  Best Month:  {best_month} ({monthly.max():+.2f}%)")
        print(f"  Worst Month: {worst_month} ({monthly.min():+.2f}%)")

    def _print_drawdown_analysis(self):
        """Print drawdown analysis."""
        print("\n" + "-" * 80)
        print("DRAWDOWN ANALYSIS")
        print("-" * 80)

        print(f"\n  Maximum Drawdown:      {self.result.max_drawdown_pct:.2f}%")
        print(
            f"  Drawdown Start:        {self.result.max_drawdown_start.strftime('%Y-%m-%d')}"
        )
        print(
            f"  Drawdown End:          {self.result.max_drawdown_end.strftime('%Y-%m-%d')}"
        )

        if self.result.max_drawdown_recovery:
            recovery_days = (
                self.result.max_drawdown_recovery - self.result.max_drawdown_end
            ).days
            print(
                f"  Recovery Date:         {self.result.max_drawdown_recovery.strftime('%Y-%m-%d')}"
            )
            print(f"  Recovery Time:         {recovery_days} days")
        else:
            print(f"  Recovery:              Not yet recovered by end of test")

        # Drawdown severity
        dd_pct = abs(self.result.max_drawdown_pct)
        if dd_pct < 10:
            severity = "Mild (acceptable)"
        elif dd_pct < 20:
            severity = "Moderate (caution)"
        elif dd_pct < 30:
            severity = "Severe (concerning)"
        else:
            severity = "Extreme (dangerous)"

        print(f"  Severity:              {severity}")

    def _print_conclusion(self):
        """Print conclusion and recommendations."""
        print("\n" + "=" * 80)
        print("CONCLUSION & RECOMMENDATIONS")
        print("=" * 80)

        print("\n  Strategy Viability:")

        # Overall assessment
        score = 0
        checks = []

        if self.result.total_return_pct > 0:
            score += 1
            checks.append("✅ Profitable")
        else:
            checks.append("🔴 Unprofitable")

        if self.result.max_drawdown_pct > -25:
            score += 1
            checks.append("✅ Drawdown controlled")
        else:
            checks.append("⚠️  Excessive drawdown")

        if self.result.sharpe_ratio > 1.0:
            score += 1
            checks.append("✅ Good Sharpe ratio")
        else:
            checks.append("🟡 Moderate Sharpe ratio")

        if self.result.profit_factor > 1.5:
            score += 1
            checks.append("✅ Good win/loss ratio")
        else:
            checks.append("🟡 Marginal win/loss ratio")

        for check in checks:
            print(f"    {check}")

        # Final verdict
        print(f"\n  Overall Score: {score}/4")

        if score == 4:
            print(
                f"\n  🟢 VERDICT: EXCELLENT - Ready for live trading with proper risk management"
            )
        elif score >= 3:
            print(f"\n  🟢 VERDICT: GOOD - Viable strategy, proceed with caution")
        elif score >= 2:
            print(
                f"\n  🟡 VERDICT: MARGINAL - Requires optimization before live trading"
            )
        else:
            print(f"\n  🔴 VERDICT: POOR - Not recommended for live trading")

        print("\n" + "=" * 80)
        print("END OF REPORT")
        print("=" * 80 + "\n")

    def _calculate_annualized_return(self) -> float:
        """Calculate annualized return."""
        duration_years = (self.result.end_date - self.result.start_date).days / 365.25
        if duration_years <= 0:
            return 0

        total_return = self.result.total_return_pct / 100
        # CAGR formula: (1 + total_return)^(1/years) - 1
        cagr = ((1 + total_return) ** (1 / duration_years) - 1) * 100
        return cagr

    def get_summary_dict(self) -> Dict:
        """Get summary as dictionary for further processing."""
        return {
            "start_date": self.result.start_date.isoformat(),
            "end_date": self.result.end_date.isoformat(),
            "initial_capital": float(self.result.initial_capital),
            "final_capital": float(self.result.final_capital),
            "total_return_pct": self.result.total_return_pct,
            "annualized_return": self._calculate_annualized_return(),
            "max_drawdown_pct": self.result.max_drawdown_pct,
            "sharpe_ratio": self.result.sharpe_ratio,
            "total_trades": self.result.total_trades,
            "win_rate_pct": self.result.win_rate_pct,
        }
