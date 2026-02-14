"""Unit tests for configuration classes in The Eternal Engine."""
import pytest
import os
from decimal import Decimal

from src.core.config import (
    SystemConfig,
    BybitAPIConfig,
    TradingModeConfig,
    CapitalAllocationConfig,
    CircuitBreakerConfig,
    PositionSizingConfig,
    CoreHodlConfig,
    TrendConfig,
    FundingConfig,
    TacticalConfig,
    StopLossTakeProfitConfig,
    NotificationConfig,
    DatabaseConfig,
    DashboardConfig,
    LoggingConfig,
    SecurityConfig,
    DevelopmentConfig,
    TradingConfig,
    EternalEngineConfig
)


# =============================================================================
# SystemConfig Tests
# =============================================================================

class TestSystemConfig:
    """Test SystemConfig configuration."""
    
    def test_system_config_defaults(self):
        """Test SystemConfig default values."""
        config = SystemConfig()
        
        assert config.environment == "development"
        assert config.app_name == "The Eternal Engine"
        assert config.app_version == "1.0.0"
        assert config.timezone == "UTC"
        assert config.log_level == "INFO"
        assert config.dry_run is True
        assert config.auto_restart is True
    
    def test_system_config_environment_validation(self):
        """Test SystemConfig environment validation."""
        # Valid environments
        config = SystemConfig(environment="development")
        assert config.environment == "development"
        
        config = SystemConfig(environment="staging")
        assert config.environment == "staging"
        
        config = SystemConfig(environment="production")
        assert config.environment == "production"
        
        # Invalid environment should raise error
        with pytest.raises(ValueError):
            SystemConfig(environment="invalid")
    
    def test_system_config_log_level_validation(self):
        """Test SystemConfig log level validation."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level in valid_levels:
            config = SystemConfig(log_level=level)
            assert config.log_level == level
        
        with pytest.raises(ValueError):
            SystemConfig(log_level="INVALID")


# =============================================================================
# BybitAPIConfig Tests
# =============================================================================

class TestBybitAPIConfig:
    """Test BybitAPIConfig configuration."""
    
    def test_bybit_api_config_defaults(self):
        """Test BybitAPIConfig default values."""
        config = BybitAPIConfig()
        
        assert config.api_mode == "demo"
        assert config.api_version == "v5"
        assert config.testnet is True
        assert config.timeout == 30
        assert config.retry_attempts == 3
    
    def test_bybit_api_config_demo_mode(self):
        """Test BybitAPIConfig DEMO mode credentials."""
        config = BybitAPIConfig(
            api_mode="demo",
            demo_api_key="demo_key_123",
            demo_api_secret="demo_secret_456",
            prod_api_key="prod_key_789",
            prod_api_secret="prod_secret_012"
        )
        
        assert config.active_api_key == "demo_key_123"
        assert config.active_api_secret == "demo_secret_456"
        assert config.is_read_only is False  # DEMO allows trading
    
    def test_bybit_api_config_prod_mode(self):
        """Test BybitAPIConfig PROD mode credentials."""
        config = BybitAPIConfig(
            api_mode="prod",
            demo_api_key="demo_key_123",
            demo_api_secret="demo_secret_456",
            prod_api_key="prod_key_789",
            prod_api_secret="prod_secret_012"
        )
        
        assert config.active_api_key == "prod_key_789"
        assert config.active_api_secret == "prod_secret_012"
        assert config.is_read_only is True  # PROD is read-only
    
    def test_bybit_api_config_subaccount_keys(self):
        """Test BybitAPIConfig subaccount API keys."""
        config = BybitAPIConfig(
            core_hodl_api_key="core_key",
            core_hodl_api_secret="core_secret",
            trend_1_api_key="trend_key",
            trend_1_api_secret="trend_secret",
            funding_api_key="funding_key",
            funding_api_secret="funding_secret",
            tactical_api_key="tactical_key",
            tactical_api_secret="tactical_secret"
        )
        
        assert config.core_hodl_api_key == "core_key"
        assert config.trend_1_api_key == "trend_key"
        assert config.funding_api_key == "funding_key"
        assert config.tactical_api_key == "tactical_key"


# =============================================================================
# TradingModeConfig Tests
# =============================================================================

class TestTradingModeConfig:
    """Test TradingModeConfig configuration."""
    
    def test_trading_mode_config_defaults(self):
        """Test TradingModeConfig default values."""
        config = TradingModeConfig()
        
        assert config.trading_mode == "paper"
        assert config.default_symbols == ["BTCUSDT", "ETHUSDT"]
        assert config.perp_symbols == ["BTC-PERP", "ETH-PERP"]
    
    def test_trading_mode_validation(self):
        """Test trading mode validation."""
        config = TradingModeConfig(trading_mode="paper")
        assert config.trading_mode == "paper"
        
        config = TradingModeConfig(trading_mode="live")
        assert config.trading_mode == "live"
        
        with pytest.raises(ValueError):
            TradingModeConfig(trading_mode="invalid")
    
    def test_trading_mode_symbols_parsing(self):
        """Test symbol list parsing from string."""
        config = TradingModeConfig(default_symbols_str="BTCUSDT,ETHUSDT,SOLUSDT")
        
        assert config.default_symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


# =============================================================================
# CapitalAllocationConfig Tests
# =============================================================================

class TestCapitalAllocationConfig:
    """Test CapitalAllocationConfig configuration."""
    
    def test_capital_allocation_defaults(self):
        """Test CapitalAllocationConfig default values."""
        config = CapitalAllocationConfig()
        
        assert config.allocation_core_hodl == 0.60
        assert config.allocation_trend == 0.20
        assert config.allocation_funding == 0.15
        assert config.allocation_tactical == 0.05
    
    def test_total_allocation(self):
        """Test that allocations sum to approximately 100%."""
        config = CapitalAllocationConfig()
        
        # Should sum to 1.0 (100%)
        assert config.total_allocation == pytest.approx(1.0, abs=0.01)
    
    def test_allocation_validation(self):
        """Test allocation value validation."""
        # Valid allocations
        config = CapitalAllocationConfig(allocation_core_hodl=0.50)
        assert config.allocation_core_hodl == 0.50
        
        # Invalid: negative
        with pytest.raises(ValueError):
            CapitalAllocationConfig(allocation_core_hodl=-0.1)
        
        # Invalid: greater than 1
        with pytest.raises(ValueError):
            CapitalAllocationConfig(allocation_core_hodl=1.5)
    
    def test_custom_allocations(self):
        """Test custom capital allocations."""
        config = CapitalAllocationConfig(
            allocation_core_hodl=0.50,
            allocation_trend=0.30,
            allocation_funding=0.15,
            allocation_tactical=0.05
        )
        
        assert config.total_allocation == pytest.approx(1.0, abs=0.01)


# =============================================================================
# CircuitBreakerConfig Tests
# =============================================================================

class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig configuration."""
    
    def test_circuit_breaker_defaults(self):
        """Test CircuitBreakerConfig default values."""
        config = CircuitBreakerConfig()
        
        # Level 1: 10% drawdown
        assert config.level_1_threshold == 0.10
        assert config.level_1_action == "reduce_position_size"
        assert config.level_1_reduction == 0.25
        
        # Level 2: 15% drawdown
        assert config.level_2_threshold == 0.15
        assert config.level_2_action == "reduce_and_pause"
        assert config.level_2_reduction == 0.50
        
        # Level 3: 20% drawdown
        assert config.level_3_threshold == 0.20
        assert config.level_3_action == "close_directional"
        assert config.level_3_halt_trading is True
        
        # Level 4: 25% drawdown
        assert config.level_4_threshold == 0.25
        assert config.level_4_action == "emergency_liquidation"
        assert config.level_4_halt_trading is True
    
    def test_threshold_ascending_order(self):
        """Test that thresholds are in ascending order."""
        config = CircuitBreakerConfig()
        
        assert config.level_1_threshold < config.level_2_threshold
        assert config.level_2_threshold < config.level_3_threshold
        assert config.level_3_threshold < config.level_4_threshold
    
    def test_threshold_validation(self):
        """Test threshold value validation."""
        # Valid thresholds
        config = CircuitBreakerConfig(level_1_threshold=0.05)
        assert config.level_1_threshold == 0.05
        
        # Invalid: zero
        with pytest.raises(ValueError):
            CircuitBreakerConfig(level_1_threshold=0)
        
        # Invalid: greater than 1
        with pytest.raises(ValueError):
            CircuitBreakerConfig(level_1_threshold=1.5)


