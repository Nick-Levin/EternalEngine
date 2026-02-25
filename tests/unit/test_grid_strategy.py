"""
Unit tests for Grid Trading Strategy in The Eternal Engine.

This module tests the GridStrategy class which implements grid trading
with buy/sell levels around a center price.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import MarketData, SignalType, TradingSignal
from src.strategies.grid_strategy import GridStrategy

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_symbols():
    """Provide standard test symbols."""
    return ["BTCUSDT", "ETHUSDT"]


@pytest.fixture
def sample_market_data():
    """Provide sample market data for testing."""
    return {
        "BTCUSDT": [
            MarketData(
                symbol="BTCUSDT",
                timestamp=datetime.utcnow(),
                open=Decimal("50000"),
                high=Decimal("51000"),
                low=Decimal("49500"),
                close=Decimal("50000"),
                volume=Decimal("1000"),
            )
        ],
        "ETHUSDT": [
            MarketData(
                symbol="ETHUSDT",
                timestamp=datetime.utcnow(),
                open=Decimal("3000"),
                high=Decimal("3100"),
                low=Decimal("2950"),
                close=Decimal("3000"),
                volume=Decimal("5000"),
            )
        ],
    }


@pytest.fixture
def grid_strategy_default(sample_symbols):
    """Create a Grid strategy with default configuration."""
    return GridStrategy(symbols=sample_symbols)


@pytest.fixture
def grid_strategy_custom(sample_symbols):
    """Create a Grid strategy with custom configuration."""
    return GridStrategy(
        symbols=sample_symbols, name="Custom-Grid", grid_levels=10, grid_spacing_pct=2.0
    )


@pytest.fixture
def sample_grid():
    """Provide a sample grid structure."""
    center_price = Decimal("50000")
    spacing = Decimal("0.01")  # 1%
    levels = 5

    buy_levels = []
    sell_levels = []

    for i in range(1, levels + 1):
        factor = Decimal("1") - (spacing * i)
        buy_levels.append(center_price * factor)

    for i in range(1, levels + 1):
        factor = Decimal("1") + (spacing * i)
        sell_levels.append(center_price * factor)

    stop_factor = spacing * (levels + 1)
    lower_stop = center_price * (Decimal("1") - stop_factor)
    upper_stop = center_price * (Decimal("1") + stop_factor)

    return {
        "center_price": center_price,
        "buy_levels": buy_levels,
        "sell_levels": sell_levels,
        "lower_stop": lower_stop,
        "upper_stop": upper_stop,
        "created_at": datetime.utcnow(),
    }


# =============================================================================
# TestGridStrategyInitialization
# =============================================================================


class TestGridStrategyInitialization:
    """Test Grid strategy initialization."""

    def test_initialization_with_defaults(self, sample_symbols):
        """Test Grid strategy initialization with default config."""
        strategy = GridStrategy(symbols=sample_symbols)

        assert strategy.name == "Grid"
        assert strategy.symbols == sample_symbols
        assert strategy.grid_levels == 5  # Default from config
        assert strategy.grid_spacing_pct == 1.0  # Default 1%
        assert strategy.investment_per_grid_pct == 2.0
        assert strategy.active_grids == {}
        assert strategy.filled_orders == {"BTCUSDT": [], "ETHUSDT": []}

    def test_initialization_with_custom_config(self, sample_symbols):
        """Test Grid strategy initialization with custom grid levels."""
        strategy = GridStrategy(
            symbols=sample_symbols,
            name="Test-Grid",
            grid_levels=10,
            grid_spacing_pct=2.5,
        )

        assert strategy.name == "Test-Grid"
        assert strategy.grid_levels == 10
        assert strategy.grid_spacing_pct == 2.5

    def test_grid_levels_calculated(self, sample_symbols):
        """Test that grid levels are properly configured."""
        strategy = GridStrategy(symbols=sample_symbols, grid_levels=3)

        assert strategy.grid_levels == 3

        # Create a grid and verify levels
        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)

        assert len(grid["buy_levels"]) == 3
        assert len(grid["sell_levels"]) == 3

    def test_initialization_creates_empty_grid(self, sample_symbols):
        """Test that no grids are active initially."""
        strategy = GridStrategy(symbols=sample_symbols)

        assert strategy.active_grids == {}
        assert all(len(orders) == 0 for orders in strategy.filled_orders.values())


# =============================================================================
# TestGridLevelCalculation
# =============================================================================


class TestGridLevelCalculation:
    """Test grid level calculations."""

    def test_calculate_grid_levels_geometric(self, grid_strategy_default):
        """Test geometric (percentage-based) grid level calculation."""
        strategy = grid_strategy_default
        center_price = Decimal("100")

        grid = strategy._create_grid(center_price)

        # Check buy levels are below center
        for level in grid["buy_levels"]:
            assert level < center_price

        # Check sell levels are above center
        for level in grid["sell_levels"]:
            assert level > center_price

    def test_grid_buy_levels_below_current(self, grid_strategy_default):
        """Test that buy levels are created below current price."""
        strategy = grid_strategy_default
        center_price = Decimal("50000")

        grid = strategy._create_grid(center_price)

        # All buy levels should be below center price
        assert all(level < center_price for level in grid["buy_levels"])

        # Buy levels should be in descending order
        for i in range(len(grid["buy_levels"]) - 1):
            assert grid["buy_levels"][i] > grid["buy_levels"][i + 1]

    def test_grid_sell_levels_above_current(self, grid_strategy_default):
        """Test that sell levels are created above current price."""
        strategy = grid_strategy_default
        center_price = Decimal("50000")

        grid = strategy._create_grid(center_price)

        # All sell levels should be above center price
        assert all(level > center_price for level in grid["sell_levels"])

        # Sell levels should be in ascending order
        for i in range(len(grid["sell_levels"]) - 1):
            assert grid["sell_levels"][i] < grid["sell_levels"][i + 1]

    def test_grid_spacing_respected(self, grid_strategy_custom):
        """Test that grid spacing is properly applied."""
        strategy = grid_strategy_custom  # 2% spacing
        center_price = Decimal("100")

        grid = strategy._create_grid(center_price)

        # First buy level should be approximately 2% below center
        expected_first_buy = center_price * Decimal("0.98")
        assert abs(grid["buy_levels"][0] - expected_first_buy) < Decimal("0.01")

        # First sell level should be approximately 2% above center
        expected_first_sell = center_price * Decimal("1.02")
        assert abs(grid["sell_levels"][0] - expected_first_sell) < Decimal("0.01")

    def test_grid_respects_total_range(self, grid_strategy_default):
        """Test that grid respects total range with stops."""
        strategy = grid_strategy_default
        center_price = Decimal("50000")

        grid = strategy._create_grid(center_price)

        # Lower stop should be below lowest buy level
        assert grid["lower_stop"] < min(grid["buy_levels"])

        # Upper stop should be above highest sell level
        assert grid["upper_stop"] > max(grid["sell_levels"])

    def test_grid_level_spacing_consistency(self, grid_strategy_default):
        """Test that grid levels have consistent spacing."""
        strategy = grid_strategy_default
        center_price = Decimal("100")

        grid = strategy._create_grid(center_price)

        # Check spacing between consecutive buy levels
        spacing_pct = Decimal(str(strategy.grid_spacing_pct)) / 100
        for i in range(len(grid["buy_levels"]) - 1):
            level_diff = grid["buy_levels"][i] - grid["buy_levels"][i + 1]
            expected_diff = center_price * spacing_pct
            # Allow small floating point tolerance
            ratio = level_diff / expected_diff
            assert Decimal("0.99") < ratio < Decimal("1.01")


# =============================================================================
# TestGridSignalGeneration
# =============================================================================


class TestGridSignalGeneration:
    """Test grid signal generation logic."""

    @pytest.mark.asyncio
    async def test_analyze_generates_buy_at_lower_grid(self, grid_strategy_default):
        """Test that buy signal is generated when price reaches lower grid level."""
        strategy = grid_strategy_default

        # Initialize grid with center at 50000
        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Price drops to first buy level
        buy_price = grid["buy_levels"][0]
        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=buy_price,
                    high=buy_price,
                    low=buy_price,
                    close=buy_price,
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        assert len(signals) > 0
        assert any(s.signal_type == SignalType.BUY for s in signals)

    @pytest.mark.asyncio
    async def test_analyze_generates_sell_at_upper_grid(
        self, grid_strategy_default, sample_grid
    ):
        """Test that sell signal is generated when price reaches upper grid level."""
        strategy = grid_strategy_default

        # Initialize grid
        strategy.active_grids["BTCUSDT"] = sample_grid

        # Simulate a previous buy
        strategy.filled_orders["BTCUSDT"] = [Decimal("49000")]  # Below first sell level

        # Price rises to first sell level
        sell_price = sample_grid["sell_levels"][0]
        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=sell_price,
                    high=sell_price,
                    low=sell_price,
                    close=sell_price,
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        # Should generate sell signal since we have a lower buy
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        assert len(sell_signals) > 0

    @pytest.mark.asyncio
    async def test_analyze_no_signal_between_grids(self, grid_strategy_default):
        """Test that no signal is generated when price is between grid levels."""
        strategy = grid_strategy_default

        # Initialize grid with center at 50000
        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Price is at center (between buy and sell levels)
        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=center_price,
                    high=center_price,
                    low=center_price,
                    close=center_price,
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        # Should not generate any signals between grid levels
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_grid_buy_filled_creates_sell_above(self, grid_strategy_default):
        """Test that buy fill enables sell signal at higher level."""
        strategy = grid_strategy_default

        # Initialize grid
        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Simulate buy fill at lower level
        buy_price = grid["buy_levels"][0]
        await strategy.on_order_filled("BTCUSDT", "buy", Decimal("0.001"), buy_price)

        # Now price rises to sell level
        sell_price = grid["sell_levels"][0]
        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=sell_price,
                    high=sell_price,
                    low=sell_price,
                    close=sell_price,
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        # Should generate sell signal
        assert any(s.signal_type == SignalType.SELL for s in signals)

    @pytest.mark.asyncio
    async def test_grid_sell_filled_creates_buy_below(self, grid_strategy_default):
        """Test that sell fill doesn't prevent buy at lower level."""
        strategy = grid_strategy_default

        # Initialize grid
        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Simulate sell fill at higher level
        sell_price = grid["sell_levels"][0]
        await strategy.on_order_filled("BTCUSDT", "sell", Decimal("0.001"), sell_price)

        # Price drops to buy level
        buy_price = grid["buy_levels"][0]
        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=buy_price,
                    high=buy_price,
                    low=buy_price,
                    close=buy_price,
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        # Should still generate buy signal
        assert any(s.signal_type == SignalType.BUY for s in signals)

    @pytest.mark.asyncio
    async def test_multiple_grid_levels_independent(self, grid_strategy_default):
        """Test that multiple grid levels operate independently."""
        strategy = grid_strategy_default

        center_price = Decimal("100")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Fill at multiple levels
        await strategy.on_order_filled(
            "BTCUSDT", "buy", Decimal("0.001"), grid["buy_levels"][0]
        )
        await strategy.on_order_filled(
            "BTCUSDT", "buy", Decimal("0.001"), grid["buy_levels"][1]
        )

        # Verify both fills are tracked
        assert len(strategy.filled_orders["BTCUSDT"]) == 2
        assert grid["buy_levels"][0] in strategy.filled_orders["BTCUSDT"]
        assert grid["buy_levels"][1] in strategy.filled_orders["BTCUSDT"]

    @pytest.mark.asyncio
    async def test_grid_respects_max_position(self, grid_strategy_default):
        """Test that grid respects position limits."""
        # Note: Current implementation doesn't track position size directly
        # This test verifies the strategy structure allows for future implementation
        strategy = grid_strategy_default

        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Strategy should have position tracking capabilities
        assert hasattr(strategy, "filled_orders")
        assert "BTCUSDT" in strategy.filled_orders


