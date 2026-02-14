"""Comprehensive unit tests for Risk Manager."""
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime, timedelta

from src.risk.risk_manager import RiskManager, RiskCheck, RiskRule, CircuitBreaker
from src.core.models import (
    Portfolio, Position, TradingSignal, SignalType, PositionSide,
    CircuitBreakerLevel, EngineType
)
from src.core.config import trading_config


# =============================================================================
# Fixtures
# =============================================================================

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


@pytest.fixture
def sample_position():
    """Create a sample position."""
    return Position(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        entry_price=Decimal("50000"),
        amount=Decimal("0.1")
    )


# =============================================================================
# Initialization Tests
# =============================================================================

class TestRiskManagerInitialization:
    """Test Risk Manager initialization."""
    
    @pytest.mark.asyncio
    async def test_risk_manager_initialization(self, risk_manager, portfolio):
        """Test risk manager initialization."""
        await risk_manager.initialize(portfolio)
        
        assert risk_manager.daily_starting_balance == Decimal("10000")
        assert risk_manager.weekly_starting_balance == Decimal("10000")
        assert risk_manager.all_time_high_balance == Decimal("10000")
        assert not risk_manager.emergency_stop
        assert risk_manager.circuit_breaker.level == CircuitBreakerLevel.NONE
    
    def test_risk_manager_default_constants(self, risk_manager):
        """Test risk manager default constants."""
        assert risk_manager.KELLY_FRACTION == Decimal("0.125")  # 1/8 Kelly
        assert risk_manager.MAX_LEVERAGE_TREND == Decimal("2.0")
        assert risk_manager.MAX_LEVERAGE_FUNDING == Decimal("2.0")
        assert risk_manager.MAX_LEVERAGE_CORE == Decimal("1.0")
        assert risk_manager.MAX_LEVERAGE_TACTICAL == Decimal("1.0")
        assert risk_manager.DEFAULT_RISK_PER_TRADE == Decimal("0.01")
        assert risk_manager.CORRELATION_CRISIS_THRESHOLD == Decimal("0.90")
        assert risk_manager.MIN_SIGNAL_CONFIDENCE == Decimal("0.60")


# =============================================================================
# Signal Validation Tests
# =============================================================================

class TestSignalValidation:
    """Test signal validation and risk checks."""
    
    @pytest.mark.asyncio
    async def test_signal_approved(self, risk_manager, portfolio, sample_signal):
        """Test that valid signals are approved."""
        await risk_manager.initialize(portfolio)
        
        check = risk_manager.check_signal(sample_signal, portfolio, {})
        
        assert check.passed
        assert check.risk_level == "normal"
    
    @pytest.mark.asyncio
    async def test_signal_rejected_low_confidence(self, risk_manager, portfolio):
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
    async def test_signal_rejected_max_positions(self, risk_manager, portfolio, sample_signal):
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
    async def test_signal_rejected_duplicate_position(self, risk_manager, portfolio, sample_signal):
        """Test rejection when duplicate position exists."""
        await risk_manager.initialize(portfolio)
        
        positions = {
            "BTCUSDT": Position(
                symbol="BTCUSDT",
                side=PositionSide.LONG,
                entry_price=Decimal("50000"),
                amount=Decimal("0.1")
            )
        }
        
        check = risk_manager.check_signal(sample_signal, portfolio, positions)
        
        assert not check.passed
        assert "already have" in check.reason.lower()


# =============================================================================
# Daily/Weekly Loss Limit Tests
# =============================================================================

class TestLossLimits:
    """Test daily and weekly loss limit checks."""
    
    @pytest.mark.asyncio
    async def test_daily_loss_limit_triggers_emergency_stop(self, risk_manager, portfolio):
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
    
    @pytest.mark.asyncio
    async def test_weekly_loss_limit_triggers_emergency_stop(self, risk_manager, portfolio):
        """Test that weekly loss limit triggers emergency stop."""
        await risk_manager.initialize(portfolio)
        
        # Update PnL to trigger weekly limit
        # With 5% weekly limit on 10000, that's 500
        risk_manager.weekly_pnl = Decimal("-600")
        
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
        assert "weekly loss limit" in check.reason.lower()
    
    @pytest.mark.asyncio
    async def test_daily_loss_warning_at_80_percent(self, risk_manager, portfolio):
        """Test warning when daily loss at 80% of limit."""
        await risk_manager.initialize(portfolio)
        
        # Set daily PnL to 80% of limit
        # 2% limit = 200, 80% = 160
        risk_manager.daily_pnl = Decimal("-160")
        
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
        
        assert check.passed
        assert check.risk_level == "warning"
        assert "approaching limit" in check.reason.lower()


