"""Configuration management for The Eternal Engine trading system."""

from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# System Configuration
# =============================================================================


class SystemConfig(BaseSettings):
    """System-level configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development", env="ENVIRONMENT"
    )
    app_name: str = Field(default="The Eternal Engine", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    timezone: str = Field(default="UTC", env="TIMEZONE")

    # Operational settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", env="LOG_LEVEL"
    )
    dry_run: bool = Field(default=True, env="DRY_RUN")
    auto_restart: bool = Field(default=True, env="AUTO_RESTART")


# =============================================================================
# Bybit API Configuration
# =============================================================================


class BybitAPIConfig(BaseSettings):
    """Bybit API configuration supporting both DEMO and PROD modes."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore", populate_by_name=True
    )

    # API Mode: "demo" for testnet, "prod" for live
    api_mode: Literal["demo", "prod"] = Field(
        default="demo", validation_alias="BYBIT_API_MODE"
    )

    # API version and settings
    api_version: str = Field(default="v5", validation_alias="BYBIT_API_VERSION")
    testnet: bool = Field(default=True, validation_alias="BYBIT_TESTNET")
    timeout: int = Field(default=30, validation_alias="BYBIT_TIMEOUT")
    retry_attempts: int = Field(default=3, validation_alias="BYBIT_RETRY_ATTEMPTS")
    rate_limit_rest: int = Field(default=120, validation_alias="BYBIT_RATE_LIMIT_REST")
    rate_limit_websocket: int = Field(
        default=1000, validation_alias="BYBIT_RATE_LIMIT_WEBSOCKET"
    )

    # DEMO API Keys (Testnet - Read/Write)
    demo_api_key: str = Field(default="", validation_alias="BYBIT_DEMO_API_KEY")
    demo_api_secret: str = Field(default="", validation_alias="BYBIT_DEMO_API_SECRET")

    # PROD API Keys (Live - Read Only for now)
    prod_api_key: str = Field(default="", validation_alias="BYBIT_PROD_API_KEY")
    prod_api_secret: str = Field(default="", validation_alias="BYBIT_PROD_API_SECRET")

    # Legacy subaccount API keys (for backward compatibility)
    master_api_key: str = Field(default="", validation_alias="BYBIT_MASTER_API_KEY")
    master_api_secret: str = Field(
        default="", validation_alias="BYBIT_MASTER_API_SECRET"
    )
    core_hodl_api_key: str = Field(
        default="", validation_alias="BYBIT_CORE_HODL_API_KEY"
    )
    core_hodl_api_secret: str = Field(
        default="", validation_alias="BYBIT_CORE_HODL_API_SECRET"
    )
    trend_1_api_key: str = Field(default="", validation_alias="BYBIT_TREND_1_API_KEY")
    trend_1_api_secret: str = Field(
        default="", validation_alias="BYBIT_TREND_1_API_SECRET"
    )
    funding_api_key: str = Field(default="", validation_alias="BYBIT_FUNDING_API_KEY")
    funding_api_secret: str = Field(
        default="", validation_alias="BYBIT_FUNDING_API_SECRET"
    )
    tactical_api_key: str = Field(default="", validation_alias="BYBIT_TACTICAL_API_KEY")
    tactical_api_secret: str = Field(
        default="", validation_alias="BYBIT_TACTICAL_API_SECRET"
    )

    @computed_field
    @property
    def active_api_key(self) -> str:
        """Get the active API key based on api_mode."""
        if self.api_mode == "demo":
            return self.demo_api_key
        return self.prod_api_key

    @computed_field
    @property
    def active_api_secret(self) -> str:
        """Get the active API secret based on api_mode."""
        if self.api_mode == "demo":
            return self.demo_api_secret
        return self.prod_api_secret

    @computed_field
    @property
    def is_read_only(self) -> bool:
        """Check if the current API mode is read-only."""
        # PROD mode is currently read-only
        return self.api_mode == "prod"


# =============================================================================
# Trading Mode Configuration
# =============================================================================