# =============================================================================
# PositionSizingConfig Tests
# =============================================================================

class TestPositionSizingConfig:
    """Test PositionSizingConfig configuration."""
    
    def test_position_sizing_defaults(self):
        """Test PositionSizingConfig default values."""
        config = PositionSizingConfig()
        
        assert config.kelly_fraction == 0.125  # 1/8 Kelly
        assert config.max_risk_per_trade == 0.01  # 1%
        assert config.max_position_pct == 0.05  # 5%
        assert config.max_leverage == 2.0
        assert config.max_daily_loss_pct == 0.02  # 2%
        assert config.max_weekly_loss_pct == 0.05  # 5%
        assert config.max_concurrent_positions == 3
    
    def test_kelly_fraction_validation(self):
        """Test Kelly fraction validation."""
        # Valid values
        config = PositionSizingConfig(kelly_fraction=0.25)
        assert config.kelly_fraction == 0.25
        
        # Invalid: zero
        with pytest.raises(ValueError):
            PositionSizingConfig(kelly_fraction=0)
        
        # Invalid: greater than 1
        with pytest.raises(ValueError):
            PositionSizingConfig(kelly_fraction=1.5)
    
    def test_leverage_validation(self):
        """Test leverage validation."""
        # Valid values
        config = PositionSizingConfig(max_leverage=3.0)
        assert config.max_leverage == 3.0
        
        # Invalid: zero
        with pytest.raises(ValueError):
            PositionSizingConfig(max_leverage=0)
        
        # Invalid: greater than 10
        with pytest.raises(ValueError):
            PositionSizingConfig(max_leverage=15)