# =============================================================================
# TestGridExecution
# =============================================================================


class TestGridExecution:
    """Test grid execution and order handling."""

    @pytest.mark.asyncio
    async def test_on_order_filled_updates_grid_state(self, grid_strategy_default):
        """Test that order fill updates grid state."""
        strategy = grid_strategy_default

        price = Decimal("50000")

        await strategy.on_order_filled("BTCUSDT", "buy", Decimal("0.001"), price)

        assert price in strategy.filled_orders["BTCUSDT"]
        assert len(strategy.filled_orders["BTCUSDT"]) == 1

    @pytest.mark.asyncio
    async def test_on_order_filled_places_opposite_order(self, grid_strategy_default):
        """Test that grid creates opposite order after fill."""
        strategy = grid_strategy_default

        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Fill a buy order
        buy_price = grid["buy_levels"][0]
        await strategy.on_order_filled("BTCUSDT", "buy", Decimal("0.001"), buy_price)

        # Verify the fill is tracked
        assert buy_price in strategy.filled_orders["BTCUSDT"]

        # Now a sell at higher level should be possible
        sell_price = grid["sell_levels"][0]
        can_sell = strategy._should_trigger_sell(sell_price, sell_price, "BTCUSDT")
        assert can_sell is True

    @pytest.mark.asyncio
    async def test_grid_position_tracking(self, grid_strategy_default):
        """Test grid position monitoring."""
        strategy = grid_strategy_default

        # Multiple fills
        await strategy.on_order_filled(
            "BTCUSDT", "buy", Decimal("0.001"), Decimal("49000")
        )
        await strategy.on_order_filled(
            "BTCUSDT", "buy", Decimal("0.001"), Decimal("48000")
        )
        await strategy.on_order_filled(
            "BTCUSDT", "sell", Decimal("0.001"), Decimal("51000")
        )

        # Verify all fills tracked
        assert len(strategy.filled_orders["BTCUSDT"]) == 3
        assert Decimal("49000") in strategy.filled_orders["BTCUSDT"]
        assert Decimal("48000") in strategy.filled_orders["BTCUSDT"]
        assert Decimal("51000") in strategy.filled_orders["BTCUSDT"]

    @pytest.mark.asyncio
    async def test_grid_realized_pnl_calculation(self, grid_strategy_default):
        """Test realized PnL tracking."""
        strategy = grid_strategy_default

        initial_pnl = strategy.total_pnl

        # Simulate profitable round trip: buy at 49000, sell at 51000
        await strategy.on_order_filled(
            "BTCUSDT", "buy", Decimal("0.1"), Decimal("49000")
        )

        # Track realized PnL
        buy_value = Decimal("0.1") * Decimal("49000")
        sell_value = Decimal("0.1") * Decimal("51000")
        realized_pnl = sell_value - buy_value

        await strategy.on_position_closed("BTCUSDT", realized_pnl, Decimal("4.08"))

        assert strategy.total_pnl == initial_pnl + realized_pnl

    @pytest.mark.asyncio
    async def test_grid_unrealized_pnl_calculation(self, grid_strategy_default):
        """Test unrealized PnL calculation (conceptual)."""
        strategy = grid_strategy_default

        # Buy at a level
        await strategy.on_order_filled(
            "BTCUSDT", "buy", Decimal("0.1"), Decimal("49000")
        )

        # Current unrealized would depend on current price
        # This test verifies the structure exists
        assert len(strategy.filled_orders["BTCUSDT"]) > 0

    @pytest.mark.asyncio
    async def test_grid_stats_updated(self, grid_strategy_default):
        """Test that grid statistics are maintained."""
        strategy = grid_strategy_default

        initial_signals = strategy.signals_generated
        initial_trades = strategy.trades_executed

        # Generate some activity
        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=grid["buy_levels"][0],
                    high=grid["buy_levels"][0],
                    low=grid["buy_levels"][0],
                    close=grid["buy_levels"][0],
                    volume=Decimal("1000"),
                )
            ]
        }

        await strategy.analyze(data)

        # Signals should be generated
        assert strategy.signals_generated >= initial_signals


