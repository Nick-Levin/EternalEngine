"""Unit tests for data models in The Eternal Engine."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from src.core.models import (
    # Enums
    OrderSide, OrderType, OrderStatus, PositionSide, SignalType,
    CircuitBreakerLevel, EngineType, TradeStatus,
    # Models
    MarketData, Order, Position, Trade, TradingSignal,
    RiskCheck, Portfolio, EngineState, SystemState,
    # Factory functions
    create_market_order, create_limit_order
)


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Test enumeration values and behavior."""
    
    def test_order_side_values(self):
        """Test OrderSide enum values."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"
    
    def test_order_type_values(self):
        """Test OrderType enum values."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP_MARKET.value == "stop_market"
    
    def test_order_status_values(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.OPEN.value == "open"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"
    
    def test_position_side_values(self):
        """Test PositionSide enum values."""
        assert PositionSide.LONG.value == "long"
        assert PositionSide.SHORT.value == "short"
        assert PositionSide.NONE.value == "none"
    
    def test_signal_type_values(self):
        """Test SignalType enum values."""
        assert SignalType.BUY.value == "buy"
        assert SignalType.SELL.value == "sell"
        assert SignalType.CLOSE.value == "close"
        assert SignalType.REBALANCE.value == "rebalance"
        assert SignalType.EMERGENCY_EXIT.value == "emergency_exit"
    
    def test_circuit_breaker_level_values(self):
        """Test CircuitBreakerLevel enum values."""
        assert CircuitBreakerLevel.NONE.value == "none"
        assert CircuitBreakerLevel.LEVEL_1.value == "level_1"
        assert CircuitBreakerLevel.LEVEL_2.value == "level_2"
        assert CircuitBreakerLevel.LEVEL_3.value == "level_3"
        assert CircuitBreakerLevel.LEVEL_4.value == "level_4"
    
    def test_engine_type_values(self):
        """Test EngineType enum values."""
        assert EngineType.CORE_HODL.value == "core_hodl"
        assert EngineType.TREND.value == "trend"
        assert EngineType.FUNDING.value == "funding"
        assert EngineType.TACTICAL.value == "tactical"


# =============================================================================
# MarketData Tests
# =============================================================================

class TestMarketData:
    """Test MarketData model."""
    
    def test_market_data_creation(self):
        """Test creating MarketData with valid values."""
        data = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49500"),
            close=Decimal("50500"),
            volume=Decimal("1000")
        )
        
        assert data.symbol == "BTCUSDT"
        assert data.open == Decimal("50000")
        assert data.high == Decimal("51000")
        assert data.low == Decimal("49500")
        assert data.close == Decimal("50500")
        assert data.volume == Decimal("1000")
        assert data.timeframe == "1h"  # Default
    
    def test_market_data_range_property(self):
        """Test MarketData range property."""
        data = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49500"),
            close=Decimal("50500"),
            volume=Decimal("1000")
        )
        
        assert data.range == Decimal("1500")  # 51000 - 49500
    
    def test_market_data_body_property(self):
        """Test MarketData body property."""
        data = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49500"),
            close=Decimal("50500"),
            volume=Decimal("1000")
        )
        
        assert data.body == Decimal("500")  # 50500 - 50000
    
    def test_market_data_is_green_property(self):
        """Test MarketData is_green property."""
        green_candle = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49500"),
            close=Decimal("50500"),
            volume=Decimal("1000")
        )
        
        red_candle = MarketData(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49500"),
            close=Decimal("49500"),
            volume=Decimal("1000")
        )
        
        assert green_candle.is_green is True
        assert red_candle.is_green is False
    
    def test_market_data_high_validation(self):
        """Test MarketData high >= open validation."""
        with pytest.raises(ValueError, match="High must be >= open"):
            MarketData(
                symbol="BTCUSDT",
                timestamp=datetime.utcnow(),
                open=Decimal("50000"),
                high=Decimal("49000"),  # Invalid: high < open
                low=Decimal("48000"),
                close=Decimal("49500"),
                volume=Decimal("1000")
            )
    
    def test_market_data_low_validation(self):
        """Test MarketData low <= high validation."""
        with pytest.raises(ValueError, match="Low must be <= high"):
            MarketData(
                symbol="BTCUSDT",
                timestamp=datetime.utcnow(),
                open=Decimal("50000"),
                high=Decimal("51000"),
                low=Decimal("52000"),  # Invalid: low > high
                close=Decimal("50500"),
                volume=Decimal("1000")
            )


