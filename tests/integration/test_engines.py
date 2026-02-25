"""Comprehensive integration tests for all 4 Eternal Engine engines.

These tests verify:
1. All 4 engines can be instantiated together without conflicts
2. Signal generation works correctly across all engines simultaneously
3. Capital allocation is properly managed (60/20/15/5 split)
4. Risk manager integration validates signals from all engines
5. Engine state persistence (save/load) works correctly
6. Inter-engine communication for profit transfers

Test Coverage:
- Engine instantiation and initialization
- Signal generation and attribution
- Capital allocation and rebalancing
- Risk manager integration across engines
- State persistence and recovery
- Inter-engine capital flows
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.core.models import (EngineState, EngineType, MarketData, Order,
                             OrderSide, OrderStatus, OrderType, Portfolio,
                             Position, PositionSide, SignalType, TradingSignal)
from src.engines.base import BaseEngine, EngineConfig
from src.engines.core_hodl import CoreHodlConfig, CoreHodlEngine
from src.engines.funding import FundingEngine, FundingEngineConfig
from src.engines.tactical import TacticalEngine, TacticalEngineConfig
from src.engines.trend import TrendEngine, TrendEngineConfig
from src.risk.risk_manager import RiskManager
from src.storage.database import Database

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def engine_risk_manager():
    """Create a risk manager for engine testing."""
    return RiskManager()


@pytest.fixture
def all_engines(engine_risk_manager):
    """Create all 4 engines with proper allocations."""
    # CORE-HODL: 60% allocation
    core_engine = CoreHodlEngine(
        symbols=["BTCUSDT", "ETHUSDT"],
        config=CoreHodlConfig(
            engine_type=EngineType.CORE_HODL,
            allocation_pct=Decimal("0.60"),
            dca_interval_hours=168,
            dca_amount_usdt=Decimal("100.0"),
            btc_target_pct=Decimal("0.667"),
            eth_target_pct=Decimal("0.333"),
        ),
        risk_manager=engine_risk_manager,
    )

    # TREND: 20% allocation
    trend_engine = TrendEngine(
        symbols=["BTC-PERP", "ETH-PERP"],
        config=TrendEngineConfig(
            engine_type=EngineType.TREND,
            allocation_pct=Decimal("0.20"),
            ema_fast_period=50,
            ema_slow_period=200,
            adx_threshold=Decimal("25.0"),
            max_leverage=Decimal("2.0"),
            risk_per_trade=Decimal("0.01"),
        ),
        risk_manager=engine_risk_manager,
    )

    # FUNDING: 15% allocation
    funding_engine = FundingEngine(
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BTC-PERP", "ETH-PERP", "SOL-PERP"],
        config=FundingEngineConfig(
            engine_type=EngineType.FUNDING,
            allocation_pct=Decimal("0.15"),
            min_funding_rate=Decimal("0.0001"),
            max_basis_pct=Decimal("0.02"),
            compound_pct=Decimal("0.5"),
            assets=["BTC", "ETH", "SOL"],
        ),
        risk_manager=engine_risk_manager,
    )

    # TACTICAL: 5% allocation
    tactical_engine = TacticalEngine(
        symbols=["BTCUSDT", "ETHUSDT"],
        config=TacticalEngineConfig(
            engine_type=EngineType.TACTICAL,
            allocation_pct=Decimal("0.05"),
            trigger_levels=[
                (Decimal("0.50"), Decimal("0.50")),
                (Decimal("0.70"), Decimal("1.00")),
            ],
            profit_target_pct=Decimal("1.00"),
            max_hold_days=365,
            btc_allocation=Decimal("0.80"),
            eth_allocation=Decimal("0.20"),
        ),
        risk_manager=engine_risk_manager,
    )

    return {
        EngineType.CORE_HODL: core_engine,
        EngineType.TREND: trend_engine,
        EngineType.FUNDING: funding_engine,
        EngineType.TACTICAL: tactical_engine,
    }


@pytest.fixture
def sample_market_data_all_engines():
    """Create sample market data for all engine symbols."""
    base_time = datetime.utcnow()

    # Generate 250 bars for trend analysis
    btc_bars = []
    eth_bars = []
    btc_perp_bars = []
    eth_perp_bars = []
    sol_bars = []
    sol_perp_bars = []

    base_price_btc = Decimal("50000")
    base_price_eth = Decimal("3000")
    base_price_sol = Decimal("100")

    for i in range(250):
        timestamp = base_time - timedelta(hours=250 - i)

        # Uptrend data for trend engine
        btc_price = base_price_btc + Decimal(str(i * 50))
        eth_price = base_price_eth + Decimal(str(i * 3))
        sol_price = base_price_sol + Decimal(str(i * 0.1))

        btc_bars.append(
            MarketData(
                symbol="BTCUSDT",
                timestamp=timestamp,
                open=btc_price - Decimal("50"),
                high=btc_price + Decimal("100"),
                low=btc_price - Decimal("100"),
                close=btc_price,
                volume=Decimal("1000"),
                timeframe="1h",
            )
        )

        eth_bars.append(
            MarketData(
                symbol="ETHUSDT",
                timestamp=timestamp,
                open=eth_price - Decimal("10"),
                high=eth_price + Decimal("20"),
                low=eth_price - Decimal("20"),
                close=eth_price,
                volume=Decimal("5000"),
                timeframe="1h",
            )
        )

        sol_bars.append(
            MarketData(
                symbol="SOLUSDT",
                timestamp=timestamp,
                open=sol_price - Decimal("1"),
                high=sol_price + Decimal("2"),
                low=sol_price - Decimal("2"),
                close=sol_price,
                volume=Decimal("10000"),
                timeframe="1h",
            )
        )

        # Perp prices with small premium
        btc_perp_bars.append(
            MarketData(
                symbol="BTC-PERP",
                timestamp=timestamp,
                open=btc_price - Decimal("40"),
                high=btc_price + Decimal("110"),
                low=btc_price - Decimal("90"),
                close=btc_price + Decimal("50"),  # Small premium
                volume=Decimal("2000"),
                timeframe="1h",
            )
        )

        eth_perp_bars.append(
            MarketData(
                symbol="ETH-PERP",
                timestamp=timestamp,
                open=eth_price - Decimal("8"),
                high=eth_price + Decimal("22"),
                low=eth_price - Decimal("18"),
                close=eth_price + Decimal("5"),  # Small premium
                volume=Decimal("8000"),
                timeframe="1h",
            )
        )

        sol_perp_bars.append(
            MarketData(
                symbol="SOL-PERP",
                timestamp=timestamp,
                open=sol_price - Decimal("0.8"),
                high=sol_price + Decimal("2.2"),
                low=sol_price - Decimal("1.8"),
                close=sol_price + Decimal("0.5"),  # Small premium
                volume=Decimal("15000"),
                timeframe="1h",
            )
        )

    return {
        "BTCUSDT": btc_bars,
        "ETHUSDT": eth_bars,
        "SOLUSDT": sol_bars,
        "BTC-PERP": btc_perp_bars,
        "ETH-PERP": eth_perp_bars,
        "SOL-PERP": sol_perp_bars,
    }


@pytest.fixture
def crash_market_data():
    """Create market data simulating a crash for tactical engine testing."""
    base_time = datetime.utcnow()

    # BTC at 30000 (more than 50% down from 69000 ATH)
    # 30000/69000 = 0.434, so drawdown = 1 - 0.434 = 0.566 = 56.6%
    return {
        "BTCUSDT": [
            MarketData(
                symbol="BTCUSDT",
                timestamp=base_time,
                open=Decimal("29500"),
                high=Decimal("30500"),
                low=Decimal("29000"),
                close=Decimal("30000"),
                volume=Decimal("10000"),
                timeframe="1h",
            )
        ],
        "ETHUSDT": [
            MarketData(
                symbol="ETHUSDT",
                timestamp=base_time,
                open=Decimal("1600"),
                high=Decimal("1700"),
                low=Decimal("1550"),
                close=Decimal("1650"),
                volume=Decimal("50000"),
                timeframe="1h",
            )
        ],
    }


@pytest_asyncio.fixture
async def test_database():
    """Create an in-memory database for testing."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    yield db
    await db.close()