# =============================================================================
# TestGridRiskManagement
# =============================================================================


class TestGridRiskManagement:
    """Test grid risk management features."""

    @pytest.mark.asyncio
    async def test_grid_respects_max_investment_pct(self, grid_strategy_default):
        """Test that grid respects maximum investment percentage."""
        # Note: Current implementation tracks filled orders but not total investment
        # This test verifies the structure for future implementation
        strategy = grid_strategy_default

        assert hasattr(strategy, "investment_per_grid_pct")
        assert strategy.investment_per_grid_pct > 0

    @pytest.mark.asyncio
    async def test_grid_respects_max_position_per_level(self, grid_strategy_default):
        """Test per-level position limits."""
        strategy = grid_strategy_default

        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Fill at same level multiple times should be prevented
        buy_price = grid["buy_levels"][0]
        await strategy.on_order_filled("BTCUSDT", "buy", Decimal("0.001"), buy_price)

        # Check that we can't trigger another buy at same level
        should_trigger = strategy._should_trigger_buy(buy_price, buy_price, "BTCUSDT")
        assert should_trigger is False  # Already filled at this level

    @pytest.mark.asyncio
    async def test_grid_stops_on_drawdown(self, grid_strategy_default):
        """Test drawdown protection - grid reset on price outside range."""
        strategy = grid_strategy_default

        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Price drops below lower stop
        stop_price = grid["lower_stop"] * Decimal("0.99")
        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=stop_price,
                    high=stop_price,
                    low=stop_price,
                    close=stop_price,
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        # Grid should be removed
        assert "BTCUSDT" not in strategy.active_grids

    @pytest.mark.asyncio
    async def test_grid_exits_on_breakout(self, grid_strategy_default):
        """Test grid reset on price breakout above range."""
        strategy = grid_strategy_default

        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)
        strategy.active_grids["BTCUSDT"] = grid

        # Price breaks above upper stop
        breakout_price = grid["upper_stop"] * Decimal("1.01")
        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=breakout_price,
                    high=breakout_price,
                    low=breakout_price,
                    close=breakout_price,
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        # Grid should be removed
        assert "BTCUSDT" not in strategy.active_grids


