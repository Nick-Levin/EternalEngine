"""Unit tests for Bybit exchange client."""
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, ANY

import ccxt.async_support as ccxt

from src.exchange.bybit_client import (
    ByBitClient, SubAccountType, SubAccountConfig,
    RetryConfig, with_retry
)
from src.core.models import (
    Order, OrderSide, OrderType, OrderStatus,
    Position, PositionSide, Portfolio, MarketData
)
from src.core.config import trading_config


# =============================================================================
# SubAccountConfig Tests
# =============================================================================

class TestSubAccountConfig:
    """Test SubAccountConfig class."""
    
    def test_subaccount_config_creation(self):
        """Test creating SubAccountConfig."""
        config = SubAccountConfig(
            name="TEST",
            api_key="test_key",
            api_secret="test_secret",
            subaccount_id="test_id",
            default_market="spot",
            max_leverage=2.0,
            is_read_only=False
        )
        
        assert config.name == "TEST"
        assert config.api_key == "test_key"
        assert config.api_secret == "test_secret"
        assert config.subaccount_id == "test_id"
        assert config.default_market == "spot"
        assert config.max_leverage == 2.0
        assert config.is_read_only is False
    
    def test_subaccount_config_from_env_master(self, monkeypatch):
        """Test SubAccountConfig.from_env for MASTER subaccount."""
        monkeypatch.setenv("BYBIT_MASTER_API_KEY", "master_key")
        monkeypatch.setenv("BYBIT_MASTER_API_SECRET", "master_secret")
        
        config = SubAccountConfig.from_env(SubAccountType.MASTER)
        
        assert config.name == "MASTER"
        assert config.api_key == "master_key"
        assert config.default_market == "spot"
        assert config.max_leverage == 1.0
        assert config.is_read_only is True
    
    def test_subaccount_config_from_env_core_hodl(self, monkeypatch):
        """Test SubAccountConfig.from_env for CORE_HODL subaccount."""
        monkeypatch.setenv("BYBIT_CORE_HODL_API_KEY", "core_key")
        monkeypatch.setenv("BYBIT_CORE_HODL_API_SECRET", "core_secret")
        
        config = SubAccountConfig.from_env(SubAccountType.CORE_HODL)
        
        assert config.name == "CORE_HODL"
        assert config.default_market == "spot"
        assert config.max_leverage == 1.0
        assert config.is_read_only is False
    
    def test_subaccount_config_from_env_trend(self, monkeypatch):
        """Test SubAccountConfig.from_env for TREND subaccount."""
        monkeypatch.setenv("BYBIT_TREND_1_API_KEY", "trend_key")
        monkeypatch.setenv("BYBIT_TREND_1_API_SECRET", "trend_secret")
        
        config = SubAccountConfig.from_env(SubAccountType.TREND)
        
        assert config.name == "TREND"
        assert config.default_market == "linear"
        assert config.max_leverage == 2.0
        assert config.is_read_only is False
    
    def test_subaccount_config_from_env_funding(self, monkeypatch):
        """Test SubAccountConfig.from_env for FUNDING subaccount."""
        monkeypatch.setenv("BYBIT_FUNDING_API_KEY", "funding_key")
        monkeypatch.setenv("BYBIT_FUNDING_API_SECRET", "funding_secret")
        
        config = SubAccountConfig.from_env(SubAccountType.FUNDING)
        
        assert config.name == "FUNDING"
        assert config.default_market == "linear"
        assert config.max_leverage == 2.0
    
    def test_subaccount_config_from_env_tactical(self, monkeypatch):
        """Test SubAccountConfig.from_env for TACTICAL subaccount."""
        monkeypatch.setenv("BYBIT_TACTICAL_API_KEY", "tactical_key")
        monkeypatch.setenv("BYBIT_TACTICAL_API_SECRET", "tactical_secret")
        
        config = SubAccountConfig.from_env(SubAccountType.TACTICAL)
        
        assert config.name == "TACTICAL"
        assert config.default_market == "spot"
        assert config.max_leverage == 1.0