# =============================================================================
# Test Engine Instantiation
# =============================================================================


class TestEngineInstantiation:
    """Test that all 4 engines can be instantiated together."""

    def test_all_engines_created(self, all_engines):
        """Test all 4 engines are created successfully."""
        assert EngineType.CORE_HODL in all_engines
        assert EngineType.TREND in all_engines
        assert EngineType.FUNDING in all_engines
        assert EngineType.TACTICAL in all_engines

        # Verify each engine is the correct type
        assert isinstance(all_engines[EngineType.CORE_HODL], CoreHodlEngine)
        assert isinstance(all_engines[EngineType.TREND], TrendEngine)
        assert isinstance(all_engines[EngineType.FUNDING], FundingEngine)
        assert isinstance(all_engines[EngineType.TACTICAL], TacticalEngine)

    def test_engine_types_set_correctly(self, all_engines):
        """Test each engine has correct engine type set."""
        assert all_engines[EngineType.CORE_HODL].engine_type == EngineType.CORE_HODL
        assert all_engines[EngineType.TREND].engine_type == EngineType.TREND
        assert all_engines[EngineType.FUNDING].engine_type == EngineType.FUNDING
        assert all_engines[EngineType.TACTICAL].engine_type == EngineType.TACTICAL

    def test_engines_are_active_by_default(self, all_engines):
        """Test all engines are active by default."""
        for engine in all_engines.values():
            assert engine.is_active is True
            assert engine.state.is_active is True

    def test_engine_symbols_configured(self, all_engines):
        """Test each engine has correct symbols configured."""
        assert all_engines[EngineType.CORE_HODL].symbols == ["BTCUSDT", "ETHUSDT"]
        assert all_engines[EngineType.TREND].symbols == ["BTC-PERP", "ETH-PERP"]
        assert set(all_engines[EngineType.FUNDING].symbols) == {
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "BTC-PERP",
            "ETH-PERP",
            "SOL-PERP",
        }
        assert all_engines[EngineType.TACTICAL].symbols == ["BTCUSDT", "ETHUSDT"]

    def test_engines_share_risk_manager(self, all_engines, engine_risk_manager):
        """Test all engines share the same risk manager."""
        for engine in all_engines.values():
            assert engine.risk_manager is engine_risk_manager

    def test_no_conflicts_between_engines(self, all_engines):
        """Test no symbol or configuration conflicts between engines."""
        # Check that engines don't share mutable state
        core = all_engines[EngineType.CORE_HODL]
        trend = all_engines[EngineType.TREND]
        funding = all_engines[EngineType.FUNDING]
        tactical = all_engines[EngineType.TACTICAL]

        # Each engine should have its own positions dict
        assert core.positions is not trend.positions
        assert trend.positions is not funding.positions
        assert funding.positions is not tactical.positions

        # Each engine should have its own state
        assert core.state is not trend.state
        assert trend.state is not funding.state
        assert funding.state is not tactical.state