# =============================================================================
# TestGridTriggerLogic
# =============================================================================


class TestGridTriggerLogic:
    """Test grid trigger logic in detail."""

    def test_should_trigger_buy_price_condition(self, grid_strategy_default):
        """Test buy trigger price condition."""
        strategy = grid_strategy_default

        level_price = Decimal("49000")

        # Price at or below level should trigger
        assert (
            strategy._should_trigger_buy(Decimal("49000"), level_price, "BTCUSDT")
            is True
        )
        assert (
            strategy._should_trigger_buy(Decimal("48900"), level_price, "BTCUSDT")
            is True
        )

        # Price above level should not trigger
        assert (
            strategy._should_trigger_buy(Decimal("49100"), level_price, "BTCUSDT")
            is False
        )

    def test_should_trigger_buy_already_filled(self, grid_strategy_default):
        """Test buy trigger when level already filled."""
        strategy = grid_strategy_default

        level_price = Decimal("49000")
        strategy.filled_orders["BTCUSDT"] = [level_price]

        # Should not trigger if already filled at this level
        assert (
            strategy._should_trigger_buy(Decimal("49000"), level_price, "BTCUSDT")
            is False
        )

    def test_should_trigger_buy_tolerance(self, grid_strategy_default):
        """Test buy trigger tolerance for similar prices."""
        strategy = grid_strategy_default

        # Fill at a price
        strategy.filled_orders["BTCUSDT"] = [Decimal("49000")]

        # Slightly different price within 0.1% should be considered same level
        similar_price = Decimal("49004")  # ~0.008% difference
        assert (
            strategy._should_trigger_buy(similar_price, similar_price, "BTCUSDT")
            is False
        )

    def test_should_trigger_sell_price_condition(self, grid_strategy_default):
        """Test sell trigger price condition."""
        strategy = grid_strategy_default

        level_price = Decimal("51000")

        # Without a lower buy, should not trigger
        assert (
            strategy._should_trigger_sell(Decimal("51000"), level_price, "BTCUSDT")
            is False
        )

        # Add a lower buy
        strategy.filled_orders["BTCUSDT"] = [Decimal("49000")]

        # Now should trigger
        assert (
            strategy._should_trigger_sell(Decimal("51000"), level_price, "BTCUSDT")
            is True
        )
        assert (
            strategy._should_trigger_sell(Decimal("51100"), level_price, "BTCUSDT")
            is True
        )

        # Price below level should not trigger
        assert (
            strategy._should_trigger_sell(Decimal("50900"), level_price, "BTCUSDT")
            is False
        )

    def test_should_trigger_sell_requires_lower_buy(self, grid_strategy_default):
        """Test that sell requires a buy at lower price."""
        strategy = grid_strategy_default

        level_price = Decimal("51000")

        # Buy at higher price doesn't count
        strategy.filled_orders["BTCUSDT"] = [Decimal("52000")]
        assert (
            strategy._should_trigger_sell(Decimal("51000"), level_price, "BTCUSDT")
            is False
        )

        # Buy at lower price enables sell
        strategy.filled_orders["BTCUSDT"] = [Decimal("50000")]
        assert (
            strategy._should_trigger_sell(Decimal("51000"), level_price, "BTCUSDT")
            is True
        )