class TradingModeConfig(BaseSettings):
    """Trading mode and general trading configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Trading mode: paper (simulation) or live (real trading)
    trading_mode: Literal["paper", "live"] = Field(default="paper", env="TRADING_MODE")

    # Default trading symbols (stored as comma-separated string, parsed to list)
    default_symbols_str: str = Field(
        default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,ADAUSDT,TRXUSDT,AVAXUSDT,LINKUSDT",
        env="DEFAULT_SYMBOLS",
    )
    perp_symbols_str: str = Field(
        default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,ADAUSDT,TRXUSDT,AVAXUSDT,LINKUSDT",
        env="PERP_SYMBOLS",
    )

    # CORE-HODL specific symbols (BTC/ETH only per AGENTS.md)
    core_hodl_symbols_str: str = Field(
        default="BTCUSDT,ETHUSDT", env="CORE_HODL_SYMBOLS"
    )

    @property
    def default_symbols(self) -> List[str]:
        """Parse default_symbols string into list."""
        return [s.strip() for s in self.default_symbols_str.split(",") if s.strip()]

    @property
    def perp_symbols(self) -> List[str]:
        """Parse perp_symbols string into list."""
        return [s.strip() for s in self.perp_symbols_str.split(",") if s.strip()]

    @property
    def core_hodl_symbols(self) -> List[str]:
        """Parse CORE-HODL symbols string into list (BTC/ETH only)."""
        return [s.strip() for s in self.core_hodl_symbols_str.split(",") if s.strip()]


# =============================================================================
# Capital Allocation Configuration
# =============================================================================


class CapitalAllocationConfig(BaseSettings):
    """Capital allocation configuration for the four engines."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Core-HODL: 60% allocation
    allocation_core_hodl: float = Field(default=0.60, env="ALLOCATION_CORE_HODL")

    # TREND: 20% allocation
    allocation_trend: float = Field(default=0.20, env="ALLOCATION_TREND")

    # FUNDING: 15% allocation
    allocation_funding: float = Field(default=0.15, env="ALLOCATION_FUNDING")

    # TACTICAL: 5% allocation
    allocation_tactical: float = Field(default=0.05, env="ALLOCATION_TACTICAL")

    @field_validator(
        "allocation_core_hodl",
        "allocation_trend",
        "allocation_funding",
        "allocation_tactical",
    )
    @classmethod
    def validate_allocation(cls, v):
        """Validate that allocation is between 0 and 1."""
        if v < 0 or v > 1:
            raise ValueError("Allocation must be between 0 and 1")
        return v

    @computed_field
    @property
    def total_allocation(self) -> float:
        """Check that total allocation sums to approximately 1.0."""
        return (
            self.allocation_core_hodl
            + self.allocation_trend
            + self.allocation_funding
            + self.allocation_tactical
        )


# =============================================================================
# Circuit Breaker Configuration
# =============================================================================


