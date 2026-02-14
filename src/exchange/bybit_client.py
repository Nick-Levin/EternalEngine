"""ByBit exchange client with unified interface."""
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import ccxt.async_support as ccxt
import structlog

from src.core.models import (
    Order, OrderSide, OrderType, OrderStatus, 
    MarketData, Position, Portfolio
)
from src.core.config import bybit_config, trading_config

logger = structlog.get_logger(__name__)


class ByBitClient:
    """ByBit exchange client wrapper."""
    
    def __init__(self):
        self.exchange: Optional[ccxt.bybit] = None
        self._ws_connected = False
        self._price_callbacks: List[Callable[[str, Decimal], Any]] = []
        self._order_callbacks: List[Callable[[Order], Any]] = []
        
    async def initialize(self):
        """Initialize the exchange connection."""
        config = {
            'apiKey': bybit_config.api_key,
            'secret': bybit_config.api_secret,
            'sandbox': bybit_config.testnet,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',  # spot, linear, inverse
            }
        }
        
        self.exchange = ccxt.bybit(config)
        
        # Load markets
        await self.exchange.load_markets()
        
        logger.info(
            "bybit_client.initialized",
            testnet=bybit_config.testnet,
            trading_mode=trading_config.trading_mode
        )
    
    async def close(self):
        """Close the exchange connection."""
        if self.exchange:
            await self.exchange.close()
            logger.info("bybit_client.closed")
    
    async def get_balance(self) -> Portfolio:
        """Get account balance."""
        try:
            balance = await self.exchange.fetch_balance()
            
            total = Decimal(str(balance.get('total', {}).get('USDT', 0)))
            free = Decimal(str(balance.get('free', {}).get('USDT', 0)))
            
            return Portfolio(
                total_balance=total,
                available_balance=free
            )
        except Exception as e:
            logger.error("bybit_client.balance_error", error=str(e))
            raise
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker data."""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': Decimal(str(ticker['last'])),
                'bid': Decimal(str(ticker['bid'])),
                'ask': Decimal(str(ticker['ask'])),
                'volume': Decimal(str(ticker['quoteVolume'])),
                'timestamp': ticker['timestamp']
            }
        except Exception as e:
            logger.error("bybit_client.ticker_error", symbol=symbol, error=str(e))
            raise
    
    async def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = '1h', 
        limit: int = 100
    ) -> List[MarketData]:
        """Fetch OHLCV data."""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
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
    
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: Decimal,
        price: Optional[Decimal] = None,
        params: Optional[Dict] = None
    ) -> Order:
        """Create a new order."""
        try:
            # Convert internal types to ccxt format
            ccxt_side = side.value
            ccxt_type = order_type.value
            
            # Prepare parameters
            order_params = params or {}
            
            if trading_config.trading_mode == "paper":
                logger.warning(
                    "bybit_client.paper_trade",
                    symbol=symbol,
                    side=side.value,
                    amount=str(amount),
                    price=str(price) if price else None
                )
                # Return simulated order
                return Order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    amount=amount,
                    price=price,
                    status=OrderStatus.FILLED,
                    filled_amount=amount,
                    average_price=price or Decimal("0")
                )
            
            # Live trading
            result = await self.exchange.create_order(
                symbol=symbol,
                type=ccxt_type,
                side=ccxt_side,
                amount=float(amount),
                price=float(price) if price else None,
                params=order_params
            )
            
            order = Order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=amount,
                price=price,
                exchange_order_id=result.get('id'),
                status=self._map_order_status(result.get('status')),
                filled_amount=Decimal(str(result.get('filled', 0))),
                average_price=Decimal(str(result.get('average', 0))) if result.get('average') else None,
                metadata={'raw_response': result}
            )
            
            logger.info(
                "bybit_client.order_created",
                order_id=order.id,
                exchange_order_id=order.exchange_order_id,
                symbol=symbol,
                side=side.value,
                status=order.status.value
            )
            
            return order
            
        except Exception as e:
            logger.error(
                "bybit_client.order_error",
                symbol=symbol,
                side=side.value,
                error=str(e)
            )
            raise
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order."""
        try:
            if trading_config.trading_mode == "paper":
                logger.info("bybit_client.paper_cancel", order_id=order_id)
                return True
            
            await self.exchange.cancel_order(order_id, symbol)
            logger.info("bybit_client.order_cancelled", order_id=order_id)
            return True
        except Exception as e:
            logger.error("bybit_client.cancel_error", order_id=order_id, error=str(e))
            return False
    
    async def get_order_status(self, order_id: str, symbol: str) -> OrderStatus:
        """Get current status of an order."""
        try:
            order_info = await self.exchange.fetch_order(order_id, symbol)
            return self._map_order_status(order_info.get('status'))
        except Exception as e:
            logger.error("bybit_client.status_error", order_id=order_id, error=str(e))
            return OrderStatus.PENDING
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all open orders."""
        try:
            orders = await self.exchange.fetch_open_orders(symbol)
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
                    average_price=Decimal(str(o['average'])) if o['average'] else None
                )
                for o in orders
            ]
        except Exception as e:
            logger.error("bybit_client.open_orders_error", error=str(e))
            return []
    
    def _map_order_status(self, status: Optional[str]) -> OrderStatus:
        """Map exchange status to internal status."""
        status_map = {
            'open': OrderStatus.OPEN,
            'closed': OrderStatus.FILLED,
            'canceled': OrderStatus.CANCELLED,
            'cancelled': OrderStatus.CANCELLED,
            'pending': OrderStatus.PENDING,
            'rejected': OrderStatus.REJECTED,
            'expired': OrderStatus.EXPIRED,
        }
        return status_map.get(status, OrderStatus.PENDING)