# =============================================================================
# Order Tests
# =============================================================================

class TestOrder:
    """Test Order model."""
    
    def test_order_creation(self):
        """Test creating an Order with valid values."""
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
            metadata={"test": "value"}
        )
        
        assert order.symbol == "BTCUSDT"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.amount == Decimal("0.1")
        assert order.status == OrderStatus.PENDING
        assert order.filled_amount == Decimal("0")
        assert isinstance(order.id, str)
        assert order.metadata == {"test": "value"}
    
    def test_limit_order_requires_price(self):
        """Test that limit orders require a price."""
        with pytest.raises(ValueError, match="Price required"):
            Order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                amount=Decimal("0.1")
            )
    
    def test_limit_order_requires_positive_price(self):
        """Test that limit orders require a positive price."""
        with pytest.raises(ValueError, match="Price required"):
            Order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                amount=Decimal("0.1"),
                price=Decimal("0")
            )
    
    def test_order_remaining_amount(self):
        """Test Order remaining_amount property."""
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1.0"),
            filled_amount=Decimal("0.3")
        )
        
        assert order.remaining_amount == Decimal("0.7")
    
    def test_order_is_filled(self):
        """Test Order is_filled property."""
        filled_order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1.0"),
            filled_amount=Decimal("1.0"),
            status=OrderStatus.FILLED
        )
        
        partial_order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1.0"),
            filled_amount=Decimal("0.5"),
            status=OrderStatus.PARTIALLY_FILLED
        )
        
        assert filled_order.is_filled is True
        assert partial_order.is_filled is False
    
    def test_order_is_active(self):
        """Test Order is_active property."""
        active_order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1.0"),
            status=OrderStatus.OPEN
        )
        
        filled_order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1.0"),
            status=OrderStatus.FILLED
        )
        
        cancelled_order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1.0"),
            status=OrderStatus.CANCELLED
        )
        
        assert active_order.is_active is True
        assert filled_order.is_active is False
        assert cancelled_order.is_active is False
    
    def test_order_fill_percentage(self):
        """Test Order fill_percentage property."""
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1.0"),
            filled_amount=Decimal("0.25")
        )
        
        assert order.fill_percentage == Decimal("25")
    
    def test_order_mark_as_filled(self):
        """Test Order mark_as_filled method."""
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("1.0"),
            filled_amount=Decimal("0.5")
        )
        
        fill_time = datetime.utcnow()
        order.mark_as_filled(fill_time)
        
        assert order.status == OrderStatus.FILLED
        assert order.filled_amount == Decimal("1.0")
        assert order.filled_at == fill_time
        assert order.updated_at is not None
    
    def test_create_market_order_factory(self):
        """Test create_market_order factory function."""
        order = create_market_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            stop_loss_price=Decimal("48000")
        )
        
        assert order.order_type == OrderType.MARKET
        assert order.symbol == "BTCUSDT"
        assert order.side == OrderSide.BUY
        assert order.amount == Decimal("0.5")
        assert order.stop_loss_price == Decimal("48000")
    
    def test_create_limit_order_factory(self):
        """Test create_limit_order factory function."""
        order = create_limit_order(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            amount=Decimal("0.5"),
            price=Decimal("55000"),
            take_profit_price=Decimal("58000")
        )
        
        assert order.order_type == OrderType.LIMIT
        assert order.symbol == "BTCUSDT"
        assert order.side == OrderSide.SELL
        assert order.amount == Decimal("0.5")
        assert order.price == Decimal("55000")
        assert order.take_profit_price == Decimal("58000")


# =============================================================================
# Position Tests
# =============================================================================