class CircuitBreakerConfig(BaseSettings):
    """Circuit breaker configuration for risk management."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Level 1: CAUTION (10% drawdown)
    level_1_threshold: float = Field(default=0.10, env="CIRCUIT_BREAKER_1_THRESHOLD")
    level_1_action: str = Field(
        default="reduce_position_size", env="CIRCUIT_BREAKER_1_ACTION"
    )
    level_1_reduction: float = Field(default=0.25, env="CIRCUIT_BREAKER_1_REDUCTION")

    # Level 2: WARNING (15% drawdown)
    level_2_threshold: float = Field(default=0.15, env="CIRCUIT_BREAKER_2_THRESHOLD")
    level_2_action: str = Field(
        default="reduce_and_pause", env="CIRCUIT_BREAKER_2_ACTION"
    )
    level_2_reduction: float = Field(default=0.50, env="CIRCUIT_BREAKER_2_REDUCTION")

    # Level 3: ALERT (20% drawdown)
    level_3_threshold: float = Field(default=0.20, env="CIRCUIT_BREAKER_3_THRESHOLD")
    level_3_action: str = Field(
        default="close_directional", env="CIRCUIT_BREAKER_3_ACTION"
    )
    level_3_halt_trading: bool = Field(
        default=True, env="CIRCUIT_BREAKER_3_HALT_TRADING"
    )

    # Level 4: EMERGENCY (25% drawdown)
    level_4_threshold: float = Field(default=0.25, env="CIRCUIT_BREAKER_4_THRESHOLD")
    level_4_action: str = Field(
        default="emergency_liquidation", env="CIRCUIT_BREAKER_4_ACTION"
    )
    level_4_halt_trading: bool = Field(
        default=True, env="CIRCUIT_BREAKER_4_HALT_TRADING"
    )

    @field_validator(
        "level_1_threshold",
        "level_2_threshold",
        "level_3_threshold",
        "level_4_threshold",
    )
    @classmethod
    def validate_threshold(cls, v):
        """Validate that threshold is between 0 and 1."""
        if v <= 0 or v > 1:
            raise ValueError("Threshold must be between 0 and 1")
        return v


# =============================================================================
# Position Sizing & Risk Configuration
# =============================================================================


class PositionSizingConfig(BaseSettings):
    """Position sizing and risk management configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Kelly Criterion fraction (1/8 Kelly = 0.125)
    kelly_fraction: float = Field(default=0.125, env="KELLY_FRACTION")

    # Maximum risk per trade (% of portfolio)
    max_risk_per_trade: float = Field(default=0.01, env="MAX_RISK_PER_TRADE")

    # Maximum position size (% of portfolio per position)
    max_position_pct: float = Field(default=0.05, env="MAX_POSITION_PCT")

    # Maximum leverage
    max_leverage: float = Field(default=2.0, env="MAX_LEVERAGE")

    # Maximum daily loss limit (% of portfolio)
    max_daily_loss_pct: float = Field(default=0.02, env="MAX_DAILY_LOSS_PCT")

    # Maximum weekly loss limit (% of portfolio)
    max_weekly_loss_pct: float = Field(default=0.05, env="MAX_WEEKLY_LOSS_PCT")

    # Maximum concurrent positions
    max_concurrent_positions: int = Field(default=3, env="MAX_CONCURRENT_POSITIONS")

    @field_validator("kelly_fraction")
    @classmethod
    def validate_kelly(cls, v):
        """Validate Kelly fraction is reasonable (0 to 1)."""
        if v <= 0 or v > 1:
            raise ValueError("Kelly fraction must be between 0 and 1")
        return v

    @field_validator("max_leverage")
    @classmethod
    def validate_leverage(cls, v):
        """Validate leverage does not exceed safe limits."""
        if v <= 0 or v > 10:
            raise ValueError("Leverage must be between 0 and 10")
        return v


# =============================================================================
# CORE-HODL Engine Configuration
# =============================================================================