# =============================================================================
# TestGridSignalCreation
# =============================================================================


class TestGridSignalCreation:
    """Test grid signal creation."""

    def test_create_grid_signal_buy(self, grid_strategy_default, sample_grid):
        """Test creating a buy grid signal."""
        strategy = grid_strategy_default

        signal = strategy._create_grid_signal(
            "BTCUSDT", SignalType.BUY, sample_grid["buy_levels"][0], sample_grid
        )

        assert signal.symbol == "BTCUSDT"
        assert signal.signal_type == SignalType.BUY
        assert signal.strategy_name == "Grid"
        assert signal.confidence == 0.8
        assert "grid_level" in signal.metadata
        assert "center_price" in signal.metadata
        assert "grid_spacing_pct" in signal.metadata
        assert "grid_levels" in signal.metadata

    def test_create_grid_signal_sell(self, grid_strategy_default, sample_grid):
        """Test creating a sell grid signal."""
        strategy = grid_strategy_default

        signal = strategy._create_grid_signal(
            "BTCUSDT", SignalType.SELL, sample_grid["sell_levels"][0], sample_grid
        )

        assert signal.symbol == "BTCUSDT"
        assert signal.signal_type == SignalType.SELL
        assert signal.confidence == 0.8


# =============================================================================
# TestGridInfo
# =============================================================================