class TestPosition:
    """Test Position model."""
    
    def test_position_creation(self):
        """Test creating a Position with valid values."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5"),
            leverage=Decimal("1")
        )
        
        assert position.symbol == "BTCUSDT"
        assert position.side == PositionSide.LONG
        assert position.entry_price == Decimal("50000")
        assert position.amount == Decimal("0.5")
        assert position.leverage == Decimal("1")
        assert position.is_open is True
    
    def test_position_is_open(self):
        """Test Position is_open property."""
        open_position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5")
        )
        
        closed_position = Position(
            symbol="BTCUSDT",
            side=PositionSide.NONE,
            entry_price=Decimal("50000"),
            amount=Decimal("0")
        )
        
        assert open_position.is_open is True
        assert closed_position.is_open is False
    
    def test_position_value(self):
        """Test Position position_value property."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5")
        )
        
        assert position.position_value == Decimal("25000")  # 50000 * 0.5
    
    def test_calculate_unrealized_pnl_long(self):
        """Test unrealized PnL calculation for long position."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("1")
        )
        
        pnl = position.calculate_unrealized_pnl(Decimal("55000"))
        assert pnl == Decimal("5000")  # (55000 - 50000) * 1
    
    def test_calculate_unrealized_pnl_short(self):
        """Test unrealized PnL calculation for short position."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=Decimal("50000"),
            amount=Decimal("1")
        )
        
        pnl = position.calculate_unrealized_pnl(Decimal("45000"))
        assert pnl == Decimal("5000")  # -(45000 - 50000) * 1 = 5000
    
    def test_calculate_pnl_percentage(self):
        """Test PnL percentage calculation."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("1"),
            leverage=Decimal("1")
        )
        
        pnl_pct = position.calculate_pnl_percentage(Decimal("55000"))
        assert pnl_pct == Decimal("10")  # (5000 / 50000) * 100
    
    def test_calculate_pnl_percentage_with_leverage(self):
        """Test PnL percentage calculation with leverage."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("1"),
            leverage=Decimal("2")
        )
        
        pnl_pct = position.calculate_pnl_percentage(Decimal("55000"))
        # PnL = 5000, Margin = 50000/2 = 25000, PnL% = (5000/25000)*100 = 20%
        assert pnl_pct == Decimal("20")
    
    def test_update_from_fill_new_position(self):
        """Test updating position from fill for new position."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.NONE,
            entry_price=Decimal("0"),
            amount=Decimal("0")
        )
        
        position.update_from_fill(Decimal("50000"), Decimal("0.5"), OrderSide.BUY)
        
        assert position.side == PositionSide.LONG
        assert position.entry_price == Decimal("50000")
        assert position.amount == Decimal("0.5")
    
    def test_update_from_fill_add_to_position(self):
        """Test updating position when adding to existing position."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("0.5")
        )
        
        position.update_from_fill(Decimal("55000"), Decimal("0.5"), OrderSide.BUY)
        
        # New average: (50000*0.5 + 55000*0.5) / 1.0 = 52500
        assert position.entry_price == Decimal("52500")
        assert position.amount == Decimal("1.0")
    
    def test_update_from_fill_partial_close(self):
        """Test updating position on partial close."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("1.0"),
            unrealized_pnl=Decimal("5000")
        )
        
        position.update_from_fill(Decimal("55000"), Decimal("0.4"), OrderSide.SELL)
        
        # Reduced position
        assert position.amount == Decimal("0.6")
        # 40% of unrealized PnL realized
        assert position.realized_pnl == Decimal("2000")  # 5000 * 0.4
    
    def test_update_from_fill_full_close(self):
        """Test updating position on full close."""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=Decimal("50000"),
            amount=Decimal("1.0"),
            unrealized_pnl=Decimal("5000")
        )
        
        position.update_from_fill(Decimal("55000"), Decimal("1.0"), OrderSide.SELL)
        
        assert position.side == PositionSide.NONE
        assert position.amount == Decimal("0")
        assert position.realized_pnl == Decimal("5000")
        assert position.closed_at is not None


# =============================================================================
# Trade Tests
# =============================================================================

class TestTrade:
    """Test Trade model."""
    
    def test_trade_creation(self):
        """Test creating a Trade with valid values."""
        trade = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("55000"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("2500"),
            realized_pnl_pct=Decimal("10"),
            strategy_name="TestStrategy",
            engine_type=EngineType.CORE_HODL
        )
        
        assert trade.symbol == "BTCUSDT"
        assert trade.side == OrderSide.BUY
        assert trade.amount == Decimal("0.5")
        assert trade.entry_price == Decimal("50000")
        assert trade.exit_price == Decimal("55000")
        assert trade.realized_pnl == Decimal("2500")
        assert trade.status == TradeStatus.OPEN  # Default
    
    def test_trade_total_fee(self):
        """Test Trade total_fee property."""
        trade = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("55000"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("2500"),
            entry_fee=Decimal("25"),
            exit_fee=Decimal("27.5")
        )
        
        assert trade.total_fee == Decimal("52.5")
    
    def test_trade_net_pnl(self):
        """Test Trade net_pnl property."""
        trade = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("55000"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("2500"),
            entry_fee=Decimal("25"),
            exit_fee=Decimal("25")
        )
        
        assert trade.net_pnl == Decimal("2450")  # 2500 - 50
    
    def test_trade_is_profitable(self):
        """Test Trade is_profitable property."""
        profitable_trade = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("55000"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("2500"),
            entry_fee=Decimal("10"),
            exit_fee=Decimal("10")
        )
        
        losing_trade = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("45000"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("-2500"),
            entry_fee=Decimal("10"),
            exit_fee=Decimal("10")
        )
        
        assert profitable_trade.is_profitable is True
        assert losing_trade.is_profitable is False
    
    def test_trade_duration(self):
        """Test Trade duration property."""
        entry_time = datetime.utcnow() - timedelta(hours=12)
        exit_time = datetime.utcnow()
        
        trade = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("55000"),
            entry_time=entry_time,
            exit_time=exit_time,
            realized_pnl=Decimal("2500")
        )
        
        assert trade.duration is not None
        assert trade.duration == pytest.approx(43200, abs=1)  # 12 hours in seconds
    
    def test_trade_close_method(self):
        """Test Trade close method."""
        trade = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            entry_price=Decimal("50000"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            realized_pnl=Decimal("0")
        )
        
        exit_time = datetime.utcnow()
        trade.close(
            exit_price=Decimal("55000"),
            exit_time=exit_time,
            reason="take_profit",
            exit_fee=Decimal("27.5")
        )
        
        assert trade.exit_price == Decimal("55000")
        assert trade.exit_time == exit_time
        assert trade.close_reason == "take_profit"
        assert trade.exit_fee == Decimal("27.5")
        assert trade.status == TradeStatus.CLOSED
        assert trade.realized_pnl == Decimal("2500")  # (55000 - 50000) * 0.5
        assert trade.realized_pnl_pct == Decimal("5")  # (2500 / 50000) * 100


# =============================================================================
# TradingSignal Tests
# =============================================================================

class TestTradingSignal:
    """Test TradingSignal model."""
    
    def test_trading_signal_creation(self):
        """Test creating a TradingSignal with valid values."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="TestStrategy",
            engine_type=EngineType.CORE_HODL,
            confidence=0.8,
            metadata={"entry_price": "50000"}
        )
        
        assert signal.symbol == "BTCUSDT"
        assert signal.signal_type == SignalType.BUY
        assert signal.strategy_name == "TestStrategy"
        assert signal.engine_type == EngineType.CORE_HODL
        assert signal.confidence == 0.8
        assert signal.metadata == {"entry_price": "50000"}
    
    def test_trading_signal_is_entry(self):
        """Test TradingSignal is_entry property."""
        buy_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test"
        )
        
        sell_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.SELL,
            strategy_name="Test"
        )
        
        close_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.CLOSE,
            strategy_name="Test"
        )
        
        assert buy_signal.is_entry is True
        assert sell_signal.is_entry is True
        assert close_signal.is_entry is False
    
    def test_trading_signal_is_exit(self):
        """Test TradingSignal is_exit property."""
        close_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.CLOSE,
            strategy_name="Test"
        )
        
        close_long_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.CLOSE_LONG,
            strategy_name="Test"
        )
        
        emergency_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.EMERGENCY_EXIT,
            strategy_name="Test"
        )
        
        buy_signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test"
        )
        
        assert close_signal.is_exit is True
        assert close_long_signal.is_exit is True
        assert emergency_signal.is_exit is True
        assert buy_signal.is_exit is False
    
    def test_trading_signal_get_entry_price(self):
        """Test TradingSignal get_entry_price method."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            metadata={"entry_price": "50000.50"}
        )
        
        assert signal.get_entry_price() == Decimal("50000.50")
    
    def test_trading_signal_get_stop_loss(self):
        """Test TradingSignal get_stop_loss method."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            metadata={"stop_loss": "48000"}
        )
        
        assert signal.get_stop_loss() == Decimal("48000")
    
    def test_trading_signal_get_take_profit(self):
        """Test TradingSignal get_take_profit method."""
        signal = TradingSignal(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strategy_name="Test",
            metadata={"take_profit": "55000"}
        )
        
        assert signal.get_take_profit() == Decimal("55000")
    
    def test_trading_signal_confidence_validation(self):
        """Test TradingSignal confidence validation."""
        with pytest.raises(ValueError):
            TradingSignal(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                strategy_name="Test",
                confidence=1.5  # Invalid: > 1
            )
        
        with pytest.raises(ValueError):
            TradingSignal(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                strategy_name="Test",
                confidence=-0.5  # Invalid: < 0
            )