class CoreHodlConfig(BaseSettings):
    """CORE-HODL engine configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Enable/disable
    enabled: bool = Field(default=True, env="CORE_ENGINE_ENABLED")

    # Rebalancing settings
    rebalance_frequency: Literal["daily", "weekly", "monthly", "quarterly"] = Field(
        default="quarterly", env="CORE_REBALANCE_FREQUENCY"
    )
    rebalance_threshold: float = Field(default=0.10, env="CORE_REBALANCE_THRESHOLD")

    # BTC allocation settings
    btc_target: float = Field(default=0.667, env="CORE_BTC_TARGET")
    btc_min: float = Field(default=0.55, env="CORE_BTC_MIN")
    btc_max: float = Field(default=0.80, env="CORE_BTC_MAX")

    # ETH allocation settings
    eth_target: float = Field(default=0.333, env="CORE_ETH_TARGET")
    eth_min: float = Field(default=0.20, env="CORE_ETH_MIN")
    eth_max: float = Field(default=0.45, env="CORE_ETH_MAX")

    # Yield generation
    yield_enabled: bool = Field(default=True, env="CORE_YIELD_ENABLED")
    eth_staking_enabled: bool = Field(default=True, env="CORE_ETH_STAKING_ENABLED")
    min_apy: float = Field(default=2.0, env="CORE_MIN_APY")

    # DCA settings
    dca_interval_hours: int = Field(
        default=168, env="CORE_DCA_INTERVAL_HOURS"
    )  # Weekly
    dca_amount_usdt: float = Field(default=100.0, env="CORE_DCA_AMOUNT_USDT")

    # Deployment settings
    max_deployment_weeks: int = Field(default=12, env="CORE_MAX_DEPLOYMENT_WEEKS")
    """Maximum weeks to deploy initial capital."""

    # Allocation ratios (must sum to 1.0)
    btc_allocation: float = Field(default=0.667, env="CORE_BTC_ALLOCATION")
    """BTC percentage within crypto allocation (67%)."""

    eth_allocation: float = Field(default=0.333, env="CORE_ETH_ALLOCATION")
    """ETH percentage within crypto allocation (33%)."""

    # Order size limits
    max_order_value: float = Field(default=10000.0, env="CORE_MAX_ORDER_VALUE")
    """Maximum single order value in USDT."""

    min_order_value: float = Field(default=5.0, env="CORE_MIN_ORDER_VALUE")
    """Minimum single order value in USDT."""

    @field_validator("btc_allocation", "eth_allocation")
    @classmethod
    def validate_allocation_range(cls, v):
        """Validate that individual allocations are between 0 and 1."""
        if v < 0 or v > 1:
            raise ValueError("Allocation must be between 0 and 1")
        return v

    @computed_field
    @property
    def total_allocation(self) -> float:
        """Check that BTC + ETH allocation sums to approximately 1.0."""
        return self.btc_allocation + self.eth_allocation


# =============================================================================
# TREND Engine Configuration
# =============================================================================


class TrendConfig(BaseSettings):
    """TREND engine configuration for trend following."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Enable/disable
    enabled: bool = Field(default=True, env="TREND_ENGINE_ENABLED")

    # EMA periods for trend detection
    ema_fast_period: int = Field(default=50, env="TREND_EMA_FAST_PERIOD")
    ema_slow_period: int = Field(default=200, env="TREND_EMA_SLOW_PERIOD")

    # ADX settings
    adx_period: int = Field(default=14, env="TREND_ADX_PERIOD")
    adx_threshold: float = Field(default=25.0, env="TREND_ADX_THRESHOLD")

    # ATR settings for stop loss
    atr_period: int = Field(default=14, env="TREND_ATR_PERIOD")
    atr_multiplier: float = Field(default=2.0, env="TREND_ATR_MULTIPLIER")

    # Market allocations
    btc_perp_allocation: float = Field(default=0.60, env="TREND_BTC_PERP_ALLOCATION")
    eth_perp_allocation: float = Field(default=0.40, env="TREND_ETH_PERP_ALLOCATION")

    # Trailing stop settings
    trailing_stop_enabled: bool = Field(default=True, env="TREND_TRAILING_STOP_ENABLED")
    trailing_activation_r: float = Field(default=1.0, env="TREND_TRAILING_ACTIVATION_R")
    trailing_distance_atr: float = Field(default=3.0, env="TREND_TRAILING_DISTANCE_ATR")

    # Risk settings
    risk_per_trade: float = Field(default=0.01, env="TREND_RISK_PER_TRADE")
    max_leverage: float = Field(default=2.0, env="TREND_MAX_LEVERAGE")


# =============================================================================
# FUNDING Engine Configuration
# =============================================================================