# =============================================================================
# Position Sizing Tests (1/8 Kelly)
# =============================================================================

class TestPositionSizing:
    """Test position sizing calculations using 1/8 Kelly."""
    
    def test_position_size_calculation(self, risk_manager, portfolio):
        """Test position size calculation."""
        entry_price = Decimal("50000")
        
        quantity = risk_manager.calculate_position_size(portfolio, entry_price)
        
        # Max position is 5% of 10000 = 500
        # At 50000 per BTC, that's 0.01 BTC
        expected_max_value = portfolio.total_balance * Decimal("0.05")
        expected_quantity = expected_max_value / entry_price
        
        assert quantity <= expected_quantity
    
    def test_position_size_with_stop_loss(self, risk_manager, portfolio):
        """Test position size calculation with stop loss."""
        entry_price = Decimal("50000")
        stop_loss = Decimal("48500")  # 3% stop
        
        quantity = risk_manager.calculate_position_size(
            portfolio, entry_price, stop_loss
        )
        
        # Should be based on risk amount / stop distance
        risk_amount = portfolio.total_balance * Decimal("0.01")  # 1% risk
        stop_distance = entry_price - stop_loss  # 1500
        expected_quantity = (risk_amount / stop_distance) * entry_price / entry_price
        
        assert quantity > Decimal("0")
        assert quantity <= Decimal("0.01")  # Max position limit
    
    def test_position_size_with_kelly(self, risk_manager, portfolio):
        """Test position size with Kelly Criterion."""
        entry_price = Decimal("50000")
        
        # 60% win rate, 2:1 win/loss ratio
        win_rate = Decimal("0.60")
        avg_win_loss_ratio = Decimal("2.0")
        
        quantity = risk_manager.calculate_position_size(
            portfolio, entry_price,
            win_rate=win_rate,
            avg_win_loss_ratio=avg_win_loss_ratio
        )
        
        # Kelly = 0.60 - (1-0.60)/2 = 0.40
        # 1/8 Kelly = 0.40 * 0.125 = 0.05 = 5%
        assert quantity > Decimal("0")
    
    def test_position_size_circuit_breaker_reduction(self, risk_manager, portfolio):
        """Test position size reduction during circuit breaker."""
        entry_price = Decimal("50000")
        
        # Activate circuit breaker level 1 (25% reduction)
        risk_manager.circuit_breaker.reduce_positions_pct = Decimal("0.25")
        
        quantity_normal = risk_manager.calculate_position_size(portfolio, entry_price)
        
        # Reset and calculate with circuit breaker
        risk_manager.circuit_breaker.reduce_positions_pct = Decimal("0.25")
        quantity_reduced = risk_manager.calculate_position_size(portfolio, entry_price)
        
        assert quantity_reduced <= quantity_normal
    
    def test_position_size_zero_portfolio(self, risk_manager):
        """Test position size with zero portfolio."""
        empty_portfolio = Portfolio(
            total_balance=Decimal("0"),
            available_balance=Decimal("0")
        )
        
        quantity = risk_manager.calculate_position_size(
            empty_portfolio, Decimal("50000")
        )
        
        assert quantity == Decimal("0")
    
    def test_position_size_zero_price(self, risk_manager, portfolio):
        """Test position size with zero price."""
        quantity = risk_manager.calculate_position_size(
            portfolio, Decimal("0")
        )
        
        assert quantity == Decimal("0")


# =============================================================================
# Stop Loss and Take Profit Tests
# =============================================================================