# =============================================================================
# RiskCheck Tests
# =============================================================================

class TestRiskCheck:
    """Test RiskCheck model."""
    
    def test_risk_check_approved_creation(self):
        """Test creating an approved RiskCheck."""
        check = RiskCheck(
            passed=True,
            risk_level="normal",
            max_position_size=Decimal("5000"),
            approved_leverage=Decimal("2"),
            checks_performed=["daily_loss", "position_size"]
        )
        
        assert check.passed is True
        assert check.risk_level == "normal"
        assert check.max_position_size == Decimal("5000")
        assert check.approved_leverage == Decimal("2")
        assert len(check.checks_performed) == 2
    
    def test_risk_check_rejected_creation(self):
        """Test creating a rejected RiskCheck."""
        check = RiskCheck(
            passed=False,
            reason="Daily loss limit exceeded",
            risk_level="critical",
            circuit_breaker_level=CircuitBreakerLevel.LEVEL_1
        )
        
        assert check.passed is False
        assert check.reason == "Daily loss limit exceeded"
        assert check.risk_level == "critical"
        assert check.circuit_breaker_level == CircuitBreakerLevel.LEVEL_1
    
    def test_risk_check_is_rejected(self):
        """Test RiskCheck is_rejected property."""
        approved = RiskCheck(passed=True)
        rejected = RiskCheck(passed=False, reason="Test")
        
        assert approved.is_rejected is False
        assert rejected.is_rejected is True
    
    def test_risk_check_approved_factory(self):
        """Test RiskCheck.approved factory method."""
        check = RiskCheck.approved(
            max_position_size=Decimal("10000"),
            approved_leverage=Decimal("3")
        )
        
        assert check.passed is True
        assert check.max_position_size == Decimal("10000")
        assert check.approved_leverage == Decimal("3")
    
    def test_risk_check_rejected_factory(self):
        """Test RiskCheck.rejected factory method."""
        check = RiskCheck.rejected(
            reason="Insufficient funds",
            risk_level="warning"
        )
        
        assert check.passed is False
        assert check.reason == "Insufficient funds"
        assert check.risk_level == "warning"


