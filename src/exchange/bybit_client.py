"""ByBit exchange client with multi-subaccount support for The Eternal Engine.

This module provides a unified interface for interacting with Bybit across multiple
subaccounts, one for each engine:
- MASTER: Read-only monitoring across all subaccounts
- CORE-HODL: 60% allocation, spot only
- TREND: 20% allocation, perpetuals, max 2x leverage
- FUNDING: 15% allocation, spot + perps (delta-neutral)
- TACTICAL: 5% allocation, spot only
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Dict, List, Optional, Callable, Any, Union
from datetime import datetime
from enum import Enum
import time

import ccxt.async_support as ccxt
import structlog

from src.core.models import (
    Order, OrderSide, OrderType, OrderStatus, 
    MarketData, Position, PositionSide, Portfolio
)
from src.core.config import trading_config, engine_config

logger = structlog.get_logger(__name__)


class SubAccountType(str, Enum):
    """Enumeration of subaccount types for The Eternal Engine."""
    MASTER = "MASTER"
    CORE_HODL = "CORE_HODL"
    TREND = "TREND"
    FUNDING = "FUNDING"
    TACTICAL = "TACTICAL"


class SubAccountConfig:
    """Configuration for a single subaccount."""
    
    def __init__(
        self,
        name: str,
        api_key: str,
        api_secret: str,
        subaccount_id: Optional[str] = None,
        default_market: str = "spot",
        max_leverage: float = 1.0,
        is_read_only: bool = False
    ):
        self.name = name
        self.api_key = api_key
        self.api_secret = api_secret
        self.subaccount_id = subaccount_id
        self.default_market = default_market
        self.max_leverage = max_leverage
        self.is_read_only = is_read_only
    
    @classmethod
    def from_env(cls, subaccount_type: SubAccountType) -> "SubAccountConfig":
        """Create subaccount config from engine configuration."""
        from src.core.config import engine_config
        
        # Get API credentials from engine_config (reads from .env file)
        api_key = engine_config.bybit.active_api_key
        api_secret = engine_config.bybit.active_api_secret
        
        # Determine market type and leverage based on subaccount purpose
        if subaccount_type == SubAccountType.MASTER:
            default_market = "spot"
            max_leverage = 1.0
            is_read_only = True
        elif subaccount_type == SubAccountType.CORE_HODL:
            default_market = "spot"
            max_leverage = 1.0
            is_read_only = False
        elif subaccount_type == SubAccountType.TREND:
            default_market = "linear"  # USDT perpetuals
            max_leverage = 2.0
            is_read_only = False
        elif subaccount_type == SubAccountType.FUNDING:
            default_market = "linear"  # Uses both spot and linear
            max_leverage = 2.0
            is_read_only = False
        elif subaccount_type == SubAccountType.TACTICAL:
            default_market = "spot"
            max_leverage = 1.0
            is_read_only = False
        else:
            default_market = "spot"
            max_leverage = 1.0
            is_read_only = False
        
        return cls(
            name=subaccount_type.value,
            api_key=api_key,
            api_secret=api_secret,
            default_market=default_market,
            max_leverage=max_leverage,
            is_read_only=is_read_only
        )


class RetryConfig:
    """Configuration for retry logic."""
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0  # seconds
    DEFAULT_MAX_DELAY = 30.0  # seconds
    DEFAULT_EXPONENTIAL_BASE = 2.0


class PybitDemoClient:
    """
    Async wrapper for pybit HTTP client (Demo Trading mode).
    
    Bybit Demo Trading requires pybit with demo=True parameter.
    This wrapper runs sync pybit calls in thread pool executor.
    """
    
    def __init__(self, api_key: str, api_secret: str):
        from pybit.unified_trading import HTTP
        
        self._client = HTTP(
            testnet=False,
            demo=True,
            api_key=api_key,
            api_secret=api_secret,
            recv_window=10000,  # 10 seconds to handle clock skew
        )
        self._executor = ThreadPoolExecutor(max_workers=4)
        self.apiKey = api_key  # For compatibility
        self.secret = api_secret
        
        # Add options dict for compatibility with ccxt-style access
        self.options = {'defaultType': 'spot'}
        
    async def fetch_balance(self, params=None):
        """Fetch wallet balance (async wrapper)."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            lambda: self._client.get_wallet_balance(accountType='UNIFIED')
        )
        return self._convert_balance(result)
    
    def _convert_balance(self, result):
        """Convert pybit response to ccxt-like format."""
        balances = {'info': result, 'free': {}, 'used': {}, 'total': {}}
        
        if result.get('retCode') == 0:
            for account in result.get('result', {}).get('list', []):
                for coin_data in account.get('coin', []):
                    coin = coin_data.get('coin', '')
                    if not coin:
                        continue
                    
                    # Handle empty strings and None values
                    wallet_str = coin_data.get('walletBalance', '0') or '0'
                    free_str = coin_data.get('availableToWithdraw', '') or wallet_str
                    
                    try:
                        wallet = float(wallet_str)
                        free = float(free_str) if free_str else wallet
                    except (ValueError, TypeError):
                        wallet = 0.0
                        free = 0.0
                    
                    # Only include coins with non-zero balance
                    if wallet > 0 or free > 0:
                        balances['total'][coin] = wallet
                        balances['free'][coin] = free
                        balances['used'][coin] = max(0, wallet - free)
                    
        return balances
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100, params=None):
        """
        Fetch OHLCV data using ccxt (public data, no auth required).
        
        This is needed for strategy analysis. We use ccxt for market data
        since pybit doesn't provide OHLCV in the same format.
        """
        # Create a temporary ccxt exchange for market data only
        if not hasattr(self, '_market_exchange'):
            self._market_exchange = ccxt.bybit({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
        
        # Convert symbol format if needed (BTCUSDT -> BTC/USDT)
        ccxt_symbol = symbol.replace('USDT', '/USDT') if '/' not in symbol else symbol
        
        try:
            ohlcv = await self._market_exchange.fetch_ohlcv(
                ccxt_symbol, 
                timeframe=timeframe, 
                limit=limit,
                params=params or {}
            )
            return ohlcv
        except Exception as e:
            logger.warning("pybit_demo.ohlcv_error", symbol=symbol, error=str(e))
            return []
    
    async def fetch_ticker(self, symbol: str, params=None):
        """Fetch ticker data using ccxt."""
        if not hasattr(self, '_market_exchange'):
            self._market_exchange = ccxt.bybit({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
        
        ccxt_symbol = symbol.replace('USDT', '/USDT') if '/' not in symbol else symbol
        
        try:
            ticker = await self._market_exchange.fetch_ticker(ccxt_symbol, params=params or {})
            return ticker
        except Exception as e:
            logger.warning("pybit_demo.ticker_error", symbol=symbol, error=str(e))
            return {}
    
    async def create_order(self, symbol: str, side, type=None, order_type=None, amount=None, price=None, params=None, **kwargs):
        """Create a real order on Bybit Demo Trading using pybit.
        
        This method accepts both ccxt-style parameters (symbol, type, side, amount) and
        our internal parameter names (order_type).
        """
        from src.core.models import Order, OrderSide, OrderType, OrderStatus
        from decimal import Decimal
        
        # Handle ccxt-style 'type' parameter (order type: market/limit)
        if order_type is None and type is not None:
            order_type = type
        
        # Handle amount as various types
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        elif amount is None:
            amount = Decimal("0")
        
        # Handle price
        if price is not None and not isinstance(price, Decimal):
            price = Decimal(str(price)) if price else None
        
        loop = asyncio.get_event_loop()
        params = params or {}
        
        # Convert symbol format for Bybit API (BTCUSDT -> BTCUSDT, but need to handle category)
        category = "spot"  # Default to spot for demo trading
        if params and params.get('market_type'):
            category = params['market_type']
        
        # Convert side and order_type to strings if needed
        side_str = side.upper() if isinstance(side, str) else side.value.upper()
        order_type_str = order_type.upper() if isinstance(order_type, str) else order_type.value.upper()
        
        # Prepare order parameters
        order_params = {
            'category': category,
            'symbol': symbol,
            'side': side_str,
            'orderType': order_type_str,
        }
        
        # For spot market buy orders, use quoteOrderQty (USDT amount) if available
        # This is more reliable than calculating base quantity
        if category == 'spot' and side_str == 'BUY' and order_type_str == 'MARKET':
            # Estimate USDT value (amount * estimated price)
            # For simplicity, we use the qty parameter with proper precision
            pass  # Fall through to qty-based logic
        
        # For spot market BUY orders, use quote amount (USDT) directly
        # This avoids precision issues with base quantity
        if category == 'spot' and side_str == 'BUY' and order_type_str == 'MARKET':
            # Get the USDT value from amount * price
            ticker = await self.fetch_ticker(symbol)
            current_price = Decimal(str(ticker.get('last', 0)))
            if current_price > 0:
                quote_amount = (amount * current_price).quantize(Decimal("0.01"))
                # Bybit minimum order value is 1 USDT, use at least 5 USDT to be safe
                if quote_amount >= Decimal("5"):
                    order_params['marketUnit'] = 'quoteCoin'
                    order_params['qty'] = str(quote_amount)
                    logger.info("pybit_demo.quote_order", symbol=symbol, 
                               quote_amount=str(quote_amount), category=category)
                else:
                    # Fall back to base quantity if quote amount too small
                    qty_str = str(amount.quantize(Decimal("0.000001")))
                    order_params['qty'] = qty_str
                    logger.info("pybit_demo.base_order", symbol=symbol, 
                               qty=qty_str, reason="quote_too_small")
            else:
                # Fallback to base quantity
                qty_str = str(amount.quantize(Decimal("0.000001")))
                order_params['qty'] = qty_str
        else:
            # Round quantity to appropriate precision for the symbol
            # Bybit spot precision: BTC=6, ETH=5, most others=4-6
            if 'BTC' in symbol:
                qty_str = str(amount.quantize(Decimal("0.000001")))
            elif 'ETH' in symbol:
                qty_str = str(amount.quantize(Decimal("0.00001")))
            else:
                qty_str = str(amount.quantize(Decimal("0.0001")))
            order_params['qty'] = qty_str
        
        # Add price for limit orders
        if price and order_type_str != 'MARKET':
            order_params['price'] = str(price)
        
        logger.info("pybit_demo.order_params", symbol=symbol, side=side_str, 
                   order_type=order_type_str, qty=order_params.get('qty'), 
                   market_unit=order_params.get('marketUnit'), category=category)
        
        try:
            # Place the order using pybit
            result = await loop.run_in_executor(
                self._executor,
                lambda: self._client.place_order(**order_params)
            )
            
            if result.get('retCode') == 0:
                order_data = result.get('result', {})
                logger.info(
                    "pybit_demo.order_placed",
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    amount=str(amount),
                    order_id=order_data.get('orderId')
                )
                
                # Create Order object
                order = Order(
                    symbol=symbol,
                    side=OrderSide(side.lower()) if isinstance(side, str) else side,
                    order_type=OrderType(order_type.lower()) if isinstance(order_type, str) else order_type,
                    amount=amount,
                    price=price,
                    exchange_order_id=order_data.get('orderId'),
                    status=OrderStatus.PENDING,
                    filled_amount=Decimal("0")
                )
                return order
            else:
                error_msg = result.get('retMsg', 'Unknown error')
                logger.error("pybit_demo.order_failed", error=error_msg, symbol=symbol)
                raise Exception(f"Bybit API error: {error_msg}")
                
        except Exception as e:
            logger.error("pybit_demo.order_error", symbol=symbol, error=str(e))
            raise
    
    async def load_markets(self):
        """Load markets using ccxt."""
        if not hasattr(self, '_market_exchange'):
            self._market_exchange = ccxt.bybit({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
        return await self._market_exchange.load_markets()
    
    async def fetch_order(self, order_id: str, symbol: str, params=None):
        """Fetch order status using pybit.
        
        Args:
            order_id: The exchange order ID
            symbol: Trading pair symbol
            params: Additional parameters
            
        Returns:
            Order info in ccxt-like format
        """
        loop = asyncio.get_event_loop()
        
        # Determine category from symbol or params
        category = params.get('category', 'spot') if params else 'spot'
        
        try:
            result = await loop.run_in_executor(
                self._executor,
                lambda: self._client.get_order_history(
                    category=category,
                    symbol=symbol,
                    orderId=order_id
                )
            )
            
            if result.get('retCode') == 0:
                orders = result.get('result', {}).get('list', [])
                if orders:
                    order = orders[0]
                    # Convert to ccxt-like format
                    return {
                        'id': order.get('orderId'),
                        'symbol': order.get('symbol'),
                        'status': self._map_order_status(order.get('orderStatus')),
                        'side': order.get('side', '').lower(),
                        'type': order.get('orderType', '').lower(),
                        'amount': float(order.get('qty', 0)),
                        'filled': float(order.get('cumExecQty', 0)),
                        'remaining': float(order.get('leavesQty', 0)),
                        'price': float(order.get('price', 0)) if order.get('price') else None,
                        'average': float(order.get('avgPrice', 0)) if order.get('avgPrice') else None,
                        'info': order
                    }
                else:
                    raise ccxt.OrderNotFound(f"Order {order_id} not found")
            else:
                error_msg = result.get('retMsg', 'Unknown error')
                raise Exception(f"Bybit API error: {error_msg}")
                
        except ccxt.OrderNotFound:
            raise
        except Exception as e:
            logger.error("pybit_demo.fetch_order_error", order_id=order_id, symbol=symbol, error=str(e))
            raise
    
    def _map_order_status(self, status: str) -> str:
        """Map Bybit order status to ccxt format."""
        status_map = {
            'Created': 'open',
            'New': 'open',
            'Rejected': 'rejected',
            'PartiallyFilled': 'open',
            'PartiallyFilledCanceled': 'canceled',
            'Filled': 'closed',
            'Cancelled': 'canceled',
            'Untriggered': 'open',
            'Triggered': 'open',
            'Deactivated': 'canceled',
        }
        return status_map.get(status, 'unknown')
    
    async def close(self):
        """Close the client."""
        if hasattr(self, '_market_exchange'):
            await self._market_exchange.close()
        self._executor.shutdown(wait=False)


def with_retry(
    max_retries: int = RetryConfig.DEFAULT_MAX_RETRIES,
    base_delay: float = RetryConfig.DEFAULT_BASE_DELAY,
    max_delay: float = RetryConfig.DEFAULT_MAX_DELAY,
    exponential_base: float = RetryConfig.DEFAULT_EXPONENTIAL_BASE,
    retryable_exceptions: tuple = (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout)
):
    """Decorator for adding retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exceptions that should trigger a retry
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        logger.warning(
                            f"{func.__name__}.retry_attempt",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=delay,
                            error=str(e)
                        )
                        await asyncio.sleep(delay)
                    else:
                        break
                except ccxt.RateLimitExceeded as e:
                    # Special handling for rate limits - always retry with longer delay
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(60.0 * (2 ** attempt), 300.0)  # Max 5 minutes
                        logger.warning(
                            f"{func.__name__}.rate_limit_hit",
                            attempt=attempt + 1,
                            delay=delay
                        )
                        await asyncio.sleep(delay)
                    else:
                        break
            
            # All retries exhausted
            logger.error(
                f"{func.__name__}.max_retries_exceeded",
                max_retries=max_retries,
                last_error=str(last_exception)
            )
            raise last_exception
        
        return wrapper
    return decorator


class ByBitClient:
    """ByBit exchange client with multi-subaccount support.
    
    This client manages connections to multiple Bybit subaccounts, providing
    isolated trading environments for each engine of The Eternal Engine.
    
    Attributes:
        exchanges: Dictionary mapping subaccount names to ccxt exchange instances
        configs: Dictionary mapping subaccount names to SubAccountConfig
        _initialized: Whether the client has been initialized
        _price_callbacks: List of callbacks for price updates
        _order_callbacks: List of callbacks for order updates
    """
    
    # Subaccount market type overrides for specific operations
    MARKET_TYPE_OVERRIDES = {
        SubAccountType.FUNDING: ["spot", "linear"]  # FUNDING uses both
    }
    
    def __init__(self):
        self.exchanges: Dict[str, ccxt.bybit] = {}
        self.configs: Dict[str, SubAccountConfig] = {}
        self._initialized = False
        self._ws_connected = False
        self._price_callbacks: List[Callable[[str, Decimal], Any]] = []
        self._order_callbacks: List[Callable[[Order], Any]] = []
        self._markets_loaded: Dict[str, bool] = {}
        
    async def initialize(
        self, 
        subaccounts: Optional[List[SubAccountType]] = None,
        testnet: Optional[bool] = None
    ):
        """Initialize connections to specified subaccounts.
        
        Args:
            subaccounts: List of subaccounts to initialize. If None, initializes all.
            testnet: Whether to use testnet. If None, reads from BYBIT_TESTNET env var.
        """
        import os
        
        if testnet is None:
            testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        
        if subaccounts is None:
            subaccounts = list(SubAccountType)
        
        init_tasks = []
        for subaccount_type in subaccounts:
            task = self._initialize_subaccount(subaccount_type, testnet)
            init_tasks.append(task)
        
        results = await asyncio.gather(*init_tasks, return_exceptions=True)
        
        # Check for exceptions - re-raise the first one
        for subaccount_type, result in zip(subaccounts, results):
            if isinstance(result, Exception):
                logger.error(
                    "bybit_client.subaccount_init_failed",
                    subaccount=subaccount_type.value,
                    error=str(result),
                    error_type=type(result).__name__
                )
                # Re-raise the original exception to preserve error type
                raise result
        
        self._initialized = True
        
        logger.info(
            "bybit_client.initialized",
            subaccounts=[s.value for s in subaccounts],
            initialized=list(self.exchanges.keys()),
            testnet=testnet,
            trading_mode=trading_config.trading_mode
        )
    
    async def _initialize_subaccount(self, subaccount_type: SubAccountType, testnet: bool):
        """Initialize a single subaccount connection."""
        config = SubAccountConfig.from_env(subaccount_type)
        
        if not config.api_key or not config.api_secret:
            logger.warning(
                "bybit_client.missing_credentials",
                subaccount=subaccount_type.value,
                message="Skipping initialization - API credentials not configured"
            )
            return
        
        # Determine if using demo trading (fake money on Bybit Demo Trading)
        is_demo_trading = engine_config.bybit.api_mode == "demo" and not testnet
        
        if is_demo_trading:
            # Use pybit for demo trading (required by Bybit)
            await self._initialize_demo_subaccount(subaccount_type, config)
        else:
            # Use ccxt for testnet and production
            await self._initialize_ccxt_subaccount(subaccount_type, config, testnet)
    
    async def _initialize_demo_subaccount(self, subaccount_type: SubAccountType, config: SubAccountConfig):
        """Initialize subaccount using pybit for Demo Trading."""
        try:
            exchange = PybitDemoClient(
                api_key=config.api_key,
                api_secret=config.api_secret
            )
            
            # Test connection by fetching balance
            await exchange.fetch_balance()
            
            self.exchanges[subaccount_type.value] = exchange
            self.configs[subaccount_type.value] = config
            self._markets_loaded[subaccount_type.value] = True
            
            logger.info(
                "bybit_client.subaccount_initialized",
                subaccount=subaccount_type.value,
                default_market=config.default_market,
                max_leverage=config.max_leverage,
                mode="demo_trading"
            )
        except Exception as e:
            logger.error(
                "bybit_client.subaccount_init_failed",
                subaccount=subaccount_type.value,
                error=str(e),
                mode="demo_trading"
            )
            raise
    
    async def _initialize_ccxt_subaccount(self, subaccount_type: SubAccountType, config: SubAccountConfig, testnet: bool):
        """Initialize subaccount using ccxt for Testnet/Production."""
        ccxt_config = {
            'apiKey': config.api_key,
            'secret': config.api_secret,
            'sandbox': testnet,
            'enableRateLimit': True,
            'options': {
                'defaultType': config.default_market,
                'adjustForTimeDifference': True,
                'recvWindow': 20000,
            }
        }
        
        # Add subaccount ID if provided
        if config.subaccount_id:
            ccxt_config['options']['subaccountId'] = config.subaccount_id
        
        exchange = ccxt.bybit(ccxt_config)
        
        try:
            # Load markets
            await exchange.load_markets()
            self.exchanges[subaccount_type.value] = exchange
            self.configs[subaccount_type.value] = config
            self._markets_loaded[subaccount_type.value] = True
            
            logger.info(
                "bybit_client.subaccount_initialized",
                subaccount=subaccount_type.value,
                default_market=config.default_market,
                max_leverage=config.max_leverage,
                mode="ccxt"
            )
        except Exception as e:
            # Close the exchange to prevent resource leaks
            try:
                await exchange.close()
            except Exception:
                pass
            
            logger.error(
                "bybit_client.subaccount_init_failed",
                subaccount=subaccount_type.value,
                error=str(e),
                mode="ccxt"
            )
            raise
    
    async def close(self):
        """Close all exchange connections."""
        close_tasks = []
        for name, exchange in self.exchanges.items():
            task = self._close_exchange(name, exchange)
            close_tasks.append(task)
        
        await asyncio.gather(*close_tasks, return_exceptions=True)
        self.exchanges.clear()
        self.configs.clear()
        self._initialized = False
        
        logger.info("bybit_client.closed")
    
    async def _close_exchange(self, name: str, exchange: ccxt.bybit):
        """Close a single exchange connection."""
        try:
            await exchange.close()
            logger.debug("bybit_client.exchange_closed", subaccount=name)
        except Exception as e:
            logger.warning(
                "bybit_client.close_error",
                subaccount=name,
                error=str(e)
            )
    
    def _get_exchange(self, subaccount: str) -> ccxt.bybit:
        """Get exchange instance for a subaccount."""
        if subaccount not in self.exchanges:
            raise ValueError(f"Subaccount '{subaccount}' not initialized. "
                           f"Available: {list(self.exchanges.keys())}")
        return self.exchanges[subaccount]
    
    def _get_config(self, subaccount: str) -> SubAccountConfig:
        """Get configuration for a subaccount."""
        if subaccount not in self.configs:
            raise ValueError(f"Subaccount '{subaccount}' not configured")
        return self.configs[subaccount]
    
    @with_retry()
    async def get_balance(
        self, 
        subaccount: str = "MASTER",
        asset: str = "USDT"
    ) -> Portfolio:
        """Get wallet balance for a subaccount.
        
        Args:
            subaccount: Subaccount name (e.g., 'CORE_HODL', 'TREND')
            asset: Base asset for balance calculation (default: USDT)
            
        Returns:
            Portfolio object with total and available balance
            
        Raises:
            ValueError: If subaccount is not initialized
            ccxt.NetworkError: On network failures (with retry)
        """
        exchange = self._get_exchange(subaccount)
        
        try:
            balance = await exchange.fetch_balance()
            
            total = Decimal(str(balance.get('total', {}).get(asset, 0)))
            free = Decimal(str(balance.get('free', {}).get(asset, 0)))
            used = Decimal(str(balance.get('used', {}).get(asset, 0)))
            
            # Calculate total portfolio value across all assets
            total_portfolio_value = Decimal("0")
            for currency, amount in balance.get('total', {}).items():
                if amount and amount > 0:
                    # For simplicity, we use the requested asset as base
                    # In production, you'd convert all assets to USD
                    if currency == asset:
                        total_portfolio_value += Decimal(str(amount))
            
            logger.debug(
                "bybit_client.balance_fetched",
                subaccount=subaccount,
                asset=asset,
                total=str(total),
                free=str(free)
            )
            
            return Portfolio(
                total_balance=total_portfolio_value or total,
                available_balance=free
            )
            
        except Exception as e:
            logger.error(
                "bybit_client.balance_error",
                subaccount=subaccount,
                asset=asset,
                error=str(e)
            )
            raise
    
    @with_retry()
    async def fetch_balance(self, subaccount: str = "MASTER") -> Dict[str, Any]:
        """
        Fetch raw wallet balance for a subaccount (ccxt-like format).
        
        Args:
            subaccount: Subaccount name (e.g., 'CORE_HODL', 'TREND')
            
        Returns:
            Dictionary with 'total', 'free', 'used' keys containing coin balances
        """
        exchange = self._get_exchange(subaccount)
        
        try:
            if isinstance(exchange, PybitDemoClient):
                # PybitDemoClient has its own fetch_balance
                balance = await exchange.fetch_balance()
            else:
                # ccxt exchange
                balance = await exchange.fetch_balance()
            
            logger.debug(
                "bybit_client.raw_balance_fetched",
                subaccount=subaccount,
                coins=list(balance.get('total', {}).keys())
            )
            
            return balance
            
        except Exception as e:
            logger.error(
                "bybit_client.fetch_balance_error",
                subaccount=subaccount,
                error=str(e)
            )
            raise
    
    @with_retry()
    async def get_positions(
        self, 
        subaccount: str,
        symbol: Optional[str] = None
    ) -> List[Position]:
        """Get open positions for a subaccount.
        
        Args:
            subaccount: Subaccount name
            symbol: Optional symbol filter (e.g., 'BTCUSDT')
            
        Returns:
            List of Position objects
            
        Note:
            For spot subaccounts (CORE_HODL, TACTICAL), this returns
            positions based on holdings. For perpetual subaccounts
            (TREND, FUNDING), this returns contract positions.
        """
        exchange = self._get_exchange(subaccount)
        config = self._get_config(subaccount)
        
        positions = []
        
        try:
            # For perpetual markets, fetch contract positions
            if config.default_market in ["linear", "inverse"]:
                raw_positions = await exchange.fetch_positions(symbol)
                
                for pos in raw_positions:
                    contracts = Decimal(str(pos.get('contracts', 0)))
                    if contracts != 0:
                        side = PositionSide.LONG if contracts > 0 else PositionSide.SHORT
                        positions.append(Position(
                            symbol=pos.get('symbol', symbol or ''),
                            side=side,
                            entry_price=Decimal(str(pos.get('entryPrice', 0))),
                            amount=abs(contracts),
                            unrealized_pnl=Decimal(str(pos.get('unrealizedPnl', 0))),
                            realized_pnl=Decimal(str(pos.get('realizedPnl', 0))),
                            metadata={
                                'leverage': pos.get('leverage', 1),
                                'marginMode': pos.get('marginMode', 'cross'),
                                'liquidationPrice': pos.get('liquidationPrice')
                            }
                        ))
            
            # For spot markets, build positions from balance
            else:
                balance = await exchange.fetch_balance()
                
                for currency, amount in balance.get('total', {}).items():
                    if currency != "USDT" and amount and amount > 0:
                        pair_symbol = f"{currency}/USDT"
                        try:
                            ticker = await exchange.fetch_ticker(pair_symbol)
                            current_price = Decimal(str(ticker['last']))
                            
                            positions.append(Position(
                                symbol=pair_symbol.replace('/', ''),
                                side=PositionSide.LONG,  # Spot is always long
                                entry_price=current_price,  # Approximation
                                amount=Decimal(str(amount)),
                                unrealized_pnl=Decimal("0"),
                                metadata={'spot': True}
                            ))
                        except:
                            # Skip if we can't get price
                            pass
            
            logger.debug(
                "bybit_client.positions_fetched",
                subaccount=subaccount,
                symbol=symbol,
                count=len(positions)
            )
            
            return positions
            
        except Exception as e:
            logger.error(
                "bybit_client.positions_error",
                subaccount=subaccount,
                symbol=symbol,
                error=str(e)
            )
            raise
    
    @with_retry()
    async def create_order(
        self,
        subaccount: str,
        symbol: str,
        side: Union[OrderSide, str],
        order_type: Union[OrderType, str],
        amount: Decimal,
        price: Optional[Decimal] = None,
        params: Optional[Dict] = None
    ) -> Order:
        """Create a new order on a subaccount.
        
        Args:
            subaccount: Subaccount to place order on
            symbol: Trading pair (e.g., 'BTCUSDT')
            side: BUY or SELL
            order_type: MARKET or LIMIT
            amount: Order quantity
            price: Limit price (required for LIMIT orders)
            params: Additional parameters (stopLoss, takeProfit, etc.)
            
        Returns:
            Order object with execution details
            
        Raises:
            ValueError: On invalid parameters or read-only subaccount
            ccxt.AuthenticationError: On API credential issues
            ccxt.InsufficientFunds: On insufficient balance
        """
        config = self._get_config(subaccount)
        
        # Check read-only
        if config.is_read_only:
            raise ValueError(f"Subaccount '{subaccount}' is read-only")
        
        # Paper trading mode
        if trading_config.trading_mode == "paper":
            return await self._simulate_order(
                subaccount, symbol, side, order_type, amount, price, params
            )
        
        exchange = self._get_exchange(subaccount)
        
        # Normalize inputs
        if isinstance(side, OrderSide):
            side = side.value
        if isinstance(order_type, OrderType):
            order_type = order_type.value
        
        # Validate limit order has price
        if order_type == "limit" and price is None:
            raise ValueError("Price is required for limit orders")
        
        # Prepare parameters
        order_params = params or {}
        
        # Add leverage for perpetual orders if not specified
        if config.default_market in ["linear", "inverse"] and "leverage" not in order_params:
            order_params["leverage"] = config.max_leverage
        
        try:
            result = await exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=float(amount),
                price=float(price) if price else None,
                params=order_params
            )
            
            # Handle case where exchange returns an Order object directly (PybitDemoClient)
            if isinstance(result, Order):
                # Update metadata with subaccount info
                result.metadata = result.metadata or {}
                result.metadata['subaccount'] = subaccount
                return result
            
            # Handle ccxt-style dictionary response
            order = Order(
                symbol=symbol,
                side=OrderSide(side),
                order_type=OrderType(order_type),
                amount=amount,
                price=price,
                exchange_order_id=result.get('id'),
                status=self._map_order_status(result.get('status')),
                filled_amount=Decimal(str(result.get('filled', 0))),
                average_price=Decimal(str(result.get('average', 0))) if result.get('average') else None,
                stop_loss_price=Decimal(str(order_params.get('stopLoss'))) if order_params.get('stopLoss') else None,
                take_profit_price=Decimal(str(order_params.get('takeProfit'))) if order_params.get('takeProfit') else None,
                metadata={
                    'raw_response': result,
                    'subaccount': subaccount
                }
            )
            
            logger.info(
                "bybit_client.order_created",
                subaccount=subaccount,
                order_id=order.id,
                exchange_order_id=order.exchange_order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=str(amount),
                status=order.status.value
            )
            
            return order
            
        except ccxt.InsufficientFunds as e:
            logger.error(
                "bybit_client.insufficient_funds",
                subaccount=subaccount,
                symbol=symbol,
                amount=str(amount),
                error=str(e)
            )
            raise
        except Exception as e:
            logger.error(
                "bybit_client.order_error",
                subaccount=subaccount,
                symbol=symbol,
                side=side,
                error=str(e)
            )
            raise
    
    async def _simulate_order(
        self,
        subaccount: str,
        symbol: str,
        side: Union[OrderSide, str],
        order_type: Union[OrderType, str],
        amount: Decimal,
        price: Optional[Decimal],
        params: Optional[Dict]
    ) -> Order:
        """Simulate an order for paper trading."""
        if isinstance(side, OrderSide):
            side = side.value
        if isinstance(order_type, OrderType):
            order_type = order_type.value
        
        # Get current price for simulation
        try:
            ticker = await self.fetch_ticker(symbol)
            sim_price = price or ticker['last']
        except:
            sim_price = price or Decimal("0")
        
        logger.warning(
            "bybit_client.paper_trade",
            subaccount=subaccount,
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=str(amount),
            price=str(price) if price else str(sim_price)
        )
        
        return Order(
            symbol=symbol,
            side=OrderSide(side),
            order_type=OrderType(order_type),
            amount=amount,
            price=price or sim_price,
            status=OrderStatus.FILLED,
            filled_amount=amount,
            average_price=sim_price,
            metadata={
                'paper_trade': True,
                'subaccount': subaccount
            }
        )
    
    @with_retry()
    async def cancel_order(
        self, 
        subaccount: str,
        order_id: str, 
        symbol: str
    ) -> bool:
        """Cancel an existing order.
        
        Args:
            subaccount: Subaccount containing the order
            order_id: Exchange order ID to cancel
            symbol: Trading pair symbol
            
        Returns:
            True if cancellation was successful
        """
        config = self._get_config(subaccount)
        
        if config.is_read_only:
            raise ValueError(f"Subaccount '{subaccount}' is read-only")
        
        if trading_config.trading_mode == "paper":
            logger.info(
                "bybit_client.paper_cancel",
                subaccount=subaccount,
                order_id=order_id
            )
            return True
        
        exchange = self._get_exchange(subaccount)
        
        try:
            await exchange.cancel_order(order_id, symbol)
            logger.info(
                "bybit_client.order_cancelled",
                subaccount=subaccount,
                order_id=order_id,
                symbol=symbol
            )
            return True
        except ccxt.OrderNotFound:
            logger.warning(
                "bybit_client.cancel_order_not_found",
                subaccount=subaccount,
                order_id=order_id
            )
            return False
        except Exception as e:
            logger.error(
                "bybit_client.cancel_error",
                subaccount=subaccount,
                order_id=order_id,
                error=str(e)
            )
            raise
    
    @with_retry()
    async def get_order_status(
        self, 
        subaccount: str,
        order_id: str, 
        symbol: str
    ) -> OrderStatus:
        """Get current status of an order.
        
        Args:
            subaccount: Subaccount containing the order
            order_id: Exchange order ID
            symbol: Trading pair symbol
            
        Returns:
            OrderStatus enum value
        """
        if trading_config.trading_mode == "paper":
            return OrderStatus.FILLED
        
        exchange = self._get_exchange(subaccount)
        
        try:
            order_info = await exchange.fetch_order(order_id, symbol)
            return self._map_order_status(order_info.get('status'))
        except ccxt.OrderNotFound:
            return OrderStatus.CANCELLED
        except Exception as e:
            logger.error(
                "bybit_client.status_error",
                subaccount=subaccount,
                order_id=order_id,
                error=str(e)
            )
            raise
    
    @with_retry()
    async def get_open_orders(
        self, 
        subaccount: str,
        symbol: Optional[str] = None
    ) -> List[Order]:
        """Get all open orders for a subaccount.
        
        Args:
            subaccount: Subaccount to query
            symbol: Optional symbol filter
            
        Returns:
            List of open Order objects
        """
        if trading_config.trading_mode == "paper":
            return []
        
        exchange = self._get_exchange(subaccount)
        
        try:
            orders = await exchange.fetch_open_orders(symbol)
            return [
                Order(
                    symbol=o['symbol'],
                    side=OrderSide(o['side']),
                    order_type=OrderType(o['type']),
                    amount=Decimal(str(o['amount'])),
                    price=Decimal(str(o['price'])) if o['price'] else None,
                    exchange_order_id=o['id'],
                    status=self._map_order_status(o['status']),
                    filled_amount=Decimal(str(o['filled'])),
                    average_price=Decimal(str(o['average'])) if o['average'] else None,
                    metadata={'subaccount': subaccount}
                )
                for o in orders
            ]
        except Exception as e:
            logger.error(
                "bybit_client.open_orders_error",
                subaccount=subaccount,
                error=str(e)
            )
            return []
    
    @with_retry()
    async def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = '1h', 
        limit: int = 100,
        market_type: str = "spot"
    ) -> List[MarketData]:
        """Fetch OHLCV (candlestick) data.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Candle interval (1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M)
            limit: Number of candles to fetch (max 1000)
            market_type: 'spot', 'linear', or 'inverse'
            
        Returns:
            List of MarketData objects
        """
        # Use MASTER subaccount or any available for market data
        exchange = None
        if SubAccountType.MASTER.value in self.exchanges:
            exchange = self.exchanges[SubAccountType.MASTER.value]
        elif self.exchanges:
            exchange = next(iter(self.exchanges.values()))
        else:
            raise ValueError("No exchanges initialized for market data")
        
        try:
            # Temporarily set market type
            original_type = exchange.options.get('defaultType')
            exchange.options['defaultType'] = market_type
            
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # Restore original type
            exchange.options['defaultType'] = original_type
            
            market_data = []
            for candle in ohlcv:
                # OHLCV format: [timestamp, open, high, low, close, volume]
                market_data.append(MarketData(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(candle[0] / 1000),
                    open=Decimal(str(candle[1])),
                    high=Decimal(str(candle[2])),
                    low=Decimal(str(candle[3])),
                    close=Decimal(str(candle[4])),
                    volume=Decimal(str(candle[5])),
                    timeframe=timeframe
                ))
            
            return market_data
            
        except Exception as e:
            logger.error(
                "bybit_client.ohlcv_error", 
                symbol=symbol, 
                timeframe=timeframe, 
                error=str(e)
            )
            raise
    
    @with_retry()
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker data for a symbol (alias for fetch_ticker).
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            
        Returns:
            Dictionary with last price, bid, ask, volume, timestamp
        """
        return await self.fetch_ticker(symbol)
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker data for a symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            
        Returns:
            Dictionary with last price, bid, ask, volume, timestamp
        """
        # Use any available exchange for market data
        exchange = None
        if SubAccountType.MASTER.value in self.exchanges:
            exchange = self.exchanges[SubAccountType.MASTER.value]
        elif self.exchanges:
            exchange = next(iter(self.exchanges.values()))
        else:
            raise ValueError("No exchanges initialized for market data")
        
        try:
            ticker = await exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': Decimal(str(ticker['last'])),
                'bid': Decimal(str(ticker['bid'])),
                'ask': Decimal(str(ticker['ask'])),
                'volume': Decimal(str(ticker.get('quoteVolume', 0))),
                'timestamp': ticker['timestamp'],
                'change_24h': Decimal(str(ticker.get('change', 0))),
                'change_pct_24h': Decimal(str(ticker.get('percentage', 0)))
            }
        except Exception as e:
            logger.error(
                "bybit_client.ticker_error", 
                symbol=symbol, 
                error=str(e)
            )
            raise
    
    @with_retry()
    async def get_funding_rate(
        self, 
        symbol: str,
        since: Optional[int] = None,
        limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Get funding rate history for a perpetual symbol.
        
        Args:
            symbol: Perpetual symbol (e.g., 'BTCUSDT')
            since: Timestamp in milliseconds to fetch from
            limit: Number of funding rate entries
            
        Returns:
            List of funding rate data dictionaries
        """
        # Use TREND or FUNDING subaccount for funding data
        exchange = None
        for subaccount in [SubAccountType.FUNDING.value, SubAccountType.TREND.value]:
            if subaccount in self.exchanges:
                exchange = self.exchanges[subaccount]
                break
        
        if exchange is None and self.exchanges:
            exchange = next(iter(self.exchanges.values()))
        elif exchange is None:
            raise ValueError("No exchanges initialized for funding data")
        
        try:
            # Set to linear market for funding rates
            original_type = exchange.options.get('defaultType')
            exchange.options['defaultType'] = 'linear'
            
            funding_rates = await exchange.fetch_funding_rate_history(symbol, since, limit)
            
            # Restore original type
            exchange.options['defaultType'] = original_type
            
            result = []
            for rate in funding_rates:
                result.append({
                    'symbol': symbol,
                    'funding_rate': Decimal(str(rate.get('fundingRate', 0))),
                    'timestamp': rate.get('timestamp'),
                    'datetime': rate.get('datetime')
                })
            
            logger.debug(
                "bybit_client.funding_rate_fetched",
                symbol=symbol,
                entries=len(result)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "bybit_client.funding_rate_error",
                symbol=symbol,
                error=str(e)
            )
            raise
    
    async def get_all_balances(self) -> Dict[str, Portfolio]:
        """Get balances for all initialized subaccounts.
        
        Returns:
            Dictionary mapping subaccount names to Portfolio objects
        """
        balances = {}
        tasks = []
        
        for subaccount in self.exchanges.keys():
            task = self._get_balance_safe(subaccount)
            tasks.append((subaccount, task))
        
        for subaccount, task in tasks:
            try:
                balance = await task
                balances[subaccount] = balance
            except Exception as e:
                logger.error(
                    "bybit_client.balance_fetch_failed",
                    subaccount=subaccount,
                    error=str(e)
                )
                balances[subaccount] = None
        
        return balances
    
    async def _get_balance_safe(self, subaccount: str) -> Optional[Portfolio]:
        """Safely get balance for a subaccount."""
        try:
            return await self.get_balance(subaccount)
        except:
            return None
    
    def _map_order_status(self, status: Optional[str]) -> OrderStatus:
        """Map exchange order status to internal OrderStatus."""
        if not status:
            return OrderStatus.PENDING
            
        status_map = {
            'open': OrderStatus.OPEN,
            'closed': OrderStatus.FILLED,
            'canceled': OrderStatus.CANCELLED,
            'cancelled': OrderStatus.CANCELLED,
            'pending': OrderStatus.PENDING,
            'rejected': OrderStatus.REJECTED,
            'expired': OrderStatus.EXPIRED,
            'NEW': OrderStatus.OPEN,
            'PARTIALLY_FILLED': OrderStatus.PARTIALLY_FILLED,
            'FILLED': OrderStatus.FILLED,
            'CANCELED': OrderStatus.CANCELLED,
            'REJECTED': OrderStatus.REJECTED,
            'EXPIRED': OrderStatus.EXPIRED,
        }
        return status_map.get(status, OrderStatus.PENDING)
    
    def register_price_callback(self, callback: Callable[[str, Decimal], Any]):
        """Register a callback for price updates."""
        self._price_callbacks.append(callback)
    
    def register_order_callback(self, callback: Callable[[Order], Any]):
        """Register a callback for order updates."""
        self._order_callbacks.append(callback)
    
    @property
    def initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized
    
    @property
    def subaccounts(self) -> List[str]:
        """Get list of initialized subaccount names."""
        return list(self.exchanges.keys())


# Convenience function to create a client with all subaccounts
async def create_bybit_client(
    testnet: Optional[bool] = None,
    subaccounts: Optional[List[SubAccountType]] = None
) -> ByBitClient:
    """Create and initialize a ByBitClient with specified subaccounts.
    
    Args:
        testnet: Whether to use testnet (default from env)
        subaccounts: List of subaccounts to initialize (default: all)
        
    Returns:
        Initialized ByBitClient instance
        
    Example:
        >>> client = await create_bybit_client()
        >>> balance = await client.get_balance("CORE_HODL")
        >>> await client.close()
    """
    client = ByBitClient()
    await client.initialize(testnet=testnet, subaccounts=subaccounts)
    return client