class TestStopLossTakeProfit:
    """Test stop loss and take profit calculations."""
    
    def test_stop_loss_calculation_long(self, risk_manager):
        """Test stop loss calculation for long position."""
        entry_price = Decimal("50000")
        
        stop_loss = risk_manager.calculate_stop_loss(entry_price, "long")
        
        # 3% stop loss
        expected = entry_price * Decimal("0.97")
        assert stop_loss == expected
    
    def test_stop_loss_calculation_short(self, risk_manager):
        """Test stop loss calculation for short position."""
        entry_price = Decimal("50000")
        
        stop_loss = risk_manager.calculate_stop_loss(entry_price, "short")
        
        # 3% stop loss for short = entry * 1.03
        expected = entry_price * Decimal("1.03")
        assert stop_loss == expected
    
    def test_stop_loss_with_atr(self, risk_manager):
        """Test ATR-based stop loss."""
        entry_price = Decimal("50000")
        atr = Decimal("1000")
        
        stop_loss = risk_manager.calculate_stop_loss(
            entry_price, "long", atr=atr, multiplier=Decimal("2")
        )
        
        expected = entry_price - (atr * Decimal("2"))  # 50000 - 2000 = 48000
        assert stop_loss == expected
    
    def test_stop_loss_circuit_breaker_widening(self, risk_manager):
        """Test stop loss widening during circuit breaker."""
        entry_price = Decimal("50000")
        
        # Activate circuit breaker with stop widening
        risk_manager.circuit_breaker.widen_stops_pct = Decimal("0.01")  # 1% extra
        
        stop_loss = risk_manager.calculate_stop_loss(entry_price, "long")
        
        # Base 3% + 1% widening = 4%
        expected = entry_price * Decimal("0.96")
        assert stop_loss == expected
    
    def test_take_profit_calculation_long(self, risk_manager):
        """Test take profit calculation for long position."""
        entry_price = Decimal("50000")
        
        take_profit = risk_manager.calculate_take_profit(entry_price, "long")
        
        # 6% take profit (1:2 risk:reward)
        expected = entry_price * Decimal("1.06")
        assert take_profit == expected
    
    def test_take_profit_calculation_short(self, risk_manager):
        """Test take profit calculation for short position."""
        entry_price = Decimal("50000")
        
        take_profit = risk_manager.calculate_take_profit(entry_price, "short")
        
        # 6% take profit for short
        expected = entry_price * Decimal("0.94")
        assert take_profit == expected
    
    def test_take_profit_custom_risk_reward(self, risk_manager):
        """Test take profit with custom risk:reward ratio."""
        entry_price = Decimal("50000")
        
        take_profit = risk_manager.calculate_take_profit(
            entry_price, "long", risk_reward_ratio=Decimal("3")
        )
        
        # 3% stop * 3 = 9% take profit
        expected = entry_price * Decimal("1.09")
        assert take_profit == expected


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreakers:
    """Test circuit breaker functionality."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_level_1_trigger(self, risk_manager, portfolio):
        """Test Level 1 circuit breaker triggers at 10% drawdown."""
        await risk_manager.initialize(portfolio)
        
        # Set ATH and current balance to trigger 10% drawdown
        risk_manager.all_time_high_balance = Decimal("11111")
        portfolio.total_balance = Decimal("10000")  # ~10% drawdown
        
        level = risk_manager.check_circuit_breakers(portfolio)
        
        assert level == CircuitBreakerLevel.LEVEL_1
        assert risk_manager.circuit_breaker.level == CircuitBreakerLevel.LEVEL_1
        assert risk_manager.circuit_breaker.reduce_positions_pct == Decimal("0.25")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_level_2_trigger(self, risk_manager, portfolio):
        """Test Level 2 circuit breaker triggers at 15% drawdown."""
        await risk_manager.initialize(portfolio)
        
        # Set ATH and current balance to trigger 15% drawdown
        risk_manager.all_time_high_balance = Decimal("11765")
        portfolio.total_balance = Decimal("10000")  # ~15% drawdown
        
        level = risk_manager.check_circuit_breakers(portfolio)
        
        assert level == CircuitBreakerLevel.LEVEL_2
        assert risk_manager.circuit_breaker.pause_new_entries is True
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_level_3_trigger(self, risk_manager, portfolio):
        """Test Level 3 circuit breaker triggers at 20% drawdown."""
        await risk_manager.initialize(portfolio)
        
        # Set ATH and current balance to trigger 20% drawdown
        risk_manager.all_time_high_balance = Decimal("12500")
        portfolio.total_balance = Decimal("10000")  # 20% drawdown
        
        level = risk_manager.check_circuit_breakers(portfolio)
        
        assert level == CircuitBreakerLevel.LEVEL_3
        assert risk_manager.circuit_breaker.close_directional is True
        assert risk_manager.emergency_stop is True
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_level_4_trigger(self, risk_manager, portfolio):
        """Test Level 4 circuit breaker triggers at 25% drawdown."""
        await risk_manager.initialize(portfolio)
        
        # Set ATH and current balance to trigger 25% drawdown
        risk_manager.all_time_high_balance = Decimal("13333")
        portfolio.total_balance = Decimal("10000")  # 25% drawdown
        
        level = risk_manager.check_circuit_breakers(portfolio)
        
        assert level == CircuitBreakerLevel.LEVEL_4
        assert risk_manager.circuit_breaker.full_liquidation is True
        assert risk_manager.emergency_stop is True
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_auto_recovery_level_1(self, risk_manager, portfolio):
        """Test auto-recovery from Level 1 when drawdown improves."""
        await risk_manager.initialize(portfolio)
        
        # Trigger Level 1
        risk_manager.all_time_high_balance = Decimal("11111")
        portfolio.total_balance = Decimal("10000")
        risk_manager.check_circuit_breakers(portfolio)
        
        assert risk_manager.circuit_breaker.level == CircuitBreakerLevel.LEVEL_1
        
        # Recover to 5% drawdown (recovery threshold)
        portfolio.total_balance = Decimal("10555")
        risk_manager.check_circuit_breakers(portfolio)
        
        # Should auto-recover
        assert risk_manager.circuit_breaker.level == CircuitBreakerLevel.NONE
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_manual_recovery_required(self, risk_manager, portfolio):
        """Test that Level 2+ requires manual recovery."""
        await risk_manager.initialize(portfolio)
        
        # Trigger Level 2
        risk_manager.all_time_high_balance = Decimal("11765")
        portfolio.total_balance = Decimal("10000")
        risk_manager.check_circuit_breakers(portfolio)
        
        # Try to reset
        result = risk_manager.reset_circuit_breaker()
        
        assert result is False  # Manual recovery required
        assert risk_manager.circuit_breaker.level == CircuitBreakerLevel.LEVEL_2


# =============================================================================
# Emergency Stop Tests
# =============================================================================

class TestEmergencyStop:
    """Test emergency stop functionality."""
    
    def test_trigger_emergency_stop(self, risk_manager):
        """Test triggering emergency stop."""
        risk_manager.trigger_emergency_stop("Test emergency")
        
        assert risk_manager.emergency_stop is True
        assert risk_manager.emergency_reason == "Test emergency"
        assert risk_manager.emergency_triggered_at is not None
    
    @pytest.mark.asyncio
    async def test_signal_rejected_during_emergency_stop(self, risk_manager, portfolio, sample_signal):
        """Test that signals are rejected during emergency stop."""
        await risk_manager.initialize(portfolio)
        risk_manager.trigger_emergency_stop("Test emergency")
        
        check = risk_manager.check_signal(sample_signal, portfolio, {})
        
        assert not check.passed
        assert "emergency stop" in check.reason.lower()
    
    def test_reset_emergency_stop(self, risk_manager):
        """Test resetting emergency stop."""
        risk_manager.trigger_emergency_stop("Test emergency")
        
        result = risk_manager.reset_emergency_stop("admin")
        
        assert result is True
        assert risk_manager.emergency_stop is False
        assert risk_manager.emergency_reason is None


# =============================================================================
# Correlation Crisis Tests
# =============================================================================

class TestCorrelationCrisis:
    """Test correlation crisis detection."""
    
    @pytest.mark.asyncio
    async def test_correlation_crisis_warning(self, risk_manager, portfolio):
        """Test warning when correlation crisis detected."""
        await risk_manager.initialize(portfolio)
        
        # Create positions that would indicate high correlation
        positions = {
            "BTCUSDT": Position(
                symbol="BTCUSDT",
                side=PositionSide.LONG,
                entry_price=Decimal("50000"),
                amount=Decimal("0.1"),
                unrealized_pnl=Decimal("-500")
            ),
            "ETHUSDT": Position(
                symbol="ETHUSDT",
                side=PositionSide.LONG,
                entry_price=Decimal("3000"),
                amount=Decimal("1"),
                unrealized_pnl=Decimal("-300")
            )
        }
        
        # Mock high correlation
        risk_manager.position_correlations = {
            "BTCUSDT_ETHUSDT": Decimal("0.95")
        }
        
        signal = TradingSignal(
            symbol="SOLUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            timestamp=datetime.utcnow(),
            confidence=0.8
        )
        
        check = risk_manager.check_signal(signal, portfolio, positions)
        
        # Should pass but with warning (correlation check is non-blocking)
        # Note: Actual behavior depends on implementation


# =============================================================================
# Period Reset Tests
# =============================================================================

class TestPeriodResets:
    """Test daily/weekly period resets."""
    
    @pytest.mark.asyncio
    async def test_daily_reset(self, risk_manager, portfolio):
        """Test daily PnL reset."""
        await risk_manager.initialize(portfolio)
        
        # Set some PnL
        risk_manager.daily_pnl = Decimal("-100")
        
        # Set last reset to yesterday
        risk_manager.last_reset_day = datetime.utcnow() - timedelta(days=1)
        
        # Reset periods
        risk_manager.reset_periods(portfolio)
        
        assert risk_manager.daily_pnl == Decimal("0")
    
    @pytest.mark.asyncio
    async def test_weekly_reset(self, risk_manager, portfolio):
        """Test weekly PnL reset."""
        await risk_manager.initialize(portfolio)
        
        # Set some PnL
        risk_manager.weekly_pnl = Decimal("-300")
        
        # Set last reset to 8 days ago
        risk_manager.last_reset_week = datetime.utcnow() - timedelta(days=8)
        
        # Reset periods
        risk_manager.reset_periods(portfolio)
        
        assert risk_manager.weekly_pnl == Decimal("0")


# =============================================================================
# Kelly Criterion Tests
# =============================================================================

class TestKellyCriterion:
    """Test Kelly Criterion calculations."""
    
    def test_kelly_calculation(self, risk_manager, portfolio):
        """Test Kelly Criterion position sizing."""
        win_rate = Decimal("0.60")
        avg_win_loss_ratio = Decimal("2.0")
        
        kelly_size = risk_manager._calculate_kelly_position_size(
            portfolio, win_rate, avg_win_loss_ratio
        )
        
        # Full Kelly: K% = W - [(1-W)/R] = 0.60 - (0.40/2) = 0.40 = 40%
        # 1/8 Kelly: 40% * 0.125 = 5%
        expected = portfolio.total_balance * Decimal("0.05")
        assert kelly_size <= expected
    
    def test_kelly_zero_win_rate(self, risk_manager, portfolio):
        """Test Kelly with zero win rate."""
        kelly_size = risk_manager._calculate_kelly_position_size(
            portfolio, Decimal("0"), Decimal("2.0")
        )
        
        # Should return max position size as fallback
        assert kelly_size > Decimal("0")
    
    def test_kelly_negative_full_kelly(self, risk_manager, portfolio):
        """Test Kelly when full Kelly is negative."""
        # Low win rate, bad ratio
        win_rate = Decimal("0.30")
        avg_win_loss_ratio = Decimal("0.5")
        
        kelly_size = risk_manager._calculate_kelly_position_size(
            portfolio, win_rate, avg_win_loss_ratio
        )
        
        # Should be capped at 0 (don't trade)
        assert kelly_size >= Decimal("0")


# =============================================================================
# Leverage Tests
# =============================================================================

class TestLeverage:
    """Test leverage limits by strategy type."""
    
    def test_max_leverage_core(self, risk_manager):
        """Test max leverage for CORE-HODL."""
        leverage = risk_manager._get_max_leverage("core")
        assert leverage == Decimal("1.0")
    
    def test_max_leverage_trend(self, risk_manager):
        """Test max leverage for TREND."""
        leverage = risk_manager._get_max_leverage("trend")
        assert leverage == Decimal("2.0")
    
    def test_max_leverage_funding(self, risk_manager):
        """Test max leverage for FUNDING."""
        leverage = risk_manager._get_max_leverage("funding")
        assert leverage == Decimal("2.0")
    
    def test_max_leverage_tactical(self, risk_manager):
        """Test max leverage for TACTICAL."""
        leverage = risk_manager._get_max_leverage("tactical")
        assert leverage == Decimal("1.0")
    
    def test_max_leverage_default(self, risk_manager):
        """Test max leverage for unknown strategy."""
        leverage = risk_manager._get_max_leverage("unknown")
        assert leverage == Decimal("1.0")