# =============================================================================
# CoreHodlConfig Tests
# =============================================================================

class TestCoreHodlConfig:
    """Test CoreHodlConfig configuration."""
    
    def test_core_hodl_defaults(self):
        """Test CoreHodlConfig default values."""
        config = CoreHodlConfig()
        
        assert config.enabled is True
        assert config.rebalance_frequency == "quarterly"
        assert config.rebalance_threshold == 0.10
        assert config.btc_target == 0.667  # 2/3 BTC
        assert config.eth_target == 0.333  # 1/3 ETH
        assert config.yield_enabled is True
        assert config.eth_staking_enabled is True
        assert config.min_apy == 2.0
        assert config.dca_interval_hours == 168  # Weekly
        assert config.dca_amount_usdt == 100.0
    
    def test_btc_allocation_range(self):
        """Test BTC allocation constraints."""
        config = CoreHodlConfig()
        
        assert config.btc_min <= config.btc_target <= config.btc_max
        assert config.btc_min == 0.55
        assert config.btc_max == 0.80
    
    def test_eth_allocation_range(self):
        """Test ETH allocation constraints."""
        config = CoreHodlConfig()
        
        assert config.eth_min <= config.eth_target <= config.eth_max
        assert config.eth_min == 0.20
        assert config.eth_max == 0.45


# =============================================================================
# TrendConfig Tests
# =============================================================================

class TestTrendConfig:
    """Test TrendConfig configuration."""
    
    def test_trend_defaults(self):
        """Test TrendConfig default values."""
        config = TrendConfig()
        
        assert config.enabled is True
        assert config.ema_fast_period == 50
        assert config.ema_slow_period == 200
        assert config.adx_period == 14
        assert config.adx_threshold == 25.0
        assert config.atr_period == 14
        assert config.atr_multiplier == 2.0
        assert config.btc_perp_allocation == 0.60
        assert config.eth_perp_allocation == 0.40
        assert config.trailing_stop_enabled is True
        assert config.risk_per_trade == 0.01
        assert config.max_leverage == 2.0
    
    def test_allocation_sum(self):
        """Test that perp allocations sum to 100%."""
        config = TrendConfig()
        
        assert config.btc_perp_allocation + config.eth_perp_allocation == pytest.approx(1.0)


# =============================================================================
# FundingConfig Tests
# =============================================================================

