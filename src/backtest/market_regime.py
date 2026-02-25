"""
Market Regime Analysis for Backtesting.

Identifies market regimes (bull, bear, sideways) and calculates
strategy performance in each regime.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.core.models import MarketData


class MarketRegime(Enum):
    """Market regime classification."""

    BULL = "bull"  # Strong uptrend (>20% from recent low)
    BEAR = "bear"  # Strong downtrend (>20% from recent high)
    SIDEWAYS = "sideways"  # Range-bound
    HIGH_VOL = "high_vol"  # High volatility regime
    LOW_VOL = "low_vol"  # Low volatility regime
    CRISIS = "crisis"  # Extreme drawdown (>40%)


@dataclass
class RegimePeriod:
    """A period of consistent market regime."""

    regime: MarketRegime
    start: datetime
    end: datetime
    start_price: float
    end_price: float
    max_price: float
    min_price: float

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days

    @property
    def return_pct(self) -> float:
        return (self.end_price - self.start_price) / self.start_price * 100


class MarketRegimeAnalyzer:
    """Analyze and classify market regimes from historical data."""

    def __init__(
        self,
        bull_threshold: float = 0.20,  # +20% from 200DMA
        bear_threshold: float = -0.20,  # -20% from ATH
        sideways_range: float = 0.15,  # ±15% range
        ath_drawdown_crisis: float = -0.40,  # -40% for crisis
    ):
        self.bull_threshold = bull_threshold
        self.bear_threshold = bear_threshold
        self.sideways_range = sideways_range
        self.ath_drawdown_crisis = ath_drawdown_crisis

    def identify_regimes(self, market_data: List[MarketData]) -> List[RegimePeriod]:
        """
        Identify market regimes from price data.

        Args:
            market_data: List of OHLCV data points

        Returns:
            List of RegimePeriod objects
        """
        if len(market_data) < 200:
            return []

        # Convert to DataFrame
        df = pd.DataFrame(
            [
                {
                    "timestamp": d.timestamp,
                    "close": float(d.close),
                    "high": float(d.high),
                    "low": float(d.low),
                }
                for d in market_data
            ]
        )

        df["sma200"] = df["close"].rolling(200).mean()
        df["ath"] = df["close"].cummax()
        df["ath_drawdown"] = (df["close"] - df["ath"]) / df["ath"]
        df["price_vs_sma200"] = (df["close"] - df["sma200"]) / df["sma200"]
        df["volatility"] = df["close"].pct_change().rolling(30).std() * np.sqrt(365)

        # Drop NaN
        df = df.dropna()

        if len(df) < 50:
            return []

        # Classify each point
        def classify_regime(row):
            # Crisis first (highest priority)
            if row["ath_drawdown"] <= self.ath_drawdown_crisis:
                return MarketRegime.CRISIS

            # High volatility
            if row["volatility"] > 1.0:  # >100% annualized
                return MarketRegime.HIGH_VOL

            # Low volatility
            if row["volatility"] < 0.3:  # <30% annualized
                return MarketRegime.LOW_VOL

            # Bull / Bear based on 200DMA
            if row["price_vs_sma200"] > self.bull_threshold:
                return MarketRegime.BULL
            elif row["price_vs_sma200"] < self.bear_threshold:
                return MarketRegime.BEAR
            else:
                return MarketRegime.SIDEWAYS

        df["regime"] = df.apply(classify_regime, axis=1)

        # Convert to periods (consecutive same regimes)
        periods = []
        current_regime = df["regime"].iloc[0]
        start_idx = 0

        for i in range(1, len(df)):
            if df["regime"].iloc[i] != current_regime:
                # End of current period
                period_df = df.iloc[start_idx:i]
                periods.append(
                    RegimePeriod(
                        regime=current_regime,
                        start=period_df["timestamp"].iloc[0],
                        end=period_df["timestamp"].iloc[-1],
                        start_price=period_df["close"].iloc[0],
                        end_price=period_df["close"].iloc[-1],
                        max_price=period_df["close"].max(),
                        min_price=period_df["close"].min(),
                    )
                )

                current_regime = df["regime"].iloc[i]
                start_idx = i

        # Don't forget the last period
        if start_idx < len(df):
            period_df = df.iloc[start_idx:]
            periods.append(
                RegimePeriod(
                    regime=current_regime,
                    start=period_df["timestamp"].iloc[0],
                    end=period_df["timestamp"].iloc[-1],
                    start_price=period_df["close"].iloc[0],
                    end_price=period_df["close"].iloc[-1],
                    max_price=period_df["close"].max(),
                    min_price=period_df["close"].min(),
                )
            )

        return periods

    def calculate_regime_performance(
        self, periods: List[RegimePeriod], engine_states: Dict
    ) -> Dict[str, Dict]:
        """
        Calculate strategy performance in each market regime.

        Args:
            periods: List of regime periods
            engine_states: Engine states from backtest

        Returns:
            Performance metrics by regime
        """
        regime_stats = {}

        for regime in MarketRegime:
            regime_periods = [p for p in periods if p.regime == regime]

            if not regime_periods:
                continue

            total_days = sum(p.duration_days for p in regime_periods)
            avg_return = np.mean([p.return_pct for p in regime_periods])

            # Calculate engine performance in this regime
            engine_performances = {}
            for engine_type, state in engine_states.items():
                regime_return = self._calculate_engine_return_in_periods(
                    state, regime_periods
                )
                engine_performances[engine_type.value] = regime_return

            regime_stats[regime.value] = {
                "occurrences": len(regime_periods),
                "total_days": total_days,
                "avg_period_return": avg_return,
                "avg_duration_days": (
                    total_days / len(regime_periods) if regime_periods else 0
                ),
                "engine_performance": engine_performances,
            }

        return regime_stats

    def _calculate_engine_return_in_periods(
        self, state, periods: List[RegimePeriod]
    ) -> Optional[float]:
        """Calculate engine return during specific regime periods."""
        if not state.equity_curve:
            return None

        # Convert equity curve to DataFrame
        equity_df = pd.DataFrame(state.equity_curve)

        total_return = 0
        valid_periods = 0

        for period in periods:
            # Find equity at start and end of period
            start_equity = (
                equity_df[equity_df["timestamp"] >= period.start]["total"].iloc[0]
                if len(equity_df[equity_df["timestamp"] >= period.start]) > 0
                else None
            )

            end_equity = (
                equity_df[equity_df["timestamp"] <= period.end]["total"].iloc[-1]
                if len(equity_df[equity_df["timestamp"] <= period.end]) > 0
                else None
            )

            if start_equity and end_equity and start_equity > 0:
                period_return = (end_equity - start_equity) / start_equity * 100
                total_return += period_return
                valid_periods += 1

        return total_return / valid_periods if valid_periods > 0 else None

    def print_regime_analysis(self, periods: List[RegimePeriod]):
        """Print regime analysis summary."""
        print("\n" + "-" * 80)
        print("MARKET REGIME ANALYSIS")
        print("-" * 80)

        if not periods:
            print("\n  No regime data available")
            return

        # Summary by regime
        regime_counts = {}
        regime_days = {}

        for period in periods:
            r = period.regime.value
            regime_counts[r] = regime_counts.get(r, 0) + 1
            regime_days[r] = regime_days.get(r, 0) + period.duration_days

        print(f"\n  {'Regime':<12} {'Periods':<10} {'Days':<10} {'% Time':<10}")
        print("  " + "-" * 45)

        total_days = sum(regime_days.values())
        for regime in ["bull", "bear", "sideways", "high_vol", "low_vol", "crisis"]:
            if regime in regime_counts:
                pct_time = regime_days[regime] / total_days * 100
                print(
                    f"  {regime:<12} {regime_counts[regime]:<10} {regime_days[regime]:<10} {pct_time:>7.1f}%"
                )

        # Longest periods
        print("\n  Longest Bull Run:")
        bull_periods = [p for p in periods if p.regime == MarketRegime.BULL]
        if bull_periods:
            longest = max(bull_periods, key=lambda p: p.duration_days)
            print(
                f"    {longest.start.strftime('%Y-%m-%d')} to {longest.end.strftime('%Y-%m-%d')}"
            )
            print(
                f"    Duration: {longest.duration_days} days, Return: {longest.return_pct:+.1f}%"
            )

        print("\n  Deepest Crisis:")
        crisis_periods = [p for p in periods if p.regime == MarketRegime.CRISIS]
        if crisis_periods:
            deepest = min(crisis_periods, key=lambda p: p.return_pct)
            print(
                f"    {deepest.start.strftime('%Y-%m-%d')} to {deepest.end.strftime('%Y-%m-%d')}"
            )
            print(
                f"    Duration: {deepest.duration_days} days, Drawdown: {deepest.return_pct:.1f}%"
            )