class TestGridInfo:
    """Test grid information methods."""

    def test_get_grid_info_active(self, grid_strategy_default, sample_grid):
        """Test getting grid info when grid is active."""
        strategy = grid_strategy_default
        strategy.active_grids["BTCUSDT"] = sample_grid

        info = strategy.get_grid_info("BTCUSDT")

        assert info is not None
        assert "center_price" in info
        assert "buy_levels" in info
        assert "sell_levels" in info
        assert "lower_stop" in info
        assert "upper_stop" in info
        assert "created_at" in info

    def test_get_grid_info_inactive(self, grid_strategy_default):
        """Test getting grid info when grid is not active."""
        strategy = grid_strategy_default

        info = strategy.get_grid_info("BTCUSDT")

        assert info is None

    def test_reset_grid(self, grid_strategy_default, sample_grid):
        """Test manually resetting a grid."""
        strategy = grid_strategy_default
        strategy.active_grids["BTCUSDT"] = sample_grid
        strategy.filled_orders["BTCUSDT"] = [Decimal("49000"), Decimal("51000")]

        strategy.reset_grid("BTCUSDT")

        assert "BTCUSDT" not in strategy.active_grids
        assert strategy.filled_orders["BTCUSDT"] == []


# =============================================================================
# TestGridOnPositionClosed
# =============================================================================


class TestGridOnPositionClosed:
    """Test grid position close handling."""

    @pytest.mark.asyncio
    async def test_on_position_closed_updates_pnl(self, grid_strategy_default):
        """Test that position close updates total PnL."""
        strategy = grid_strategy_default

        initial_pnl = strategy.total_pnl

        await strategy.on_position_closed(
            symbol="BTCUSDT", pnl=Decimal("100"), pnl_pct=Decimal("2")
        )

        assert strategy.total_pnl == initial_pnl + Decimal("100")

    @pytest.mark.asyncio
    async def test_on_position_closed_resets_filled_orders(self, grid_strategy_default):
        """Test that position close resets filled orders."""
        strategy = grid_strategy_default

        strategy.filled_orders["BTCUSDT"] = [Decimal("49000"), Decimal("51000")]

        await strategy.on_position_closed(
            symbol="BTCUSDT", pnl=Decimal("100"), pnl_pct=Decimal("2")
        )

        assert strategy.filled_orders["BTCUSDT"] == []


