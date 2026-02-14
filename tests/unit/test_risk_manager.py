"""Unit tests for Risk Manager."""
import pytest
from decimal import Decimal
from datetime import datetime

from src.risk.risk_manager import RiskManager
from src.core.models import Portfolio, Position, TradingSignal, SignalType, PositionSide
from src.core.config import trading_config


@pytest.fixture
def risk_manager():
    """Create a fresh risk manager for each test."""
    return RiskManager()


@pytest.fixture
def portfolio():
    """Create a test portfolio."""
    return Portfolio(
        total_balance=Decimal("10000"),
        available_balance=Decimal("8000")
    )


@pytest.fixture
def sample_signal():
    """Create a sample trading signal."""
    return TradingSignal(
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        strategy_name="Test",
        timestamp=datetime.utcnow(),
        confidence=0.8
    )


@pytest.mark.asyncio
async def test_risk_manager_initialization(risk_manager, portfolio):
    """Test risk manager initialization."""
    await risk_manager.initialize(portfolio)
    
    assert risk_manager.daily_starting_balance == Decimal("10000")
    assert risk_manager.weekly_starting_balance == Decimal("10000")
    assert not risk_manager.emergency_stop


@pytest.mark.asyncio
async def test_signal_approved(risk_manager, portfolio, sample_signal):
    """Test that valid signals are approved."""
    await risk_manager.initialize(portfolio)
    
    check = risk_manager.check_signal(sample_signal, portfolio, {})
    
    assert check.passed
    assert check.risk_level == "normal"


@pytest.mark.asyncio
async def test_signal_rejected_low_confidence(risk_manager, portfolio):
    """Test rejection of low confidence signals."""
    await risk_manager.initialize(portfolio)
    
    low_confidence_signal = TradingSignal(
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        strategy_name="Test",
        timestamp=datetime.utcnow(),
        confidence=0.3  # Below threshold
    )
    
    check = risk_manager.check_signal(low_confidence_signal, portfolio, {})
    
    assert not check.passed
    assert "confidence" in check.reason.lower()


@pytest.mark.asyncio
async def test_signal_rejected_max_positions(risk_manager, portfolio, sample_signal):
    """Test rejection when max positions reached."""
    await risk_manager.initialize(portfolio)
    
    # Create max positions
    positions = {}
    for i in range(trading_config.max_concurrent_positions):
        positions[f"SYM{i}"] = Position(
            symbol=f"SYM{i}",
            side=PositionSide.LONG,
            entry_price=Decimal("100"),
            amount=Decimal("1")
        )
    
    check = risk_manager.check_signal(sample_signal, portfolio, positions)
    
    assert not check.passed
    assert "max concurrent" in check.reason.lower()


@pytest.mark.asyncio
async def test_daily_loss_limit_triggers_emergency_stop(risk_manager, portfolio):
    """Test that daily loss limit triggers emergency stop."""
    await risk_manager.initialize(portfolio)
    
    # Update PnL to trigger limit
    # With 2% daily limit on 10000, that's 200
    risk_manager.daily_pnl = Decimal("-250")
    
    check = risk_manager.check_signal(
        TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            timestamp=datetime.utcnow(),
            confidence=0.8
        ),
        portfolio,
        {}
    )
    
    assert not check.passed
    assert risk_manager.emergency_stop
    assert "daily loss limit" in check.reason.lower()


def test_position_size_calculation(risk_manager, portfolio):
    """Test position size calculation."""
    entry_price = Decimal("50000")
    
    quantity = risk_manager.calculate_position_size(portfolio, entry_price)
    
    # Max position is 5% of 10000 = 500
    # At 50000 per BTC, that's 0.01 BTC
    expected_max_value = portfolio.total_balance * Decimal("0.05")
    expected_quantity = expected_max_value / entry_price
    
    assert quantity <= expected_quantity


def test_stop_loss_calculation(risk_manager):
    """Test stop loss price calculation."""
    entry_price = Decimal("50000")
    
    stop_loss = risk_manager.calculate_stop_loss(entry_price, "long")
    
    # 3% stop loss
    expected = entry_price * Decimal("0.97")
    assert stop_loss == expected


def test_take_profit_calculation(risk_manager):
    """Test take profit price calculation."""
    entry_price = Decimal("50000")
    
    take_profit = risk_manager.calculate_take_profit(entry_price, "long")
    
    # 6% take profit (1:2 risk:reward)
    expected = entry_price * Decimal("1.06")
    assert take_profit == expected