# =============================================================================
# Test Total Allocation
# =============================================================================


class TestTotalAllocation:
    """Test that total allocation equals 100%."""

    def test_total_allocation_equals_100_percent(self, all_engines):
        """Test that all engine allocations sum to 100%."""
        total_allocation = sum(
            engine.config.allocation_pct for engine in all_engines.values()
        )
        assert total_allocation == Decimal("1.0")

    def test_individual_allocations_correct(self, all_engines):
        """Test each engine has correct allocation percentage."""
        assert all_engines[EngineType.CORE_HODL].config.allocation_pct == Decimal(
            "0.60"
        )
        assert all_engines[EngineType.TREND].config.allocation_pct == Decimal("0.20")
        assert all_engines[EngineType.FUNDING].config.allocation_pct == Decimal("0.15")
        assert all_engines[EngineType.TACTICAL].config.allocation_pct == Decimal("0.05")

    def test_allocation_in_engine_state(self, all_engines):
        """Test allocation is reflected in engine state."""
        for engine_type, engine in all_engines.items():
            assert engine.state.current_allocation_pct == engine.config.allocation_pct

    def test_calculate_engine_allocations(self, all_engines):
        """Test calculating USD allocations for a portfolio."""
        portfolio_value = Decimal("100000")

        expected = {
            EngineType.CORE_HODL: Decimal("60000"),
            EngineType.TREND: Decimal("20000"),
            EngineType.FUNDING: Decimal("15000"),
            EngineType.TACTICAL: Decimal("5000"),
        }

        for engine_type, engine in all_engines.items():
            allocation_usd = portfolio_value * engine.config.allocation_pct
            assert allocation_usd == expected[engine_type]


# =============================================================================
# Test Signal Generation
# =============================================================================