# =============================================================================
# Portfolio Tests
# =============================================================================

class TestPortfolio:
    """Test Portfolio model."""
    
    def test_portfolio_creation(self):
        """Test creating a Portfolio with valid values."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"),
            available_balance=Decimal("80000"),
            daily_pnl=Decimal("500"),
            all_time_high=Decimal("105000")
        )
        
        assert portfolio.total_balance == Decimal("100000")
        assert portfolio.available_balance == Decimal("80000")
        assert portfolio.daily_pnl == Decimal("500")
        assert portfolio.all_time_high == Decimal("105000")
    
    def test_portfolio_used_balance(self):
        """Test Portfolio used_balance property."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"),
            available_balance=Decimal("80000")
        )
        
        assert portfolio.used_balance == Decimal("20000")
    
    def test_portfolio_exposure_pct(self):
        """Test Portfolio exposure_pct property."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"),
            available_balance=Decimal("80000")
        )
        
        assert portfolio.exposure_pct == Decimal("20")
    
    def test_portfolio_current_drawdown_pct(self):
        """Test Portfolio current_drawdown_pct property."""
        portfolio = Portfolio(
            total_balance=Decimal("90000"),
            available_balance=Decimal("80000"),
            all_time_high=Decimal("100000")
        )
        
        # (100000 - 90000) / 100000 * 100 = 10%
        assert portfolio.current_drawdown_pct == Decimal("10")
    
    def test_portfolio_total_unrealized_pnl(self, sample_positions):
        """Test Portfolio total_unrealized_pnl property."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"),
            available_balance=Decimal("80000"),
            positions=sample_positions
        )
        
        # Positions have unrealized_pnl = 0 by default
        assert portfolio.total_unrealized_pnl == Decimal("0")
    
    def test_portfolio_total_realized_pnl(self, sample_positions):
        """Test Portfolio total_realized_pnl property."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"),
            available_balance=Decimal("80000"),
            positions=sample_positions
        )
        
        # Positions have realized_pnl = 0 by default
        assert portfolio.total_realized_pnl == Decimal("0")
    
    def test_portfolio_update_ath(self):
        """Test Portfolio update_ath method."""
        portfolio = Portfolio(
            total_balance=Decimal("110000"),
            available_balance=Decimal("90000"),
            all_time_high=Decimal("100000")
        )
        
        portfolio.update_ath()
        
        assert portfolio.all_time_high == Decimal("110000")
        assert portfolio.max_drawdown_pct == Decimal("0")
    
    def test_portfolio_get_engine_exposure(self):
        """Test Portfolio get_engine_exposure method."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"),
            available_balance=Decimal("80000"),
            engine_values={
                EngineType.CORE_HODL: Decimal("60000"),
                EngineType.TREND: Decimal("20000")
            }
        )
        
        core_exposure = portfolio.get_engine_exposure(EngineType.CORE_HODL)
        trend_exposure = portfolio.get_engine_exposure(EngineType.TREND)
        
        assert core_exposure == Decimal("60")
        assert trend_exposure == Decimal("20")
    
    def test_portfolio_calculate_total_equity(self, sample_positions):
        """Test Portfolio calculate_total_equity method."""
        portfolio = Portfolio(
            total_balance=Decimal("100000"),
            available_balance=Decimal("80000"),
            positions=sample_positions
        )
        
        current_prices = {
            "BTCUSDT": Decimal("55000"),
            "ETHUSDT": Decimal("3200")
        }
        
        equity = portfolio.calculate_total_equity(current_prices)
        
        # Total balance + unrealized PnL
        # BTC: (55000 - 50000) * 0.5 = 2500
        # ETH: (3200 - 3000) * 5 = 1000
        assert equity == Decimal("103500")


