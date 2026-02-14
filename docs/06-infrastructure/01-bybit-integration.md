# Bybit Exchange Integration - Technical Reference

> **Version:** API V5 | **Last Updated:** 2026-02-13  
> **Document Type:** Technical Integration Guide for Python Trading Systems

---

## Table of Contents

1. [Overview](#overview)
2. [Bybit API V5 Specifications](#1-bybit-api-v5-specifications)
3. [Unified Trading Account (UTA)](#2-unified-trading-account-uta)
4. [Order Types and Execution](#3-order-types-and-execution)
5. [Perpetual Futures Mechanics](#4-perpetual-futures-mechanics)
6. [Subaccount Architecture](#5-subaccount-architecture)
7. [Error Handling](#6-error-handling)
8. [Appendix: Complete Integration Example](#appendix-complete-integration-example)

---

## Overview

Bybit API V5 provides a unified interface for spot, linear perpetual, inverse perpetual, and options trading. This document provides comprehensive technical specifications for integrating Bybit into algorithmic trading systems.

### API Base URLs

| Environment | REST API | WebSocket Public | WebSocket Private |
|-------------|----------|------------------|-------------------|
| **Mainnet** | `https://api.bybit.com` | `wss://stream.bybit.com/v5/public` | `wss://stream.bybit.com/v5/private` |
| **Testnet** | `https://api-testnet.bybit.com` | `wss://stream-testnet.bybit.com/v5/public` | `wss://stream-testnet.bybit.com/v5/private` |

### Market Categories

```python
from enum import Enum

class MarketCategory(str, Enum):
    """Bybit market categories."""
    SPOT = "spot"
    LINEAR = "linear"      # USDT-M perpetual futures
    INVERSE = "inverse"    # Coin-M perpetual futures
    OPTION = "option"
```

---

## 1. Bybit API V5 Specifications

### 1.1 REST API Endpoints

#### Market Data Endpoints

```python
from dataclasses import dataclass
from typing import Optional, List, Dict
from decimal import Decimal
import aiohttp
import asyncio

@dataclass
class MarketEndpoints:
    """Market data endpoints mapping."""
    
    # Server time
    SERVER_TIME = "/v5/market/time"
    
    # Kline/OHLCV data
    KLINE = "/v5/market/kline"
    MARK_PRICE_KLINE = "/v5/market/mark-price-kline"
    INDEX_PRICE_KLINE = "/v5/market/index-price-kline"
    PREMIUM_INDEX_KLINE = "/v5/market/premium-index-kline"
    
    # Orderbook
    ORDERBOOK = "/v5/market/orderbook"
    
    # Tickers
    TICKERS = "/v5/market/tickers"
    
    # Funding rate
    FUNDING_RATE = "/v5/market/funding/history"
    
    # Recent trades
    RECENT_TRADES = "/v5/market/recent-trade"


class BybitMarketClient:
    """Market data client implementation."""
    
    def __init__(self, api_key: Optional[str] = None, testnet: bool = False):
        self.api_key = api_key
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def get_klines(
        self,
        category: str,
        symbol: str,
        interval: str,  # 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
        limit: int = 200,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch Kline/candlestick data.
        
        Args:
            category: Market category (spot, linear, inverse)
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Kline interval
            limit: Number of candles (max 1000)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
        """
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1000)
        }
        if start_time:
            params["start"] = start_time
        if end_time:
            params["end"] = end_time
        
        url = f"{self.base_url}{MarketEndpoints.KLINE}"
        
        async with self.session.get(url, params=params) as resp:
            data = await resp.json()
            
            if data["retCode"] != 0:
                raise BybitAPIError(data["retCode"], data["retMsg"])
            
            # Response format: [timestamp, open, high, low, close, volume, turnover]
            candles = []
            for item in data["result"]["list"]:
                candles.append({
                    "timestamp": int(item[0]),
                    "open": Decimal(item[1]),
                    "high": Decimal(item[2]),
                    "low": Decimal(item[3]),
                    "close": Decimal(item[4]),
                    "volume": Decimal(item[5]),
                    "turnover": Decimal(item[6])
                })
            return candles
    
    async def get_orderbook(
        self,
        category: str,
        symbol: str,
        limit: int = 25  # 1, 25, 50, 100, 200, 500
    ) -> Dict:
        """Fetch orderbook data."""
        params = {
            "category": category,
            "symbol": symbol,
            "limit": limit
        }
        
        url = f"{self.base_url}{MarketEndpoints.ORDERBOOK}"
        
        async with self.session.get(url, params=params) as resp:
            data = await resp.json()
            
            if data["retCode"] != 0:
                raise BybitAPIError(data["retCode"], data["retMsg"])
            
            result = data["result"]
            return {
                "symbol": result["s"],
                "bids": [[Decimal(p), Decimal(q)] for p, q in result["b"]],
                "asks": [[Decimal(p), Decimal(q)] for p, q in result["a"]],
                "timestamp": result["ts"],
                "update_id": result.get("u", 0)
            }
```

#### Trading Endpoints

```python
@dataclass
class TradingEndpoints:
    """Trading operation endpoints."""
    
    # Order management
    PLACE_ORDER = "/v5/order/create"
    AMEND_ORDER = "/v5/order/amend"
    CANCEL_ORDER = "/v5/order/cancel"
    CANCEL_ALL = "/v5/order/cancel-all"
    GET_ORDERS = "/v5/order/realtime"
    GET_ORDER_HISTORY = "/v5/order/history"
    
    # Batch operations
    BATCH_PLACE_ORDER = "/v5/order/create-batch"
    BATCH_AMEND_ORDER = "/v5/order/amend-batch"
    BATCH_CANCEL_ORDER = "/v5/order/cancel-batch"
    
    # Position management
    GET_POSITIONS = "/v5/position/list"
    SET_LEVERAGE = "/v5/position/set-leverage"
    SWITCH_MARGIN_MODE = "/v5/position/switch-isolated"
    SWITCH_POSITION_MODE = "/v5/position/switch-mode"
    SET_TRADING_STOP = "/v5/position/trading-stop"
    SET_AUTO_ADD_MARGIN = "/v5/position/set-auto-add-margin"
    
    # Account
    GET_WALLET_BALANCE = "/v5/account/wallet-balance"
    GET_ACCOUNT_INFO = "/v5/account/info"
    GET_TRANSACTION_LOG = "/v5/account/transaction-log"
    
    # Funding
    GET_COLLATERAL_INFO = "/v5/account/collateral-info"
    GET_COINS_BALANCE = "/v5/asset/transfer/query-account-coins-balance"
```

### 1.2 WebSocket Streams

#### Public WebSocket Streams

```python
import websockets
import json
from typing import Callable, Optional

class BybitPublicWebSocket:
    """
    Bybit Public WebSocket client.
    
    Supports:
    - Orderbook (Level 1, 25, 50, 100, 200, 500)
    - Trade streams
    - Ticker/24hr statistics
    - Kline/Candlestick streams
    - Liquidation streams
    - LT (Leveraged Token) streams
    """
    
    def __init__(self, category: str = "linear", testnet: bool = False):
        self.category = category
        self.testnet = testnet
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.subscriptions = set()
        
        base = "stream-testnet.bybit.com" if testnet else "stream.bybit.com"
        self.ws_url = f"wss://{base}/v5/public/{category}"
    
    async def connect(self):
        """Establish WebSocket connection."""
        self.ws = await websockets.connect(self.ws_url)
        self.running = True
        
        # Start ping/pong keepalive
        asyncio.create_task(self._keepalive())
        
        # Start message handler
        asyncio.create_task(self._message_handler())
    
    async def subscribe_orderbook(
        self, 
        symbols: List[str], 
        depth: int = 25,
        callback: Optional[Callable[[Dict], None]] = None
    ):
        """
        Subscribe to orderbook updates.
        
        Args:
            symbols: List of trading pairs
            depth: Orderbook depth (1, 25, 50, 100, 200, 500)
            callback: Function to handle updates
        """
        args = [f"orderbook.{depth}.{s}" for s in symbols]
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": arg} for arg in args]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        
        for symbol in symbols:
            self.subscriptions.add(f"orderbook.{depth}.{symbol}")
        
        if callback:
            self._orderbook_callback = callback
    
    async def subscribe_tickers(
        self,
        symbols: List[str],
        callback: Optional[Callable[[Dict], None]] = None
    ):
        """
        Subscribe to ticker updates.
        
        Provides: last price, index price, mark price, funding rate, 
        24h volume, 24h turnover, price change percent
        """
        args = [{"channel": "tickers", "symbol": s} for s in symbols]
        
        subscribe_msg = {
            "op": "subscribe",
            "args": args
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        
        if callback:
            self._ticker_callback = callback
    
    async def subscribe_trades(
        self,
        symbols: List[str],
        callback: Optional[Callable[[Dict], None]] = None
    ):
        """Subscribe to real-time trade streams."""
        args = [{"channel": "publicTrade", "symbol": s} for s in symbols]
        
        subscribe_msg = {
            "op": "subscribe",
            "args": args
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        
        if callback:
            self._trade_callback = callback
    
    async def subscribe_klines(
        self,
        symbols: List[str],
        interval: str,  # 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
        callback: Optional[Callable[[Dict], None]] = None
    ):
        """Subscribe to kline/candlestick streams."""
        args = [{"channel": f"kline.{interval}", "symbol": s} for s in symbols]
        
        subscribe_msg = {
            "op": "subscribe",
            "args": args
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        
        if callback:
            self._kline_callback = callback
    
    async def _keepalive(self):
        """Send periodic ping messages."""
        while self.running:
            try:
                if self.ws and self.ws.open:
                    await self.ws.send(json.dumps({"op": "ping"}))
                await asyncio.sleep(20)  # Ping every 20 seconds
            except Exception as e:
                print(f"Keepalive error: {e}")
                break
    
    async def _message_handler(self):
        """Handle incoming WebSocket messages."""
        while self.running:
            try:
                if not self.ws:
                    await asyncio.sleep(0.1)
                    continue
                
                msg = await self.ws.recv()
                data = json.loads(msg)
                
                # Handle pong response
                if data.get("op") == "pong":
                    continue
                
                # Handle subscription success
                if data.get("success") is not None:
                    if data.get("success"):
                        print(f"Subscribed: {data.get('ret_msg')}")
                    else:
                        print(f"Subscription failed: {data.get('ret_msg')}")
                    continue
                
                # Handle data updates
                topic = data.get("topic", "")
                
                if "orderbook" in topic:
                    if hasattr(self, '_orderbook_callback'):
                        self._orderbook_callback(data)
                
                elif "tickers" in topic:
                    if hasattr(self, '_ticker_callback'):
                        self._ticker_callback(data)
                
                elif "publicTrade" in topic:
                    if hasattr(self, '_trade_callback'):
                        self._trade_callback(data)
                
                elif "kline" in topic:
                    if hasattr(self, '_kline_callback'):
                        self._kline_callback(data)
                
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed")
                self.running = False
                break
            except Exception as e:
                print(f"Message handler error: {e}")
    
    async def close(self):
        """Close WebSocket connection."""
        self.running = False
        if self.ws:
            await self.ws.close()
```

#### Private WebSocket Streams

```python
class BybitPrivateWebSocket:
    """
    Bybit Private WebSocket client for account data.
    
    Requires authentication.
    Provides:
    - Order updates
    - Position updates
    - Wallet balance updates
    - Execution reports
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        
        base = "stream-testnet.bybit.com" if testnet else "stream.bybit.com"
        self.ws_url = f"wss://{base}/v5/private"
        
        # Callbacks
        self.order_callback: Optional[Callable] = None
        self.position_callback: Optional[Callable] = None
        self.wallet_callback: Optional[Callable] = None
        self.execution_callback: Optional[Callable] = None
    
    async def connect(self):
        """Connect and authenticate."""
        self.ws = await websockets.connect(self.ws_url)
        
        # Generate authentication signature
        expires = int((asyncio.get_event_loop().time() + 10) * 1000)
        signature = self._generate_signature(expires)
        
        auth_msg = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        
        await self.ws.send(json.dumps(auth_msg))
        
        # Wait for auth response
        response = await self.ws.recv()
        auth_response = json.loads(response)
        
        if not auth_response.get("success"):
            raise AuthenticationError(
                f"Auth failed: {auth_response.get('ret_msg')}"
            )
        
        self.running = True
        
        # Start handlers
        asyncio.create_task(self._keepalive())
        asyncio.create_task(self._message_handler())
    
    def _generate_signature(self, expires: int) -> str:
        """Generate HMAC signature for WebSocket auth."""
        import hmac
        import hashlib
        
        message = f"GET/realtime{expires}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def subscribe_orders(self, callback: Callable[[Dict], None]):
        """Subscribe to order updates."""
        self.order_callback = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "order"}]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def subscribe_positions(self, callback: Callable[[Dict], None]):
        """Subscribe to position updates."""
        self.position_callback = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "position"}]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def subscribe_wallet(self, callback: Callable[[Dict], None]):
        """Subscribe to wallet balance updates."""
        self.wallet_callback = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "wallet"}]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def subscribe_executions(self, callback: Callable[[Dict], None]):
        """Subscribe to execution/fill reports."""
        self.execution_callback = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "execution"}]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def _message_handler(self):
        """Handle incoming private messages."""
        while self.running:
            try:
                msg = await self.ws.recv()
                data = json.loads(msg)
                
                if data.get("op") == "pong":
                    continue
                
                topic = data.get("topic", "")
                
                if topic == "order" and self.order_callback:
                    for item in data.get("data", []):
                        self.order_callback(item)
                
                elif topic == "position" and self.position_callback:
                    for item in data.get("data", []):
                        self.position_callback(item)
                
                elif topic == "wallet" and self.wallet_callback:
                    for item in data.get("data", []):
                        self.wallet_callback(item)
                
                elif topic == "execution" and self.execution_callback:
                    for item in data.get("data", []):
                        self.execution_callback(item)
                
            except Exception as e:
                print(f"Private WS error: {e}")
    
    async def _keepalive(self):
        """Keep connection alive."""
        while self.running:
            try:
                if self.ws and self.ws.open:
                    await self.ws.send(json.dumps({"op": "ping"}))
                await asyncio.sleep(20)
            except Exception:
                break
```

### 1.3 Authentication Methods

#### HMAC Authentication

```python
import hmac
import hashlib
import json
from urllib.parse import urlencode
from typing import Dict, Optional

class BybitHMACAuth:
    """
    HMAC SHA256 authentication for Bybit API.
    
    Used for:
    - API Key + Secret authentication
    - REST API request signing
    - WebSocket authentication
    """
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def sign_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Generate request signature and headers.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            body: Request body for POST/PUT
            
        Returns:
            Dictionary of headers to include in request
        """
        timestamp = str(int(asyncio.get_event_loop().time() * 1000))
        recv_window = "5000"  # 5 seconds recommended
        
        # Build payload for signing
        if method == "GET" and params:
            payload = urlencode(sorted(params.items()))
            payload = f"{timestamp}{self.api_key}{recv_window}{payload}"
        elif body:
            payload = json.dumps(body)
            payload = f"{timestamp}{self.api_key}{recv_window}{payload}"
        else:
            payload = f"{timestamp}{self.api_key}{recv_window}"
        
        # Generate signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "Content-Type": "application/json"
        }


# Example usage
async def example_hmac_auth():
    auth = BybitHMACAuth("YOUR_API_KEY", "YOUR_API_SECRET")
    
    # Sign a GET request
    headers = auth.sign_request(
        method="GET",
        endpoint="/v5/account/wallet-balance",
        params={"accountType": "UNIFIED"}
    )
    
    # Sign a POST request
    order_body = {
        "category": "linear",
        "symbol": "BTCUSDT",
        "side": "Buy",
        "orderType": "Limit",
        "qty": "0.1",
        "price": "25000"
    }
    
    headers = auth.sign_request(
        method="POST",
        endpoint="/v5/order/create",
        body=order_body
    )
```

#### RSA Authentication

```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import base64

class BybitRSAAuth:
    """
    RSA authentication for enhanced security.
    
    RSA is recommended over HMAC for:
    - Higher security requirements
    - API keys shared across team members
    - Compliance requirements
    """
    
    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        
        # Load private key
        with open(private_key_path, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )
    
    def sign_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None
    ) -> Dict[str, str]:
        """Generate RSA signature for request."""
        timestamp = str(int(asyncio.get_event_loop().time() * 1000))
        recv_window = "5000"
        
        # Build payload
        if method == "GET" and params:
            payload = urlencode(sorted(params.items()))
            payload = f"{timestamp}{self.api_key}{recv_window}{payload}"
        elif body:
            payload = json.dumps(body)
            payload = f"{timestamp}{self.api_key}{recv_window}{payload}"
        else:
            payload = f"{timestamp}{self.api_key}{recv_window}"
        
        # RSA sign
        signature = self.private_key.sign(
            payload.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature_b64,
            "Content-Type": "application/json"
        }


# RSA Key Generation Example
def generate_rsa_keypair(output_dir: str = "."):
    """Generate RSA key pair for Bybit API authentication."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Save private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    with open(f"{output_dir}/bybit_private.pem", "wb") as f:
        f.write(private_pem)
    
    # Save public key (to upload to Bybit)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    with open(f"{output_dir}/bybit_public.pem", "wb") as f:
        f.write(public_pem)
    
    print(f"RSA keys generated in {output_dir}/")
    print("Upload bybit_public.pem to Bybit API management page")
```

### 1.4 Rate Limiting

```python
from dataclasses import dataclass
from typing import Dict, Optional
import asyncio
from collections import deque
import time

@dataclass
class RateLimitConfig:
    """Bybit API rate limit configurations."""
    
    # Bybit uses two types of limits:
    # 1. Request-based limits (per endpoint)
    # 2. Weight-based limits (total API weight)
    
    # Public endpoints (IP-based)
    PUBLIC_IP_LIMIT = 600  # requests per minute per IP
    
    # Private endpoints (API key-based)
    PRIVATE_LIMIT_TIER_1 = 120  # requests per second for standard accounts
    PRIVATE_LIMIT_TIER_2 = 120  # requests per second for VIP accounts
    PRIVATE_LIMIT_TIER_3 = 120  # requests per second for Pro accounts
    
    # Specific endpoint limits
    ORDER_CREATION_LIMIT = 10  # per second
    ORDER_AMEND_LIMIT = 10     # per second
    ORDER_CANCEL_LIMIT = 10    # per second
    POSITION_SET_LEVERAGE = 10  # per minute
    
    # Batch order limits
    BATCH_ORDER_LIMIT = 10     # orders per batch request
    BATCH_REQUEST_LIMIT = 10   # batch requests per second


class RateLimiter:
    """
    Token bucket rate limiter for Bybit API.
    
    Implements:
    - Per-endpoint rate limiting
    - Weight-based limiting
    - Automatic retry with exponential backoff
    """
    
    def __init__(self):
        # Track request timestamps per endpoint type
        self.order_timestamps: deque = deque()
        self.general_timestamps: deque = deque()
        
        self.order_limit = 10  # per second
        self.general_limit = 120  # per second
        
        self._lock = asyncio.Lock()
    
    async def acquire(self, endpoint_type: str = "general") -> float:
        """
        Acquire rate limit permission.
        
        Args:
            endpoint_type: Type of endpoint ("order", "general")
            
        Returns:
            Wait time in seconds before request should be made
        """
        async with self._lock:
            now = time.time()
            
            if endpoint_type == "order":
                queue = self.order_timestamps
                limit = self.order_limit
                window = 1.0  # 1 second window
            else:
                queue = self.general_timestamps
                limit = self.general_limit
                window = 1.0
            
            # Remove timestamps outside the window
            while queue and queue[0] < now - window:
                queue.popleft()
            
            # Check if we need to wait
            if len(queue) >= limit:
                wait_time = queue[0] + window - now
                return max(0, wait_time)
            
            queue.append(now)
            return 0
    
    async def execute_with_limit(self, coro, endpoint_type: str = "general"):
        """Execute coroutine with rate limiting."""
        wait = await self.acquire(endpoint_type)
        if wait > 0:
            await asyncio.sleep(wait)
        return await coro


class RateLimitHeaders:
    """Parse rate limit information from API response headers."""
    
    @staticmethod
    def parse(headers: Dict[str, str]) -> Dict[str, int]:
        """
        Extract rate limit information from response headers.
        
        Headers:
        - X-Bapi-Limit-Status: Remaining requests in current window
        - X-Bapi-Limit: Total limit for the endpoint
        - X-Bapi-Limit-Reset-Timestamp: When the limit resets (ms)
        """
        return {
            "limit_status": int(headers.get("X-Bapi-Limit-Status", 0)),
            "limit": int(headers.get("X-Bapi-Limit", 0)),
            "reset_timestamp": int(headers.get("X-Bapi-Limit-Reset-Timestamp", 0))
        }
```

---

## 2. Unified Trading Account (UTA)

### 2.1 Account Structure and Margin Modes

```python
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict, Optional

class AccountType(str, Enum):
    """Bybit account types."""
    CONTRACT = "CONTRACT"      # Classic derivatives account
    SPOT = "SPOT"              # Spot trading account
    UNIFIED = "UNIFIED"        # Unified Trading Account (UTA 1.0)
    UNIFIED_TRADE = "UNIFIED_TRADE"  # UTA 2.0 Pro

class MarginMode(str, Enum):
    """Margin modes for derivatives trading."""
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"

class PositionMode(str, Enum):
    """Position modes."""
    ONE_WAY = 0        # Can only hold positions in one direction
    HEDGE = 3          # Can hold both long and short positions


@dataclass
class UnifiedAccountInfo:
    """
    Unified Trading Account (UTA) structure.
    
    UTA combines:
    - Spot trading
    - USDT perpetual (linear)
    - USDC perpetual (linear)
    - Inverse perpetual
    - Options
    - Margin trading
    
    All share unified margin and collateral.
    """
    account_type: str = "UNIFIED"
    
    # Account status
    margin_mode: MarginMode = MarginMode.CROSS
    position_mode: PositionMode = PositionMode.ONE_WAY
    
    # Margin metrics (in USDT equivalent)
    total_equity: Decimal = Decimal("0")
    available_balance: Decimal = Decimal("0")
    used_margin: Decimal = Decimal("0")
    
    # Risk metrics
    initial_margin_rate: Decimal = Decimal("0")  # IMR
    maintenance_margin_rate: Decimal = Decimal("0")  # MMR
    
    # Position metrics
    total_position_im: Decimal = Decimal("0")  # Total initial margin for positions
    total_position_mm: Decimal = Decimal("0")  # Total maintenance margin for positions
    
    # Borrow metrics (for margin trading)
    total_borrow: Decimal = Decimal("0")
    
    def calculate_margin_ratio(self) -> Decimal:
        """Calculate current margin ratio."""
        if self.used_margin == 0:
            return Decimal("999")
        return self.total_equity / self.used_margin
    
    def is_liquidation_risk(self) -> bool:
        """Check if account is at risk of liquidation."""
        return self.maintenance_margin_rate > Decimal("1")


class AccountManager:
    """Manager for UTA operations."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def get_wallet_balance(self, account_type: str = "UNIFIED") -> UnifiedAccountInfo:
        """
        Get unified account wallet balance.
        
        Returns detailed breakdown of:
        - Total equity
        - Available balance
        - Per-asset balances
        - Margin usage
        """
        endpoint = "/v5/account/wallet-balance"
        params = {"accountType": account_type}
        
        headers = self.auth.sign_request("GET", endpoint, params)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=headers
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                result = data["result"]["list"][0]
                
                return UnifiedAccountInfo(
                    account_type=result["accountType"],
                    total_equity=Decimal(result["totalEquity"]),
                    available_balance=Decimal(result["availableToWithdraw"]),
                    used_margin=Decimal(result.get("totalPositionIM", "0")),
                    initial_margin_rate=Decimal(result.get("initialMarginRate", "0")),
                    maintenance_margin_rate=Decimal(result.get("maintainMarginRate", "0"))
                )
    
    async def switch_margin_mode(
        self,
        category: str,
        symbol: str,
        margin_mode: MarginMode,
        buy_leverage: str,
        sell_leverage: str
    ):
        """
        Switch between ISOLATED and CROSS margin mode.
        
        WARNING: Switching margin mode will:
        - Cancel all active orders for the symbol
        - May cause position to be partially closed if insufficient margin
        """
        endpoint = "/v5/position/switch-isolated"
        
        body = {
            "category": category,
            "symbol": symbol,
            "tradeMode": 1 if margin_mode == MarginMode.ISOLATED else 0,
            "buyLeverage": buy_leverage,
            "sellLeverage": sell_leverage
        }
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
    
    async def switch_position_mode(
        self,
        category: str,
        symbol: Optional[str] = None,
        mode: PositionMode = PositionMode.ONE_WAY
    ):
        """
        Switch between One-way and Hedge position mode.
        
        Args:
            category: "linear" or "inverse"
            symbol: Specific symbol or None for all symbols
            mode: ONE_WAY (0) or HEDGE (3)
        
        WARNING: Cannot switch if there are existing positions or orders.
        """
        endpoint = "/v5/position/switch-mode"
        
        body = {
            "category": category,
            "mode": mode.value
        }
        
        if symbol:
            body["symbol"] = symbol
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
```

### 2.2 Cross-Collateral Mechanics

```python
@dataclass
class CollateralInfo:
    """Information about collateral assets."""
    
    coin: str
    equity: Decimal
    wallet_balance: Decimal
    
    # Margin metrics
    available_balance: Decimal
    
    # Borrow metrics (for margin trading)
    borrow_amount: Decimal
    available_to_borrow: Decimal
    
    # Collateral settings
    collateral_ratio: Decimal  # How much this coin counts as collateral (0-1)
    
    def effective_collateral_value(self) -> Decimal:
        """Calculate effective collateral value considering ratio."""
        return self.wallet_balance * self.collateral_ratio


class CrossCollateralManager:
    """
    Manager for cross-collateral functionality.
    
    In UTA, multiple assets can be used as collateral:
    - USDT (100% collateral ratio)
    - BTC, ETH (typically 95% ratio)
    - Altcoins (variable ratios, often 80-90%)
    
    Collateral ratios are determined by Bybit's risk engine.
    """
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def get_collateral_info(self, currency: Optional[str] = None) -> List[CollateralInfo]:
        """
        Get collateral information for assets.
        
        Shows:
        - Which coins can be used as collateral
        - Collateral ratios for each coin
        - Current margin usage per coin
        """
        endpoint = "/v5/account/collateral-info"
        params = {}
        if currency:
            params["currency"] = currency
        
        headers = self.auth.sign_request("GET", endpoint, params)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=headers
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                collateral_list = []
                for item in data["result"]["list"]:
                    collateral_list.append(CollateralInfo(
                        coin=item["currency"],
                        equity=Decimal(item.get("equity", "0")),
                        wallet_balance=Decimal(item.get("walletBalance", "0")),
                        available_balance=Decimal(item.get("availableBalance", "0")),
                        borrow_amount=Decimal(item.get("borrowAmount", "0")),
                        available_to_borrow=Decimal(item.get("availableToBorrow", "0")),
                        collateral_ratio=Decimal(item.get("collateralRatio", "1"))
                    ))
                
                return collateral_list
    
    def calculate_total_collateral(
        self,
        collateral_list: List[CollateralInfo]
    ) -> Dict[str, Decimal]:
        """
        Calculate total effective collateral across all assets.
        
        Returns:
            Dict with raw total and effective (after collateral ratio) totals
        """
        raw_total = Decimal("0")
        effective_total = Decimal("0")
        
        for coll in collateral_list:
            raw_total += coll.wallet_balance
            effective_total += coll.effective_collateral_value()
        
        return {
            "raw_total": raw_total,
            "effective_total": effective_total,
            "haircut": raw_total - effective_total
        }
```

### 2.3 IMR/MMR Calculations

```python
@dataclass
class MarginRequirements:
    """
    Initial Margin Requirement (IMR) and 
    Maintenance Margin Requirement (MMR) calculations.
    
    Understanding margin:
    - IMR: Minimum margin to OPEN a position
    - MMR: Minimum margin to MAINTAIN a position (liquidation threshold)
    """
    
    # Position size
    position_value: Decimal
    leverage: Decimal
    
    # Margin requirements
    initial_margin_rate: Decimal  # IMR = 1 / leverage
    initial_margin: Decimal       # IM = position_value * IMR
    
    maintenance_margin_rate: Decimal  # MMR typically 0.5% at lowest tier
    maintenance_margin: Decimal       # MM = position_value * MMR
    
    # Available margin
    available_margin: Decimal
    
    # Risk metrics
    margin_ratio: Decimal  # MR = MM / (position_value + available_margin)
    liquidation_price: Optional[Decimal] = None
    
    def is_liquidation_imminent(self) -> bool:
        """Check if position is close to liquidation."""
        # Liquidation occurs when position margin <= maintenance margin
        return self.margin_ratio > Decimal("0.8")
    
    def safe_leverage(self, max_position_value: Decimal) -> Decimal:
        """
        Calculate safe leverage given available margin.
        
        Formula: max_leverage = available_margin / (position_value * IMR)
        """
        if self.position_value == 0 or self.available_margin == 0:
            return Decimal("1")
        
        max_leverage = self.available_margin / (max_position_value * self.initial_margin_rate)
        return min(max_leverage, Decimal("100"))  # Cap at 100x


class MarginCalculator:
    """
    Calculate margin requirements for derivatives positions.
    
    Bybit uses tiered margin system:
    - Higher position value = higher margin requirements
    - Each tier has different max leverage, IMR, and MMR
    """
    
    # Tier structure (simplified - actual tiers vary by symbol)
    LINEAR_TIERS = [
        {"max_position": 200_000, "max_leverage": 100, "mmr": Decimal("0.005")},
        {"max_position": 400_000, "max_leverage": 50, "mmr": Decimal("0.01")},
        {"max_position": 600_000, "max_leverage": 33, "mmr": Decimal("0.015")},
        {"max_position": 800_000, "max_leverage": 25, "mmr": Decimal("0.02")},
        {"max_position": 1_000_000, "max_leverage": 20, "mmr": Decimal("0.025")},
    ]
    
    @classmethod
    def calculate_margin_requirements(
        cls,
        position_value: Decimal,
        leverage: Decimal,
        available_margin: Decimal,
        entry_price: Decimal,
        position_side: str  # "long" or "short"
    ) -> MarginRequirements:
        """
        Calculate margin requirements for a position.
        
        Args:
            position_value: Value of position in quote currency
            leverage: Desired leverage (1-100)
            available_margin: Available margin for this position
            entry_price: Position entry price
            position_side: "long" or "short"
        """
        # Determine tier
        tier = cls._get_tier(position_value)
        
        # Calculate IMR and MMR
        imr = Decimal("1") / leverage
        mmr = tier["mmr"]
        
        im = position_value * imr
        mm = position_value * mmr
        
        # Calculate margin ratio
        # For long: MR = MM / (entry_price * position_size + available)
        # For short: similar calculation
        denominator = position_value + available_margin
        margin_ratio = mm / denominator if denominator > 0 else Decimal("0")
        
        # Calculate liquidation price
        liq_price = cls._calculate_liquidation_price(
            entry_price, position_side, imr, mmr, leverage
        )
        
        return MarginRequirements(
            position_value=position_value,
            leverage=leverage,
            initial_margin_rate=imr,
            initial_margin=im,
            maintenance_margin_rate=mmr,
            maintenance_margin=mm,
            available_margin=available_margin,
            margin_ratio=margin_ratio,
            liquidation_price=liq_price
        )
    
    @classmethod
    def _get_tier(cls, position_value: Decimal) -> Dict:
        """Get margin tier for position value."""
        for tier in cls.LINEAR_TIERS:
            if position_value <= tier["max_position"]:
                return tier
        return cls.LINEAR_TIERS[-1]
    
    @classmethod
    def _calculate_liquidation_price(
        cls,
        entry_price: Decimal,
        side: str,
        imr: Decimal,
        mmr: Decimal,
        leverage: Decimal
    ) -> Decimal:
        """Calculate estimated liquidation price."""
        # Simplified calculation - actual Bybit formula is more complex
        if side == "long":
            return entry_price * (Decimal("1") - imr + mmr)
        else:
            return entry_price * (Decimal("1") + imr - mmr)
```

### 2.4 Auto-Borrowing Risks

```python
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
import asyncio

@dataclass
class AutoBorrowConfig:
    """
    Auto-borrowing configuration for margin trading.
    
    WARNING: Auto-borrowing can lead to significant losses if not monitored.
    """
    enabled: bool = False
    
    # Limits
    max_borrow_usd: Decimal = Decimal("0")
    max_borrow_ratio: Decimal = Decimal("0.5")  # Max 50% of equity
    
    # Auto-repay settings
    auto_repay: bool = True
    repay_threshold: Decimal = Decimal("0.95")  # Repay when collateral ratio drops


class AutoBorrowRiskManager:
    """
    Manager for auto-borrowing risks.
    
    RISKS:
    1. Interest costs compound quickly
    2. Borrowed assets are subject to liquidation
    3. Collateral ratio changes with market volatility
    4. Borrow limits can be reduced during high volatility
    """
    
    # Hourly interest rates (approximate - check Bybit for current rates)
    BORROW_RATES = {
        "USDT": Decimal("0.0001"),  # 0.01% per hour = ~87.6% APY
        "BTC": Decimal("0.00005"),
        "ETH": Decimal("0.00005"),
    }
    
    def __init__(self):
        self.config = AutoBorrowConfig()
        self._monitoring = False
    
    def calculate_borrow_cost(
        self,
        asset: str,
        amount: Decimal,
        duration_hours: int
    ) -> Decimal:
        """
        Calculate cost of borrowing.
        
        Args:
            asset: Asset to borrow
            amount: Amount to borrow
            duration_hours: Expected borrow duration
        """
        rate = self.BORROW_RATES.get(asset, Decimal("0.0001"))
        return amount * rate * duration_hours
    
    def assess_borrow_risk(
        self,
        account: UnifiedAccountInfo,
        borrow_asset: str,
        borrow_amount: Decimal
    ) -> Dict:
        """
        Assess risks of taking a borrow position.
        
        Returns risk assessment including:
        - Collateral impact
        - Liquidation risk increase
        - Cost projection
        """
        # Current state
        current_collateral_ratio = account.total_equity / account.used_margin if account.used_margin > 0 else Decimal("999")
        
        # Post-borrow state (borrowed asset adds to position value)
        new_position_value = account.total_position_im + borrow_amount
        new_used_margin = account.used_margin + (borrow_amount * account.initial_margin_rate)
        new_collateral_ratio = account.total_equity / new_used_margin if new_used_margin > 0 else Decimal("999")
        
        # Risk assessment
        risk_level = "LOW"
        if new_collateral_ratio < Decimal("1.2"):
            risk_level = "CRITICAL"
        elif new_collateral_ratio < Decimal("1.5"):
            risk_level = "HIGH"
        elif new_collateral_ratio < Decimal("2.0"):
            risk_level = "MEDIUM"
        
        # Calculate 24h cost
        daily_cost = self.calculate_borrow_cost(borrow_asset, borrow_amount, 24)
        
        return {
            "current_collateral_ratio": current_collateral_ratio,
            "projected_collateral_ratio": new_collateral_ratio,
            "risk_level": risk_level,
            "daily_borrow_cost": daily_cost,
            "recommended": risk_level in ["LOW", "MEDIUM"]
        }
    
    async def start_monitoring(
        self,
        account_manager: AccountManager,
        check_interval: int = 60
    ):
        """
        Start monitoring borrow positions for risks.
        
        Alerts on:
        - Collateral ratio dropping
        - Borrow costs accumulating
        - Approaching liquidation
        """
        self._monitoring = True
        
        while self._monitoring:
            try:
                account = await account_manager.get_wallet_balance()
                
                # Check borrow status
                if account.total_borrow > 0:
                    collateral_ratio = account.total_equity / account.used_margin
                    
                    if collateral_ratio < Decimal("1.1"):
                        print(f"CRITICAL: Collateral ratio at {collateral_ratio:.2f}")
                        print("Immediate action required - consider reducing positions")
                    elif collateral_ratio < Decimal("1.3"):
                        print(f"WARNING: Collateral ratio at {collateral_ratio:.2f}")
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                await asyncio.sleep(check_interval)
    
    def stop_monitoring(self):
        """Stop risk monitoring."""
        self._monitoring = False
```


---

## 3. Order Types and Execution

### 3.1 Order Types

```python
from enum import Enum
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, List
from datetime import datetime

class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "Buy"
    SELL = "Sell"

class OrderTypeStr(str, Enum):
    """Order type enumeration."""
    MARKET = "Market"
    LIMIT = "Limit"

class TimeInForce(str, Enum):
    """
    Time in Force - Order execution behavior.
    
    - GTC: Good Till Canceled (default for limit orders)
    - IOC: Immediate Or Cancel
    - FOK: Fill Or Kill
    - PostOnly: Ensure maker rebate
    """
    GTC = "GTC"           # Good Till Canceled
    IOC = "IOC"           # Immediate Or Cancel
    FOK = "FOK"           # Fill Or Kill
    POST_ONLY = "PostOnly"  # Post Only (guarantees maker fee)

class TriggerDirection(int, Enum):
    """Trigger direction for conditional orders."""
    RISES_TO = 1   # Price rises to trigger price
    FALLS_TO = 2   # Price falls to trigger price

class OrderStatus(str, Enum):
    """Order status enumeration."""
    CREATED = "Created"
    NEW = "New"
    REJECTED = "Rejected"
    PARTIALLY_FILLED = "PartiallyFilled"
    PARTIALLY_FILLED_CANCELED = "PartiallyFilledCanceled"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    UNTRIGGERED = "Untriggered"
    TRIGGERED = "Triggered"
    DEACTIVATED = "Deactivated"


@dataclass
class OrderRequest:
    """Base order request structure."""
    
    category: str                    # spot, linear, inverse, option
    symbol: str                      # Trading pair (e.g., "BTCUSDT")
    side: OrderSide                  # Buy or Sell
    order_type: OrderTypeStr         # Market or Limit
    qty: Decimal                     # Order quantity
    
    # Limit order parameters
    price: Optional[Decimal] = None  # Required for limit orders
    time_in_force: TimeInForce = TimeInForce.GTC
    
    # Order linking
    order_link_id: Optional[str] = None  # Client-generated order ID (UUID)
    
    # Reduce-only flag (for closing positions)
    reduce_only: bool = False
    
    # Close on trigger (for conditional orders)
    close_on_trigger: bool = False
    
    # Market order protection
    market_unit: Optional[str] = None  # "baseCoin" or "quoteCoin"
    
    def to_api_params(self) -> Dict:
        """Convert to API-compatible parameters."""
        params = {
            "category": self.category,
            "symbol": self.symbol,
            "side": self.side.value,
            "orderType": self.order_type.value,
            "qty": str(self.qty),
        }
        
        if self.price:
            params["price"] = str(self.price)
        
        if self.order_type == OrderTypeStr.LIMIT:
            params["timeInForce"] = self.time_in_force.value
        
        if self.order_link_id:
            params["orderLinkId"] = self.order_link_id
        
        if self.reduce_only:
            params["reduceOnly"] = True
        
        if self.close_on_trigger:
            params["closeOnTrigger"] = True
        
        if self.market_unit:
            params["marketUnit"] = self.market_unit
        
        return params


@dataclass
class ConditionalOrderRequest(OrderRequest):
    """
    Conditional order (stop order) request.
    
    Conditional orders are triggered when price reaches a certain level.
    Common uses:
    - Stop-loss orders
    - Take-profit orders
    - Breakout entries
    """
    
    trigger_price: Decimal
    trigger_direction: TriggerDirection
    
    # Optional: Trigger by different price types
    trigger_by: str = "LastPrice"  # LastPrice, IndexPrice, MarkPrice
    
    def to_api_params(self) -> Dict:
        """Convert conditional order to API parameters."""
        params = super().to_api_params()
        params["triggerPrice"] = str(self.trigger_price)
        params["triggerDirection"] = self.trigger_direction.value
        params["triggerBy"] = self.trigger_by
        return params
```

### 3.2 Order Execution

```python
class OrderManager:
    """Manager for order operations."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def place_order(self, order: OrderRequest) -> Dict:
        """
        Place a single order.
        
        Returns order details including:
        - orderId: Exchange order ID
        - orderLinkId: Client order ID
        """
        endpoint = "/v5/order/create"
        body = order.to_api_params()
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
    
    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        category: str = "linear",
        reduce_only: bool = False
    ) -> Dict:
        """
        Place a market order.
        
        IMPORTANT: Market orders execute immediately at best available price.
        Price slippage can be significant during volatile periods.
        """
        order = OrderRequest(
            category=category,
            symbol=symbol,
            side=side,
            order_type=OrderTypeStr.MARKET,
            qty=qty,
            reduce_only=reduce_only
        )
        return await self.place_order(order)
    
    async def place_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        price: Decimal,
        category: str = "linear",
        time_in_force: TimeInForce = TimeInForce.GTC,
        post_only: bool = False,
        reduce_only: bool = False
    ) -> Dict:
        """
        Place a limit order.
        
        Args:
            post_only: If True, order will be rejected if it would take liquidity
        """
        tif = TimeInForce.POST_ONLY if post_only else time_in_force
        
        order = OrderRequest(
            category=category,
            symbol=symbol,
            side=side,
            order_type=OrderTypeStr.LIMIT,
            qty=qty,
            price=price,
            time_in_force=tif,
            reduce_only=reduce_only
        )
        return await self.place_order(order)
    
    async def place_stop_loss_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        trigger_price: Decimal,
        category: str = "linear",
        trigger_by: str = "MarkPrice"
    ) -> Dict:
        """
        Place a stop-loss conditional order.
        
        For long positions: trigger_direction = FALLS_TO (2)
        For short positions: trigger_direction = RISES_TO (1)
        """
        trigger_direction = (
            TriggerDirection.FALLS_TO if side == OrderSide.SELL 
            else TriggerDirection.RISES_TO
        )
        
        order = ConditionalOrderRequest(
            category=category,
            symbol=symbol,
            side=side,
            order_type=OrderTypeStr.MARKET,  # Execute as market when triggered
            qty=qty,
            trigger_price=trigger_price,
            trigger_direction=trigger_direction,
            trigger_by=trigger_by,
            close_on_trigger=True  # Important: closes position
        )
        return await self.place_order(order)
    
    async def amend_order(
        self,
        symbol: str,
        category: str = "linear",
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None,
        new_price: Optional[Decimal] = None,
        new_qty: Optional[Decimal] = None,
        new_trigger_price: Optional[Decimal] = None
    ) -> Dict:
        """
        Amend an existing order.
        
        Can modify:
        - Price (limit orders)
        - Quantity
        - Trigger price (conditional orders)
        
        Cannot modify:
        - Symbol
        - Side
        - Order type
        """
        endpoint = "/v5/order/amend"
        
        body = {
            "category": category,
            "symbol": symbol,
        }
        
        if order_id:
            body["orderId"] = order_id
        elif order_link_id:
            body["orderLinkId"] = order_link_id
        else:
            raise ValueError("Either order_id or order_link_id required")
        
        if new_price:
            body["price"] = str(new_price)
        if new_qty:
            body["qty"] = str(new_qty)
        if new_trigger_price:
            body["triggerPrice"] = str(new_trigger_price)
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
    
    async def cancel_order(
        self,
        symbol: str,
        category: str = "linear",
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None
    ) -> Dict:
        """Cancel an active order."""
        endpoint = "/v5/order/cancel"
        
        body = {
            "category": category,
            "symbol": symbol,
        }
        
        if order_id:
            body["orderId"] = order_id
        elif order_link_id:
            body["orderLinkId"] = order_link_id
        else:
            raise ValueError("Either order_id or order_link_id required")
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
    
    async def cancel_all_orders(
        self,
        symbol: Optional[str] = None,
        category: str = "linear"
    ) -> Dict:
        """
        Cancel all active orders.
        
        If symbol is None, cancels all orders in the category.
        """
        endpoint = "/v5/order/cancel-all"
        
        body = {"category": category}
        
        if symbol:
            body["symbol"] = symbol
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
```

### 3.3 Stop Loss / Take Profit Attachments

```python
@dataclass
class TradingStopConfig:
    """
    Trading stop configuration for attaching SL/TP to positions.
    
    Advantages over separate conditional orders:
    - Tied to position lifecycle
    - Automatically adjusted on position changes
    - Better for position-based strategies
    """
    
    # Stop Loss
    stop_loss: Optional[Decimal] = None
    sl_trigger_by: str = "LastPrice"  # LastPrice, IndexPrice, MarkPrice
    
    # Take Profit
    take_profit: Optional[Decimal] = None
    tp_trigger_by: str = "LastPrice"
    
    # Trailing Stop
    trailing_stop: Optional[Decimal] = None  # Trailing distance
    
    # Position size to close
    tp_size: Optional[Decimal] = None  # Default: close entire position
    sl_size: Optional[Decimal] = None
    
    def to_api_params(self) -> Dict:
        """Convert to API parameters."""
        params = {}
        
        if self.stop_loss:
            params["stopLoss"] = str(self.stop_loss)
            params["slTriggerBy"] = self.sl_trigger_by
        
        if self.take_profit:
            params["takeProfit"] = str(self.take_profit)
            params["tpTriggerBy"] = self.tp_trigger_by
        
        if self.trailing_stop:
            params["trailingStop"] = str(self.trailing_stop)
        
        if self.tp_size:
            params["tpSize"] = str(self.tp_size)
        
        if self.sl_size:
            params["slSize"] = str(self.sl_size)
        
        return params


class TradingStopManager:
    """Manager for position-based trading stops."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def set_trading_stop(
        self,
        symbol: str,
        category: str = "linear",
        config: TradingStopConfig = None,
        position_idx: int = 0  # 0=OneWay, 1=BuySide(Hedge), 2=SellSide(Hedge)
    ) -> Dict:
        """
        Set trading stop for an existing position.
        
        This attaches SL/TP directly to the position rather than creating
        separate conditional orders.
        """
        endpoint = "/v5/position/trading-stop"
        
        body = {
            "category": category,
            "symbol": symbol,
            "positionIdx": position_idx
        }
        
        if config:
            body.update(config.to_api_params())
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
    
    def calculate_sl_tp_prices(
        self,
        entry_price: Decimal,
        side: str,  # "long" or "short"
        sl_pct: Optional[Decimal] = None,
        tp_pct: Optional[Decimal] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate stop loss and take profit prices based on percentages.
        
        Args:
            entry_price: Position entry price
            side: "long" or "short"
            sl_pct: Stop loss percentage (e.g., 0.02 for 2%)
            tp_pct: Take profit percentage (e.g., 0.06 for 6%)
        """
        prices = {}
        
        if side == "long":
            if sl_pct:
                prices["stop_loss"] = entry_price * (Decimal("1") - sl_pct)
            if tp_pct:
                prices["take_profit"] = entry_price * (Decimal("1") + tp_pct)
        else:  # short
            if sl_pct:
                prices["stop_loss"] = entry_price * (Decimal("1") + sl_pct)
            if tp_pct:
                prices["take_profit"] = entry_price * (Decimal("1") - tp_pct)
        
        return prices
```

### 3.4 Batch Orders

```python
from typing import List

@dataclass
class BatchOrderResult:
    """Result of a batch order operation."""
    successful: List[Dict] = field(default_factory=list)
    failed: List[Dict] = field(default_factory=list)
    
    @property
    def success_count(self) -> int:
        return len(self.successful)
    
    @property
    def failure_count(self) -> int:
        return len(self.failed)


class BatchOrderManager:
    """
    Manager for batch order operations.
    
    LIMITS:
    - Max 10 orders per batch request
    - Max 10 batch requests per second
    - Mixed symbols allowed within same category
    """
    
    MAX_BATCH_SIZE = 10
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def place_batch_orders(
        self,
        orders: List[OrderRequest],
        category: str = "linear"
    ) -> BatchOrderResult:
        """
        Place multiple orders in a single request.
        
        Benefits:
        - Reduced API call overhead
        - Atomic processing
        - Better rate limit efficiency
        
        Note: If one order fails validation, the entire batch may be rejected.
        """
        if len(orders) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Maximum {self.MAX_BATCH_SIZE} orders per batch")
        
        endpoint = "/v5/order/create-batch"
        
        body = {
            "category": category,
            "request": [order.to_api_params() for order in orders]
        }
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                result = BatchOrderResult()
                
                # Parse results
                if "result" in data and "list" in data["result"]:
                    for item in data["result"]["list"]:
                        if item.get("code") == 0:
                            result.successful.append(item)
                        else:
                            result.failed.append(item)
                
                return result
    
    async def amend_batch_orders(
        self,
        amendments: List[Dict],
        category: str = "linear"
    ) -> BatchOrderResult:
        """
        Amend multiple orders in a single request.
        
        Each amendment dict must contain:
        - symbol: Trading pair
        - orderId or orderLinkId: Order identifier
        - price, qty, or triggerPrice: New values
        """
        if len(amendments) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Maximum {self.MAX_BATCH_SIZE} amendments per batch")
        
        endpoint = "/v5/order/amend-batch"
        
        body = {
            "category": category,
            "request": amendments
        }
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                result = BatchOrderResult()
                
                if "result" in data and "list" in data["result"]:
                    for item in data["result"]["list"]:
                        if item.get("code") == 0:
                            result.successful.append(item)
                        else:
                            result.failed.append(item)
                
                return result
    
    async def cancel_batch_orders(
        self,
        cancellations: List[Dict],
        category: str = "linear"
    ) -> BatchOrderResult:
        """
        Cancel multiple orders in a single request.
        
        Each cancellation dict must contain:
        - symbol: Trading pair
        - orderId or orderLinkId: Order identifier
        """
        if len(cancellations) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Maximum {self.MAX_BATCH_SIZE} cancellations per batch")
        
        endpoint = "/v5/order/cancel-batch"
        
        body = {
            "category": category,
            "request": cancellations
        }
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                result = BatchOrderResult()
                
                if "result" in data and "list" in data["result"]:
                    for item in data["result"]["list"]:
                        if item.get("code") == 0:
                            result.successful.append(item)
                        else:
                            result.failed.append(item)
                
                return result
    
    async def place_orders_bulk(
        self,
        orders: List[OrderRequest],
        category: str = "linear"
    ) -> BatchOrderResult:
        """
        Place many orders using multiple batch requests if needed.
        
        Automatically chunks orders into batches of MAX_BATCH_SIZE.
        """
        all_results = BatchOrderResult()
        
        # Chunk orders into batches
        for i in range(0, len(orders), self.MAX_BATCH_SIZE):
            batch = orders[i:i + self.MAX_BATCH_SIZE]
            result = await self.place_batch_orders(batch, category)
            
            all_results.successful.extend(result.successful)
            all_results.failed.extend(result.failed)
            
            # Rate limiting between batches
            if i + self.MAX_BATCH_SIZE < len(orders):
                await asyncio.sleep(0.1)  # 100ms between batches
        
        return all_results
```

---

## 4. Perpetual Futures Mechanics

### 4.1 Funding Rate Calculation

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
from datetime import datetime, timedelta

@dataclass
class FundingRateInfo:
    """
    Funding rate information for perpetual contracts.
    
    Funding payments occur every 8 hours at:
    - 00:00 UTC
    - 08:00 UTC  
    - 16:00 UTC
    """
    symbol: str
    
    # Current funding rate (positive = longs pay shorts)
    funding_rate: Decimal
    
    # Predicted next funding rate (updates 5 min before funding)
    predicted_funding_rate: Decimal
    
    # Funding interval in hours (typically 8)
    funding_interval: int = 8
    
    # Next funding time
    next_funding_time: Optional[datetime] = None
    
    # Historical context
    avg_funding_24h: Optional[Decimal] = None
    avg_funding_7d: Optional[Decimal] = None
    
    def calculate_funding_payment(
        self,
        position_size: Decimal,
        position_value: Decimal
    ) -> Decimal:
        """
        Calculate funding payment for a position.
        
        Positive return = you pay funding
        Negative return = you receive funding
        """
        return position_value * self.funding_rate
    
    def is_premium(self) -> bool:
        """Check if funding rate indicates premium (longs pay)."""
        return self.funding_rate > 0
    
    def is_discount(self) -> bool:
        """Check if funding rate indicates discount (shorts pay)."""
        return self.funding_rate < 0


class FundingRateCalculator:
    """
    Calculator for funding rate mechanics.
    
    Funding Rate Formula (simplified):
    Funding Rate = Premium Index + Interest Rate
    
    Premium Index = (Mark Price - Index Price) / Index Price
    Interest Rate = 0.01% per 8 hours (typically)
    
    Clamp: Funding rate is clamped between -0.75% and 0.75%
    """
    
    INTEREST_RATE = Decimal("0.0001")  # 0.01% per 8 hours
    FUNDING_CLAMP = Decimal("0.0075")  # 0.75% max
    
    @classmethod
    def calculate_funding_rate(
        cls,
        mark_price: Decimal,
        index_price: Decimal,
        premium_1h_avg: Decimal
    ) -> Decimal:
        """
        Calculate estimated funding rate.
        
        Bybit uses 1-hour TWAP of premium index.
        """
        # Current premium
        current_premium = (mark_price - index_price) / index_price
        
        # Funding rate = avg premium + interest rate
        funding_rate = premium_1h_avg + cls.INTEREST_RATE
        
        # Clamp to limits
        funding_rate = max(-cls.FUNDING_CLAMP, min(cls.FUNDING_CLAMP, funding_rate))
        
        return funding_rate
    
    @classmethod
    def estimate_annualized_funding(
        cls,
        funding_rate: Decimal,
        periods_per_day: int = 3  # 3 periods of 8 hours
    ) -> Decimal:
        """Calculate annualized funding rate (APY)."""
        daily_rate = funding_rate * periods_per_day
        annual_rate = daily_rate * 365
        return annual_rate


class FundingRateManager:
    """Manager for funding rate operations."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def get_funding_rate_history(
        self,
        category: str,
        symbol: str,
        limit: int = 200,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[FundingRateInfo]:
        """
        Get historical funding rates.
        
        Useful for:
        - Analyzing funding trends
        - Strategy backtesting
        - Cost estimation
        """
        endpoint = "/v5/market/funding/history"
        
        params = {
            "category": category,
            "symbol": symbol,
            "limit": min(limit, 200)
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                funding_list = []
                for item in data["result"]["list"]:
                    funding_list.append(FundingRateInfo(
                        symbol=symbol,
                        funding_rate=Decimal(item["fundingRate"]),
                        funding_interval=int(item.get("fundingRateInterval", 8)),
                        next_funding_time=datetime.fromtimestamp(
                            int(item["fundingRateTimestamp"]) / 1000
                        )
                    ))
                
                return funding_list
    
    async def get_current_funding_rate(
        self,
        category: str,
        symbol: str
    ) -> FundingRateInfo:
        """Get current funding rate from ticker."""
        endpoint = "/v5/market/tickers"
        
        params = {
            "category": category,
            "symbol": symbol
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                ticker = data["result"]["list"][0]
                
                return FundingRateInfo(
                    symbol=symbol,
                    funding_rate=Decimal(ticker.get("fundingRate", "0")),
                    predicted_funding_rate=Decimal(
                        ticker.get("predictedFundingRate", "0")
                    ),
                    next_funding_time=datetime.fromtimestamp(
                        int(ticker.get("nextFundingTime", "0")) / 1000
                    ) if ticker.get("nextFundingTime") else None
                )
```

### 4.2 Funding Payment Schedule

```python
from dataclasses import dataclass
from datetime import datetime, time, timezone
import pytz

@dataclass
class FundingSchedule:
    """
    Bybit funding schedule.
    
    Funding occurs at fixed UTC times:
    - 00:00 UTC
    - 08:00 UTC
    - 16:00 UTC
    
    Payment is exchanged at these times based on position held.
    """
    
    FUNDING_TIMES_UTC = [time(0, 0), time(8, 0), time(16, 0)]
    FUNDING_INTERVAL_HOURS = 8
    
    @classmethod
    def get_next_funding_time(cls, from_time: Optional[datetime] = None) -> datetime:
        """Calculate the next funding time from given time."""
        if from_time is None:
            from_time = datetime.now(timezone.utc)
        
        current_time = from_time.time()
        
        # Find next funding time
        for funding_time in cls.FUNDING_TIMES_UTC:
            if current_time < funding_time:
                return datetime.combine(from_time.date(), funding_time, timezone.utc)
        
        # If past all times today, next is first time tomorrow
        next_day = from_time.date() + timedelta(days=1)
        return datetime.combine(next_day, cls.FUNDING_TIMES_UTC[0], timezone.utc)
    
    @classmethod
    def get_time_until_funding(
        cls,
        from_time: Optional[datetime] = None
    ) -> timedelta:
        """Get time remaining until next funding."""
        next_funding = cls.get_next_funding_time(from_time)
        if from_time is None:
            from_time = datetime.now(timezone.utc)
        return next_funding - from_time
    
    @classmethod
    def is_funding_period(cls, minutes_before: int = 5) -> bool:
        """
        Check if currently in a funding period (close to funding time).
        
        During funding periods, spreads may widen and liquidity may decrease.
        """
        now = datetime.now(timezone.utc)
        time_until = cls.get_time_until_funding(now)
        
        # Check if we're within X minutes of funding
        return time_until.total_seconds() < minutes_before * 60


class FundingCostCalculator:
    """Calculate funding costs for position management."""
    
    def calculate_position_funding_cost(
        self,
        position_size: Decimal,
        entry_price: Decimal,
        funding_rates: List[Decimal],
        hold_periods: int
    ) -> Decimal:
        """
        Estimate funding cost for holding a position.
        
        Args:
            position_size: Size of position in base currency
            entry_price: Average entry price
            funding_rates: Historical or predicted funding rates
            hold_periods: Number of 8-hour funding periods to hold
        """
        position_value = position_size * entry_price
        
        total_cost = Decimal("0")
        for i in range(min(hold_periods, len(funding_rates))):
            total_cost += position_value * funding_rates[i]
        
        return total_cost
    
    def should_avoid_funding(
        self,
        current_funding_rate: Decimal,
        position_side: str,  # "long" or "short"
        strategy_type: str = "momentum"
    ) -> bool:
        """
        Determine if position should be closed before funding.
        
        Strategies may want to avoid paying funding if the cost
        outweighs expected profits from holding through funding.
        """
        if strategy_type == "scalping":
            # Scalpers typically avoid funding payments
            if position_side == "long" and current_funding_rate > Decimal("0.0001"):
                return True
            if position_side == "short" and current_funding_rate < Decimal("-0.0001"):
                return True
        
        elif strategy_type == "momentum":
            # Momentum traders may accept funding if trend is strong
            threshold = Decimal("0.001")  # 0.1%
            if position_side == "long" and current_funding_rate > threshold:
                return True
            if position_side == "short" and current_funding_rate < -threshold:
                return True
        
        return False
```

### 4.3 Mark Price vs Last Price

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass
class PriceData:
    """
    Price data structure showing different price types.
    
    Understanding price types:
    - Last Price: Most recent trade price (can be manipulated)
    - Mark Price: Fair value price used for P&L and liquidation
    - Index Price: Spot market reference price
    """
    symbol: str
    
    # Trade price
    last_price: Decimal
    
    # Fair value price
    mark_price: Decimal
    
    # Spot reference price
    index_price: Decimal
    
    # Premium
    premium: Decimal  # mark_price - index_price
    premium_pct: Decimal  # (mark_price - index_price) / index_price
    
    def calculate_basis(self) -> Decimal:
        """Calculate basis (difference between mark and index)."""
        return self.mark_price - self.index_price
    
    def calculate_pnl(
        self,
        entry_price: Decimal,
        position_size: Decimal,
        position_side: str,
        use_mark_price: bool = True
    ) -> Decimal:
        """
        Calculate unrealized P&L.
        
        Bybit uses mark price for unrealized P&L and liquidation.
        """
        current_price = self.mark_price if use_mark_price else self.last_price
        
        if position_side == "long":
            pnl = (current_price - entry_price) * position_size
        else:
            pnl = (entry_price - current_price) * position_size
        
        return pnl


class PriceManager:
    """Manager for price-related operations."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def get_prices(self, category: str, symbol: str) -> PriceData:
        """Get all price types for a symbol."""
        endpoint = "/v5/market/tickers"
        
        params = {
            "category": category,
            "symbol": symbol
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                ticker = data["result"]["list"][0]
                
                last_price = Decimal(ticker["lastPrice"])
                mark_price = Decimal(ticker["markPrice"])
                index_price = Decimal(ticker.get("indexPrice", mark_price))
                
                return PriceData(
                    symbol=symbol,
                    last_price=last_price,
                    mark_price=mark_price,
                    index_price=index_price,
                    premium=mark_price - index_price,
                    premium_pct=(mark_price - index_price) / index_price
                )
    
    def calculate_liquidation_risk(
        self,
        entry_price: Decimal,
        position_size: Decimal,
        position_side: str,
        margin: Decimal,
        mark_price: Decimal,
        maintenance_margin_rate: Decimal
    ) -> Dict:
        """
        Calculate liquidation risk metrics.
        
        Liquidation occurs when:
        Position Margin + Unrealized PnL <= Maintenance Margin
        """
        position_value = position_size * entry_price
        
        # Calculate unrealized PnL
        if position_side == "long":
            unrealized_pnl = (mark_price - entry_price) * position_size
        else:
            unrealized_pnl = (entry_price - mark_price) * position_size
        
        # Maintenance margin required
        maintenance_margin = position_value * maintenance_margin_rate
        
        # Effective margin
        effective_margin = margin + unrealized_pnl
        
        # Distance to liquidation
        distance_to_liq = effective_margin - maintenance_margin
        
        # Liquidation price estimate
        if position_side == "long":
            liq_price = entry_price - (margin / position_size)
        else:
            liq_price = entry_price + (margin / position_size)
        
        return {
            "unrealized_pnl": unrealized_pnl,
            "effective_margin": effective_margin,
            "maintenance_margin": maintenance_margin,
            "distance_to_liquidation": distance_to_liq,
            "liquidation_price": liq_price,
            "risk_level": "HIGH" if distance_to_liq < margin * Decimal("0.1") else "NORMAL"
        }


class MarkPriceCalculator:
    """
    Calculator for mark price methodology.
    
    Mark Price Formula (for linear perpetuals):
    Mark Price = Median of:
        1. Index Price
        2. Last Price
        3. 30-second EMA of (Index Price + 30-second EMA of Premium)
    
    Where Premium = (Last Price - Index Price)
    """
    
    @staticmethod
    def calculate_mark_price(
        index_price: Decimal,
        last_price: Decimal,
        premium_ema: Decimal
    ) -> Decimal:
        """
        Calculate mark price from components.
        
        This is a simplified version - actual Bybit calculation
        uses more sophisticated EMA calculations.
        """
        # Fair basis = EMA of premium
        fair_basis = premium_ema
        
        # Fair price
        fair_price = index_price + fair_basis
        
        # Mark price is median of index, last, and fair
        prices = sorted([index_price, last_price, fair_price])
        return prices[1]  # Median
```

### 4.4 Liquidation Mechanics

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict
from enum import Enum

class LiquidationStatus(str, Enum):
    """Liquidation status enumeration."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    LIQUIDATED = "liquidated"


@dataclass
class LiquidationRisk:
    """Liquidation risk assessment."""
    
    position_value: Decimal
    entry_price: Decimal
    position_size: Decimal
    position_side: str
    
    # Margin info
    initial_margin: Decimal
    maintenance_margin: Decimal
    available_balance: Decimal
    
    # Price info
    mark_price: Decimal
    liquidation_price: Decimal
    
    # Risk metrics
    margin_ratio: Decimal  # MMR / (Margin + Unrealized PnL)
    distance_to_liquidation_pct: Decimal
    
    status: LiquidationStatus
    
    def get_recommended_action(self) -> str:
        """Get recommended action based on risk level."""
        if self.status == LiquidationStatus.NORMAL:
            return "Monitor position normally"
        elif self.status == LiquidationStatus.WARNING:
            return "Consider adding margin or reducing position"
        elif self.status == LiquidationStatus.CRITICAL:
            return "URGENT: Add margin immediately or close position"
        else:
            return "Position has been liquidated"


class LiquidationCalculator:
    """
    Calculator for liquidation mechanics.
    
    Liquidation Process:
    1. Position margin + unrealized PnL <= Maintenance Margin
    2. Liquidation engine takes over position
    3. Position closed at bankruptcy price
    4. Remaining margin transferred to insurance fund
    """
    
    def calculate_liquidation_price(
        self,
        entry_price: Decimal,
        position_size: Decimal,
        position_side: str,
        margin: Decimal,
        maintenance_margin_rate: Decimal,
        leverage: Decimal
    ) -> Decimal:
        """
        Calculate estimated liquidation price.
        
        Simplified formula:
        Long:  Liq Price = Entry * (1 - Initial Margin Rate + MMR)
        Short: Liq Price = Entry * (1 + Initial Margin Rate - MMR)
        """
        imr = Decimal("1") / leverage  # Initial Margin Rate
        
        if position_side == "long":
            liquidation_price = entry_price * (Decimal("1") - imr + maintenance_margin_rate)
        else:
            liquidation_price = entry_price * (Decimal("1") + imr - maintenance_margin_rate)
        
        return max(liquidation_price, Decimal("0"))
    
    def assess_liquidation_risk(
        self,
        entry_price: Decimal,
        position_size: Decimal,
        position_side: str,
        margin: Decimal,
        available_balance: Decimal,
        mark_price: Decimal,
        maintenance_margin_rate: Decimal,
        leverage: Decimal
    ) -> LiquidationRisk:
        """
        Comprehensive liquidation risk assessment.
        """
        position_value = position_size * entry_price
        
        # Calculate unrealized PnL
        if position_side == "long":
            unrealized_pnl = (mark_price - entry_price) * position_size
        else:
            unrealized_pnl = (entry_price - mark_price) * position_size
        
        # Calculate effective margin
        effective_margin = margin + unrealized_pnl
        maintenance_margin = position_value * maintenance_margin_rate
        
        # Calculate liquidation price
        liq_price = self.calculate_liquidation_price(
            entry_price, position_size, position_side,
            margin, maintenance_margin_rate, leverage
        )
        
        # Calculate margin ratio
        if effective_margin > 0:
            margin_ratio = maintenance_margin / effective_margin
        else:
            margin_ratio = Decimal("999")
        
        # Calculate distance to liquidation
        if position_side == "long":
            distance = (mark_price - liq_price) / mark_price
        else:
            distance = (liq_price - mark_price) / liq_price
        
        # Determine status
        if margin_ratio >= Decimal("1"):
            status = LiquidationStatus.LIQUIDATED
        elif margin_ratio >= Decimal("0.8"):
            status = LiquidationStatus.CRITICAL
        elif margin_ratio >= Decimal("0.5"):
            status = LiquidationStatus.WARNING
        else:
            status = LiquidationStatus.NORMAL
        
        return LiquidationRisk(
            position_value=position_value,
            entry_price=entry_price,
            position_size=position_size,
            position_side=position_side,
            initial_margin=margin,
            maintenance_margin=maintenance_margin,
            available_balance=available_balance,
            mark_price=mark_price,
            liquidation_price=liq_price,
            margin_ratio=margin_ratio,
            distance_to_liquidation_pct=distance,
            status=status
        )
    
    def calculate_max_position_size(
        self,
        available_margin: Decimal,
        entry_price: Decimal,
        leverage: Decimal,
        max_risk_pct: Decimal = Decimal("0.9")
    ) -> Decimal:
        """
        Calculate maximum safe position size.
        
        Args:
            max_risk_pct: Maximum percentage of margin to use (safety buffer)
        """
        max_position_value = available_margin * leverage * max_risk_pct
        max_position_size = max_position_value / entry_price
        return max_position_size


class InsuranceFundInfo:
    """
    Information about Bybit's insurance fund.
    
    The insurance fund protects against socialized losses from
    liquidations that can't be filled at bankruptcy price.
    """
    
    def __init__(self):
        self.base_url = "https://api.bybit.com"
    
    async def get_insurance_fund_balance(self, coin: str = "USDT") -> Decimal:
        """Get current insurance fund balance for a coin."""
        endpoint = "/v5/market/insurance"
        
        params = {"coin": coin}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return Decimal(data["result"]["balance"])
```


---

## 5. Subaccount Architecture

### 5.1 Creating and Managing Subaccounts

```python
from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from enum import Enum

class SubaccountType(str, Enum):
    """Subaccount types."""
    STANDARD = "STANDARD"
    CUSTOM = "CUSTOM"

class SubaccountStatus(str, Enum):
    """Subaccount status."""
    ACTIVE = "ACTIVE"
    FREEZE = "FREEZE"
    BANNED = "BANNED"


@dataclass
class Subaccount:
    """Subaccount information."""
    sub_id: str
    name: str
    status: SubaccountStatus
    type: SubaccountType
    
    # Account types enabled
    is_unified: bool = False
    is_contract: bool = False
    is_spot: bool = False
    
    # Creation info
    created_at: Optional[datetime] = None
    
    def is_active(self) -> bool:
        return self.status == SubaccountStatus.ACTIVE


class SubaccountManager:
    """
    Manager for subaccount operations.
    
    Subaccounts provide:
    - Isolation of funds and positions
    - Separate trading strategies
    - Different risk profiles
    - API key segregation
    """
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def create_subaccount(
        self,
        username: str,
        is_unified: bool = True,
        note: Optional[str] = None
    ) -> Subaccount:
        """
        Create a new subaccount.
        
        Args:
            username: Unique username for subaccount (6-32 chars)
            is_unified: Whether to enable Unified Trading Account
            note: Optional description
        
        LIMITS:
        - Max 20 subaccounts per master account
        - Username must be unique and cannot be changed
        """
        endpoint = "/v5/user/create-sub-member"
        
        body = {
            "username": username,
            "isUta": is_unified
        }
        
        if note:
            body["note"] = note
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                result = data["result"]
                return Subaccount(
                    sub_id=result["uid"],
                    name=username,
                    status=SubaccountStatus.ACTIVE,
                    type=SubaccountType.STANDARD,
                    is_unified=is_unified
                )
    
    async def get_subaccount_list(self) -> List[Subaccount]:
        """Get list of all subaccounts."""
        endpoint = "/v5/user/query-sub-members"
        
        headers = self.auth.sign_request("GET", endpoint)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                subaccounts = []
                for item in data["result"]["subMembers"]:
                    subaccounts.append(Subaccount(
                        sub_id=item["uid"],
                        name=item["username"],
                        status=SubaccountStatus(item["status"]),
                        type=SubaccountType(item.get("type", "STANDARD")),
                        is_unified=item.get("isUta", False)
                    ))
                
                return subaccounts
    
    async def freeze_subaccount(self, sub_id: str) -> bool:
        """
        Freeze a subaccount (disable trading).
        
        Use for:
        - Emergency risk control
        - Strategy suspension
        - Compliance requirements
        """
        endpoint = "/v5/user/frozen-sub-member"
        
        body = {"subMemberId": sub_id}
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                return data["retCode"] == 0
    
    async def get_subaccount_api_keys(self, sub_id: str) -> List[Dict]:
        """Get API keys for a subaccount."""
        endpoint = "/v5/user/sub-apikeys"
        
        params = {"subMemberId": sub_id}
        
        headers = self.auth.sign_request("GET", endpoint, params)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=headers
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]["apiKeys"]
```

### 5.2 API Key Permissions per Subaccount

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class PermissionType(str, Enum):
    """API key permission types."""
    ORDER_READ = "Order"
    ORDER_WRITE = "Order"
    POSITION_READ = "Position"
    POSITION_WRITE = "Position"
    ACCOUNT_READ = "Account"
    WITHDRAW = "Withdraw"
    
class ReadWriteType(str, Enum):
    """Read/Write permission."""
    READ = "Read"
    WRITE = "ReadWrite"


@dataclass
class APIKeyPermissions:
    """
    API key permissions structure.
    
    Best practices:
    - Use minimal permissions needed
    - Separate keys for trading vs read-only
    - Restrict IPs for production keys
    - Use subaccounts to isolate permissions
    """
    
    # Contract trading permissions
    contract_orders: Optional[str] = None  # Read or ReadWrite
    contract_positions: Optional[str] = None
    
    # Spot trading permissions
    spot_orders: Optional[str] = None
    spot_positions: Optional[str] = None
    
    # Wallet/Account permissions
    wallet: Optional[str] = None  # Account info, balances
    withdraw: Optional[str] = None  # Withdrawal permission (DANGEROUS)
    
    # Asset transfer
    asset_transfer: Optional[str] = None
    
    # Subaccount management
    sub_member: Optional[str] = None
    
    # Options
    options: Optional[str] = None
    
    def to_api_format(self) -> Dict:
        """Convert to API permission format."""
        permissions = []
        
        if self.contract_orders:
            permissions.append(f"ContractTrade.{self.contract_orders}")
        if self.spot_orders:
            permissions.append(f"SpotTrade.{self.spot_orders}")
        if self.wallet:
            permissions.append(f"Wallet.{self.wallet}")
        if self.withdraw:
            permissions.append(f"Withdraw.{self.withdraw}")
        if self.asset_transfer:
            permissions.append(f"Transfer.{self.asset_transfer}")
        if self.sub_member:
            permissions.append(f"SubMember.{self.sub_member}")
        if self.options:
            permissions.append(f"Options.{self.options}")
        
        return permissions


class APIKeyManager:
    """Manager for API key operations."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def create_api_key(
        self,
        sub_id: Optional[str],
        permissions: APIKeyPermissions,
        note: str = "",
        ip_restriction: Optional[List[str]] = None
    ) -> Dict:
        """
        Create a new API key for master or subaccount.
        
        SECURITY RECOMMENDATIONS:
        1. Always use IP restrictions for production
        2. Never grant Withdraw permission to trading bots
        3. Use separate keys for different strategies
        4. Rotate keys regularly
        
        Args:
            sub_id: Subaccount ID (None for master account)
            permissions: API key permissions
            note: Description of key purpose
            ip_restriction: List of allowed IPs
        """
        endpoint = "/v5/user/create-sub-api"
        
        body = {
            "permissions": permissions.to_api_format(),
            "note": note
        }
        
        if sub_id:
            body["subMemberId"] = sub_id
        
        if ip_restriction:
            body["ips"] = ",".join(ip_restriction)
            body["readOnly"] = 0  # IP restriction requires read-write mode
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return {
                    "api_key": data["result"]["apiKey"],
                    "api_secret": data["result"]["apiSecret"],
                    "permissions": permissions.to_api_format()
                }
    
    def create_trading_bot_permissions(self) -> APIKeyPermissions:
        """
        Create standard permissions for trading bots.
        
        Includes:
        - Contract trading (read/write)
        - Position management (read/write)
        - Account info (read)
        
        Excludes:
        - Withdrawals
        - Asset transfers
        """
        return APIKeyPermissions(
            contract_orders="ReadWrite",
            contract_positions="ReadWrite",
            wallet="Read",
            spot_orders="ReadWrite",
            spot_positions="ReadWrite"
        )
    
    def create_read_only_permissions(self) -> APIKeyPermissions:
        """Create read-only permissions for monitoring."""
        return APIKeyPermissions(
            contract_orders="Read",
            contract_positions="Read",
            wallet="Read",
            spot_orders="Read",
            spot_positions="Read"
        )
    
    async def delete_api_key(self, api_key: str, sub_id: Optional[str] = None) -> bool:
        """Delete an API key."""
        endpoint = "/v5/user/delete-sub-api"
        
        body = {"apikey": api_key}
        
        if sub_id:
            body["subMemberId"] = sub_id
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                return data["retCode"] == 0
```

### 5.3 Capital Transfer Between Accounts

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
from enum import Enum

class TransferStatus(str, Enum):
    """Transfer status enumeration."""
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    FAILED = "FAILED"

class AccountType(str, Enum):
    """Account types for transfers."""
    CONTRACT = "CONTRACT"
    SPOT = "SPOT"
    INVESTMENT = "INVESTMENT"
    OPTION = "OPTION"
    UNIFIED = "UNIFIED"
    FUND = "FUND"  # Funding account


@dataclass
class TransferRequest:
    """Capital transfer request."""
    transfer_id: str  # Client-generated UUID
    coin: str
    amount: Decimal
    from_account_type: AccountType
    to_account_type: AccountType
    from_sub_id: Optional[str] = None  # None for master account
    to_sub_id: Optional[str] = None


class TransferManager:
    """
    Manager for capital transfers.
    
    Transfer capabilities:
    - Master to Subaccount
    - Subaccount to Master
    - Subaccount to Subaccount
    - Between account types (Spot <-> Contract <-> Unified)
    """
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def transfer_between_subaccounts(
        self,
        transfer: TransferRequest
    ) -> Dict:
        """
        Transfer assets between subaccounts or account types.
        
        LIMITS:
        - Minimum transfer amounts apply per coin
        - Transfer fees may apply for certain transfers
        - Some transfers require 2FA if enabled
        """
        endpoint = "/v5/asset/transfer/inter-transfer"
        
        body = {
            "transferId": transfer.transfer_id,
            "coin": transfer.coin,
            "amount": str(transfer.amount),
            "fromAccountType": transfer.from_account_type.value,
            "toAccountType": transfer.to_account_type.value
        }
        
        if transfer.from_sub_id:
            body["fromMemberId"] = transfer.from_sub_id
        if transfer.to_sub_id:
            body["toMemberId"] = transfer.to_sub_id
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
    
    async def get_transfer_history(
        self,
        coin: Optional[str] = None,
        status: Optional[TransferStatus] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get transfer history."""
        endpoint = "/v5/asset/transfer/query-inter-transfer-list"
        
        params = {"limit": limit}
        
        if coin:
            params["coin"] = coin
        if status:
            params["status"] = status.value
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        headers = self.auth.sign_request("GET", endpoint, params)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=headers
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]["list"]
    
    async def get_subaccount_balances(
        self,
        sub_id: str,
        account_type: str = "UNIFIED"
    ) -> Dict:
        """
        Get balances for a specific subaccount.
        
        Useful for:
        - Risk monitoring
        - Rebalancing decisions
        - Performance tracking
        """
        endpoint = "/v5/asset/transfer/query-sub-member-list"
        
        params = {
            "subMemberId": sub_id,
            "accountType": account_type
        }
        
        headers = self.auth.sign_request("GET", endpoint, params)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=headers
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
    
    async def universal_transfer(
        self,
        transfer: TransferRequest
    ) -> Dict:
        """
        Universal transfer supporting all account types.
        
        More flexible than inter-transfer but may have different limits.
        """
        endpoint = "/v5/asset/transfer/universal-transfer"
        
        body = {
            "transferId": transfer.transfer_id,
            "coin": transfer.coin,
            "amount": str(transfer.amount),
            "fromAccountType": transfer.from_account_type.value,
            "toAccountType": transfer.to_account_type.value
        }
        
        if transfer.from_sub_id:
            body["fromMemberId"] = transfer.from_sub_id
        if transfer.to_sub_id:
            body["toMemberId"] = transfer.to_sub_id
        
        headers = self.auth.sign_request("POST", endpoint, body=body)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=body
            ) as resp:
                data = await resp.json()
                
                if data["retCode"] != 0:
                    raise BybitAPIError(data["retCode"], data["retMsg"])
                
                return data["result"]
```

### 5.4 Risk Isolation Benefits

```python
from dataclasses import dataclass
from typing import Dict, List
from decimal import Decimal

@dataclass
class RiskIsolationConfig:
    """
    Configuration for risk isolation using subaccounts.
    
    Benefits of risk isolation:
    1. Position isolation - losses in one don't affect others
    2. Margin isolation - separate margin pools
    3. API isolation - separate API keys per strategy
    4. Operational isolation - independent controls
    """
    
    subaccount_name: str
    max_allocation_pct: Decimal  # % of master account to allocate
    
    # Risk limits
    max_position_value: Decimal
    max_leverage: Decimal
    max_daily_loss: Decimal
    
    # Strategy type
    strategy_type: str  # e.g., "momentum", "arbitrage", "market_making"
    
    # Alerts
    alert_threshold_pct: Decimal = Decimal("0.5")  # Alert at 50% of limit


class RiskIsolationManager:
    """
    Manager for risk isolation architecture.
    
    Recommended architecture:
    - Master account: Read-only monitoring, capital allocation
    - Subaccount 1: Conservative strategy (low leverage, tight stops)
    - Subaccount 2: Aggressive strategy (higher risk tolerance)
    - Subaccount 3: Experimental/development strategies
    """
    
    def __init__(
        self,
        master_auth: BybitHMACAuth,
        testnet: bool = False
    ):
        self.master_auth = master_auth
        self.testnet = testnet
        self.sub_manager = SubaccountManager(master_auth, testnet)
        self.transfer_manager = TransferManager(master_auth, testnet)
    
    async def setup_isolated_strategy(
        self,
        config: RiskIsolationConfig
    ) -> Dict:
        """
        Set up a new isolated strategy subaccount.
        
        Process:
        1. Create subaccount
        2. Create API keys with appropriate permissions
        3. Allocate capital
        4. Set up monitoring
        """
        results = {}
        
        # 1. Create subaccount
        subaccount = await self.sub_manager.create_subaccount(
            username=config.subaccount_name,
            is_unified=True,
            note=f"Isolated {config.strategy_type} strategy"
        )
        results["subaccount"] = subaccount
        
        # 2. Create API keys
        key_manager = APIKeyManager(self.master_auth, self.testnet)
        permissions = key_manager.create_trading_bot_permissions()
        
        api_keys = await key_manager.create_api_key(
            sub_id=subaccount.sub_id,
            permissions=permissions,
            note=f"API for {config.strategy_type}"
        )
        results["api_keys"] = api_keys
        
        return results
    
    async def get_consolidated_risk_report(
        self,
        subaccount_ids: List[str]
    ) -> Dict:
        """
        Get consolidated risk report across all subaccounts.
        
        Provides:
        - Total exposure
        - Risk concentration
        - Correlation analysis
        """
        account_manager = AccountManager(self.master_auth, self.testnet)
        
        total_equity = Decimal("0")
        total_position_value = Decimal("0")
        subaccount_reports = []
        
        for sub_id in subaccount_ids:
            try:
                # This requires subaccount API keys - simplified here
                # In practice, use subaccount-specific auth
                report = {
                    "sub_id": sub_id,
                    "equity": Decimal("0"),  # Would fetch from subaccount
                    "position_value": Decimal("0"),
                    "margin_ratio": Decimal("0")
                }
                subaccount_reports.append(report)
                
            except Exception as e:
                subaccount_reports.append({
                    "sub_id": sub_id,
                    "error": str(e)
                })
        
        # Calculate concentration metrics
        concentration = {}
        if total_equity > 0:
            for report in subaccount_reports:
                if "equity" in report:
                    pct = report["equity"] / total_equity
                    concentration[report["sub_id"]] = pct
        
        return {
            "total_equity": total_equity,
            "total_position_value": total_position_value,
            "subaccounts": subaccount_reports,
            "concentration": concentration,
            "diversification_score": self._calculate_diversification(concentration)
        }
    
    def _calculate_diversification(
        self,
        concentration: Dict[str, Decimal]
    ) -> Decimal:
        """
        Calculate diversification score (0-1).
        
        1 = Perfectly diversified
        0 = Fully concentrated
        """
        if not concentration:
            return Decimal("0")
        
        # Herfindahl-Hirschman Index
        hhi = sum(pct ** 2 for pct in concentration.values())
        
        # Convert to diversification score
        n = len(concentration)
        if n == 1:
            return Decimal("0")
        
        max_hhi = Decimal("1") / n  # Equal distribution
        diversification = (Decimal("1") - hhi) / (Decimal("1") - max_hhi)
        
        return max(Decimal("0"), min(Decimal("1"), diversification))
    
    async def emergency_liquidation(
        self,
        subaccount_id: str,
        reason: str = "Risk limit breach"
    ) -> bool:
        """
        Emergency liquidation of a subaccount.
        
        Steps:
        1. Freeze subaccount (prevent new orders)
        2. Cancel all open orders
        3. Close all positions
        4. Transfer remaining capital to master
        """
        try:
            # 1. Freeze subaccount
            await self.sub_manager.freeze_subaccount(subaccount_id)
            
            # 2. Cancel all orders and close positions
            # (Requires subaccount API keys)
            
            # 3. Transfer remaining balance
            # (Implementation depends on available balances)
            
            return True
            
        except Exception as e:
            print(f"Emergency liquidation failed: {e}")
            return False
```

---

## 6. Error Handling

### 6.1 Common API Error Codes

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Callable
import asyncio

class BybitErrorCode(int, Enum):
    """
    Common Bybit API error codes.
    
    Source: Bybit API documentation
    """
    # Success
    SUCCESS = 0
    
    # Request errors (1xxx)
    PARAM_ERROR = 10001
    INVALID_API_KEY = 10003
    INVALID_SIGN = 10004
    PERMISSION_DENIED = 10005
    TOO_MANY_VISITS = 10006  # Rate limit exceeded
    
    # Trading errors (11xxx)
    ORDER_NOT_FOUND = 110001
    ORDER_STATUS_NOT_MODIFIABLE = 110002
    ORDER_WOULD_TRIGGER_IMMEDIATELY = 110003
    INSUFFICIENT_BALANCE = 110012
    POSITION_NOT_FOUND = 110013
    MARGIN_INSUFFICIENT = 110014
    LIQUIDATION_IN_PROGRESS = 110015
    ORDER_PRICE_TOO_HIGH = 110017
    ORDER_PRICE_TOO_LOW = 110018
    ORDER_QTY_TOO_LARGE = 110019
    ORDER_QTY_TOO_SMALL = 110020
    EXCEEDS_MAX_ORDER_COUNT = 110021
    ORDER_HAS_BEEN_FILLED = 110022
    ORDER_HAS_BEEN_CANCELLED = 110023
    
    # Position errors (12xxx)
    POSITION_MODE_NOT_MODIFIED = 120001
    LEVERAGE_NOT_MODIFIED = 120002
    POSITION_IS_CROSS_MARGIN = 120003
    POSITION_SIZE_EXCEEDS_LIMIT = 120004
    
    # Account errors (13xxx)
    ACCOUNT_NOT_FOUND = 130001
    BORROW_FAILED = 130002
    REPAY_FAILED = 130003


@dataclass
class BybitAPIError(Exception):
    """Bybit API error exception."""
    code: int
    message: str
    
    def __str__(self):
        return f"BybitAPIError {self.code}: {self.message}"
    
    def is_retryable(self) -> bool:
        """Check if error is potentially retryable."""
        retryable_codes = [
            BybitErrorCode.TOO_MANY_VISITS,
            BybitErrorCode.ORDER_STATUS_NOT_MODIFIABLE,
            500,  # Server errors
            502,
            503,
            504,
        ]
        return self.code in retryable_codes
    
    def requires_user_action(self) -> bool:
        """Check if error requires manual intervention."""
        action_codes = [
            BybitErrorCode.INVALID_API_KEY,
            BybitErrorCode.INVALID_SIGN,
            BybitErrorCode.PERMISSION_DENIED,
            BybitErrorCode.LIQUIDATION_IN_PROGRESS,
        ]
        return self.code in action_codes


class ErrorCodeHelper:
    """Helper for understanding and handling error codes."""
    
    ERROR_DESCRIPTIONS = {
        BybitErrorCode.SUCCESS: "Success",
        BybitErrorCode.PARAM_ERROR: "Request parameter error - check your request",
        BybitErrorCode.INVALID_API_KEY: "Invalid API key - check credentials",
        BybitErrorCode.INVALID_SIGN: "Invalid signature - check signing implementation",
        BybitErrorCode.PERMISSION_DENIED: "Permission denied - check API key permissions",
        BybitErrorCode.TOO_MANY_VISITS: "Rate limit exceeded - slow down requests",
        BybitErrorCode.ORDER_NOT_FOUND: "Order not found - may have been cancelled/filled",
        BybitErrorCode.ORDER_STATUS_NOT_MODIFIABLE: "Order cannot be modified in current state",
        BybitErrorCode.INSUFFICIENT_BALANCE: "Insufficient balance for order",
        BybitErrorCode.MARGIN_INSUFFICIENT: "Insufficient margin for position",
        BybitErrorCode.ORDER_PRICE_TOO_HIGH: "Order price above maximum allowed",
        BybitErrorCode.ORDER_PRICE_TOO_LOW: "Order price below minimum allowed",
        BybitErrorCode.ORDER_QTY_TOO_LARGE: "Order quantity exceeds maximum",
        BybitErrorCode.ORDER_QTY_TOO_SMALL: "Order quantity below minimum",
    }
    
    @classmethod
    def get_description(cls, code: int) -> str:
        """Get human-readable description of error code."""
        return cls.ERROR_DESCRIPTIONS.get(code, f"Unknown error code: {code}")
```

### 6.2 Retry Strategies

```python
import random
from typing import Type, Tuple

class RetryStrategy:
    """
    Configurable retry strategy for API calls.
    
    Implements:
    - Exponential backoff
    - Jitter to prevent thundering herd
    - Circuit breaker pattern
    - Max retry limits
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (BybitAPIError,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        
        # Circuit breaker state
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_threshold = 5
        self.circuit_reset_timeout = 60.0
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add random jitter (0-50% of delay)
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay
    
    async def execute(self, coro, *args, **kwargs):
        """
        Execute coroutine with retry logic.
        
        Usage:
            result = await retry_strategy.execute(api_call, param1, param2)
        """
        # Check circuit breaker
        if self.circuit_open:
            raise CircuitBreakerOpen("Circuit breaker is open")
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await coro(*args, **kwargs)
                
                # Success - reset circuit breaker
                self.failure_count = 0
                
                return result
                
            except self.retryable_exceptions as e:
                last_exception = e
                
                # Check if error is retryable
                if isinstance(e, BybitAPIError) and not e.is_retryable():
                    raise
                
                # Update circuit breaker
                self.failure_count += 1
                if self.failure_count >= self.circuit_threshold:
                    self.circuit_open = True
                    asyncio.create_task(self._reset_circuit())
                    raise CircuitBreakerOpen("Circuit breaker opened due to failures")
                
                # Don't retry on last attempt
                if attempt == self.max_retries:
                    break
                
                # Calculate delay and wait
                delay = self.calculate_delay(attempt)
                await asyncio.sleep(delay)
        
        # All retries exhausted
        raise MaxRetriesExceeded(f"Failed after {self.max_retries} retries") from last_exception
    
    async def _reset_circuit(self):
        """Reset circuit breaker after timeout."""
        await asyncio.sleep(self.circuit_reset_timeout)
        self.circuit_open = False
        self.failure_count = 0


class CircuitBreakerOpen(Exception):
    """Circuit breaker is open."""
    pass

class MaxRetriesExceeded(Exception):
    """Maximum retries exceeded."""
    pass


class OrderRetryPolicy:
    """
    Specialized retry policy for order operations.
    
    Different retry strategies for different order types:
    - Market orders: Fast retry (price sensitive)
    - Limit orders: Standard retry
    - Conditional orders: Longer retry window
    """
    
    @staticmethod
    def for_market_order() -> RetryStrategy:
        """Retry strategy for market orders."""
        return RetryStrategy(
            max_retries=2,
            base_delay=0.5,
            max_delay=5.0
        )
    
    @staticmethod
    def for_limit_order() -> RetryStrategy:
        """Retry strategy for limit orders."""
        return RetryStrategy(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0
        )
    
    @staticmethod
    def for_cancel_order() -> RetryStrategy:
        """Retry strategy for cancel operations."""
        return RetryStrategy(
            max_retries=5,
            base_delay=0.5,
            max_delay=10.0
        )
```

### 6.3 Partial Fill Handling

```python
from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal

@dataclass
class PartialFillInfo:
    """Information about a partial fill."""
    order_id: str
    filled_qty: Decimal
    remaining_qty: Decimal
    avg_fill_price: Decimal
    fill_count: int
    last_fill_time: Optional[int] = None
    
    @property
    def fill_percentage(self) -> Decimal:
        """Calculate fill percentage."""
        total = self.filled_qty + self.remaining_qty
        if total == 0:
            return Decimal("0")
        return self.filled_qty / total
    
    def is_fully_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.remaining_qty == 0
    
    def is_partially_filled(self) -> bool:
        """Check if order has partial fills."""
        return self.filled_qty > 0 and self.remaining_qty > 0


class PartialFillHandler:
    """
    Handler for partial fill scenarios.
    
    Strategies for handling partial fills:
    1. Wait for remaining fill
    2. Cancel remaining and re-submit
    3. Accept partial and adjust position
    """
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
        self.partial_fills: Dict[str, PartialFillInfo] = {}
    
    async def handle_partial_fill(
        self,
        order_id: str,
        symbol: str,
        strategy: str = "wait",
        max_wait_seconds: int = 60
    ) -> PartialFillInfo:
        """
        Handle a partial fill based on strategy.
        
        Strategies:
        - "wait": Wait for remaining quantity to fill
        - "cancel": Cancel remaining and accept partial
        - "resubmit": Cancel and re-submit remaining quantity
        """
        # Get current order status
        order = await self.order_manager.get_order(order_id, symbol)
        
        fill_info = PartialFillInfo(
            order_id=order_id,
            filled_qty=Decimal(order.get("cumExecQty", "0")),
            remaining_qty=Decimal(order.get("leavesQty", "0")),
            avg_fill_price=Decimal(order.get("avgPrice", "0")),
            fill_count=int(order.get("cumExecQty", 0))
        )
        
        if strategy == "wait":
            # Wait for remaining fill
            fill_info = await self._wait_for_fill(
                order_id, symbol, max_wait_seconds
            )
        
        elif strategy == "cancel":
            # Cancel remaining
            if fill_info.remaining_qty > 0:
                await self.order_manager.cancel_order(
                    symbol=symbol,
                    order_id=order_id
                )
        
        elif strategy == "resubmit":
            # Cancel and re-submit
            if fill_info.remaining_qty > 0:
                await self.order_manager.cancel_order(
                    symbol=symbol,
                    order_id=order_id
                )
                # Re-submit remaining quantity
                # (Implementation depends on original order details)
        
        self.partial_fills[order_id] = fill_info
        return fill_info
    
    async def _wait_for_fill(
        self,
        order_id: str,
        symbol: str,
        max_wait_seconds: int
    ) -> PartialFillInfo:
        """Wait for order to fill completely."""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            order = await self.order_manager.get_order(order_id, symbol)
            
            filled_qty = Decimal(order.get("cumExecQty", "0"))
            remaining_qty = Decimal(order.get("leavesQty", "0"))
            
            if remaining_qty == 0:
                # Fully filled
                return PartialFillInfo(
                    order_id=order_id,
                    filled_qty=filled_qty,
                    remaining_qty=remaining_qty,
                    avg_fill_price=Decimal(order.get("avgPrice", "0")),
                    fill_count=int(order.get("cumExecQty", 0))
                )
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait_seconds:
                return PartialFillInfo(
                    order_id=order_id,
                    filled_qty=filled_qty,
                    remaining_qty=remaining_qty,
                    avg_fill_price=Decimal(order.get("avgPrice", "0")),
                    fill_count=int(order.get("cumExecQty", 0))
                )
            
            await asyncio.sleep(1)  # Poll every second
```

### 6.4 Connection Failure Recovery

```python
import logging
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class ConnectionRecoveryManager:
    """
    Manager for WebSocket connection recovery.
    
    Handles:
    - Automatic reconnection with backoff
    - State recovery after reconnection
    - Order state synchronization
    - Data integrity checks
    """
    
    def __init__(
        self,
        ws_client,
        max_reconnect_attempts: int = 10,
        reconnect_base_delay: float = 1.0,
        max_reconnect_delay: float = 60.0
    ):
        self.ws_client = ws_client
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_base_delay = reconnect_base_delay
        self.max_reconnect_delay = max_reconnect_delay
        
        self.state = ConnectionState.DISCONNECTED
        self.reconnect_count = 0
        self.last_message_time: Optional[float] = None
        
        # Callbacks for state changes
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_reconnect: Optional[Callable] = None
    
    async def connect_with_recovery(self):
        """Connect with automatic recovery."""
        self.state = ConnectionState.CONNECTING
        
        try:
            await self.ws_client.connect()
            self.state = ConnectionState.CONNECTED
            self.reconnect_count = 0
            
            if self.on_connect:
                await self.on_connect()
            
            # Start monitoring connection
            asyncio.create_task(self._monitor_connection())
            
        except Exception as e:
            logger.error(f"Initial connection failed: {e}")
            await self._attempt_reconnect()
    
    async def _monitor_connection(self):
        """Monitor connection health."""
        while self.state == ConnectionState.CONNECTED:
            try:
                # Check if connection is still alive
                if hasattr(self.ws_client, 'ws') and self.ws_client.ws:
                    if not self.ws_client.ws.open:
                        raise ConnectionError("WebSocket closed unexpectedly")
                
                # Update last message time
                self.last_message_time = asyncio.get_event_loop().time()
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Connection monitoring error: {e}")
                await self._attempt_reconnect()
                break
    
    async def _attempt_reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        self.state = ConnectionState.RECONNECTING
        
        while self.reconnect_count < self.max_reconnect_attempts:
            try:
                # Calculate delay
                delay = min(
                    self.reconnect_base_delay * (2 ** self.reconnect_count),
                    self.max_reconnect_delay
                )
                
                logger.info(f"Reconnecting in {delay:.1f}s (attempt {self.reconnect_count + 1})")
                await asyncio.sleep(delay)
                
                # Attempt reconnection
                await self.ws_client.connect()
                
                # Re-subscribe to channels
                await self._resubscribe()
                
                self.state = ConnectionState.CONNECTED
                self.reconnect_count = 0
                
                if self.on_reconnect:
                    await self.on_reconnect()
                
                # Restart monitoring
                asyncio.create_task(self._monitor_connection())
                
                return
                
            except Exception as e:
                self.reconnect_count += 1
                logger.error(f"Reconnection attempt {self.reconnect_count} failed: {e}")
        
        # Max reconnection attempts exceeded
        self.state = ConnectionState.FAILED
        logger.critical("Max reconnection attempts exceeded. Manual intervention required.")
    
    async def _resubscribe(self):
        """Re-subscribe to channels after reconnection."""
        # Re-subscribe to previously subscribed channels
        if hasattr(self.ws_client, 'subscriptions'):
            for subscription in self.ws_client.subscriptions:
                try:
                    await self.ws_client.subscribe(subscription)
                except Exception as e:
                    logger.error(f"Failed to re-subscribe to {subscription}: {e}")


class OrderStateSynchronizer:
    """
    Synchronizes order state after connection recovery.
    
    Ensures no orders are lost during disconnections.
    """
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
        self.pending_orders: Dict[str, Dict] = {}
    
    async def sync_orders(self, symbol: Optional[str] = None):
        """
        Synchronize order state with exchange.
        
        Steps:
        1. Query all open orders
        2. Compare with local pending orders
        3. Update state for any discrepancies
        4. Handle unknown fills
        """
        # Get open orders from exchange
        open_orders = await self.order_manager.get_open_orders(symbol)
        
        # Build set of active order IDs
        active_order_ids = {order["orderId"] for order in open_orders}
        
        # Check for missing orders
        for order_id, local_order in self.pending_orders.items():
            if order_id not in active_order_ids:
                # Order not found - check if filled or cancelled
                order_history = await self.order_manager.get_order_history(
                    symbol=local_order.get("symbol"),
                    order_id=order_id
                )
                
                if order_history:
                    # Update local state
                    self._update_order_state(order_id, order_history[0])
                else:
                    # Unknown state - log for investigation
                    logger.warning(f"Order {order_id} state unknown after sync")
        
        # Update pending orders with current state
        for order in open_orders:
            self.pending_orders[order["orderId"]] = order
        
        return self.pending_orders
    
    def _update_order_state(self, order_id: str, order_data: Dict):
        """Update local order state."""
        self.pending_orders[order_id] = order_data
        
        # Remove if terminal state
        if order_data.get("orderStatus") in ["Filled", "Cancelled", "Rejected"]:
            del self.pending_orders[order_id]
```

---

## Appendix: Complete Integration Example

```python
"""
Complete Bybit Integration Example

This example demonstrates a production-ready integration with Bybit API V5,
including all the concepts covered in this documentation.
"""

import asyncio
import os
from decimal import Decimal
from typing import Optional
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)


class BybitTradingBot:
    """
    Production-ready Bybit trading bot example.
    
    Features:
    - Secure authentication (HMAC/RSA)
    - Rate limiting
    - Error handling with retries
    - WebSocket for real-time data
    - Position risk management
    - Order management with partial fill handling
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        use_rsa: bool = False
    ):
        self.testnet = testnet
        
        # Initialize authentication
        if use_rsa:
            self.auth = BybitRSAAuth(api_key, api_secret)
        else:
            self.auth = BybitHMACAuth(api_key, api_secret)
        
        # Initialize managers
        self.account_manager = AccountManager(self.auth, testnet)
        self.order_manager = OrderManager(self.auth, testnet)
        self.batch_manager = BatchOrderManager(self.auth, testnet)
        self.trading_stop_manager = TradingStopManager(self.auth, testnet)
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter()
        
        # Initialize retry strategies
        self.market_order_retry = OrderRetryPolicy.for_market_order()
        self.limit_order_retry = OrderRetryPolicy.for_limit_order()
        
        # State
        self.running = False
        self.ws_client: Optional[BybitPrivateWebSocket] = None
    
    async def initialize(self):
        """Initialize the bot."""
        logger.info("bot.initializing", testnet=self.testnet)
        
        # Verify account access
        try:
            account = await self.account_manager.get_wallet_balance()
            logger.info(
                "bot.account_verified",
                total_equity=str(account.total_equity),
                available_balance=str(account.available_balance)
            )
        except Exception as e:
            logger.error("bot.account_verification_failed", error=str(e))
            raise
        
        # Initialize WebSocket
        self.ws_client = BybitPrivateWebSocket(
            self.auth.api_key,
            self.auth.api_secret,
            self.testnet
        )
        
        await self.ws_client.connect()
        
        # Subscribe to updates
        await self.ws_client.subscribe_orders(self._on_order_update)
        await self.ws_client.subscribe_positions(self._on_position_update)
        await self.ws_client.subscribe_wallet(self._on_wallet_update)
        
        self.running = True
        logger.info("bot.initialized")
    
    async def place_trade_with_risk_management(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        price: Optional[Decimal] = None,
        stop_loss_pct: Optional[Decimal] = None,
        take_profit_pct: Optional[Decimal] = None
    ) -> Dict:
        """
        Place a trade with comprehensive risk management.
        
        Args:
            symbol: Trading pair
            side: "Buy" or "Sell"
            qty: Order quantity
            price: Limit price (None for market order)
            stop_loss_pct: Stop loss percentage (e.g., 0.02 for 2%)
            take_profit_pct: Take profit percentage (e.g., 0.06 for 6%)
        """
        try:
            # 1. Check account balance
            account = await self.account_manager.get_wallet_balance()
            
            # 2. Calculate position value
            if price:
                position_value = qty * price
            else:
                # Get current price for market order
                market_client = BybitMarketClient(testnet=self.testnet)
                async with market_client:
                    ticker = await market_client.get_ticker(symbol)
                    position_value = qty * ticker["last"]
            
            # 3. Verify sufficient margin
            if position_value > account.available_balance * Decimal("0.95"):
                raise ValueError("Insufficient margin for trade")
            
            # 4. Place order
            if price:
                # Limit order
                result = await self.limit_order_retry.execute(
                    self.order_manager.place_limit_order,
                    symbol=symbol,
                    side=OrderSide(side),
                    qty=qty,
                    price=price,
                    post_only=True
                )
            else:
                # Market order
                result = await self.market_order_retry.execute(
                    self.order_manager.place_market_order,
                    symbol=symbol,
                    side=OrderSide(side),
                    qty=qty
                )
            
            order_id = result["orderId"]
            logger.info(
                "trade.placed",
                order_id=order_id,
                symbol=symbol,
                side=side,
                qty=str(qty),
                price=str(price) if price else "MARKET"
            )
            
            # 5. Set stop loss / take profit if specified
            if stop_loss_pct or take_profit_pct:
                sl_tp_prices = self.trading_stop_manager.calculate_sl_tp_prices(
                    entry_price=price or position_value / qty,
                    side="long" if side == "Buy" else "short",
                    sl_pct=stop_loss_pct,
                    tp_pct=take_profit_pct
                )
                
                config = TradingStopConfig(
                    stop_loss=sl_tp_prices.get("stop_loss"),
                    take_profit=sl_tp_prices.get("take_profit")
                )
                
                await self.trading_stop_manager.set_trading_stop(
                    symbol=symbol,
                    config=config
                )
                
                logger.info(
                    "trade.stops_set",
                    order_id=order_id,
                    stop_loss=str(config.stop_loss),
                    take_profit=str(config.take_profit)
                )
            
            return result
            
        except Exception as e:
            logger.error(
                "trade.failed",
                symbol=symbol,
                side=side,
                error=str(e)
            )
            raise
    
    def _on_order_update(self, order_data: Dict):
        """Handle order updates from WebSocket."""
        logger.info(
            "order.update",
            order_id=order_data.get("orderId"),
            status=order_data.get("orderStatus"),
            filled_qty=order_data.get("cumExecQty"),
            remaining_qty=order_data.get("leavesQty")
        )
    
    def _on_position_update(self, position_data: Dict):
        """Handle position updates from WebSocket."""
        logger.info(
            "position.update",
            symbol=position_data.get("symbol"),
            size=position_data.get("size"),
            unrealised_pnl=position_data.get("unrealisedPnl")
        )
    
    def _on_wallet_update(self, wallet_data: Dict):
        """Handle wallet updates from WebSocket."""
        logger.info(
            "wallet.update",
            coin=wallet_data.get("coin"),
            equity=wallet_data.get("equity")
        )
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("bot.shutting_down")
        self.running = False
        
        if self.ws_client:
            await self.ws_client.close()
        
        logger.info("bot.shutdown_complete")


# Example usage
async def main():
    """Main entry point."""
    
    # Load credentials from environment
    api_key = os.getenv("BYBIT_API_KEY", "your_api_key")
    api_secret = os.getenv("BYBIT_API_SECRET", "your_api_secret")
    testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
    
    # Create bot
    bot = BybitTradingBot(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )
    
    try:
        # Initialize
        await bot.initialize()
        
        # Example: Place a limit buy order with stop loss
        result = await bot.place_trade_with_risk_management(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("0.01"),
            price=Decimal("25000"),
            stop_loss_pct=Decimal("0.03"),  # 3% stop loss
            take_profit_pct=Decimal("0.06")  # 6% take profit
        )
        
        print(f"Order placed: {result}")
        
        # Keep running for a while
        await asyncio.sleep(60)
        
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Quick Reference

### Common Symbols

| Symbol | Description |
|--------|-------------|
| BTCUSDT | Bitcoin perpetual |
| ETHUSDT | Ethereum perpetual |
| SOLUSDT | Solana perpetual |

### Time Intervals

| Interval | Value |
|----------|-------|
| 1 minute | 1 |
| 5 minutes | 5 |
| 15 minutes | 15 |
| 1 hour | 60 |
| 4 hours | 240 |
| 1 day | D |

### Order Status Flow

```
Created -> New -> PartiallyFilled -> Filled
                      |
                      -> Cancelled
```

### Important Reminders

1. **Always use Testnet first** - Test all strategies on testnet before live trading
2. **Implement proper risk management** - Never risk more than you can afford to lose
3. **Monitor rate limits** - Respect API rate limits to avoid bans
4. **Handle errors gracefully** - Always implement retry logic and error handling
5. **Use subaccounts for isolation** - Separate different strategies with subaccounts
6. **Secure your API keys** - Never commit API keys to version control
7. **Monitor funding rates** - High funding can erode profits quickly
8. **Understand liquidation risks** - Always know your liquidation price

---

*Document Version: 1.0.0*  
*For questions or updates, refer to the official Bybit API documentation*
