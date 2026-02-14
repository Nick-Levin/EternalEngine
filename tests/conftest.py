"""Pytest fixtures and utilities for The Eternal Engine test suite."""
import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# Import models
from src.core.models import (
    Order, OrderSide, OrderType, OrderStatus,
    Position, PositionSide, Trade, TradeStatus,
    MarketData, TradingSignal, SignalType,
    Portfolio, EngineState, EngineType,
    RiskCheck, CircuitBreakerLevel
)

from src.core.config import (
    TradingConfig, BybitAPIConfig, CapitalAllocationConfig,
    CircuitBreakerConfig, PositionSizingConfig,
    CoreHodlConfig, TrendConfig, FundingConfig, TacticalConfig
)

from src.risk.risk_manager import RiskManager
from src.storage.database import Database


# =============================================================================
# Event Loop Fixture
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def test_trading_config():
    """Create a test trading configuration."""
    config = TradingConfig(
        trading_mode="paper",
        default_symbols=["BTCUSDT", "ETHUSDT"],
        max_position_pct=5.0,
        max_daily_loss_pct=2.0,
        max_weekly_loss_pct=5.0,
        max_concurrent_positions=3,
        enable_stop_loss=True,
        stop_loss_pct=3.0,
        enable_take_profit=True,
        take_profit_pct=6.0
    )
    return config


@pytest.fixture
def test_bybit_api_config():
    """Create a test Bybit API configuration."""
    config = BybitAPIConfig(
        api_mode="demo",
        demo_api_key="test_demo_key",
        demo_api_secret="test_demo_secret",
        prod_api_key="test_prod_key",
        prod_api_secret="test_prod_secret",
        testnet=True,
        timeout=30,
        retry_attempts=3
    )
    return config


@pytest.fixture
def test_capital_allocation_config():
    """Create a test capital allocation configuration."""
    config = CapitalAllocationConfig(
        allocation_core_hodl=0.60,
        allocation_trend=0.20,
        allocation_funding=0.15,
        allocation_tactical=0.05
    )
    return config


@pytest.fixture
def test_circuit_breaker_config():
    """Create a test circuit breaker configuration."""
    config = CircuitBreakerConfig(
        level_1_threshold=0.10,
        level_1_action="reduce_position_size",
        level_1_reduction=0.25,
        level_2_threshold=0.15,
        level_2_action="reduce_and_pause",
        level_2_reduction=0.50,
        level_3_threshold=0.20,
        level_3_action="close_directional",
        level_3_halt_trading=True,
        level_4_threshold=0.25,
        level_4_action="emergency_liquidation",
        level_4_halt_trading=True
    )
    return config


@pytest.fixture
def test_position_sizing_config():
    """Create a test position sizing configuration."""
    config = PositionSizingConfig(
        kelly_fraction=0.125,
        max_risk_per_trade=0.01,
        max_position_pct=0.05,
        max_leverage=2.0,
        max_daily_loss_pct=0.02,
        max_weekly_loss_pct=0.05,
        max_concurrent_positions=3
    )
    return config


@pytest.fixture
def test_core_hodl_config():
    """Create a test CORE-HODL engine configuration."""
    config = CoreHodlConfig(
        enabled=True,
        rebalance_frequency="quarterly",
        rebalance_threshold=0.10,
        btc_target=0.667,
        btc_min=0.55,
        btc_max=0.80,
        eth_target=0.333,
        eth_min=0.20,
        eth_max=0.45,
        yield_enabled=True,
        eth_staking_enabled=True,
        min_apy=2.0,
        dca_interval_hours=168,
        dca_amount_usdt=100.0
    )
    return config


@pytest.fixture
def test_trend_config():
    """Create a test TREND engine configuration."""
    config = TrendConfig(
        enabled=True,
        ema_fast_period=50,
        ema_slow_period=200,
        adx_period=14,
        adx_threshold=25.0,
        atr_period=14,
        atr_multiplier=2.0,
        btc_perp_allocation=0.60,
        eth_perp_allocation=0.40,
        trailing_stop_enabled=True,
        trailing_activation_r=1.0,
        trailing_distance_atr=3.0,
        risk_per_trade=0.01,
        max_leverage=2.0
    )
    return config


