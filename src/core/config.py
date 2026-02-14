"""Configuration management for the trading bot."""
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class TradingConfig(BaseSettings):
    """Trading configuration settings."""
    
    # Mode: 'paper' for testing, 'live' for real trading
    trading_mode: str = Field(default="paper", env="TRADING_MODE")
    
    # Default trading pairs
    default_symbols: List[str] = Field(
        default=["BTCUSDT", "ETHUSDT"], 
        env="DEFAULT_SYMBOLS"
    )
    
    # Risk Management - HARD LIMITS
    max_position_pct: float = Field(default=5.0, env="MAX_POSITION_PCT")  # Max % per position
    max_daily_loss_pct: float = Field(default=2.0, env="MAX_DAILY_LOSS_PCT")
    max_weekly_loss_pct: float = Field(default=5.0, env="MAX_WEEKLY_LOSS_PCT")
    max_concurrent_positions: int = Field(default=3, env="MAX_CONCURRENT_POSITIONS")
    
    # Stop Loss / Take Profit
    enable_stop_loss: bool = Field(default=True, env="ENABLE_STOP_LOSS")
    stop_loss_pct: float = Field(default=3.0, env="STOP_LOSS_PCT")
    enable_take_profit: bool = Field(default=True, env="ENABLE_TAKE_PROFIT")
    take_profit_pct: float = Field(default=6.0, env="TAKE_PROFIT_PCT")
    
    @validator("trading_mode")
    def validate_trading_mode(cls, v):
        if v not in ("paper", "live"):
            raise ValueError("trading_mode must be 'paper' or 'live'")
        return v
    
    @validator("max_position_pct", "max_daily_loss_pct", "max_weekly_loss_pct")
    def validate_percentages(cls, v):
        if v <= 0 or v > 100:
            raise ValueError("Percentage values must be between 0 and 100")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class ByBitConfig(BaseSettings):
    """ByBit exchange configuration."""
    
    api_key: str = Field(..., env="BYBIT_API_KEY")
    api_secret: str = Field(..., env="BYBIT_API_SECRET")
    testnet: bool = Field(default=True, env="BYBIT_TESTNET")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class StrategyConfig(BaseSettings):
    """Strategy-specific configuration."""
    
    default_strategy: str = Field(default="dca", env="DEFAULT_STRATEGY")
    
    # DCA Settings
    dca_interval_hours: int = Field(default=24, env="DCA_INTERVAL_HOURS")
    dca_amount_usdt: float = Field(default=100.0, env="DCA_AMOUNT_USDT")
    
    # Grid Trading Settings
    grid_levels: int = Field(default=5, env="GRID_LEVELS")
    grid_spacing_pct: float = Field(default=1.0, env="GRID_SPACING_PCT")
    
    # Trend Following Settings
    trend_fast_ema: int = Field(default=9, env="TREND_FAST_EMA")
    trend_slow_ema: int = Field(default=21, env="TREND_SLOW_EMA")
    trend_timeframes: List[str] = Field(
        default=["1h", "4h"], 
        env="TREND_TIMEFRAMES"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class NotificationConfig(BaseSettings):
    """Notification configuration."""
    
    telegram_bot_token: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")
    notify_on_trade: bool = Field(default=True, env="NOTIFY_ON_TRADE")
    notify_on_error: bool = Field(default=True, env="NOTIFY_ON_ERROR")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    
    database_url: str = Field(
        default="sqlite:///./trading_bot.db", 
        env="DATABASE_URL"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/trading_bot.log", env="LOG_FILE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global configuration instances
trading_config = TradingConfig()
bybit_config = ByBitConfig()
strategy_config = StrategyConfig()
notification_config = NotificationConfig()
database_config = DatabaseConfig()
logging_config = LoggingConfig()