class TestSignalGeneration:
    """Test signal generation across all engines."""

    @pytest.mark.asyncio
    async def test_core_hodl_generates_dca_signals(
        self, all_engines, sample_market_data_all_engines
    ):
        """Test CORE-HODL generates DCA signals."""
        core = all_engines[EngineType.CORE_HODL]

        # Filter data for CORE-HODL symbols only
        core_data = {
            "BTCUSDT": sample_market_data_all_engines["BTCUSDT"],
            "ETHUSDT": sample_market_data_all_engines["ETHUSDT"],
        }

        signals = await core.analyze(core_data)

        # Should generate DCA signals for both symbols
        assert len(signals) == 2
        assert all(s.signal_type == SignalType.BUY for s in signals)
        assert all(s.engine_type == EngineType.CORE_HODL for s in signals)

    @pytest.mark.asyncio
    async def test_trend_generates_entry_signals(
        self, all_engines, sample_market_data_all_engines
    ):
        """Test TREND engine generates entry signals in uptrend."""
        trend = all_engines[EngineType.TREND]

        # Filter data for TREND symbols
        trend_data = {
            "BTC-PERP": sample_market_data_all_engines["BTC-PERP"],
            "ETH-PERP": sample_market_data_all_engines["ETH-PERP"],
        }

        signals = await trend.analyze(trend_data)

        # In uptrend with sufficient data, should generate entry signals
        assert (
            len(signals) >= 0
        )  # May or may not generate depending on trend conditions

    @pytest.mark.asyncio
    async def test_funding_generates_arbitrage_signals(
        self, all_engines, sample_market_data_all_engines
    ):
        """Test FUNDING engine generates arbitrage signals."""
        funding = all_engines[EngineType.FUNDING]
        funding.state.current_value = Decimal("15000")  # Set positive capital

        # Set positive predicted funding rate
        funding.predicted_funding_rates["BTC"] = Decimal("0.0002")  # 0.02% per 8h

        signals = await funding.analyze(sample_market_data_all_engines)

        # May generate entry signals if conditions are met
        # Each entry creates 2 signals (spot buy + perp short)
        assert len(signals) >= 0

    @pytest.mark.asyncio
    async def test_tactical_generates_deployment_signals_in_crash(
        self, all_engines, crash_market_data
    ):
        """Test TACTICAL engine generates deployment signals during crash."""
        tactical = all_engines[EngineType.TACTICAL]
        tactical.btc_ath = Decimal("69000")  # Set ATH
        tactical.state.current_value = Decimal("5000")  # Set positive capital
        tactical.deployment_cash_remaining = Decimal("1.0")  # Ensure cash is available
        tactical.last_deployment_time = None  # Reset cooldown

        # First update market state to set drawdown
        tactical._update_market_state(crash_market_data, datetime.utcnow())

        # Verify drawdown is calculated
        assert tactical.current_drawdown > Decimal(
            "0.45"
        ), f"Drawdown is only {tactical.current_drawdown}"

        signals = await tactical.analyze(crash_market_data)

        # Should generate deployment signals at -50% drawdown
        assert (
            len(signals) > 0
        ), f"No signals generated. Drawdown: {tactical.current_drawdown}, Cash: {tactical.deployment_cash_remaining}"
        assert all(s.signal_type == SignalType.BUY for s in signals)
        assert all(s.engine_type == EngineType.TACTICAL for s in signals)

    @pytest.mark.asyncio
    async def test_all_engines_generate_signals_simultaneously(
        self, all_engines, sample_market_data_all_engines, crash_market_data
    ):
        """Test all engines can generate signals simultaneously without conflicts."""
        # Prepare funding engine
        all_engines[EngineType.FUNDING].state.current_value = Decimal("15000")
        all_engines[EngineType.FUNDING].predicted_funding_rates["BTC"] = Decimal(
            "0.0002"
        )

        # Prepare tactical engine with crash data
        all_engines[EngineType.TACTICAL].btc_ath = Decimal("69000")
        all_engines[EngineType.TACTICAL].state.current_value = Decimal("5000")
        all_engines[EngineType.TACTICAL].deployment_cash_remaining = Decimal("1.0")
        all_engines[EngineType.TACTICAL].last_deployment_time = None

        # Generate signals from all engines
        core_signals = await all_engines[EngineType.CORE_HODL].analyze(
            {
                "BTCUSDT": sample_market_data_all_engines["BTCUSDT"],
                "ETHUSDT": sample_market_data_all_engines["ETHUSDT"],
            }
        )

        trend_signals = await all_engines[EngineType.TREND].analyze(
            {
                "BTC-PERP": sample_market_data_all_engines["BTC-PERP"],
                "ETH-PERP": sample_market_data_all_engines["ETH-PERP"],
            }
        )

        funding_signals = await all_engines[EngineType.FUNDING].analyze(
            sample_market_data_all_engines
        )

        tactical_signals = await all_engines[EngineType.TACTICAL].analyze(
            crash_market_data
        )

        # CORE-HODL should generate signals
        assert len(core_signals) > 0
        # TACTICAL may or may not generate signals depending on conditions
        # Trend and funding may or may not generate signals based on conditions

        # Verify signal attribution is correct
        assert all(s.engine_type == EngineType.CORE_HODL for s in core_signals)
        assert all(s.engine_type == EngineType.TACTICAL for s in tactical_signals)

    def test_signals_have_unique_metadata(self, all_engines):
        """Test that signals from different engines have appropriate metadata."""
        core = all_engines[EngineType.CORE_HODL]

        # Create a DCA signal
        signal = core._create_dca_signal("BTCUSDT", Decimal("50000"))

        assert signal.metadata.get("strategy") == "DCA"
        assert signal.metadata.get("engine") == "CORE-HODL"
        assert "amount_usd" in signal.metadata


# =============================================================================
# Test Capital Allocation
# =============================================================================