@pytest.fixture
def test_funding_config():
    """Create a test FUNDING engine configuration."""
    config = FundingConfig(
        enabled=True,
        min_annualized_rate=0.10,
        max_basis_pct=0.005,
        min_predicted_rate=0.01,
        rebalance_threshold=0.02,
        prediction_lookback=168,
        max_leverage=2.0,
        min_margin_ratio=0.30
    )
    return config


@pytest.fixture
def test_tactical_config():
    """Create a test TACTICAL engine configuration."""
    config = TacticalConfig(
        enabled=True,
        trigger_10_pct_allocation=0.10,
        trigger_20_pct_allocation=0.15,
        trigger_30_pct_allocation=0.20,
        trigger_40_pct_allocation=0.25,
        trigger_50_pct_allocation=0.30,
        fear_greed_extreme_fear=20,
        fear_greed_fear=40,
        fear_greed_neutral=50,
        fear_greed_greed=75,
        fear_greed_extreme_greed=80,
        deployment_days=30,
        max_deployment_pct=0.50,
        min_hold_days=90,
        max_hold_days=365,
        profit_target_pct=100.0,
        grid_levels=5,
        grid_spacing_pct=1.0
    )
    return config


# =============================================================================
# Model Fixtures
# =============================================================================

@pytest.fixture
def sample_market_data_btc():
    """Create sample BTC market data."""
    base_time = datetime.utcnow() - timedelta(hours=100)
    data = []
    base_price = Decimal("50000")
    
    for i in range(100):
        timestamp = base_time + timedelta(hours=i)
        # Simulate some price movement
        change = Decimal(str((i % 10 - 5) * 100))
        open_price = base_price + change
        close_price = open_price + Decimal(str((i % 5 - 2) * 50))
        high_price = max(open_price, close_price) + Decimal("100")
        low_price = min(open_price, close_price) - Decimal("100")
        
        data.append(MarketData(
            symbol="BTCUSDT",
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=Decimal("1000"),
            timeframe="1h"
        ))
    
    return data


@pytest.fixture
def sample_market_data_eth():
    """Create sample ETH market data."""
    base_time = datetime.utcnow() - timedelta(hours=100)
    data = []
    base_price = Decimal("3000")
    
    for i in range(100):
        timestamp = base_time + timedelta(hours=i)
        change = Decimal(str((i % 10 - 5) * 10))
        open_price = base_price + change
        close_price = open_price + Decimal(str((i % 5 - 2) * 5))
        high_price = max(open_price, close_price) + Decimal("20")
        low_price = min(open_price, close_price) - Decimal("20")
        
        data.append(MarketData(
            symbol="ETHUSDT",
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=Decimal("5000"),
            timeframe="1h"
        ))
    
    return data


@pytest.fixture
def sample_market_data_dict(sample_market_data_btc, sample_market_data_eth):
    """Create a dictionary of sample market data."""
    return {
        "BTCUSDT": sample_market_data_btc,
        "ETHUSDT": sample_market_data_eth
    }


@pytest.fixture
def sample_order():
    """Create a sample order."""
    return Order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        amount=Decimal("0.1"),
        price=None,
        status=OrderStatus.PENDING,
        metadata={"engine_type": "CORE_HODL"}
    )


@pytest.fixture
def sample_limit_order():
    """Create a sample limit order."""
    return Order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        amount=Decimal("0.1"),
        price=Decimal("49000"),
        status=OrderStatus.OPEN,
        metadata={"engine_type": "CORE_HODL"}
    )


@pytest.fixture
def sample_position_btc():
    """Create a sample BTC long position."""
    return Position(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        entry_price=Decimal("50000"),
        amount=Decimal("0.5"),
        stop_loss_price=Decimal("48500"),
        take_profit_price=Decimal("53000"),
        metadata={"engine_type": "CORE_HODL"}
    )


@pytest.fixture
def sample_position_eth():
    """Create a sample ETH long position."""
    return Position(
        symbol="ETHUSDT",
        side=PositionSide.LONG,
        entry_price=Decimal("3000"),
        amount=Decimal("5"),
        stop_loss_price=Decimal("2900"),
        take_profit_price=Decimal("3200"),
        metadata={"engine_type": "CORE_HODL"}
    )


@pytest.fixture
def sample_short_position():
    """Create a sample short position."""
    return Position(
        symbol="BTC-PERP",
        side=PositionSide.SHORT,
        entry_price=Decimal("51000"),
        amount=Decimal("0.3"),
        leverage=Decimal("2"),
        stop_loss_price=Decimal("53000"),
        metadata={"engine_type": "TREND"}
    )