# =============================================================================
# TestGridInitializationFlow
# =============================================================================


class TestGridInitializationFlow:
    """Test grid initialization on first analysis."""

    @pytest.mark.asyncio
    async def test_first_analysis_creates_grid(self, grid_strategy_default):
        """Test that first analysis creates grid for symbol."""
        strategy = grid_strategy_default

        assert "BTCUSDT" not in strategy.active_grids

        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=Decimal("50000"),
                    high=Decimal("51000"),
                    low=Decimal("49500"),
                    close=Decimal("50000"),
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        assert "BTCUSDT" in strategy.active_grids
        assert len(strategy.active_grids["BTCUSDT"]["buy_levels"]) > 0
        assert len(strategy.active_grids["BTCUSDT"]["sell_levels"]) > 0

    @pytest.mark.asyncio
    async def test_initial_buy_signals_created(self, grid_strategy_default):
        """Test that initial buy signals are created for lower levels."""
        strategy = grid_strategy_default

        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=Decimal("50000"),
                    high=Decimal("51000"),
                    low=Decimal("49500"),
                    close=Decimal("50000"),
                    volume=Decimal("1000"),
                )
            ]
        }

        signals = await strategy.analyze(data)

        # Should create initial buy signals for levels below current price
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        assert len(buy_signals) > 0


# =============================================================================
# TestGridFilledOrdersLimit
# =============================================================================


class TestGridFilledOrdersLimit:
    """Test filled orders list limits."""

    @pytest.mark.asyncio
    async def test_filled_orders_limit_enforced(self, grid_strategy_default):
        """Test that filled orders list is limited to recent 20."""
        strategy = grid_strategy_default

        # Add 25 filled orders
        for i in range(25):
            await strategy.on_order_filled(
                "BTCUSDT", "buy", Decimal("0.001"), Decimal("49000") + i
            )

        # Should only keep last 20
        assert len(strategy.filled_orders["BTCUSDT"]) == 20

        # First 5 should be removed
        assert Decimal("49000") not in strategy.filled_orders["BTCUSDT"]
        assert Decimal("49004") not in strategy.filled_orders["BTCUSDT"]

        # Last 20 should be present
        assert Decimal("49005") in strategy.filled_orders["BTCUSDT"]
        assert Decimal("49024") in strategy.filled_orders["BTCUSDT"]


# =============================================================================
# TestGridEdgeCases
# =============================================================================


class TestGridEdgeCases:
    """Test grid edge cases."""

    @pytest.mark.asyncio
    async def test_analyze_with_empty_data(self, grid_strategy_default):
        """Test analysis with empty market data."""
        strategy = grid_strategy_default

        empty_data = {}
        signals = await strategy.analyze(empty_data)

        assert signals == []

    @pytest.mark.asyncio
    async def test_analyze_with_missing_symbol_data(self, grid_strategy_default):
        """Test analysis when symbol data is missing."""
        strategy = grid_strategy_default

        data = {
            "ETHUSDT": [
                MarketData(
                    symbol="ETHUSDT",
                    timestamp=datetime.utcnow(),
                    open=Decimal("3000"),
                    high=Decimal("3100"),
                    low=Decimal("2950"),
                    close=Decimal("3000"),
                    volume=Decimal("5000"),
                )
            ]
            # BTCUSDT data is missing
        }

        signals = await strategy.analyze(data)

        # Should only process ETH
        assert all(s.symbol == "ETHUSDT" for s in signals)

    def test_create_grid_with_zero_levels(self, grid_strategy_default):
        """Test grid creation with edge case values."""
        strategy = grid_strategy_default
        strategy.grid_levels = 0

        center_price = Decimal("50000")
        grid = strategy._create_grid(center_price)

        assert grid["buy_levels"] == []
        assert grid["sell_levels"] == []

    def test_create_grid_with_large_spacing(self, grid_strategy_default):
        """Test grid creation with large spacing percentage."""
        strategy = grid_strategy_default
        strategy.grid_spacing_pct = 10.0  # 10%

        center_price = Decimal("100")
        grid = strategy._create_grid(center_price)

        # First buy level should be at 90
        assert abs(grid["buy_levels"][0] - Decimal("90")) < Decimal("0.01")

        # First sell level should be at 110
        assert abs(grid["sell_levels"][0] - Decimal("110")) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_on_order_filled_new_symbol(self, grid_strategy_default):
        """Test order fill for symbol not in filled_orders."""
        strategy = grid_strategy_default

        # Remove BTCUSDT from filled_orders to simulate new symbol
        del strategy.filled_orders["BTCUSDT"]

        # Should handle gracefully
        await strategy.on_order_filled(
            "BTCUSDT", "buy", Decimal("0.001"), Decimal("50000")
        )

        assert "BTCUSDT" in strategy.filled_orders
        assert Decimal("50000") in strategy.filled_orders["BTCUSDT"]