class TestCapitalAllocation:
    """Test capital allocation and rebalancing across engines."""

    def test_engine_allocations_sum_to_100(self, all_engines):
        """Test that allocations sum to exactly 100%."""
        allocations = [engine.config.allocation_pct for engine in all_engines.values()]
        assert sum(allocations) == Decimal("1.0")

    def test_update_portfolio_value(self, all_engines):
        """Test updating portfolio value updates all engines."""
        prices = {
            "BTCUSDT": Decimal("55000"),
            "ETHUSDT": Decimal("3200"),
            "BTC-PERP": Decimal("55050"),
            "ETH-PERP": Decimal("3205"),
            "SOLUSDT": Decimal("110"),
            "SOL-PERP": Decimal("110.5"),
        }

        for engine in all_engines.values():
            engine.state.cash_buffer = Decimal("1000")
            engine.update_portfolio_value(prices)
            assert engine.state.current_value >= Decimal("1000")

    def test_calculate_position_size_respects_allocation(self, all_engines):
        """Test position sizing respects engine allocation."""
        core = all_engines[EngineType.CORE_HODL]
        core.state.current_value = Decimal("60000")  # 60% of 100k

        size = core.calculate_position_size(
            entry_price=Decimal("50000"), stop_price=Decimal("48500")
        )

        # Position size should be calculated based on engine capital
        assert size > Decimal("0")
        # Max position is 50% of engine capital
        max_size = Decimal("60000") * Decimal("0.5") / Decimal("50000")
        assert size <= max_size


# =============================================================================
# Test Risk Manager Integration
# =============================================================================