class FundingConfig(BaseSettings):
    """FUNDING engine configuration for funding rate arbitrage."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Enable/disable
    enabled: bool = Field(default=True, env="FUNDING_ENGINE_ENABLED")

    # Funding rate thresholds
    min_annualized_rate: float = Field(default=0.10, env="FUNDING_MIN_ANNUALIZED_RATE")
    max_basis_pct: float = Field(default=0.005, env="FUNDING_MAX_BASIS_PCT")
    min_predicted_rate: float = Field(default=0.01, env="FUNDING_MIN_PREDICTED_RATE")

    # Rebalancing settings
    rebalance_threshold: float = Field(default=0.02, env="FUNDING_REBALANCE_THRESHOLD")
    prediction_lookback: int = Field(default=168, env="FUNDING_PREDICTION_LOOKBACK")

    # Risk settings
    max_leverage: float = Field(default=2.0, env="FUNDING_MAX_LEVERAGE")
    min_margin_ratio: float = Field(default=0.30, env="FUNDING_MIN_MARGIN_RATIO")


# =============================================================================
# TACTICAL Engine Configuration
# =============================================================================


class TacticalConfig(BaseSettings):
    """TACTICAL engine configuration for crisis deployment."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Enable/disable
    enabled: bool = Field(default=True, env="TACTICAL_ENGINE_ENABLED")

    # Drawdown triggers (% from ATH)
    trigger_10_pct_allocation: float = Field(
        default=0.10, env="TACTICAL_TRIGGER_10_PCT_ALLOCATION"
    )
    trigger_20_pct_allocation: float = Field(
        default=0.15, env="TACTICAL_TRIGGER_20_PCT_ALLOCATION"
    )
    trigger_30_pct_allocation: float = Field(
        default=0.20, env="TACTICAL_TRIGGER_30_PCT_ALLOCATION"
    )
    trigger_40_pct_allocation: float = Field(
        default=0.25, env="TACTICAL_TRIGGER_40_PCT_ALLOCATION"
    )
    trigger_50_pct_allocation: float = Field(
        default=0.30, env="TACTICAL_TRIGGER_50_PCT_ALLOCATION"
    )

    # Fear & Greed thresholds
    fear_greed_extreme_fear: int = Field(
        default=20, env="TACTICAL_FEAR_GREED_EXTREME_FEAR"
    )
    fear_greed_fear: int = Field(default=40, env="TACTICAL_FEAR_GREED_FEAR")
    fear_greed_neutral: int = Field(default=50, env="TACTICAL_FEAR_GREED_NEUTRAL")
    fear_greed_greed: int = Field(default=75, env="TACTICAL_FEAR_GREED_GREED")
    fear_greed_extreme_greed: int = Field(
        default=80, env="TACTICAL_FEAR_GREED_EXTREME_GREED"
    )

    # Deployment settings
    deployment_days: int = Field(default=30, env="TACTICAL_DEPLOYMENT_DAYS")
    max_deployment_pct: float = Field(default=0.50, env="TACTICAL_MAX_DEPLOYMENT_PCT")
    min_hold_days: int = Field(default=90, env="TACTICAL_MIN_HOLD_DAYS")
    max_hold_days: int = Field(default=365, env="TACTICAL_MAX_HOLD_DAYS")
    profit_target_pct: float = Field(default=100.0, env="TACTICAL_PROFIT_TARGET_PCT")

    # Grid settings
    grid_levels: int = Field(default=5, env="TACTICAL_GRID_LEVELS")
    grid_spacing_pct: float = Field(default=1.0, env="TACTICAL_GRID_SPACING_PCT")


# =============================================================================
# Stop Loss & Take Profit Configuration
# =============================================================================


class StopLossTakeProfitConfig(BaseSettings):
    """Stop loss and take profit configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Stop loss settings
    enable_stop_loss: bool = Field(default=True, env="ENABLE_STOP_LOSS")
    stop_loss_pct: float = Field(default=3.0, env="STOP_LOSS_PCT")
    stop_loss_atr_multiplier: float = Field(default=2.0, env="STOP_LOSS_ATR_MULTIPLIER")

    # Take profit settings
    enable_take_profit: bool = Field(default=True, env="ENABLE_TAKE_PROFIT")
    take_profit_pct: float = Field(default=6.0, env="TAKE_PROFIT_PCT")

    # Tiered take profit levels
    tier1_pct: float = Field(default=1.5, env="TAKE_PROFIT_TIER1_PCT")
    tier1_size: float = Field(default=0.30, env="TAKE_PROFIT_TIER1_SIZE")
    tier2_pct: float = Field(default=3.0, env="TAKE_PROFIT_TIER2_PCT")
    tier2_size: float = Field(default=0.40, env="TAKE_PROFIT_TIER2_SIZE")
    tier3_pct: float = Field(default=5.0, env="TAKE_PROFIT_TIER3_PCT")
    tier3_size: float = Field(default=0.30, env="TAKE_PROFIT_TIER3_SIZE")


# =============================================================================
# Notification Configuration
# =============================================================================


class NotificationConfig(BaseSettings):
    """Notification configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Telegram settings
    telegram_bot_token: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")

    # Notification triggers
    notify_on_trade: bool = Field(default=True, env="NOTIFY_ON_TRADE")
    notify_on_error: bool = Field(default=True, env="NOTIFY_ON_ERROR")
    notify_on_circuit_breaker: bool = Field(
        default=True, env="NOTIFY_ON_CIRCUIT_BREAKER"
    )
    notify_level_1: bool = Field(default=False, env="NOTIFY_LEVEL_1")
    notify_level_2: bool = Field(default=True, env="NOTIFY_LEVEL_2")
    notify_level_3: bool = Field(default=True, env="NOTIFY_LEVEL_3")
    notify_level_4: bool = Field(default=True, env="NOTIFY_LEVEL_4")

    # SMTP settings
    smtp_host: str = Field(default="smtp.gmail.com", env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, env="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, env="SMTP_USE_TLS")
    email_alert_recipients_str: Optional[str] = Field(
        default=None, env="EMAIL_ALERT_RECIPIENTS"
    )
    email_on_critical: bool = Field(default=True, env="EMAIL_ON_CRITICAL")
    email_on_circuit_breaker: bool = Field(default=True, env="EMAIL_ON_CIRCUIT_BREAKER")
    email_on_daily_report: bool = Field(default=False, env="EMAIL_ON_DAILY_REPORT")

    # Webhook settings
    webhook_url: Optional[str] = Field(default=None, env="WEBHOOK_URL")
    webhook_timeout: int = Field(default=10, env="WEBHOOK_TIMEOUT")
    webhook_retry_attempts: int = Field(default=3, env="WEBHOOK_RETRY_ATTEMPTS")

    @property
    def email_alert_recipients(self) -> List[str]:
        """Parse email recipients string into list."""
        if not self.email_alert_recipients_str:
            return []
        # Skip if it's the example value
        if self.email_alert_recipients_str == "admin@example.com,ops@example.com":
            return []
        return [
            s.strip() for s in self.email_alert_recipients_str.split(",") if s.strip()
        ]


# =============================================================================
# Database Configuration
# =============================================================================


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # PostgreSQL
    database_url: str = Field(
        default="sqlite:///./data/eternal_engine.db", env="DATABASE_URL"
    )
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, env="DATABASE_POOL_TIMEOUT")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_timeout: int = Field(default=5, env="REDIS_TIMEOUT")
    redis_retry_attempts: int = Field(default=3, env="REDIS_RETRY_ATTEMPTS")

    # SQLite fallback
    sqlite_url: str = Field(
        default="sqlite:///./data/eternal_engine.db", env="SQLITE_URL"
    )