# =============================================================================
# EngineState Tests
# =============================================================================

class TestEngineState:
    """Test EngineState model."""
    
    def test_engine_state_creation(self):
        """Test creating an EngineState with valid values."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            is_active=True,
            current_allocation_pct=Decimal("0.60"),
            current_value=Decimal("60000"),
            total_trades=100
        )
        
        assert state.engine_type == EngineType.CORE_HODL
        assert state.is_active is True
        assert state.current_allocation_pct == Decimal("0.60")
        assert state.current_value == Decimal("60000")
        assert state.total_trades == 100
    
    def test_engine_state_win_rate(self):
        """Test EngineState win_rate property."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            total_trades=100,
            winning_trades=65,
            losing_trades=35
        )
        
        assert state.win_rate == Decimal("65")
    
    def test_engine_state_win_rate_zero_trades(self):
        """Test EngineState win_rate with zero trades."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            total_trades=0
        )
        
        assert state.win_rate == Decimal("0")
    
    def test_engine_state_profit_factor(self):
        """Test EngineState profit_factor property."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            metadata={
                "gross_profit": Decimal("10000"),
                "gross_loss": Decimal("-5000")
            }
        )
        
        assert state.profit_factor == Decimal("2")
    
    def test_engine_state_can_trade(self):
        """Test EngineState can_trade property."""
        active_state = EngineState(
            engine_type=EngineType.CORE_HODL,
            is_active=True,
            is_paused=False
        )
        
        paused_state = EngineState(
            engine_type=EngineType.CORE_HODL,
            is_active=True,
            is_paused=True
        )
        
        inactive_state = EngineState(
            engine_type=EngineType.CORE_HODL,
            is_active=False
        )
        
        circuit_breaker_state = EngineState(
            engine_type=EngineType.CORE_HODL,
            is_active=True,
            circuit_breaker_level=CircuitBreakerLevel.LEVEL_3
        )
        
        assert active_state.can_trade is True
        assert paused_state.can_trade is False
        assert inactive_state.can_trade is False
        assert circuit_breaker_state.can_trade is False
    
    def test_engine_state_record_trade(self):
        """Test EngineState record_trade method."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            total_trades=0,
            total_pnl=Decimal("0")
        )
        
        trade = Trade(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            amount=Decimal("0.5"),
            entry_price=Decimal("50000"),
            exit_price=Decimal("55000"),
            entry_time=datetime.utcnow() - timedelta(days=1),
            exit_time=datetime.utcnow(),
            realized_pnl=Decimal("2500"),
            entry_fee=Decimal("25"),
            exit_fee=Decimal("27.5")
        )
        
        state.record_trade(trade)
        
        assert state.total_trades == 1
        assert state.winning_trades == 1
        assert state.total_pnl == Decimal("2447.5")  # 2500 - 52.5 fees
        assert state.last_trade_time is not None
    
    def test_engine_state_record_error(self):
        """Test EngineState record_error method."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            error_count=0
        )
        
        state.record_error("Connection timeout")
        
        assert state.error_count == 1
        assert state.last_error == "Connection timeout"
        assert state.last_error_time is not None
    
    def test_engine_state_clear_errors(self):
        """Test EngineState clear_errors method."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            error_count=5,
            last_error="Test error"
        )
        
        state.clear_errors()
        
        assert state.error_count == 0
        assert state.last_error is None
    
    def test_engine_state_pause(self):
        """Test EngineState pause method."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            is_paused=False
        )
        
        state.pause("Manual pause", duration_seconds=3600)
        
        assert state.is_paused is True
        assert state.pause_reason == "Manual pause"
        assert state.pause_until is not None
    
    def test_engine_state_resume(self):
        """Test EngineState resume method."""
        state = EngineState(
            engine_type=EngineType.CORE_HODL,
            is_paused=True,
            pause_reason="Test",
            pause_until=datetime.utcnow() + timedelta(hours=1)
        )
        
        state.resume()
        
        assert state.is_paused is False
        assert state.pause_reason is None
        assert state.pause_until is None