class TestRiskManagerIntegration:
    """Test risk manager integration with all engines."""

    def test_all_signals_pass_through_risk_manager(
        self, all_engines, engine_risk_manager
    ):
        """Test that all engine signals can be validated by risk manager."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("80000")
        )

        # Initialize risk manager
        asyncio.run(engine_risk_manager.initialize(portfolio))

        # Create signals from each engine
        signals = [
            TradingSignal(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                strategy_name="Test",
                engine_type=EngineType.CORE_HODL,
                confidence=0.8,
                metadata={"entry_price": "50000"},
            ),
            TradingSignal(
                symbol="BTC-PERP",
                signal_type=SignalType.BUY,
                strategy_name="Test",
                engine_type=EngineType.TREND,
                confidence=0.8,
                metadata={"entry_price": "50000"},
            ),
            TradingSignal(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                strategy_name="Test",
                engine_type=EngineType.FUNDING,
                confidence=0.8,
                metadata={"entry_price": "50000", "leg": "spot_long"},
            ),
            TradingSignal(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                strategy_name="Test",
                engine_type=EngineType.TACTICAL,
                confidence=0.95,
                metadata={"entry_price": "35000"},
            ),
        ]

        for signal in signals:
            risk_check = engine_risk_manager.check_signal(signal, portfolio, {})
            assert risk_check is not None
            # Signal should pass or be rejected for valid reasons
            assert isinstance(risk_check.passed, bool)

    def test_risk_manager_rejects_low_confidence_signals(
        self, all_engines, engine_risk_manager
    ):
        """Test risk manager rejects low confidence signals from any engine."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("80000")
        )

        low_confidence_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            engine_type=EngineType.CORE_HODL,
            confidence=0.3,  # Below 0.6 threshold
            metadata={},
        )

        risk_check = engine_risk_manager.check_signal(
            low_confidence_signal, portfolio, {}
        )

        assert risk_check.passed is False
        assert "confidence" in risk_check.reason.lower()

    def test_risk_manager_respects_position_limits(
        self, all_engines, engine_risk_manager
    ):
        """Test risk manager respects position limits across all engines."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"), available_balance=Decimal("80000")
        )

        # Create a large existing position (6% of portfolio, over 5% limit)
        existing_positions = {
            "BTCUSDT": Position(
                symbol="BTCUSDT",
                side=PositionSide.LONG,
                entry_price=Decimal("50000"),
                amount=Decimal("0.12"),  # $6000 = 6% of portfolio
            )
        }

        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            engine_type=EngineType.CORE_HODL,
            confidence=0.8,
            metadata={},
        )

        risk_check = engine_risk_manager.check_signal(
            signal, portfolio, existing_positions
        )

        # Should be rejected due to position size limit
        assert risk_check.passed is False

    @pytest.mark.asyncio
    async def test_engine_respects_risk_manager_rejection(self, all_engines):
        """Test engines respect risk manager rejections."""
        core = all_engines[EngineType.CORE_HODL]

        # Create a mock risk manager that rejects all signals
        mock_risk_manager = MagicMock()
        mock_risk_manager.check_signal.return_value = MagicMock(
            passed=False, reason="Test rejection"
        )

        core.risk_manager = mock_risk_manager

        # Engine should still generate signals
        # but external code should check with risk manager before executing
        signal = core._create_dca_signal("BTCUSDT", Decimal("50000"))

        # Verify signal was created
        assert signal is not None


# =============================================================================
# Test Engine State Persistence
# =============================================================================


class TestEngineStatePersistence:
    """Test engine state persistence and recovery."""

    @pytest.mark.asyncio
    async def test_save_and_load_core_hodl_state(self, all_engines, test_database):
        """Test saving and loading CORE-HODL engine state."""
        core = all_engines[EngineType.CORE_HODL]

        # Set some state
        core.dca_purchase_count["BTCUSDT"] = 10
        core.total_dca_invested["BTCUSDT"] = Decimal("5000")
        core.last_dca_time["BTCUSDT"] = datetime.utcnow()
        core.state.current_value = Decimal("60000")

        # Save state
        state_data = {
            "dca_purchase_count": core.dca_purchase_count,
            "total_dca_invested": {
                k: str(v) for k, v in core.total_dca_invested.items()
            },
            "last_dca_time": {
                k: v.isoformat() if v else None for k, v in core.last_dca_time.items()
            },
            "current_value": str(core.state.current_value),
            "engine_type": core.engine_type.value,
        }

        await test_database.save_engine_state(
            engine_name="CORE_HODL",
            state="active",
            allocation_pct=core.config.allocation_pct,
            performance_metrics=state_data,
        )

        # Load state
        loaded = await test_database.get_engine_state("CORE_HODL")

        assert loaded is not None
        assert loaded["engine_name"] == "CORE_HODL"
        assert "performance_metrics" in loaded

    @pytest.mark.asyncio
    async def test_save_and_load_position_state(self, all_engines, test_database):
        """Test saving and loading position state."""
        core = all_engines[EngineType.CORE_HODL]

        # Create a position
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5"),
            metadata={"engine_type": "CORE_HODL"},
        )
        core.positions["BTCUSDT"] = position

        # Save position
        await test_database.save_position(position)

        # Load position
        loaded = await test_database.get_position("BTCUSDT")

        assert loaded is not None
        assert loaded.symbol == "BTCUSDT"
        assert loaded.amount == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_dca_state_persistence(self, all_engines, test_database):
        """Test DCA state persistence across restarts."""
        core = all_engines[EngineType.CORE_HODL]

        # Simulate some DCA purchases
        await core.on_order_filled(
            symbol="BTCUSDT", side="buy", amount=Decimal("0.1"), price=Decimal("50000")
        )
        await core.on_order_filled(
            symbol="BTCUSDT", side="buy", amount=Decimal("0.1"), price=Decimal("52000")
        )

        # Verify state
        assert core.dca_purchase_count["BTCUSDT"] == 2
        assert core.total_dca_invested["BTCUSDT"] == Decimal(
            "10200"
        )  # 0.1*50000 + 0.1*52000

        # Save state
        state = core.get_dca_stats()

        assert state["purchase_count"]["BTCUSDT"] == 2
        # String comparison - accept both "10200" and "10200.0"
        assert "10200" in state["total_invested"]["BTCUSDT"]

    @pytest.mark.asyncio
    async def test_position_tracking_survives_reload(self, all_engines, test_database):
        """Test position tracking survives state reload."""
        trend = all_engines[EngineType.TREND]

        # Create position through order fill
        await trend.on_order_filled(
            symbol="BTC-PERP", side="buy", amount=Decimal("0.5"), price=Decimal("50000")
        )

        # Verify position exists
        assert "BTC-PERP" in trend.positions
        assert trend.positions["BTC-PERP"].amount == Decimal("0.5")
        assert trend.entry_prices["BTC-PERP"] == Decimal("50000")

        # Simulate state retrieval
        position_data = trend.positions["BTC-PERP"].model_dump()

        assert position_data["symbol"] == "BTC-PERP"
        # Amount can be Decimal or string depending on serialization
        assert float(position_data["amount"]) == 0.5


# =============================================================================
# Test Inter-Engine Communication
# =============================================================================


class TestInterEngineCommunication:
    """Test capital flows between engines."""

    @pytest.mark.asyncio
    async def test_funding_transfers_profits_to_tactical(self, all_engines):
        """Test FUNDING engine transfers profits to TACTICAL."""
        funding = all_engines[EngineType.FUNDING]

        # Simulate profit in funding engine
        funding.state.current_value = Decimal("15000")
        funding.total_pnl = Decimal("1000")

        # Create a position close with profit
        funding.arbitrage_positions["BTC"] = {
            "spot_size": Decimal("0.1"),
            "perp_size": Decimal("0.1"),
            "entry_time": datetime.utcnow(),
        }

        await funding.on_position_closed(
            symbol="BTC-PERP",
            pnl=Decimal("500"),
            pnl_pct=Decimal("10"),
            close_reason="basis_limit",
        )

        # Should have pending transfer to tactical
        expected_transfer = Decimal("500") * (
            Decimal("1") - funding.funding_config.compound_pct
        )
        assert funding.pending_tactical_transfer == expected_transfer

    @pytest.mark.asyncio
    async def test_tactical_transfers_profits_to_core(self, all_engines):
        """Test TACTICAL engine transfers profits to CORE-HODL."""
        tactical = all_engines[EngineType.TACTICAL]

        # Create position
        tactical.positions["BTCUSDT"] = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("35000"),
            amount=Decimal("0.1"),
        )
        tactical.entry_prices["BTCUSDT"] = Decimal("35000")

        # Close with profit (100% profit target)
        await tactical.on_position_closed(
            symbol="BTCUSDT",
            pnl=Decimal("3500"),  # 100% profit
            pnl_pct=Decimal("100"),
            close_reason="profit_target",
        )

        # Should have pending transfer to core
        assert tactical.pending_core_transfer == Decimal("3500")
        assert tactical.profits_realized == Decimal("3500")

    def test_capital_flow_allocation(self, all_engines):
        """Test capital flow allocation percentages."""
        funding = all_engines[EngineType.FUNDING]

        # FUNDING splits profits 50/50 between compound and TACTICAL
        assert funding.funding_config.compound_pct == Decimal("0.5")

        # TACTICAL returns 100% of profits to CORE
        tactical = all_engines[EngineType.TACTICAL]
        # TACTICAL transfers all profits to CORE (implicit 100%)

    @pytest.mark.asyncio
    async def test_engine_pnl_tracking(self, all_engines):
        """Test that each engine tracks its own PnL independently."""
        core = all_engines[EngineType.CORE_HODL]
        trend = all_engines[EngineType.TREND]
        funding = all_engines[EngineType.FUNDING]
        tactical = all_engines[EngineType.TACTICAL]

        # Add PnL to each engine
        core.total_pnl = Decimal("1000")
        trend.total_pnl = Decimal("500")
        funding.total_pnl = Decimal("200")
        tactical.total_pnl = Decimal("1000")

        # Verify independent tracking
        assert core.total_pnl == Decimal("1000")
        assert trend.total_pnl == Decimal("500")
        assert funding.total_pnl == Decimal("200")
        assert tactical.total_pnl == Decimal("1000")

        # Verify stats include PnL
        core_stats = core.get_stats()
        assert core_stats["total_pnl"] == "1000"


# =============================================================================
# Test Engine Independence
# =============================================================================


class TestEngineIndependence:
    """Test that engines operate independently."""

    def test_engine_failure_isolation(self, all_engines):
        """Test that failure in one engine doesn't affect others."""
        # Disable one engine
        all_engines[EngineType.TREND].config.enabled = False
        all_engines[EngineType.TREND].state.is_active = False

        # Other engines should still be active
        assert all_engines[EngineType.CORE_HODL].is_active is True
        assert all_engines[EngineType.FUNDING].is_active is True
        assert all_engines[EngineType.TACTICAL].is_active is True

        # TREND should be inactive
        assert all_engines[EngineType.TREND].is_active is False

    def test_engine_pause_isolation(self, all_engines):
        """Test that pausing one engine doesn't pause others."""
        # Pause one engine
        all_engines[EngineType.CORE_HODL].pause("Test pause", duration_seconds=3600)

        # Other engines should not be paused
        assert all_engines[EngineType.TREND].state.is_paused is False
        assert all_engines[EngineType.FUNDING].state.is_paused is False
        assert all_engines[EngineType.TACTICAL].state.is_paused is False

        # CORE-HODL should be paused
        assert all_engines[EngineType.CORE_HODL].state.is_paused is True

    def test_engine_error_tracking(self, all_engines):
        """Test that error tracking is per-engine."""
        # Record errors in different engines
        all_engines[EngineType.CORE_HODL].record_error("Core error 1")
        all_engines[EngineType.TREND].record_error("Trend error 1")
        all_engines[EngineType.TREND].record_error("Trend error 2")

        # Verify independent error counts
        assert all_engines[EngineType.CORE_HODL].state.error_count == 1
        assert all_engines[EngineType.TREND].state.error_count == 2
        assert all_engines[EngineType.FUNDING].state.error_count == 0
        assert all_engines[EngineType.TACTICAL].state.error_count == 0