# =============================================================================
# Dashboard & Monitoring Configuration
# =============================================================================


class DashboardConfig(BaseSettings):
    """Dashboard and monitoring configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Dashboard settings
    enabled: bool = Field(default=True, env="DASHBOARD_ENABLED")
    port: int = Field(default=8080, env="DASHBOARD_PORT")
    host: str = Field(default="0.0.0.0", env="DASHBOARD_HOST")
    auth_enabled: bool = Field(default=True, env="DASHBOARD_AUTH_ENABLED")

    # Report schedule
    report_daily_enabled: bool = Field(default=True, env="REPORT_DAILY_ENABLED")
    report_daily_time: str = Field(default="00:00", env="REPORT_DAILY_TIME")
    report_weekly_enabled: bool = Field(default=True, env="REPORT_WEEKLY_ENABLED")
    report_weekly_day: str = Field(default="sunday", env="REPORT_WEEKLY_DAY")
    report_monthly_enabled: bool = Field(default=True, env="REPORT_MONTHLY_ENABLED")
    report_monthly_day: int = Field(default=1, env="REPORT_MONTHLY_DAY")


# =============================================================================
# Logging Configuration
# =============================================================================


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Log level
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", env="LOG_LEVEL"
    )

    # Log settings
    log_file: str = Field(default="logs/eternal_engine.log", env="LOG_FILE")
    log_file_max_size_mb: int = Field(default=100, env="LOG_FILE_MAX_SIZE_MB")
    log_file_backup_count: int = Field(default=10, env="LOG_FILE_BACKUP_COUNT")

    # Audit log
    audit_log_enabled: bool = Field(default=True, env="AUDIT_LOG_ENABLED")
    audit_log_file: str = Field(default="logs/audit.log", env="AUDIT_LOG_FILE")


# =============================================================================
# Security Configuration
# =============================================================================


class SecurityConfig(BaseSettings):
    """Security configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Encryption
    encryption_key: Optional[str] = Field(default=None, env="ENCRYPTION_KEY")

    # JWT
    jwt_secret: Optional[str] = Field(default=None, env="JWT_SECRET")
    jwt_expiry_hours: int = Field(default=24, env="JWT_EXPIRY_HOURS")

    # IP Whitelist (stored as string, accessed as list via property)
    ip_whitelist_str: str = Field(default="127.0.0.1/32", env="IP_WHITELIST")

    # Dual authorization
    dual_auth_enabled: bool = Field(default=True, env="DUAL_AUTH_ENABLED")
    dual_auth_operators_str: Optional[str] = Field(
        default=None, env="DUAL_AUTH_OPERATORS"
    )

    @property
    def ip_whitelist(self) -> List[str]:
        """Parse IP whitelist string into list."""
        if not self.ip_whitelist_str:
            return ["127.0.0.1/32"]
        return [s.strip() for s in self.ip_whitelist_str.split(",") if s.strip()]

    @property
    def dual_auth_operators(self) -> List[str]:
        """Parse dual auth operators string into list."""
        if not self.dual_auth_operators_str:
            return []
        # Skip if it's the example value
        if (
            self.dual_auth_operators_str
            == "operator1@example.com,operator2@example.com"
        ):
            return []
        return [s.strip() for s in self.dual_auth_operators_str.split(",") if s.strip()]