# =============================================================================
# SystemState Tests
# =============================================================================

class TestSystemState:
    """Test SystemState model."""
    
    def test_system_state_creation(self, sample_portfolio, sample_engine_states):
        """Test creating a SystemState with valid values."""
        state = SystemState(
            portfolio=sample_portfolio,
            engines=sample_engine_states,
            positions={},
            orders=[],
            circuit_breaker_level=CircuitBreakerLevel.NONE,
            is_trading_halted=False
        )
        
        assert state.portfolio == sample_portfolio
        assert len(state.engines) == 4
        assert state.circuit_breaker_level == CircuitBreakerLevel.NONE
        assert state.is_trading_halted is False
    
    def test_system_state_all_engines_active(self, sample_portfolio, sample_engine_states):
        """Test SystemState all_engines_active property."""
        state = SystemState(
            portfolio=sample_portfolio,
            engines=sample_engine_states
        )
        
        assert state.all_engines_active is True
        
        # Pause one engine
        sample_engine_states[EngineType.TREND].is_paused = True
        
        assert state.all_engines_active is False
    
    def test_system_state_total_exposure_pct(self, sample_portfolio, sample_engine_states):
        """Test SystemState total_exposure_pct property."""
        state = SystemState(
            portfolio=sample_portfolio,
            engines=sample_engine_states
        )
        
        assert state.total_exposure_pct == Decimal("20")  # From portfolio