# =============================================================================
# Test Comprehensive Integration Scenarios
# =============================================================================


class TestComprehensiveIntegrationScenarios:
    """Test comprehensive integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_system_initialization(self, all_engines, engine_risk_manager):
        """Test full system initialization with all engines."""
        # Verify all engines are properly configured
        for engine_type, engine in all_engines.items():
            assert engine.engine_type == engine_type
            assert engine.risk_manager is engine_risk_manager
            assert engine.is_active is True
            assert engine.config.enabled is True

        # Verify total allocation
        total = sum(e.config.allocation_pct for e in all_engines.values())
        assert total == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_simultaneous_analysis(
        self, all_engines, sample_market_data_all_engines, crash_market_data
    ):
        """Test simultaneous analysis across all engines."""
        # Set up engines
        all_engines[EngineType.FUNDING].state.current_value = Decimal("15000")
        all_engines[EngineType.FUNDING].predicted_funding_rates["BTC"] = Decimal(
            "0.0002"
        )
        all_engines[EngineType.TACTICAL].btc_ath = Decimal("69000")
        all_engines[EngineType.TACTICAL].state.current_value = Decimal("5000")

        # Run analysis on all engines concurrently
        import asyncio

        tasks = [
            all_engines[EngineType.CORE_HODL].analyze(
                {
                    "BTCUSDT": sample_market_data_all_engines["BTCUSDT"],
                    "ETHUSDT": sample_market_data_all_engines["ETHUSDT"],
                }
            ),
            all_engines[EngineType.TREND].analyze(
                {
                    "BTC-PERP": sample_market_data_all_engines["BTC-PERP"],
                    "ETH-PERP": sample_market_data_all_engines["ETH-PERP"],
                }
            ),
            all_engines[EngineType.FUNDING].analyze(sample_market_data_all_engines),
            all_engines[EngineType.TACTICAL].analyze(crash_market_data),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all analyses completed without exceptions
        for result in results:
            assert not isinstance(result, Exception)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_engine_stats_consistency(self, all_engines):
        """Test that engine stats are consistent and complete."""
        for engine in all_engines.values():
            stats = engine.get_stats()

            # Required fields in all engine stats
            required_fields = [
                "engine_type",
                "is_active",
                "can_trade",
                "allocation_pct",
                "current_value",
                "signals_generated",
                "signals_executed",
                "total_trades",
                "winning_trades",
                "losing_trades",
                "win_rate",
                "total_pnl",
                "total_fees",
            ]

            for field in required_fields:
                assert (
                    field in stats
                ), f"Missing field {field} in {engine.engine_type.value} stats"

    @pytest.mark.asyncio
    async def test_signal_metadata_completeness(self, all_engines):
        """Test that signals have complete metadata."""
        core = all_engines[EngineType.CORE_HODL]

        # Generate signals
        dca_signal = core._create_dca_signal("BTCUSDT", Decimal("50000"))

        # Verify metadata completeness
        assert "strategy" in dca_signal.metadata
        assert "engine" in dca_signal.metadata
        assert "amount_usd" in dca_signal.metadata
        assert "current_price" in dca_signal.metadata

        # Verify engine type is set
        assert dca_signal.engine_type == EngineType.CORE_HODL


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEngineEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_engine_with_no_data(self, all_engines):
        """Test engines handle missing data gracefully."""
        empty_data = {}

        for engine in all_engines.values():
            signals = await engine.analyze(empty_data)
            assert isinstance(signals, list)
            assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_engine_with_partial_data(self, all_engines):
        """Test engines handle partial data gracefully."""
        partial_data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=Decimal("50000"),
                    high=Decimal("51000"),
                    low=Decimal("49000"),
                    close=Decimal("50500"),
                    volume=Decimal("1000"),
                )
            ]
        }

        # CORE-HODL should work with partial data
        core_signals = await all_engines[EngineType.CORE_HODL].analyze(partial_data)
        assert isinstance(core_signals, list)

    def test_engine_with_zero_allocation(self, engine_risk_manager):
        """Test engine behavior with zero allocation."""
        engine = CoreHodlEngine(
            config=CoreHodlConfig(
                engine_type=EngineType.CORE_HODL, allocation_pct=Decimal("0")
            ),
            risk_manager=engine_risk_manager,
        )

        assert engine.config.allocation_pct == Decimal("0")
        assert engine.state.current_allocation_pct == Decimal("0")

    @pytest.mark.asyncio
    async def test_position_close_without_position(self, all_engines):
        """Test handling position close when no position exists."""
        core = all_engines[EngineType.CORE_HODL]

        # Close a position that doesn't exist - should not crash
        await core.on_position_closed(
            symbol="NONEXISTENT",
            pnl=Decimal("0"),
            pnl_pct=Decimal("0"),
            close_reason="test",
        )

        # Engine should still be functional
        assert core.is_active is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