@pytest.fixture
def sample_positions(sample_position_btc, sample_position_eth):
    """Create a dictionary of sample positions."""
    return {
        "BTCUSDT": sample_position_btc,
        "ETHUSDT": sample_position_eth
    }


@pytest.fixture
def sample_trade():
    """Create a sample completed trade."""
    return Trade(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        amount=Decimal("0.1"),
        entry_price=Decimal("50000"),
        exit_price=Decimal("51500"),
        entry_time=datetime.utcnow() - timedelta(days=1),
        exit_time=datetime.utcnow(),
        realized_pnl=Decimal("150"),
        realized_pnl_pct=Decimal("3"),
        entry_fee=Decimal("5"),
        exit_fee=Decimal("5.15"),
        strategy_name="TestStrategy",
        engine_type=EngineType.CORE_HODL,
        close_reason="take_profit",
        status=TradeStatus.CLOSED
    )


@pytest.fixture
def sample_buy_signal():
    """Create a sample buy signal."""
    return TradingSignal(
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        strategy_name="TestStrategy",
        engine_type=EngineType.CORE_HODL,
        timestamp=datetime.utcnow(),
        confidence=0.8,
        metadata={
            "entry_price": "50000",
            "stop_loss": "48500",
            "take_profit": "53000"
        }
    )


@pytest.fixture
def sample_sell_signal():
    """Create a sample sell signal."""
    return TradingSignal(
        symbol="BTCUSDT",
        signal_type=SignalType.SELL,
        strategy_name="TestStrategy",
        engine_type=EngineType.TREND,
        timestamp=datetime.utcnow(),
        confidence=0.75,
        metadata={"exit_price": "51000"}
    )


@pytest.fixture
def sample_close_signal():
    """Create a sample close signal."""
    return TradingSignal(
        symbol="BTCUSDT",
        signal_type=SignalType.CLOSE,
        strategy_name="TestStrategy",
        engine_type=EngineType.CORE_HODL,
        timestamp=datetime.utcnow(),
        confidence=1.0,
        metadata={"reason": "stop_loss"}
    )


@pytest.fixture
def sample_portfolio():
    """Create a sample portfolio."""
    return Portfolio(
        total_balance=Decimal("100000"),
        available_balance=Decimal("80000"),
        daily_pnl=Decimal("500"),
        weekly_pnl=Decimal("1500"),
        all_time_high=Decimal("102000"),
        max_drawdown_pct=Decimal("2"),
        engine_allocations={
            EngineType.CORE_HODL: Decimal("60000"),
            EngineType.TREND: Decimal("20000"),
            EngineType.FUNDING: Decimal("15000"),
            EngineType.TACTICAL: Decimal("5000")
        }
    )


@pytest.fixture
def sample_portfolio_with_positions(sample_portfolio, sample_positions):
    """Create a sample portfolio with positions."""
    sample_portfolio.positions = sample_positions
    return sample_portfolio


@pytest.fixture
def sample_engine_states():
    """Create sample engine states for all 4 engines."""
    return {
        EngineType.CORE_HODL: EngineState(
            engine_type=EngineType.CORE_HODL,
            is_active=True,
            current_allocation_pct=Decimal("0.60"),
            current_value=Decimal("60000"),
            total_trades=100,
            winning_trades=85,
            losing_trades=15
        ),
        EngineType.TREND: EngineState(
            engine_type=EngineType.TREND,
            is_active=True,
            current_allocation_pct=Decimal("0.20"),
            current_value=Decimal("20000"),
            total_trades=50,
            winning_trades=28,
            losing_trades=22
        ),
        EngineType.FUNDING: EngineState(
            engine_type=EngineType.FUNDING,
            is_active=True,
            current_allocation_pct=Decimal("0.15"),
            current_value=Decimal("15000"),
            total_trades=200,
            winning_trades=195,
            losing_trades=5
        ),
        EngineType.TACTICAL: EngineState(
            engine_type=EngineType.TACTICAL,
            is_active=True,
            current_allocation_pct=Decimal("0.05"),
            current_value=Decimal("5000"),
            total_trades=5,
            winning_trades=3,
            losing_trades=2
        )
    }