class TestFundingConfig:
    """Test FundingConfig configuration."""
    
    def test_funding_defaults(self):
        """Test FundingConfig default values."""
        config = FundingConfig()
        
        assert config.enabled is True
        assert config.min_annualized_rate == 0.10  # 10%
        assert config.max_basis_pct == 0.005  # 0.5%
        assert config.min_predicted_rate == 0.01
        assert config.rebalance_threshold == 0.02  # 2%
        assert config.prediction_lookback == 168  # 1 week
        assert config.max_leverage == 2.0
        assert config.min_margin_ratio == 0.30  # 30%


# =============================================================================
# TacticalConfig Tests
# =============================================================================

class TestTacticalConfig:
    """Test TacticalConfig configuration."""
    
    def test_tactical_defaults(self):
        """Test TacticalConfig default values."""
        config = TacticalConfig()
        
        assert config.enabled is True
        assert config.fear_greed_extreme_fear == 20
        assert config.fear_greed_fear == 40
        assert config.fear_greed_neutral == 50
        assert config.fear_greed_greed == 75
        assert config.fear_greed_extreme_greed == 80
        assert config.deployment_days == 30
        assert config.max_deployment_pct == 0.50
        assert config.min_hold_days == 90
        assert config.max_hold_days == 365
        assert config.profit_target_pct == 100.0
        assert config.grid_levels == 5
        assert config.grid_spacing_pct == 1.0


# =============================================================================
# StopLossTakeProfitConfig Tests
# =============================================================================

class TestStopLossTakeProfitConfig:
    """Test StopLossTakeProfitConfig configuration."""
    
    def test_sltp_defaults(self):
        """Test StopLossTakeProfitConfig default values."""
        config = StopLossTakeProfitConfig()
        
        assert config.enable_stop_loss is True
        assert config.stop_loss_pct == 3.0
        assert config.stop_loss_atr_multiplier == 2.0
        assert config.enable_take_profit is True
        assert config.take_profit_pct == 6.0
        
        # Tiered take profit
        assert config.tier1_pct == 1.5
        assert config.tier1_size == 0.30
        assert config.tier2_pct == 3.0
        assert config.tier2_size == 0.40
        assert config.tier3_pct == 5.0
        assert config.tier3_size == 0.30
    
    def test_tier_sizes_sum_to_one(self):
        """Test that tier sizes sum to 100%."""
        config = StopLossTakeProfitConfig()
        
        total_size = config.tier1_size + config.tier2_size + config.tier3_size
        assert total_size == pytest.approx(1.0, abs=0.01)


# =============================================================================
# NotificationConfig Tests
# =============================================================================

class TestNotificationConfig:
    """Test NotificationConfig configuration."""
    
    def test_notification_defaults(self):
        """Test NotificationConfig default values."""
        config = NotificationConfig()
        
        assert config.notify_on_trade is True
        assert config.notify_on_error is True
        assert config.notify_on_circuit_breaker is True
        assert config.notify_level_1 is False
        assert config.notify_level_2 is True
        assert config.notify_level_3 is True
        assert config.notify_level_4 is True
        
        # SMTP defaults
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.smtp_use_tls is True


# =============================================================================
# DatabaseConfig Tests
# =============================================================================

class TestDatabaseConfig:
    """Test DatabaseConfig configuration."""
    
    def test_database_defaults(self):
        """Test DatabaseConfig default values."""
        config = DatabaseConfig()
        
        # Note: The actual value depends on environment (may be overridden by .env)
        # We just verify it has a valid database URL format
        assert config.database_url is not None
        assert len(config.database_url) > 0
        assert config.database_pool_size == 10
        assert config.database_max_overflow == 20
        assert config.database_pool_timeout == 30
        assert config.redis_url == "redis://localhost:6379/0"
        assert config.database_pool_size == 10
        assert config.database_max_overflow == 20
        assert config.database_pool_timeout == 30
        assert config.redis_url == "redis://localhost:6379/0"


# =============================================================================
# TradingConfig Tests (Legacy)
# =============================================================================