# =============================================================================
# Development & Testing Configuration
# =============================================================================


class DevelopmentConfig(BaseSettings):
    """Development and testing configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Testnet settings
    testnet_initial_balance_usdt: float = Field(
        default=100000.0, env="TESTNET_INITIAL_BALANCE_USDT"
    )

    # Paper trading settings
    paper_initial_balance_usdt: float = Field(
        default=100000.0, env="PAPER_INITIAL_BALANCE_USDT"
    )

    # Feature flags
    feature_flag_grid_trading: bool = Field(
        default=False, env="FEATURE_FLAG_GRID_TRADING"
    )
    feature_flag_ml_predictions: bool = Field(
        default=False, env="FEATURE_FLAG_ML_PREDICTIONS"
    )


# =============================================================================
# Main Trading Configuration
# =============================================================================


class TradingConfig(BaseSettings):
    """
    Comprehensive trading configuration for The Eternal Engine.

    This class aggregates all configuration sections and provides
    easy access to all settings for the 4-engine trading system.
    """

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Mode: 'paper' for testing, 'live' for real trading
    trading_mode: Literal["paper", "live"] = Field(default="paper", env="TRADING_MODE")

    # Default trading pairs (stored as string, accessed as list via property)
    default_symbols_str: str = Field(
        default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,ADAUSDT,TRXUSDT,AVAXUSDT,LINKUSDT",
        env="DEFAULT_SYMBOLS",
    )

    # CORE-HODL specific symbols (BTC/ETH only per AGENTS.md)
    core_hodl_symbols_str: str = Field(
        default="BTCUSDT,ETHUSDT", env="CORE_HODL_SYMBOLS"
    )

    # Risk Management - HARD LIMITS (decimal representation: 0.05 = 5%)
    max_position_pct: float = Field(default=0.05, env="MAX_POSITION_PCT")
    max_daily_loss_pct: float = Field(default=0.02, env="MAX_DAILY_LOSS_PCT")
    max_weekly_loss_pct: float = Field(default=0.05, env="MAX_WEEKLY_LOSS_PCT")
    max_concurrent_positions: int = Field(default=3, env="MAX_CONCURRENT_POSITIONS")

    # Stop Loss / Take Profit
    enable_stop_loss: bool = Field(default=True, env="ENABLE_STOP_LOSS")
    stop_loss_pct: float = Field(default=3.0, env="STOP_LOSS_PCT")
    enable_take_profit: bool = Field(default=True, env="ENABLE_TAKE_PROFIT")
    take_profit_pct: float = Field(default=6.0, env="TAKE_PROFIT_PCT")

    @property
    def default_symbols(self) -> List[str]:
        """Parse default_symbols string into list."""
        return [s.strip() for s in self.default_symbols_str.split(",") if s.strip()]

    @property
    def core_hodl_symbols(self) -> List[str]:
        """Parse CORE-HODL symbols string into list."""
        return [s.strip() for s in self.core_hodl_symbols_str.split(",") if s.strip()]

    @field_validator("trading_mode")
    @classmethod
    def validate_trading_mode(cls, v):
        if v not in ("paper", "live"):
            raise ValueError("trading_mode must be 'paper' or 'live'")
        return v

    @field_validator("max_position_pct", "max_daily_loss_pct", "max_weekly_loss_pct")
    @classmethod
    def validate_percentages(cls, v):
        if v <= 0 or v > 100:
            raise ValueError("Percentage values must be between 0 and 100")
        return v


# =============================================================================
# Global Configuration Container
# =============================================================================


class EternalEngineConfig:
    """
    Container for all Eternal Engine configurations.

    Usage:
        from src.core.config import engine_config

        # Access API configuration
        api_key = engine_config.bybit.active_api_key

        # Access engine settings
        if engine_config.core_hodl.enabled:
            dca_amount = engine_config.core_hodl.dca_amount_usdt

        # Switch between DEMO and PROD
        # Set BYBIT_API_MODE=demo or BYBIT_API_MODE=prod in .env
    """

    def __init__(self):
        self.system = SystemConfig()
        self.bybit = BybitAPIConfig()
        self.trading_mode = TradingModeConfig()
        self.allocation = CapitalAllocationConfig()
        self.circuit_breaker = CircuitBreakerConfig()
        self.position_sizing = PositionSizingConfig()
        self.core_hodl = CoreHodlConfig()
        self.trend = TrendConfig()
        self.funding = FundingConfig()
        self.tactical = TacticalConfig()
        self.stop_loss_take_profit = StopLossTakeProfitConfig()
        self.notification = NotificationConfig()
        self.database = DatabaseConfig()
        self.dashboard = DashboardConfig()
        self.logging = LoggingConfig()
        self.security = SecurityConfig()
        self.development = DevelopmentConfig()

        # Legacy config for backward compatibility
        self.legacy = TradingConfig()

    @property
    def is_demo_mode(self) -> bool:
        """Check if running in DEMO mode."""
        return self.bybit.api_mode == "demo"

    @property
    def is_prod_mode(self) -> bool:
        """Check if running in PROD mode."""
        return self.bybit.api_mode == "prod"

    @property
    def is_paper_trading(self) -> bool:
        """Check if running in paper trading mode."""
        return self.trading_mode.trading_mode == "paper"

    @property
    def is_live_trading(self) -> bool:
        """Check if running in live trading mode."""
        return self.trading_mode.trading_mode == "live"

    def get_active_api_credentials(self) -> tuple[str, str]:
        """Get the currently active API key and secret."""
        return self.bybit.active_api_key, self.bybit.active_api_secret

    def validate_configuration(self) -> dict:
        """
        Validate the complete configuration and return any issues.

        Returns:
            Dictionary with 'valid' boolean and 'issues' list
        """
        issues = []

        # Check API credentials
        api_key, api_secret = self.get_active_api_credentials()
        if not api_key or api_key.startswith("your_"):
            issues.append(f"Missing or invalid API key for {self.bybit.api_mode} mode")
        if not api_secret or api_secret.startswith("your_"):
            issues.append(
                f"Missing or invalid API secret for {self.bybit.api_mode} mode"
            )

        # Check allocation sums to ~1.0
        total = self.allocation.total_allocation
        if not 0.99 <= total <= 1.01:
            issues.append(f"Total allocation ({total:.2f}) should sum to 1.0")

        # Check circuit breaker thresholds are in ascending order
        if not (
            self.circuit_breaker.level_1_threshold
            < self.circuit_breaker.level_2_threshold
            < self.circuit_breaker.level_3_threshold
            < self.circuit_breaker.level_4_threshold
        ):
            issues.append("Circuit breaker thresholds must be in ascending order")

        return {"valid": len(issues) == 0, "issues": issues}


# =============================================================================
# Global Configuration Instances
# =============================================================================

# Global configuration instances (legacy)
trading_config = TradingConfig()
bybit_config = BybitAPIConfig()  # Replaces old ByBitConfig
strategy_config = None  # Deprecated - use engine-specific configs
notification_config = NotificationConfig()
database_config = DatabaseConfig()
logging_config = LoggingConfig()

# New comprehensive configuration
engine_config = EternalEngineConfig()


# Convenience exports
__all__ = [
    # Legacy configs
    "TradingConfig",
    "trading_config",
    "bybit_config",
    "notification_config",
    "database_config",
    "logging_config",
    # New comprehensive config
    "EternalEngineConfig",
    "engine_config",
    # Individual config classes
    "SystemConfig",
    "BybitAPIConfig",
    "TradingModeConfig",
    "CapitalAllocationConfig",
    "CircuitBreakerConfig",
    "PositionSizingConfig",
    "CoreHodlConfig",
    "TrendConfig",
    "FundingConfig",
    "TacticalConfig",
    "StopLossTakeProfitConfig",
    "NotificationConfig",
    "DatabaseConfig",
    "DashboardConfig",
    "LoggingConfig",
    "SecurityConfig",
    "DevelopmentConfig",
]