@pytest.fixture
def sample_risk_check_approved():
    """Create an approved risk check."""
    return RiskCheck(
        passed=True,
        risk_level="normal",
        max_position_size=Decimal("5000"),
        approved_leverage=Decimal("2"),
        circuit_breaker_level=CircuitBreakerLevel.NONE,
        checks_performed=["daily_loss", "position_size", "confidence"]
    )


@pytest.fixture
def sample_risk_check_rejected():
    """Create a rejected risk check."""
    return RiskCheck(
        passed=False,
        reason="Daily loss limit exceeded",
        risk_level="critical",
        circuit_breaker_level=CircuitBreakerLevel.LEVEL_1,
        checks_performed=["daily_loss"]
    )


# =============================================================================
# Component Fixtures
# =============================================================================

@pytest.fixture
def risk_manager():
    """Create a fresh risk manager for testing."""
    return RiskManager()


@pytest_asyncio.fixture
async def test_database():
    """Create an in-memory test database."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def mock_exchange():
    """Create a mock exchange client."""
    exchange = MagicMock()
    
    # Mock async methods
    exchange.get_balance = AsyncMock(return_value=Portfolio(
        total_balance=Decimal("100000"),
        available_balance=Decimal("80000")
    ))
    
    exchange.get_positions = AsyncMock(return_value=[])
    
    exchange.create_order = AsyncMock(return_value=Order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        amount=Decimal("0.1"),
        status=OrderStatus.FILLED,
        filled_amount=Decimal("0.1"),
        average_price=Decimal("50000")
    ))
    
    exchange.cancel_order = AsyncMock(return_value=True)
    
    exchange.get_order_status = AsyncMock(return_value=OrderStatus.FILLED)
    
    exchange.get_open_orders = AsyncMock(return_value=[])
    
    exchange.fetch_ohlcv = AsyncMock(return_value=[])
    
    exchange.fetch_ticker = AsyncMock(return_value={
        "symbol": "BTCUSDT",
        "last": Decimal("50000"),
        "bid": Decimal("49990"),
        "ask": Decimal("50010"),
        "volume": Decimal("1000000"),
        "timestamp": int(datetime.utcnow().timestamp() * 1000),
        "change_24h": Decimal("500"),
        "change_pct_24h": Decimal("1")
    })
    
    exchange.get_funding_rate = AsyncMock(return_value=[{
        "symbol": "BTCUSDT",
        "funding_rate": Decimal("0.0001"),
        "timestamp": int(datetime.utcnow().timestamp() * 1000)
    }])
    
    exchange.get_all_balances = AsyncMock(return_value={
        "CORE_HODL": Portfolio(total_balance=Decimal("60000"), available_balance=Decimal("50000")),
        "TREND": Portfolio(total_balance=Decimal("20000"), available_balance=Decimal("18000"))
    })
    
    exchange.close = AsyncMock()
    
    return exchange


# =============================================================================
# Helper Functions
# =============================================================================

def create_test_market_data(
    symbol: str = "BTCUSDT",
    bars: int = 100,
    base_price: Decimal = Decimal("50000"),
    volatility: Decimal = Decimal("0.02")
) -> List[MarketData]:
    """Helper to create test market data with random walk."""
    import random
    
    data = []
    current_price = base_price
    base_time = datetime.utcnow() - timedelta(hours=bars)
    
    for i in range(bars):
        timestamp = base_time + timedelta(hours=i)
        
        # Random price movement
        change_pct = Decimal(str(random.uniform(-float(volatility), float(volatility))))
        change = current_price * change_pct
        
        open_price = current_price
        close_price = current_price + change
        high_price = max(open_price, close_price) * (Decimal("1") + Decimal(str(random.uniform(0, 0.005))))
        low_price = min(open_price, close_price) * (Decimal("1") - Decimal(str(random.uniform(0, 0.005))))
        
        data.append(MarketData(
            symbol=symbol,
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=Decimal(str(random.uniform(1000, 10000))),
            timeframe="1h"
        ))
        
        current_price = close_price
    
    return data


def create_test_portfolio(
    total_balance: Decimal = Decimal("100000"),
    available_pct: float = 0.8
) -> Portfolio:
    """Helper to create a test portfolio."""
    available = total_balance * Decimal(str(available_pct))
    return Portfolio(
        total_balance=total_balance,
        available_balance=available
    )


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "async_test: Async tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Add unit marker by default
        if not any(marker.name in ["unit", "integration"] for marker in item.own_markers):
            item.add_marker(pytest.mark.unit)