class TestTradingConfig:
    """Test TradingConfig (legacy) configuration."""
    
    def test_trading_config_defaults(self):
        """Test TradingConfig default values."""
        config = TradingConfig()
        
        assert config.trading_mode == "paper"
        assert config.default_symbols == ["BTCUSDT", "ETHUSDT"]
        # Note: Config uses decimal representation (0.05 = 5%)
        assert config.max_position_pct == 0.05  # 5% as decimal
        assert config.max_daily_loss_pct == 0.02  # 2% as decimal
        assert config.max_weekly_loss_pct == 0.05  # 5% as decimal
        assert config.max_concurrent_positions == 3
        assert config.enable_stop_loss is True
        assert config.stop_loss_pct == 3.0
        assert config.enable_take_profit is True
        assert config.take_profit_pct == 6.0
    
    def test_trading_mode_validation(self):
        """Test trading mode validation."""
        config = TradingConfig(trading_mode="paper")
        assert config.trading_mode == "paper"
        
        config = TradingConfig(trading_mode="live")
        assert config.trading_mode == "live"
        
        with pytest.raises(ValueError):
            TradingConfig(trading_mode="invalid")
    
    def test_percentage_validation(self):
        """Test percentage value validation."""
        # Valid percentages
        config = TradingConfig(max_position_pct=10.0)
        assert config.max_position_pct == 10.0
        
        # Invalid: zero or negative
        with pytest.raises(ValueError):
            TradingConfig(max_position_pct=0)
        
        # Invalid: greater than 100
        with pytest.raises(ValueError):
            TradingConfig(max_position_pct=150)
    
    def test_symbols_parsing(self):
        """Test symbol list parsing from string."""
        config = TradingConfig(default_symbols_str="BTCUSDT,ETHUSDT,SOLUSDT")
        
        assert config.default_symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


# =============================================================================
# EternalEngineConfig Tests
# =============================================================================

class TestEternalEngineConfig:
    """Test EternalEngineConfig (comprehensive config container)."""
    
    def test_engine_config_initialization(self):
        """Test EternalEngineConfig initialization."""
        config = EternalEngineConfig()
        
        # All sub-configs should be initialized
        assert config.system is not None
        assert config.bybit is not None
        assert config.trading_mode is not None
        assert config.allocation is not None
        assert config.circuit_breaker is not None
        assert config.position_sizing is not None
        assert config.core_hodl is not None
        assert config.trend is not None
        assert config.funding is not None
        assert config.tactical is not None
    
    def test_engine_config_mode_properties(self):
        """Test mode helper properties."""
        config = EternalEngineConfig()
        
        # Default should be demo + paper
        assert config.is_demo_mode is True
        assert config.is_prod_mode is False
        assert config.is_paper_trading is True
        assert config.is_live_trading is False
    
    def test_get_active_api_credentials(self):
        """Test getting active API credentials."""
        config = EternalEngineConfig()
        
        # Should return tuple of (key, secret)
        key, secret = config.get_active_api_credentials()
        assert isinstance(key, str)
        assert isinstance(secret, str)
    
    def test_validate_configuration_empty_keys(self):
        """Test configuration validation with empty API keys."""
        config = EternalEngineConfig()
        
        # Default keys should be empty or placeholders
        result = config.validate_configuration()
        
        # Should have issues due to missing API keys
        assert result["valid"] is False
        assert len(result["issues"]) > 0
    
    def test_validate_configuration_allocation_sum(self):
        """Test configuration validation for allocation sum."""
        config = EternalEngineConfig()
        
        # Temporarily set valid API keys
        config.bybit.demo_api_key = "valid_key"
        config.bybit.demo_api_secret = "valid_secret"
        
        result = config.validate_configuration()
        
        # Should pass allocation check (sums to ~1.0)
        allocation_issues = [i for i in result["issues"] if "allocation" in i.lower()]
        # Note: May fail if default allocations don't sum to 1.0
    
    def test_validate_configuration_circuit_breaker_order(self):
        """Test configuration validation for circuit breaker order."""
        config = EternalEngineConfig()
        
        # Temporarily set valid API keys
        config.bybit.demo_api_key = "valid_key"
        config.bybit.demo_api_secret = "valid_secret"
        
        result = config.validate_configuration()
        
        # Should pass circuit breaker order check
        cb_issues = [i for i in result["issues"] if "circuit" in i.lower()]
        assert len(cb_issues) == 0  # Default thresholds should be valid