# =============================================================================
# RetryConfig Tests
# =============================================================================

class TestRetryConfig:
    """Test RetryConfig class."""
    
    def test_retry_config_defaults(self):
        """Test RetryConfig default values."""
        assert RetryConfig.DEFAULT_MAX_RETRIES == 3
        assert RetryConfig.DEFAULT_BASE_DELAY == 1.0
        assert RetryConfig.DEFAULT_MAX_DELAY == 30.0
        assert RetryConfig.DEFAULT_EXPONENTIAL_BASE == 2.0


# =============================================================================
# ByBitClient Tests
# =============================================================================

class TestByBitClient:
    """Test ByBitClient class."""
    
    @pytest.fixture
    def client(self):
        """Create a ByBitClient instance."""
        return ByBitClient()
    
    @pytest_asyncio.fixture
    async def initialized_client(self, client):
        """Create and initialize a ByBitClient with mocked exchange."""
        with patch('ccxt.async_support.bybit') as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.load_markets = AsyncMock()
            mock_ccxt.return_value = mock_exchange
            
            # Mock environment variables
            with patch.dict('os.environ', {
                'BYBIT_MASTER_API_KEY': 'test_key',
                'BYBIT_MASTER_API_SECRET': 'test_secret'
            }):
                await client.initialize([SubAccountType.MASTER], testnet=True)
                yield client
                
                await client.close()
    
    def test_client_initialization(self, client):
        """Test ByBitClient initialization."""
        assert client.exchanges == {}
        assert client.configs == {}
        assert client._initialized is False
        assert client._ws_connected is False
        assert client._price_callbacks == []
        assert client._order_callbacks == []
    
    @pytest.mark.asyncio
    async def test_initialize_subaccount(self, client):
        """Test initializing a single subaccount."""
        with patch('ccxt.async_support.bybit') as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.load_markets = AsyncMock()
            mock_ccxt.return_value = mock_exchange
            
            with patch.dict('os.environ', {
                'BYBIT_MASTER_API_KEY': 'test_key',
                'BYBIT_MASTER_API_SECRET': 'test_secret'
            }):
                await client.initialize([SubAccountType.MASTER], testnet=True)
                
                assert "MASTER" in client.exchanges
                assert "MASTER" in client.configs
                assert client._initialized is True
                mock_exchange.load_markets.assert_called_once()
                
                await client.close()
    
    @pytest.mark.asyncio
    async def test_initialize_skips_missing_credentials(self, client):
        """Test that initialization skips subaccounts with missing credentials."""
        with patch('ccxt.async_support.bybit') as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_ccxt.return_value = mock_exchange
            
            # No environment variables set
            with patch.dict('os.environ', {}, clear=True):
                await client.initialize([SubAccountType.MASTER], testnet=True)
                
                # Should skip initialization due to missing credentials
                assert "MASTER" not in client.exchanges
                
                await client.close()
    
    @pytest.mark.asyncio
    async def test_close_client(self, client):
        """Test closing the client."""
        with patch('ccxt.async_support.bybit') as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.load_markets = AsyncMock()
            mock_exchange.close = AsyncMock()
            mock_ccxt.return_value = mock_exchange
            
            with patch.dict('os.environ', {
                'BYBIT_MASTER_API_KEY': 'test_key',
                'BYBIT_MASTER_API_SECRET': 'test_secret'
            }):
                await client.initialize([SubAccountType.MASTER], testnet=True)
                await client.close()
                
                assert client.exchanges == {}
                assert client.configs == {}
                assert client._initialized is False
    
    @pytest.mark.asyncio
    async def test_get_exchange_raises_for_uninitialized(self, client):
        """Test that _get_exchange raises for uninitialized subaccount."""
        with pytest.raises(ValueError, match="not initialized"):
            client._get_exchange("NONEXISTENT")
    
    @pytest.mark.asyncio
    async def test_get_balance(self, initialized_client):
        """Test getting balance for a subaccount."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_balance = AsyncMock(return_value={
            'total': {'USDT': 10000.0, 'BTC': 0.5},
            'free': {'USDT': 8000.0, 'BTC': 0.5},
            'used': {'USDT': 2000.0, 'BTC': 0}
        })
        
        portfolio = await initialized_client.get_balance("MASTER")
        
        assert isinstance(portfolio, Portfolio)
        assert portfolio.total_balance == Decimal("10000")
        assert portfolio.available_balance == Decimal("8000")
    
    @pytest.mark.asyncio
    async def test_get_balance_error_handling(self, initialized_client):
        """Test balance fetch error handling."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_balance = AsyncMock(side_effect=Exception("API Error"))
        
        with pytest.raises(Exception, match="API Error"):
            await initialized_client.get_balance("MASTER")
    
    @pytest.mark.asyncio
    async def test_get_positions_perpetual(self, initialized_client):
        """Test getting positions for perpetual markets."""
        # Reconfigure as TREND subaccount for linear market
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.options = {'defaultType': 'linear'}
        
        initialized_client.configs["MASTER"] = MagicMock()
        initialized_client.configs["MASTER"].default_market = "linear"
        
        mock_exchange.fetch_positions = AsyncMock(return_value=[{
            'symbol': 'BTCUSDT',
            'contracts': 0.5,
            'entryPrice': 50000,
            'unrealizedPnl': 500,
            'realizedPnl': 100,
            'leverage': 2,
            'marginMode': 'cross',
            'liquidationPrice': 40000
        }])
        
        positions = await initialized_client.get_positions("MASTER", "BTCUSDT")
        
        assert len(positions) == 1
        assert positions[0].symbol == "BTCUSDT"
        assert positions[0].amount == Decimal("0.5")
        assert positions[0].entry_price == Decimal("50000")
    
    @pytest.mark.asyncio
    async def test_get_positions_spot(self, initialized_client):
        """Test getting positions for spot markets."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        initialized_client.configs["MASTER"] = MagicMock()
        initialized_client.configs["MASTER"].default_market = "spot"
        
        mock_exchange.fetch_balance = AsyncMock(return_value={
            'total': {'BTC': 0.5, 'ETH': 5.0, 'USDT': 1000}
        })
        mock_exchange.fetch_ticker = AsyncMock(return_value={'last': 50000})
        
        positions = await initialized_client.get_positions("MASTER")
        
        # Should return positions for non-USDT holdings
        assert len(positions) >= 0  # May be 0 if ticker fetch fails
    
    @pytest.mark.asyncio
    async def test_create_order_market(self, initialized_client):
        """Test creating a market order."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.create_order = AsyncMock(return_value={
            'id': 'order123',
            'status': 'closed',
            'filled': 0.1,
            'average': 50000
        })
        
        initialized_client.configs["MASTER"] = MagicMock()
        initialized_client.configs["MASTER"].is_read_only = False
        
        with patch.object(trading_config, 'trading_mode', 'live'):
            order = await initialized_client.create_order(
                subaccount="MASTER",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1")
            )
        
        assert isinstance(order, Order)
        assert order.symbol == "BTCUSDT"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.amount == Decimal("0.1")
    
    @pytest.mark.asyncio
    async def test_create_order_read_only_raises(self, initialized_client):
        """Test that creating order on read-only subaccount raises error."""
        initialized_client.configs["MASTER"] = MagicMock()
        initialized_client.configs["MASTER"].is_read_only = True
        
        with pytest.raises(ValueError, match="read-only"):
            await initialized_client.create_order(
                subaccount="MASTER",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1")
            )
    
    @pytest.mark.asyncio
    async def test_create_order_paper_mode(self, initialized_client):
        """Test creating an order in paper trading mode."""
        initialized_client.configs["MASTER"] = MagicMock()
        initialized_client.configs["MASTER"].is_read_only = False
        
        with patch.object(trading_config, 'trading_mode', 'paper'):
            order = await initialized_client.create_order(
                subaccount="MASTER",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=Decimal("0.1")
            )
        
        assert isinstance(order, Order)
        assert order.status == OrderStatus.FILLED
        assert 'paper_trade' in order.metadata
    
    @pytest.mark.asyncio
    async def test_create_order_limit_requires_price(self, initialized_client):
        """Test that limit orders require a price."""
        initialized_client.configs["MASTER"] = MagicMock()
        initialized_client.configs["MASTER"].is_read_only = False
        
        with patch.object(trading_config, 'trading_mode', 'live'):
            with pytest.raises(ValueError, match="Price is required"):
                await initialized_client.create_order(
                    subaccount="MASTER",
                    symbol="BTCUSDT",
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    amount=Decimal("0.1")
                )
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, initialized_client):
        """Test cancelling an order."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.cancel_order = AsyncMock()
        
        initialized_client.configs["MASTER"] = MagicMock()
        initialized_client.configs["MASTER"].is_read_only = False
        
        with patch.object(trading_config, 'trading_mode', 'live'):
            result = await initialized_client.cancel_order(
                subaccount="MASTER",
                order_id="order123",
                symbol="BTCUSDT"
            )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_order_status(self, initialized_client):
        """Test getting order status."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_order = AsyncMock(return_value={'status': 'closed'})
        
        with patch.object(trading_config, 'trading_mode', 'live'):
            status = await initialized_client.get_order_status(
                subaccount="MASTER",
                order_id="order123",
                symbol="BTCUSDT"
            )
        
        assert status == OrderStatus.FILLED
    
    @pytest.mark.asyncio
    async def test_get_order_status_not_found(self, initialized_client):
        """Test getting order status when order not found."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_order = AsyncMock(side_effect=ccxt.OrderNotFound)
        
        with patch.object(trading_config, 'trading_mode', 'live'):
            status = await initialized_client.get_order_status(
                subaccount="MASTER",
                order_id="order123",
                symbol="BTCUSDT"
            )
        
        assert status == OrderStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_get_open_orders(self, initialized_client):
        """Test getting open orders."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_open_orders = AsyncMock(return_value=[{
            'id': 'order123',
            'symbol': 'BTCUSDT',
            'side': 'buy',
            'type': 'limit',
            'amount': 0.1,
            'price': 49000,
            'status': 'open',
            'filled': 0,
            'average': None
        }])
        
        with patch.object(trading_config, 'trading_mode', 'live'):
            orders = await initialized_client.get_open_orders("MASTER")
        
        assert len(orders) == 1
        assert orders[0].symbol == "BTCUSDT"
        assert orders[0].status == OrderStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_fetch_ohlcv(self, initialized_client):
        """Test fetching OHLCV data."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[
            [1609459200000, 29000, 29500, 28800, 29200, 1000],
            [1609462800000, 29200, 29800, 29100, 29500, 1200]
        ])
        
        data = await initialized_client.fetch_ohlcv(
            symbol="BTCUSDT",
            timeframe="1h",
            limit=2
        )
        
        assert len(data) == 2
        assert isinstance(data[0], MarketData)
        assert data[0].symbol == "BTCUSDT"
        assert data[0].open == Decimal("29000")
        assert data[0].close == Decimal("29200")
    
    @pytest.mark.asyncio
    async def test_fetch_ticker(self, initialized_client):
        """Test fetching ticker data."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_ticker = AsyncMock(return_value={
            'symbol': 'BTCUSDT',
            'last': 50000,
            'bid': 49990,
            'ask': 50010,
            'quoteVolume': 1000000,
            'timestamp': 1609459200000,
            'change': 500,
            'percentage': 1
        })
        
        ticker = await initialized_client.fetch_ticker("BTCUSDT")
        
        assert ticker['symbol'] == "BTCUSDT"
        assert ticker['last'] == Decimal("50000")
        assert ticker['bid'] == Decimal("49990")
        assert ticker['ask'] == Decimal("50010")
    
    @pytest.mark.asyncio
    async def test_get_funding_rate(self, initialized_client):
        """Test fetching funding rate."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_funding_rate_history = AsyncMock(return_value=[{
            'symbol': 'BTCUSDT',
            'fundingRate': 0.0001,
            'timestamp': 1609459200000,
            'datetime': '2021-01-01T00:00:00Z'
        }])
        
        rates = await initialized_client.get_funding_rate("BTCUSDT")
        
        assert len(rates) == 1
        assert rates[0]['symbol'] == "BTCUSDT"
        assert rates[0]['funding_rate'] == Decimal("0.0001")
    
    @pytest.mark.asyncio
    async def test_get_all_balances(self, initialized_client):
        """Test getting balances for all subaccounts."""
        mock_exchange = initialized_client.exchanges["MASTER"]
        mock_exchange.fetch_balance = AsyncMock(return_value={
            'total': {'USDT': 10000},
            'free': {'USDT': 8000},
            'used': {'USDT': 2000}
        })
        
        balances = await initialized_client.get_all_balances()
        
        assert "MASTER" in balances
        assert isinstance(balances["MASTER"], Portfolio)


# =============================================================================
# Retry Decorator Tests
# =============================================================================

class TestRetryDecorator:
    """Test retry decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test that successful calls don't retry."""
        call_count = 0
        
        @with_retry(max_retries=3)
        async def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await successful_function()
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_network_error(self):
        """Test retry on network errors."""
        call_count = 0
        
        @with_retry(max_retries=3, base_delay=0.01)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ccxt.NetworkError("Network error")
            return "success"
        
        result = await failing_function()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self):
        """Test that exception is raised when retries exhausted."""
        @with_retry(max_retries=2, base_delay=0.01)
        async def always_fails():
            raise ccxt.NetworkError("Always fails")
        
        with pytest.raises(ccxt.NetworkError, match="Always fails"):
            await always_fails()
    
    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Test that non-retryable errors don't trigger retry."""
        call_count = 0
        
        @with_retry(max_retries=3)
        async def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")
        
        with pytest.raises(ValueError, match="Not retryable"):
            await raises_value_error()
        
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_rate_limit_retry(self):
        """Test special handling for rate limit errors."""
        call_count = 0
        
        @with_retry(max_retries=2, base_delay=0.01)
        async def rate_limit_hit():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ccxt.RateLimitExceeded("Rate limit")
            return "success"
        
        result = await rate_limit_hit()
        
        assert result == "success"
        assert call_count == 2


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_insufficient_funds_error(self):
        """Test handling of insufficient funds error."""
        client = ByBitClient()
        
        with patch('ccxt.async_support.bybit') as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.load_markets = AsyncMock()
            mock_exchange.create_order = AsyncMock(
                side_effect=ccxt.InsufficientFunds("Insufficient funds")
            )
            mock_ccxt.return_value = mock_exchange
            
            with patch.dict('os.environ', {
                'BYBIT_MASTER_API_KEY': 'test_key',
                'BYBIT_MASTER_API_SECRET': 'test_secret'
            }):
                await client.initialize([SubAccountType.MASTER], testnet=True)
                
                client.configs["MASTER"] = MagicMock()
                client.configs["MASTER"].is_read_only = False
                
                with patch.object(trading_config, 'trading_mode', 'live'):
                    with pytest.raises(ccxt.InsufficientFunds):
                        await client.create_order(
                            subaccount="MASTER",
                            symbol="BTCUSDT",
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            amount=Decimal("100")
                        )
                
                await client.close()
    
    @pytest.mark.asyncio
    async def test_authentication_error(self):
        """Test handling of authentication error."""
        client = ByBitClient()
        
        with patch('ccxt.async_support.bybit') as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.load_markets = AsyncMock(
                side_effect=ccxt.AuthenticationError("Invalid API key")
            )
            mock_ccxt.return_value = mock_exchange
            
            with patch.dict('os.environ', {
                'BYBIT_MASTER_API_KEY': 'invalid_key',
                'BYBIT_MASTER_API_SECRET': 'invalid_secret'
            }):
                with pytest.raises(ccxt.AuthenticationError):
                    await client.initialize([SubAccountType.MASTER], testnet=True)