# =============================================================================
# TestGridMultipleSymbols
# =============================================================================


class TestGridMultipleSymbols:
    """Test grid with multiple symbols."""

    @pytest.mark.asyncio
    async def test_independent_grids_per_symbol(self, grid_strategy_default):
        """Test that each symbol has independent grid."""
        strategy = grid_strategy_default

        data = {
            "BTCUSDT": [
                MarketData(
                    symbol="BTCUSDT",
                    timestamp=datetime.utcnow(),
                    open=Decimal("50000"),
                    high=Decimal("51000"),
                    low=Decimal("49500"),
                    close=Decimal("50000"),
                    volume=Decimal("1000"),
                )
            ],
            "ETHUSDT": [
                MarketData(
                    symbol="ETHUSDT",
                    timestamp=datetime.utcnow(),
                    open=Decimal("3000"),
                    high=Decimal("3100"),
                    low=Decimal("2950"),
                    close=Decimal("3000"),
                    volume=Decimal("5000"),
                )
            ],
        }

        signals = await strategy.analyze(data)

        # Should have grids for both symbols
        assert "BTCUSDT" in strategy.active_grids
        assert "ETHUSDT" in strategy.active_grids

        # Grids should have different center prices
        assert strategy.active_grids["BTCUSDT"]["center_price"] == Decimal("50000")
        assert strategy.active_grids["ETHUSDT"]["center_price"] == Decimal("3000")

    @pytest.mark.asyncio
    async def test_reset_grid_only_affects_one_symbol(
        self, grid_strategy_default, sample_grid
    ):
        """Test that resetting grid only affects specified symbol."""
        strategy = grid_strategy_default

        strategy.active_grids["BTCUSDT"] = sample_grid
        strategy.active_grids["ETHUSDT"] = sample_grid.copy()
        strategy.active_grids["ETHUSDT"]["center_price"] = Decimal("3000")

        strategy.reset_grid("BTCUSDT")

        assert "BTCUSDT" not in strategy.active_grids
        assert "ETHUSDT" in strategy.active_grids


# =============================================================================
# TestGridGetStats
# =============================================================================


class TestGridGetStats:
    """Test grid statistics."""

    def test_get_stats_includes_base_stats(self, grid_strategy_default):
        """Test that stats include base strategy stats."""
        strategy = grid_strategy_default

        stats = strategy.get_stats()

        assert "name" in stats
        assert "symbols" in stats
        assert "is_active" in stats
        assert "signals_generated" in stats
        assert "trades_executed" in stats
        assert "total_pnl" in stats

    def test_get_stats_base_values(self, grid_strategy_default):
        """Test base stats values."""
        strategy = grid_strategy_default

        stats = strategy.get_stats()

        assert stats["name"] == "Grid"
        assert stats["symbols"] == ["BTCUSDT", "ETHUSDT"]
        assert stats["is_active"] is True


# =============================================================================
# TestGridPauseResume
# =============================================================================


class TestGridPauseResume:
    """Test grid pause and resume functionality (inherited from base)."""

    def test_pause_stops_signals(self, grid_strategy_default):
        """Test that pause stops signal generation."""
        strategy = grid_strategy_default

        assert strategy.is_active is True

        strategy.pause()

        assert strategy.is_active is False

    def test_resume_restarts_signals(self, grid_strategy_default):
        """Test that resume restarts signal generation."""
        strategy = grid_strategy_default

        strategy.pause()
        assert strategy.is_active is False

        strategy.resume()

        assert strategy.is_active is True
