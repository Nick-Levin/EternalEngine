# Интеграция с биржей Bybit - Технический справочник

> **Версия:** API V5 | **Последнее обновление:** 2026-02-13  
> **Тип документа:** Техническое руководство по интеграции для торговых систем на Python

---

## Содержание

1. [Обзор](#обзор)
2. [Спецификации Bybit API V5](#1-спецификации-bybit-api-v5)
3. [Унифицированный торговый счет (UTA)](#2-унифицированный-торговый-счет-uta)
4. [Типы ордеров и исполнение](#3-типы-ордеров-и-исполнение)
5. [Механика бессрочных фьючерсов](#4-механика-бессрочных-фьючерсов)
6. [Архитектура субсчетов](#5-архитектура-субсчетов)
7. [Обработка ошибок](#6-обработка-ошибок)
8. [Приложение: Полный пример интеграции](#приложение-полный-пример-интеграции)

---

## Обзор

Bybit API V5 предоставляет унифицированный интерфейс для спотовой торговли, линейных бессрочных, обратных бессрочных и опционов. Этот документ содержит комплексные технические спецификации для интеграции Bybit в алгоритмические торговые системы.

### Базовые URL API

| Окружение | REST API | WebSocket Public | WebSocket Private |
|-----------|----------|------------------|-------------------|
| **Mainnet** | `https://api.bybit.com` | `wss://stream.bybit.com/v5/public` | `wss://stream.bybit.com/v5/private` |
| **Testnet** | `https://api-testnet.bybit.com` | `wss://stream-testnet.bybit.com/v5/public` | `wss://stream-testnet.bybit.com/v5/private` |

### Категории рынков

```python
from enum import Enum

class MarketCategory(str, Enum):
    """Категории рынков Bybit."""
    SPOT = "spot"
    LINEAR = "linear"      # USDT-M бессрочные фьючерсы
    INVERSE = "inverse"    # Coin-M бессрочные фьючерсы
    OPTION = "option"
```

---

## 1. Спецификации Bybit API V5

### 1.1 REST API эндпоинты

#### Эндпоинты рыночных данных

```python
from dataclasses import dataclass
from typing import Optional, List, Dict
from decimal import Decimal
import aiohttp
import asyncio

@dataclass
class MarketEndpoints:
    """Карта эндпоинтов рыночных данных."""
    
    # Время сервера
    SERVER_TIME = "/v5/market/time"
    
    # Данные Kline/OHLCV
    KLINE = "/v5/market/kline"
    MARK_PRICE_KLINE = "/v5/market/mark-price-kline"
    INDEX_PRICE_KLINE = "/v5/market/index-price-kline"
    PREMIUM_INDEX_KLINE = "/v5/market/premium-index-kline"
    
    # Стакан ордеров
    ORDERBOOK = "/v5/market/orderbook"
    
    # Тикеры
    TICKERS = "/v5/market/tickers"
    
    # Ставка финансирования
    FUNDING_RATE = "/v5/market/funding/history"
    
    # Недавние сделки
    RECENT_TRADES = "/v5/market/recent-trade"


class BybitMarketClient:
    """Реализация клиента рыночных данных."""
    
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
        Получение данных Kline/свечей.
        
        Args:
            category: Категория рынка (spot, linear, inverse)
            symbol: Торговая пара (например, "BTCUSDT")
            interval: Интервал Kline
            limit: Количество свечей (макс 1000)
            start_time: Начальная метка времени в миллисекундах
            end_time: Конечная метка времени в миллисекундах
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
            
            # Формат ответа: [timestamp, open, high, low, close, volume, turnover]
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
        """Получение данных стакана ордеров."""
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

#### Торговые эндпоинты

```python
@dataclass
class TradingEndpoints:
    """Эндпоинты торговых операций."""
    
    # Управление ордерами
    PLACE_ORDER = "/v5/order/create"
    AMEND_ORDER = "/v5/order/amend"
    CANCEL_ORDER = "/v5/order/cancel"
    CANCEL_ALL = "/v5/order/cancel-all"
    GET_ORDERS = "/v5/order/realtime"
    GET_ORDER_HISTORY = "/v5/order/history"
    
    # Пакетные операции
    BATCH_PLACE_ORDER = "/v5/order/create-batch"
    BATCH_AMEND_ORDER = "/v5/order/amend-batch"
    BATCH_CANCEL_ORDER = "/v5/order/cancel-batch"
    
    # Управление позициями
    GET_POSITIONS = "/v5/position/list"
    SET_LEVERAGE = "/v5/position/set-leverage"
    SWITCH_MARGIN_MODE = "/v5/position/switch-isolated"
    SWITCH_POSITION_MODE = "/v5/position/switch-mode"
    SET_TRADING_STOP = "/v5/position/trading-stop"
    SET_AUTO_ADD_MARGIN = "/v5/position/set-auto-add-margin"
    
    # Счет
    GET_WALLET_BALANCE = "/v5/account/wallet-balance"
    GET_ACCOUNT_INFO = "/v5/account/info"
    GET_TRANSACTION_LOG = "/v5/account/transaction-log"
    
    # Финансирование
    GET_COLLATERAL_INFO = "/v5/account/collateral-info"
    GET_COINS_BALANCE = "/v5/asset/transfer/query-account-coins-balance"
```

### 1.2 WebSocket потоки

#### Публичные WebSocket потоки

```python
import websockets
import json
from typing import Callable, Optional

class BybitPublicWebSocket:
    """
    Публичный WebSocket клиент Bybit.
    
    Поддерживает:
    - Стакан ордеров (Уровень 1, 25, 50, 100, 200, 500)
    - Потоки сделок
    - Тикер/24-часовая статистика
    - Потоки Kline/свечей
    - Потоки ликвидаций
    - Потоки LT (плечевых токенов)
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
        """Установка WebSocket соединения."""
        self.ws = await websockets.connect(self.ws_url)
        self.running = True
        
        # Запуск keepalive ping/pong
        asyncio.create_task(self._keepalive())
        
        # Запуск обработчика сообщений
        asyncio.create_task(self._message_handler())
    
    async def subscribe_orderbook(
        self, 
        symbols: List[str], 
        depth: int = 25,
        callback: Optional[Callable[[Dict], None]] = None
    ):
        """
        Подписка на обновления стакана ордеров.
        
        Args:
            symbols: Список торговых пар
            depth: Глубина стакана (1, 25, 50, 100, 200, 500)
            callback: Функция для обработки обновлений
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
        Подписка на обновления тикеров.
        
        Предоставляет: последнюю цену, индексную цену, цену маркировки, ставку финансирования,
        24-часовой объем, 24-часовой оборот, процент изменения цены
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
        """Подписка на потоки сделок в реальном времени."""
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
        """Подписка на потоки Kline/свечей."""
        args = [{"channel": f"kline.{interval}", "symbol": s} for s in symbols]
        
        subscribe_msg = {
            "op": "subscribe",
            "args": args
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        
        if callback:
            self._kline_callback = callback
    
    async def _keepalive(self):
        """Отправка периодических ping сообщений."""
        while self.running:
            try:
                if self.ws and self.ws.open:
                    await self.ws.send(json.dumps({"op": "ping"}))
                await asyncio.sleep(20)  # Ping каждые 20 секунд
            except Exception as e:
                print(f"Ошибка keepalive: {e}")
                break
    
    async def _message_handler(self):
        """Обработка входящих WebSocket сообщений."""
        while self.running:
            try:
                if not self.ws:
                    await asyncio.sleep(0.1)
                    continue
                
                msg = await self.ws.recv()
                data = json.loads(msg)
                
                # Обработка ответа pong
                if data.get("op") == "pong":
                    continue
                
                # Обработка успешной подписки
                if data.get("success") is not None:
                    if data.get("success"):
                        print(f"Подписано: {data.get('ret_msg')}")
                    else:
                        print(f"Подписка не удалась: {data.get('ret_msg')}")
                    continue
                
                # Обработка обновлений данных
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
                print("WebSocket соединение закрыто")
                self.running = False
                break
            except Exception as e:
                print(f"Ошибка обработчика сообщений: {e}")
    
    async def close(self):
        """Закрытие WebSocket соединения."""
        self.running = False
        if self.ws:
            await self.ws.close()
```

#### Приватные WebSocket потоки

```python
class BybitPrivateWebSocket:
    """
    Приватный WebSocket клиент Bybit для данных счета.
    
    Требует аутентификации.
    Предоставляет:
    - Обновления ордеров
    - Обновления позиций
    - Обновления баланса кошелька
    - Отчеты об исполнении
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
        """Подключение и аутентификация."""
        self.ws = await websockets.connect(self.ws_url)
        
        # Генерация подписи аутентификации
        expires = int((asyncio.get_event_loop().time() + 10) * 1000)
        signature = self._generate_signature(expires)
        
        auth_msg = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        
        await self.ws.send(json.dumps(auth_msg))
        
        # Ожидание ответа auth
        response = await self.ws.recv()
        auth_response = json.loads(response)
        
        if not auth_response.get("success"):
            raise AuthenticationError(
                f"Ошибка аутентификации: {auth_response.get('ret_msg')}"
            )
        
        self.running = True
        
        # Запуск обработчиков
        asyncio.create_task(self._keepalive())
        asyncio.create_task(self._message_handler())
    
    def _generate_signature(self, expires: int) -> str:
        """Генерация HMAC подписи для WebSocket auth."""
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
        """Подписка на обновления ордеров."""
        self.order_callback = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "order"}]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def subscribe_positions(self, callback: Callable[[Dict], None]):
        """Подписка на обновления позиций."""
        self.position_callback = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "position"}]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def subscribe_wallet(self, callback: Callable[[Dict], None]):
        """Подписка на обновления баланса кошелька."""
        self.wallet_callback = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "wallet"}]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def subscribe_executions(self, callback: Callable[[Dict], None]):
        """Подписка на отчеты об исполнении/заполнении."""
        self.execution_callback = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "execution"}]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def _message_handler(self):
        """Обработка входящих приватных сообщений."""
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
                print(f"Ошибка приватного WS: {e}")
    
    async def _keepalive(self):
        """Поддержание соединения."""
        while self.running:
            try:
                if self.ws and self.ws.open:
                    await self.ws.send(json.dumps({"op": "ping"}))
                await asyncio.sleep(20)
            except Exception:
                break
```

### 1.3 Методы аутентификации

#### HMAC Аутентификация

```python
import hmac
import hashlib
import json
from urllib.parse import urlencode
from typing import Dict, Optional

class BybitHMACAuth:
    """
    HMAC SHA256 аутентификация для Bybit API.
    
    Используется для:
    - Аутентификации по API Key + Secret
    - Подписи REST API запросов
    - Аутентификации WebSocket
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
        Генерация подписи запроса и заголовков.
        
        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            endpoint: Путь эндпоинта API
            params: Query параметры
            body: Тело запроса для POST/PUT
            
        Returns:
            Словарь заголовков для включения в запрос
        """
        timestamp = str(int(asyncio.get_event_loop().time() * 1000))
        recv_window = "5000"  # Рекомендуется 5 секунд
        
        # Сборка payload для подписи
        if method == "GET" and params:
            payload = urlencode(sorted(params.items()))
            payload = f"{timestamp}{self.api_key}{recv_window}{payload}"
        elif body:
            payload = json.dumps(body)
            payload = f"{timestamp}{self.api_key}{recv_window}{payload}"
        else:
            payload = f"{timestamp}{self.api_key}{recv_window}"
        
        # Генерация подписи
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


# Пример использования
async def example_hmac_auth():
    auth = BybitHMACAuth("YOUR_API_KEY", "YOUR_API_SECRET")
    
    # Подпись GET запроса
    headers = auth.sign_request(
        method="GET",
        endpoint="/v5/account/wallet-balance",
        params={"accountType": "UNIFIED"}
    )
    
    # Подпись POST запроса
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

#### RSA Аутентификация

```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import base64

class BybitRSAAuth:
    """
    RSA аутентификация для повышенной безопасности.
    
    RSA рекомендуется вместо HMAC для:
    - Повышенных требований безопасности
    - API ключей, используемых несколькими членами команды
    - Требований соответствия нормативам
    """
    
    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        
        # Загрузка приватного ключа
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
        """Генерация RSA подписи для запроса."""
        timestamp = str(int(asyncio.get_event_loop().time() * 1000))
        recv_window = "5000"
        
        # Сборка payload
        if method == "GET" and params:
            payload = urlencode(sorted(params.items()))
            payload = f"{timestamp}{self.api_key}{recv_window}{payload}"
        elif body:
            payload = json.dumps(body)
            payload = f"{timestamp}{self.api_key}{recv_window}{payload}"
        else:
            payload = f"{timestamp}{self.api_key}{recv_window}"
        
        # RSA подпись
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


# Пример генерации RSA ключей
def generate_rsa_keypair(output_dir: str = "."):
    """Генерация пары RSA ключей для аутентификации Bybit API."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Сохранение приватного ключа
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    with open(f"{output_dir}/bybit_private.pem", "wb") as f:
        f.write(private_pem)
    
    # Сохранение публичного ключа (для загрузки на Bybit)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    with open(f"{output_dir}/bybit_public.pem", "wb") as f:
        f.write(public_pem)
    
    print(f"RSA ключи сгенерированы в {output_dir}/")
    print("Загрузите bybit_public.pem на страницу управления API Bybit")
```

### 1.4 Ограничение частоты запросов

```python
from dataclasses import dataclass
from typing import Dict, Optional
import asyncio
from collections import deque
import time

@dataclass
class RateLimitConfig:
    """Конфигурации ограничения частоты запросов Bybit API."""
    
    # Bybit использует два типа лимитов:
    # 1. Лимиты на основе запросов (по эндпоинту)
    # 2. Лимиты на основе веса (общий вес API)
    
    # Публичные эндпоинты (на основе IP)
    PUBLIC_IP_LIMIT = 600  # запросов в минуту на IP
    
    # Приватные эндпоинты (на основе API ключа)
    PRIVATE_LIMIT_TIER_1 = 120  # запросов в секунду для стандартных счетов
    PRIVATE_LIMIT_TIER_2 = 120  # запросов в секунду для VIP счетов
    PRIVATE_LIMIT_TIER_3 = 120  # запросов в секунду для Pro счетов
    
    # Специфические лимиты эндпоинтов
    ORDER_CREATION_LIMIT = 10  # в секунду
    ORDER_AMEND_LIMIT = 10     # в секунду
    ORDER_CANCEL_LIMIT = 10    # в секунду
    POSITION_SET_LEVERAGE = 10  # в минуту
    
    # Лимиты пакетных ордеров
    BATCH_ORDER_LIMIT = 10     # ордеров в пакетном запросе
    BATCH_REQUEST_LIMIT = 10   # пакетных запросов в секунду


class RateLimiter:
    """
    Rate limiter с алгоритмом ведра токенов для Bybit API.
    
    Реализует:
    - Ограничение частоты по эндпоинтам
    - Ограничение по весу
    - Автоматический повтор с экспоненциальной задержкой
    """
    
    def __init__(self):
        # Отслеживание временных меток запросов по типу эндпоинта
        self.order_timestamps: deque = deque()
        self.general_timestamps: deque = deque()
        
        self.order_limit = 10  # в секунду
        self.general_limit = 120  # в секунду
        
        self._lock = asyncio.Lock()
    
    async def acquire(self, endpoint_type: str = "general") -> float:
        """
        Получение разрешения на rate limit.
        
        Args:
            endpoint_type: Тип эндпоинта ("order", "general")
            
        Returns:
            Время ожидания в секундах перед выполнением запроса
        """
        async with self._lock:
            now = time.time()
            
            if endpoint_type == "order":
                queue = self.order_timestamps
                limit = self.order_limit
                window = 1.0  # Окно 1 секунда
            else:
                queue = self.general_timestamps
                limit = self.general_limit
                window = 1.0
            
            # Удаление временных меток вне окна
            while queue and queue[0] < now - window:
                queue.popleft()
            
            # Проверка необходимости ожидания
            if len(queue) >= limit:
                wait_time = queue[0] + window - now
                return max(0, wait_time)
            
            queue.append(now)
            return 0
    
    async def execute_with_limit(self, coro, endpoint_type: str = "general"):
        """Выполнение корутины с ограничением частоты."""
        wait = await self.acquire(endpoint_type)
        if wait > 0:
            await asyncio.sleep(wait)
        return await coro


class RateLimitHeaders:
    """Парсинг информации об ограничении частоты из заголовков ответа."""
    
    @staticmethod
    def parse(headers: Dict[str, str]) -> Dict[str, int]:
        """
        Извлечение информации об ограничении частоты из заголовков ответа.
        
        Заголовки:
        - X-Bapi-Limit-Status: Оставшиеся запросы в текущем окне
        - X-Bapi-Limit: Общий лимит для эндпоинта
        - X-Bapi-Limit-Reset-Timestamp: Когда сбросится лимит (мс)
        """
        return {
            "limit_status": int(headers.get("X-Bapi-Limit-Status", 0)),
            "limit": int(headers.get("X-Bapi-Limit", 0)),
            "reset_timestamp": int(headers.get("X-Bapi-Limit-Reset-Timestamp", 0))
        }
```

---

## 2. Унифицированный торговый счет (UTA)

### 2.1 Структура счета и режимы маржи

```python
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict, Optional

class AccountType(str, Enum):
    """Типы счетов Bybit."""
    CONTRACT = "CONTRACT"      # Классический деривативный счет
    SPOT = "SPOT"              # Спотовый торговый счет
    UNIFIED = "UNIFIED"        # Унифицированный торговый счет (UTA 1.0)
    UNIFIED_TRADE = "UNIFIED_TRADE"  # UTA 2.0 Pro

class MarginMode(str, Enum):
    """Режимы маржи для торговли деривативами."""
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"

class PositionMode(str, Enum):
    """Режимы позиций."""
    ONE_WAY = 0        # Можно держать позиции только в одном направлении
    HEDGE = 3          # Можно держать и длинные, и короткие позиции


@dataclass
class UnifiedAccountInfo:
    """
    Структура унифицированного торгового счета (UTA).
    
    UTA объединяет:
    - Спотовую торговлю
    - USDT бессрочные (linear)
    - USDC бессрочные (linear)
    - Обратные бессрочные
    - Опционы
    - Маржинальную торговлю
    
    Все используют единую маржу и обеспечение.
    """
    account_type: str = "UNIFIED"
    
    # Статус счета
    margin_mode: MarginMode = MarginMode.CROSS
    position_mode: PositionMode = PositionMode.ONE_WAY
    
    # Метрики маржи (в эквиваленте USDT)
    total_equity: Decimal = Decimal("0")
    available_balance: Decimal = Decimal("0")
    used_margin: Decimal = Decimal("0")
    
    # Метрики риска
    initial_margin_rate: Decimal = Decimal("0")  # IMR
    maintenance_margin_rate: Decimal = Decimal("0")  # MMR
    
    # Метрики позиций
    total_position_im: Decimal = Decimal("0")  # Общая начальная маржа для позиций
    total_position_mm: Decimal = Decimal("0")  # Общая поддерживающая маржа для позиций
    
    # Метрики займов (для маржинальной торговли)
    total_borrow: Decimal = Decimal("0")
    
    def calculate_margin_ratio(self) -> Decimal:
        """Расчет текущего коэффициента маржи."""
        if self.used_margin == 0:
            return Decimal("999")
        return self.total_equity / self.used_margin
    
    def is_liquidation_risk(self) -> bool:
        """Проверка риска ликвидации счета."""
        return self.maintenance_margin_rate > Decimal("1")


class AccountManager:
    """Менеджер для операций UTA."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def get_wallet_balance(self, account_type: str = "UNIFIED") -> UnifiedAccountInfo:
        """
        Получение баланса кошелька унифицированного счета.
        
        Возвращает детальную разбивку:
        - Общий капитал
        - Доступный баланс
        - Балансы по активам
        - Использование маржи
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
        Переключение между режимами ISOLATED и CROSS маржи.
        
        ВНИМАНИЕ: Переключение режима маржи:
        - Отменит все активные ордера для символа
        - Может привести к частичному закрытию позиции при недостаточной марже
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
        Переключение между режимами One-way и Hedge позиций.
        
        Args:
            category: "linear" или "inverse"
            symbol: Конкретный символ или None для всех символов
            mode: ONE_WAY (0) или HEDGE (3)
        
        ВНИМАНИЕ: Нельзя переключиться, если есть открытые позиции или ордера.
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


### 2.2 Механика кросс-коллатерали

```python
@dataclass
class CollateralInfo:
    """Информация об активах обеспечения."""
    
    coin: str
    equity: Decimal
    wallet_balance: Decimal
    
    # Метрики маржи
    available_balance: Decimal
    
    # Метрики займов (для маржинальной торговли)
    borrow_amount: Decimal
    available_to_borrow: Decimal
    
    # Настройки обеспечения
    collateral_ratio: Decimal  # Какая часть этой монеты считается обеспечением (0-1)
    
    def effective_collateral_value(self) -> Decimal:
        """Расчет эффективной стоимости обеспечения с учетом коэффициента."""
        return self.wallet_balance * self.collateral_ratio


class CrossCollateralManager:
    """
    Менеджер для функциональности кросс-коллатерали.
    
    В UTA в качестве обеспечения могут использоваться несколько активов:
    - USDT (100% коэффициент обеспечения)
    - BTC, ETH (обычно 95% коэффициент)
    - Альткоины (переменные коэффициенты, часто 80-90%)
    
    Коэффициенты обеспечения определяются риск-движком Bybit.
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
        Получение информации об обеспечении для активов.
        
        Показывает:
        - Какие монеты могут использоваться в качестве обеспечения
        - Коэффициенты обеспечения для каждой монеты
        - Текущее использование маржи для каждой монеты
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
        Расчет общего эффективного обеспечения по всем активам.
        
        Returns:
            Словарь с суммарным и эффективным (после коэффициента обеспечения) итогом
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

### 2.3 Расчеты IMR/MMR

```python
@dataclass
class MarginRequirements:
    """
    Расчеты требований начальной маржи (IMR) и 
    поддерживающей маржи (MMR).
    
    Понимание маржи:
    - IMR: Минимальная маржа для ОТКРЫТИЯ позиции
    - MMR: Минимальная маржа для ПОДДЕРЖАНИЯ позиции (порог ликвидации)
    """
    
    # Размер позиции
    position_value: Decimal
    leverage: Decimal
    
    # Требования маржи
    initial_margin_rate: Decimal  # IMR = 1 / leverage
    initial_margin: Decimal       # IM = position_value * IMR
    
    maintenance_margin_rate: Decimal  # MMR обычно 0.5% на самом низком уровне
    maintenance_margin: Decimal       # MM = position_value * MMR
    
    # Доступная маржа
    available_margin: Decimal
    
    # Метрики риска
    margin_ratio: Decimal  # MR = MM / (position_value + available_margin)
    liquidation_price: Optional[Decimal] = None
    
    def is_liquidation_imminent(self) -> bool:
        """Проверка, близка ли позиция к ликвидации."""
        # Ликвидация происходит, когда маржа позиции <= поддерживающей маржи
        return self.margin_ratio > Decimal("0.8")
    
    def safe_leverage(self, max_position_value: Decimal) -> Decimal:
        """
        Расчет безопасного плеча с учетом доступной маржи.
        
        Формула: max_leverage = available_margin / (position_value * IMR)
        """
        if self.position_value == 0 or self.available_margin == 0:
            return Decimal("1")
        
        max_leverage = self.available_margin / (max_position_value * self.initial_margin_rate)
        return min(max_leverage, Decimal("100"))  # Ограничение 100x


class MarginCalculator:
    """
    Калькулятор требований маржи для позиций деривативов.
    
    Bybit использует многоуровневую систему маржи:
    - Большая стоимость позиции = выше требования маржи
    - Каждый уровень имеет разное максимальное плечо, IMR и MMR
    """
    
    # Структура уровней (упрощенная - фактические уровни варьируются по символу)
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
        position_side: str  # "long" или "short"
    ) -> MarginRequirements:
        """
        Расчет требований маржи для позиции.
        
        Args:
            position_value: Стоимость позиции в котируемой валюте
            leverage: Желаемое плечо (1-100)
            available_margin: Доступная маржа для этой позиции
            entry_price: Цена входа в позицию
            position_side: "long" или "short"
        """
        # Определение уровня
        tier = cls._get_tier(position_value)
        
        # Расчет IMR и MMR
        imr = Decimal("1") / leverage
        mmr = tier["mmr"]
        
        im = position_value * imr
        mm = position_value * mmr
        
        # Расчет коэффициента маржи
        # Для long: MR = MM / (entry_price * position_size + available)
        # Для short: аналогичный расчет
        denominator = position_value + available_margin
        margin_ratio = mm / denominator if denominator > 0 else Decimal("0")
        
        # Расчет цены ликвидации
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
        """Получение уровня маржи для стоимости позиции."""
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
        """Расчет оценочной цены ликвидации."""
        # Упрощенный расчет - фактическая формула Bybit сложнее
        if side == "long":
            return entry_price * (Decimal("1") - imr + mmr)
        else:
            return entry_price * (Decimal("1") + imr - mmr)
```

### 2.4 Риски автоматического заимствования

```python
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
import asyncio

@dataclass
class AutoBorrowConfig:
    """
    Конфигурация автоматического заимствования для маржинальной торговли.
    
    ВНИМАНИЕ: Автоматическое заимствование может привести к значительным убыткам при отсутствии мониторинга.
    """
    enabled: bool = False
    
    # Лимиты
    max_borrow_usd: Decimal = Decimal("0")
    max_borrow_ratio: Decimal = Decimal("0.5")  # Максимум 50% от капитала
    
    # Настройки автопогашения
    auto_repay: bool = True
    repay_threshold: Decimal = Decimal("0.95")  # Погашение при падении коэффициента обеспечения


class AutoBorrowRiskManager:
    """
    Менеджер рисков автоматического заимствования.
    
    РИСКИ:
    1. Процентные расходы накапливаются быстро
    2. Заимствованные активы подвержены ликвидации
    3. Коэффициент обеспечения меняется с волатильностью рынка
    4. Лимиты заимствования могут быть снижены в период высокой волатильности
    """
    
    # Почасовые процентные ставки (приблизительные - проверяйте актуальные на Bybit)
    BORROW_RATES = {
        "USDT": Decimal("0.0001"),  # 0.01% в час = ~87.6% годовых
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
        Расчет стоимости заимствования.
        
        Args:
            asset: Актив для заимствования
            amount: Сумма для заимствования
            duration_hours: Ожидаемая продолжительность займа
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
        Оценка рисков открытия позиции займа.
        
        Returns оценку риска, включая:
        - Влияние на обеспечение
        - Увеличение риска ликвидации
        - Прогноз стоимости
        """
        # Текущее состояние
        current_collateral_ratio = account.total_equity / account.used_margin if account.used_margin > 0 else Decimal("999")
        
        # Состояние после займа (заимствованный актив добавляется к стоимости позиции)
        new_position_value = account.total_position_im + borrow_amount
        new_used_margin = account.used_margin + (borrow_amount * account.initial_margin_rate)
        new_collateral_ratio = account.total_equity / new_used_margin if new_used_margin > 0 else Decimal("999")
        
        # Оценка риска
        risk_level = "LOW"
        if new_collateral_ratio < Decimal("1.2"):
            risk_level = "CRITICAL"
        elif new_collateral_ratio < Decimal("1.5"):
            risk_level = "HIGH"
        elif new_collateral_ratio < Decimal("2.0"):
            risk_level = "MEDIUM"
        
        # Расчет стоимости за 24 часа
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
        Запуск мониторинга позиций займа на предмет рисков.
        
        Оповещает при:
        - Падении коэффициента обеспечения
        - Накоплении расходов на займ
        - Приближении к ликвидации
        """
        self._monitoring = True
        
        while self._monitoring:
            try:
                account = await account_manager.get_wallet_balance()
                
                # Проверка статуса займа
                if account.total_borrow > 0:
                    collateral_ratio = account.total_equity / account.used_margin
                    
                    if collateral_ratio < Decimal("1.1"):
                        print(f"КРИТИЧЕСКИ: Коэффициент обеспечения {collateral_ratio:.2f}")
                        print("Требуется немедленное действие - рассмотрите сокращение позиций")
                    elif collateral_ratio < Decimal("1.3"):
                        print(f"ВНИМАНИЕ: Коэффициент обеспечения {collateral_ratio:.2f}")
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                print(f"Ошибка мониторинга: {e}")
                await asyncio.sleep(check_interval)
    
    def stop_monitoring(self):
        """Остановка мониторинга рисков."""
        self._monitoring = False
```


---

## 3. Типы ордеров и исполнение

### 3.1 Типы ордеров

```python
from enum import Enum
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, List
from datetime import datetime

class OrderSide(str, Enum):
    """Перечисление сторон ордера."""
    BUY = "Buy"
    SELL = "Sell"

class OrderTypeStr(str, Enum):
    """Перечисление типов ордеров."""
    MARKET = "Market"
    LIMIT = "Limit"

class TimeInForce(str, Enum):
    """
    Time in Force - Поведение исполнения ордера.
    
    - GTC: Действителен до отмены (по умолчанию для лимитных ордеров)
    - IOC: Немедленно или отменить
    - FOK: Заполнить полностью или отменить
    - PostOnly: Гарантия мейкерской комиссии
    """
    GTC = "GTC"           # Good Till Canceled
    IOC = "IOC"           # Immediate Or Cancel
    FOK = "FOK"           # Fill Or Kill
    POST_ONLY = "PostOnly"  # Post Only (гарантирует мейкерскую комиссию)

class TriggerDirection(int, Enum):
    """Направление триггера для условных ордеров."""
    RISES_TO = 1   # Цена растет до триггерной цены
    FALLS_TO = 2   # Цена падает до триггерной цены

class OrderStatus(str, Enum):
    """Перечисление статусов ордера."""
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
    """Базовая структура запроса ордера."""
    
    category: str                    # spot, linear, inverse, option
    symbol: str                      # Торговая пара (например, "BTCUSDT")
    side: OrderSide                  # Buy или Sell
    order_type: OrderTypeStr         # Market или Limit
    qty: Decimal                     # Количество ордера
    
    # Параметры лимитного ордера
    price: Optional[Decimal] = None  # Обязательно для лимитных ордеров
    time_in_force: TimeInForce = TimeInForce.GTC
    
    # Связывание ордеров
    order_link_id: Optional[str] = None  # Клиентский ID ордера (UUID)
    
    # Флаг только уменьшения (для закрытия позиций)
    reduce_only: bool = False
    
    # Закрытие по триггеру (для условных ордеров)
    close_on_trigger: bool = False
    
    # Защита рыночного ордера
    market_unit: Optional[str] = None  # "baseCoin" или "quoteCoin"
    
    def to_api_params(self) -> Dict:
        """Конвертация в параметры, совместимые с API."""
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
    Запрос условного ордера (стоп-ордера).
    
    Условные ордера активируются, когда цена достигает определенного уровня.
    Типичное использование:
    - Стоп-лосс ордера
    - Тейк-профит ордера
    - Входы при пробое
    """
    
    trigger_price: Decimal
    trigger_direction: TriggerDirection
    
    # Опционально: Триггер по разным типам цен
    trigger_by: str = "LastPrice"  # LastPrice, IndexPrice, MarkPrice
    
    def to_api_params(self) -> Dict:
        """Конвертация условного ордера в параметры API."""
        params = super().to_api_params()
        params["triggerPrice"] = str(self.trigger_price)
        params["triggerDirection"] = self.trigger_direction.value
        params["triggerBy"] = self.trigger_by
        return params
```

### 3.2 Исполнение ордеров

```python
class OrderManager:
    """Менеджер для операций с ордерами."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def place_order(self, order: OrderRequest) -> Dict:
        """
        Размещение одного ордера.
        
        Возвращает детали ордера, включая:
        - orderId: ID ордера биржи
        - orderLinkId: Клиентский ID ордера
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
        Размещение рыночного ордера.
        
        ВАЖНО: Рыночные ордера исполняются немедленно по лучшей доступной цене.
        Проскальзывание цены может быть значительным в периоды волатильности.
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
        Размещение лимитного ордера.
        
        Args:
            post_only: Если True, ордер будет отклонен, если он заберет ликвидность
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
        Размещение условного ордера стоп-лосс.
        
        Для длинных позиций: trigger_direction = FALLS_TO (2)
        Для коротких позиций: trigger_direction = RISES_TO (1)
        """
        trigger_direction = (
            TriggerDirection.FALLS_TO if side == OrderSide.SELL 
            else TriggerDirection.RISES_TO
        )
        
        order = ConditionalOrderRequest(
            category=category,
            symbol=symbol,
            side=side,
            order_type=OrderTypeStr.MARKET,  # Исполняется как рыночный при срабатывании
            qty=qty,
            trigger_price=trigger_price,
            trigger_direction=trigger_direction,
            trigger_by=trigger_by,
            close_on_trigger=True  # Важно: закрывает позицию
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
        Изменение существующего ордера.
        
        Можно изменить:
        - Цену (лимитные ордера)
        - Количество
        - Триггерную цену (условные ордера)
        
        Нельзя изменить:
        - Символ
        - Сторону
        - Тип ордера
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
            raise ValueError("Требуется order_id или order_link_id")
        
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
        """Отмена активного ордера."""
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
            raise ValueError("Требуется order_id или order_link_id")
        
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
        Отмена всех активных ордеров.
        
        Если symbol равен None, отменяет все ордера в категории.
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


### 3.3 Настройки стоп-лосс / тейк-профит

```python
@dataclass
class TradingStopConfig:
    """
    Конфигурация торговых стопов для привязки SL/TP к позициям.
    
    Преимущества перед отдельными условными ордерами:
    - Привязаны к жизненному циклу позиции
    - Автоматически корректируются при изменении позиции
    - Лучше подходят для стратегий на основе позиций
    """
    
    # Стоп-лосс
    stop_loss: Optional[Decimal] = None
    sl_trigger_by: str = "LastPrice"  # LastPrice, IndexPrice, MarkPrice
    
    # Тейк-профит
    take_profit: Optional[Decimal] = None
    tp_trigger_by: str = "LastPrice"
    
    # Трейлинг-стоп
    trailing_stop: Optional[Decimal] = None  # Дистанция трейлинга
    
    # Размер позиции для закрытия
    tp_size: Optional[Decimal] = None  # По умолчанию: закрыть всю позицию
    sl_size: Optional[Decimal] = None
    
    def to_api_params(self) -> Dict:
        """Конвертация в параметры API."""
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
    """Менеджер для торговых стопов на основе позиций."""
    
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
        Установка торгового стопа для существующей позиции.
        
        Привязывает SL/TP непосредственно к позиции, а не создает
        отдельные условные ордера.
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
        side: str,  # "long" или "short"
        sl_pct: Optional[Decimal] = None,
        tp_pct: Optional[Decimal] = None
    ) -> Dict[str, Decimal]:
        """
        Расчет цен стоп-лосс и тейк-профит на основе процентов.
        
        Args:
            entry_price: Цена входа в позицию
            side: "long" или "short"
            sl_pct: Процент стоп-лосса (например, 0.02 для 2%)
            tp_pct: Процент тейк-профита (например, 0.06 для 6%)
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

### 3.4 Пакетные ордера

```python
from typing import List

@dataclass
class BatchOrderResult:
    """Результат пакетной операции с ордерами."""
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
    Менеджер для пакетных операций с ордерами.
    
    ЛИМИТЫ:
    - Максимум 10 ордеров в пакетном запросе
    - Максимум 10 пакетных запросов в секунду
    - Разрешен смешанный выбор символов внутри одной категории
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
        Размещение нескольких ордеров в одном запросе.
        
        Преимущества:
        - Снижение накладных расходов API вызовов
        - Атомарная обработка
        - Лучшая эффективность лимитов частоты
        
        Примечание: Если один ордер не проходит валидацию, весь пакет может быть отклонен.
        """
        if len(orders) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Максимум {self.MAX_BATCH_SIZE} ордеров в пакете")
        
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
                
                # Парсинг результатов
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
        Изменение нескольких ордеров в одном запросе.
        
        Каждый словарь изменений должен содержать:
        - symbol: Торговая пара
        - orderId или orderLinkId: Идентификатор ордера
        - price, qty, или triggerPrice: Новые значения
        """
        if len(amendments) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Максимум {self.MAX_BATCH_SIZE} изменений в пакете")
        
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
        Отмена нескольких ордеров в одном запросе.
        
        Каждый словарь отмены должен содержать:
        - symbol: Торговая пара
        - orderId или orderLinkId: Идентификатор ордера
        """
        if len(cancellations) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Максимум {self.MAX_BATCH_SIZE} отмен в пакете")
        
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
        Размещение множества ордеров с использованием нескольких пакетных запросов при необходимости.
        
        Автоматически разбивает ордера на пакеты по MAX_BATCH_SIZE.
        """
        all_results = BatchOrderResult()
        
        # Разбиение ордеров на пакеты
        for i in range(0, len(orders), self.MAX_BATCH_SIZE):
            batch = orders[i:i + self.MAX_BATCH_SIZE]
            result = await self.place_batch_orders(batch, category)
            
            all_results.successful.extend(result.successful)
            all_results.failed.extend(result.failed)
            
            # Ограничение частоты между пакетами
            if i + self.MAX_BATCH_SIZE < len(orders):
                await asyncio.sleep(0.1)  # 100мс между пакетами
        
        return all_results
```

---

## 4. Механика бессрочных фьючерсов

### 4.1 Расчет ставки финансирования

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
from datetime import datetime, timedelta

@dataclass
class FundingRateInfo:
    """
    Информация о ставке финансирования для бессрочных контрактов.
    
    Платежи по финансированию происходят каждые 8 часов в:
    - 00:00 UTC
    - 08:00 UTC  
    - 16:00 UTC
    """
    symbol: str
    
    # Текущая ставка финансирования (положительная = лонгисты платят шортистам)
    funding_rate: Decimal
    
    # Прогнозируемая следующая ставка (обновляется за 5 минут до финансирования)
    predicted_funding_rate: Decimal
    
    # Интервал финансирования в часах (обычно 8)
    funding_interval: int = 8
    
    # Время следующего финансирования
    next_funding_time: Optional[datetime] = None
    
    # Исторический контекст
    avg_funding_24h: Optional[Decimal] = None
    avg_funding_7d: Optional[Decimal] = None
    
    def calculate_funding_payment(
        self,
        position_size: Decimal,
        position_value: Decimal
    ) -> Decimal:
        """
        Расчет платежа по финансированию для позиции.
        
        Положительный результат = вы платите финансирование
        Отрицательный результат = вы получаете финансирование
        """
        return position_value * self.funding_rate
    
    def is_premium(self) -> bool:
        """Проверка, указывает ли ставка финансирования на премию (лонгисты платят)."""
        return self.funding_rate > 0
    
    def is_discount(self) -> bool:
        """Проверка, указывает ли ставка финансирования на дисконт (шортисты платят)."""
        return self.funding_rate < 0


class FundingRateCalculator:
    """
    Калькулятор механики ставок финансирования.
    
    Формула ставки финансирования (упрощенная):
    Ставка финансирования = Премиальный индекс + Процентная ставка
    
    Премиальный индекс = (Цена маркировки - Индексная цена) / Индексная цена
    Процентная ставка = 0.01% за 8 часов (обычно)
    
    Ограничение: Ставка финансирования ограничена между -0.75% и 0.75%
    """
    
    INTEREST_RATE = Decimal("0.0001")  # 0.01% за 8 часов
    FUNDING_CLAMP = Decimal("0.0075")  # Максимум 0.75%
    
    @classmethod
    def calculate_funding_rate(
        cls,
        mark_price: Decimal,
        index_price: Decimal,
        premium_1h_avg: Decimal
    ) -> Decimal:
        """
        Расчет оценочной ставки финансирования.
        
        Bybit использует 1-часовую TWAP премиального индекса.
        """
        # Текущая премия
        current_premium = (mark_price - index_price) / index_price
        
        # Ставка финансирования = средняя премия + процентная ставка
        funding_rate = premium_1h_avg + cls.INTEREST_RATE
        
        # Ограничение лимитами
        funding_rate = max(-cls.FUNDING_CLAMP, min(cls.FUNDING_CLAMP, funding_rate))
        
        return funding_rate
    
    @classmethod
    def estimate_annualized_funding(
        cls,
        funding_rate: Decimal,
        periods_per_day: int = 3  # 3 периода по 8 часов
    ) -> Decimal:
        """Расчет годовой ставки финансирования (APY)."""
        daily_rate = funding_rate * periods_per_day
        annual_rate = daily_rate * 365
        return annual_rate


class FundingRateManager:
    """Менеджер для операций со ставками финансирования."""
    
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
        Получение исторических ставок финансирования.
        
        Полезно для:
        - Анализа трендов финансирования
        - Бэктестинга стратегий
        - Оценки затрат
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
        """Получение текущей ставки финансирования из тикера."""
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

### 4.2 Расписание платежей по финансированию

```python
from dataclasses import dataclass
from datetime import datetime, time, timezone
import pytz

@dataclass
class FundingSchedule:
    """
    Расписание финансирования Bybit.
    
    Финансирование происходит в фиксированное время UTC:
    - 00:00 UTC
    - 08:00 UTC
    - 16:00 UTC
    
    Платежи обмениваются в эти моменты на основе удерживаемой позиции.
    """
    
    FUNDING_TIMES_UTC = [time(0, 0), time(8, 0), time(16, 0)]
    FUNDING_INTERVAL_HOURS = 8
    
    @classmethod
    def get_next_funding_time(cls, from_time: Optional[datetime] = None) -> datetime:
        """Расчет времени следующего финансирования от заданного времени."""
        if from_time is None:
            from_time = datetime.now(timezone.utc)
        
        current_time = from_time.time()
        
        # Поиск времени следующего финансирования
        for funding_time in cls.FUNDING_TIMES_UTC:
            if current_time < funding_time:
                return datetime.combine(from_time.date(), funding_time, timezone.utc)
        
        # Если прошли все времена сегодня, следующее - первое время завтра
        next_day = from_time.date() + timedelta(days=1)
        return datetime.combine(next_day, cls.FUNDING_TIMES_UTC[0], timezone.utc)
    
    @classmethod
    def get_time_until_funding(
        cls,
        from_time: Optional[datetime] = None
    ) -> timedelta:
        """Получение времени до следующего финансирования."""
        next_funding = cls.get_next_funding_time(from_time)
        if from_time is None:
            from_time = datetime.now(timezone.utc)
        return next_funding - from_time
    
    @classmethod
    def is_funding_period(cls, minutes_before: int = 5) -> bool:
        """
        Проверка, находимся ли мы в периоде финансирования (близко ко времени).
        
        В периоды финансирования спреды могут расширяться, а ликвидность снижаться.
        """
        now = datetime.now(timezone.utc)
        time_until = cls.get_time_until_funding(now)
        
        # Проверка, находимся ли мы в пределах X минут от финансирования
        return time_until.total_seconds() < minutes_before * 60


class FundingCostCalculator:
    """Расчет затрат на финансирование для управления позициями."""
    
    def calculate_position_funding_cost(
        self,
        position_size: Decimal,
        entry_price: Decimal,
        funding_rates: List[Decimal],
        hold_periods: int
    ) -> Decimal:
        """
        Оценка затрат на финансирование для удержания позиции.
        
        Args:
            position_size: Размер позиции в базовой валюте
            entry_price: Средняя цена входа
            funding_rates: Исторические или прогнозируемые ставки финансирования
            hold_periods: Количество 8-часовых периодов удержания
        """
        position_value = position_size * entry_price
        
        total_cost = Decimal("0")
        for i in range(min(hold_periods, len(funding_rates))):
            total_cost += position_value * funding_rates[i]
        
        return total_cost
    
    def should_avoid_funding(
        self,
        current_funding_rate: Decimal,
        position_side: str,  # "long" или "short"
        strategy_type: str = "momentum"
    ) -> bool:
        """
        Определение, следует ли закрыть позицию перед финансированием.
        
        Стратегии могут захотеть избежать оплаты финансирования, если стоимость
        превышает ожидаемую прибыль от удержания через финансирование.
        """
        if strategy_type == "scalping":
            # Скальперы обычно избегают платежей по финансированию
            if position_side == "long" and current_funding_rate > Decimal("0.0001"):
                return True
            if position_side == "short" and current_funding_rate < Decimal("-0.0001"):
                return True
        
        elif strategy_type == "momentum":
            # Моментумные трейдеры могут принять финансирование, если тренд силен
            threshold = Decimal("0.001")  # 0.1%
            if position_side == "long" and current_funding_rate > threshold:
                return True
            if position_side == "short" and current_funding_rate < -threshold:
                return True
        
        return False
```


### 4.3 Цена маркировки vs цена последней сделки

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass
class PriceData:
    """
    Структура данных цены, показывающая разные типы цен.
    
    Понимание типов цен:
    - Цена последней сделки: Цена последней сделки (может манипулироваться)
    - Цена маркировки: Справедливая цена для P&L и ликвидации
    - Индексная цена: Цена спотового рынка-референса
    """
    symbol: str
    
    # Цена сделки
    last_price: Decimal
    
    # Справедливая цена
    mark_price: Decimal
    
    # Справочная цена спота
    index_price: Decimal
    
    # Премия
    premium: Decimal  # mark_price - index_price
    premium_pct: Decimal  # (mark_price - index_price) / index_price
    
    def calculate_basis(self) -> Decimal:
        """Расчет базиса (разница между маркировкой и индексом)."""
        return self.mark_price - self.index_price
    
    def calculate_pnl(
        self,
        entry_price: Decimal,
        position_size: Decimal,
        position_side: str,
        use_mark_price: bool = True
    ) -> Decimal:
        """
        Расчет нереализованного P&L.
        
        Bybit использует цену маркировки для нереализованного P&L и ликвидации.
        """
        current_price = self.mark_price if use_mark_price else self.last_price
        
        if position_side == "long":
            pnl = (current_price - entry_price) * position_size
        else:
            pnl = (entry_price - current_price) * position_size
        
        return pnl


class PriceManager:
    """Менеджер для операций, связанных с ценами."""
    
    def __init__(self, auth: BybitHMACAuth, testnet: bool = False):
        self.auth = auth
        self.testnet = testnet
        self.base_url = (
            "https://api-testnet.bybit.com" if testnet 
            else "https://api.bybit.com"
        )
    
    async def get_prices(self, category: str, symbol: str) -> PriceData:
        """Получение всех типов цен для символа."""
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
        Расчет метрик риска ликвидации.
        
        Ликвидация происходит, когда:
        Маржа позиции + Нереализованный PnL <= Поддерживающая маржа
        """
        position_value = position_size * entry_price
        
        # Расчет нереализованного PnL
        if position_side == "long":
            unrealized_pnl = (mark_price - entry_price) * position_size
        else:
            unrealized_pnl = (entry_price - mark_price) * position_size
        
        # Требуемая поддерживающая маржа
        maintenance_margin = position_value * maintenance_margin_rate
        
        # Эффективная маржа
        effective_margin = margin + unrealized_pnl
        
        # Дистанция до ликвидации
        distance_to_liq = effective_margin - maintenance_margin
        
        # Оценка цены ликвидации
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
    Калькулятор методологии цены маркировки.
    
    Формула цены маркировки (для линейных бессрочных):
    Цена маркировки = Медиана из:
        1. Индексная цена
        2. Цена последней сделки
        3. 30-секундная EMA от (Индексная цена + 30-секундная EMA от Премии)
    
    Где Премия = (Цена последней сделки - Индексная цена)
    """
    
    @staticmethod
    def calculate_mark_price(
        index_price: Decimal,
        last_price: Decimal,
        premium_ema: Decimal
    ) -> Decimal:
        """
        Расчет цены маркировки из компонентов.
        
        Это упрощенная версия - фактический расчет Bybit
        использует более сложные вычисления EMA.
        """
        # Справедливый базис = EMA премии
        fair_basis = premium_ema
        
        # Справедливая цена
        fair_price = index_price + fair_basis
        
        # Цена маркировки - медиана из индекса, последней и справедливой
        prices = sorted([index_price, last_price, fair_price])
        return prices[1]  # Медиана
```

### 4.4 Механика ликвидации

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict
from enum import Enum

class LiquidationStatus(str, Enum):
    """Перечисление статусов ликвидации."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    LIQUIDATED = "liquidated"


@dataclass
class LiquidationRisk:
    """Оценка риска ликвидации."""
    
    position_value: Decimal
    entry_price: Decimal
    position_size: Decimal
    position_side: str
    
    # Информация о марже
    initial_margin: Decimal
    maintenance_margin: Decimal
    available_balance: Decimal
    
    # Информация о цене
    mark_price: Decimal
    liquidation_price: Decimal
    
    # Метрики риска
    margin_ratio: Decimal  # MMR / (Margin + Unrealized PnL)
    distance_to_liquidation_pct: Decimal
    
    status: LiquidationStatus
    
    def get_recommended_action(self) -> str:
        """Получение рекомендуемого действия на основе уровня риска."""
        if self.status == LiquidationStatus.NORMAL:
            return "Нормальный мониторинг позиции"
        elif self.status == LiquidationStatus.WARNING:
            return "Рассмотрите добавление маржи или сокращение позиции"
        elif self.status == LiquidationStatus.CRITICAL:
            return "СРОЧНО: Немедленно добавьте маржу или закройте позицию"
        else:
            return "Позиция была ликвидирована"


class LiquidationCalculator:
    """
    Калькулятор механики ликвидации.
    
    Процесс ликвидации:
    1. Маржа позиции + нереализованный PnL <= Поддерживающая маржа
    2. Движок ликвидации берет управление позицией
    3. Позиция закрывается по цене банкротства
    4. Оставшаяся маржа переводится в страховой фонд
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
        Расчет оценочной цены ликвидации.
        
        Упрощенная формула:
        Long:  Цена ликв = Вход * (1 - Начальная ставка маржи + MMR)
        Short: Цена ликв = Вход * (1 + Начальная ставка маржи - MMR)
        """
        imr = Decimal("1") / leverage  # Начальная ставка маржи
        
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
        Комплексная оценка риска ликвидации.
        """
        position_value = position_size * entry_price
        
        # Расчет нереализованного PnL
        if position_side == "long":
            unrealized_pnl = (mark_price - entry_price) * position_size
        else:
            unrealized_pnl = (entry_price - mark_price) * position_size
        
        # Расчет эффективной маржи
        effective_margin = margin + unrealized_pnl
        maintenance_margin = position_value * maintenance_margin_rate
        
        # Расчет цены ликвидации
        liq_price = self.calculate_liquidation_price(
            entry_price, position_size, position_side,
            margin, maintenance_margin_rate, leverage
        )
        
        # Расчет коэффициента маржи
        if effective_margin > 0:
            margin_ratio = maintenance_margin / effective_margin
        else:
            margin_ratio = Decimal("999")
        
        # Расчет дистанции до ликвидации
        if position_side == "long":
            distance = (mark_price - liq_price) / mark_price
        else:
            distance = (liq_price - mark_price) / liq_price
        
        # Определение статуса
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
        Расчет максимального безопасного размера позиции.
        
        Args:
            max_risk_pct: Максимальный процент маржи для использования (буфер безопасности)
        """
        max_position_value = available_margin * leverage * max_risk_pct
        max_position_size = max_position_value / entry_price
        return max_position_size


class InsuranceFundInfo:
    """
    Информация о страховом фонде Bybit.
    
    Страховой фонд защищает от социализированных убытков от
    ликвидаций, которые нельзя заполнить по цене банкротства.
    """
    
    def __init__(self):
        self.base_url = "https://api.bybit.com"
    
    async def get_insurance_fund_balance(self, coin: str = "USDT") -> Decimal:
        """Получение текущего баланса страхового фонда для монеты."""
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

## 5. Архитектура субсчетов

### 5.1 Создание и управление субсчетами

```python
from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from enum import Enum

class SubaccountType(str, Enum):
    """Типы субсчетов."""
    STANDARD = "STANDARD"
    CUSTOM = "CUSTOM"

class SubaccountStatus(str, Enum):
    """Статусы субсчетов."""
    ACTIVE = "ACTIVE"
    FREEZE = "FREEZE"
    BANNED = "BANNED"


@dataclass
class Subaccount:
    """Информация о субсчете."""
    sub_id: str
    name: str
    status: SubaccountStatus
    type: SubaccountType
    
    # Включенные типы счетов
    is_unified: bool = False
    is_contract: bool = False
    is_spot: bool = False
    
    # Информация о создании
    created_at: Optional[datetime] = None
    
    def is_active(self) -> bool:
        return self.status == SubaccountStatus.ACTIVE


class SubaccountManager:
    """
    Менеджер для операций с субсчетами.
    
    Субсчета обеспечивают:
    - Изоляцию средств и позиций
    - Отдельные торговые стратегии
    - Разные профили риска
    - Сегрегацию API ключей
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
        Создание нового субсчета.
        
        Args:
            username: Уникальное имя пользователя для субсчета (6-32 символов)
            is_unified: Включить ли Унифицированный торговый счет
            note: Опциональное описание
        
        ЛИМИТЫ:
        - Максимум 20 субсчетов на мастер-счет
        - Имя пользователя должно быть уникальным и не может быть изменено
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
        """Получение списка всех субсчетов."""
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
        Заморозка субсчета (отключение торговли).
        
        Используется для:
        - Экстренного контроля риска
        - Приостановки стратегии
        - Требований соответствия нормативам
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
        """Получение API ключей для субсчета."""
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


### 5.2 Разрешения API ключей для субсчетов

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class PermissionType(str, Enum):
    """Типы разрешений API ключа."""
    ORDER_READ = "Order"
    ORDER_WRITE = "Order"
    POSITION_READ = "Position"
    POSITION_WRITE = "Position"
    ACCOUNT_READ = "Account"
    WITHDRAW = "Withdraw"
    
class ReadWriteType(str, Enum):
    """Разрешение чтения/записи."""
    READ = "Read"
    WRITE = "ReadWrite"


@dataclass
class APIKeyPermissions:
    """
    Структура разрешений API ключа.
    
    Лучшие практики:
    - Используйте минимальные необходимые разрешения
    - Разделяйте ключи для торговли и только для чтения
    - Ограничивайте IP для production ключей
    - Используйте субсчета для изоляции разрешений
    """
    
    # Разрешения торговли контрактами
    contract_orders: Optional[str] = None  # Read или ReadWrite
    contract_positions: Optional[str] = None
    
    # Разрешения спотовой торговли
    spot_orders: Optional[str] = None
    spot_positions: Optional[str] = None
    
    # Разрешения кошелька/счета
    wallet: Optional[str] = None  # Информация о счете, балансы
    withdraw: Optional[str] = None  # Разрешение на вывод (ОПАСНО)
    
    # Перевод активов
    asset_transfer: Optional[str] = None
    
    # Управление субсчетами
    sub_member: Optional[str] = None
    
    # Опционы
    options: Optional[str] = None
    
    def to_api_format(self) -> Dict:
        """Конвертация в формат разрешений API."""
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
    """Менеджер для операций с API ключами."""
    
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
        Создание нового API ключа для мастер-счета или субсчета.
        
        РЕКОМЕНДАЦИИ ПО БЕЗОПАСНОСТИ:
        1. Всегда используйте IP ограничения для production
        2. Никогда не давайте разрешение на вывод торговым ботам
        3. Используйте отдельные ключи для разных стратегий
        4. Регулярно меняйте ключи
        
        Args:
            sub_id: ID субсчета (None для мастер-счета)
            permissions: Разрешения API ключа
            note: Описание назначения ключа
            ip_restriction: Список разрешенных IP
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
            body["readOnly"] = 0  # IP ограничение требует режима чтения-записи
        
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
        Создание стандартных разрешений для торговых ботов.
        
        Включает:
        - Торговля контрактами (чтение/запись)
        - Управление позициями (чтение/запись)
        - Информация о счете (чтение)
        
        Исключает:
        - Выводы
        - Переводы активов
        """
        return APIKeyPermissions(
            contract_orders="ReadWrite",
            contract_positions="ReadWrite",
            wallet="Read",
            spot_orders="ReadWrite",
            spot_positions="ReadWrite"
        )
    
    def create_read_only_permissions(self) -> APIKeyPermissions:
        """Создание разрешений только для чтения для мониторинга."""
        return APIKeyPermissions(
            contract_orders="Read",
            contract_positions="Read",
            wallet="Read",
            spot_orders="Read",
            spot_positions="Read"
        )
    
    async def delete_api_key(self, api_key: str, sub_id: Optional[str] = None) -> bool:
        """Удаление API ключа."""
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

### 5.3 Перевод капитала между счетами

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
from enum import Enum

class TransferStatus(str, Enum):
    """Перечисление статусов перевода."""
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    FAILED = "FAILED"

class AccountType(str, Enum):
    """Типы счетов для переводов."""
    CONTRACT = "CONTRACT"
    SPOT = "SPOT"
    INVESTMENT = "INVESTMENT"
    OPTION = "OPTION"
    UNIFIED = "UNIFIED"
    FUND = "FUND"  # Счет финансирования


@dataclass
class TransferRequest:
    """Запрос на перевод капитала."""
    transfer_id: str  # Клиентский UUID
    coin: str
    amount: Decimal
    from_account_type: AccountType
    to_account_type: AccountType
    from_sub_id: Optional[str] = None  # None для мастер-счета
    to_sub_id: Optional[str] = None


class TransferManager:
    """
    Менеджер для переводов капитала.
    
    Возможности перевода:
    - Мастер на субсчет
    - Субсчет на мастер
    - Субсчет на субсчет
    - Между типами счетов (Spot <-> Contract <-> Unified)
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
        Перевод активов между субсчетами или типами счетов.
        
        ЛИМИТЫ:
        - Применяются минимальные суммы перевода для каждой монеты
        - Могут взиматься комиссии за определенные переводы
        - Некоторые переводы требуют 2FA, если включен
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
        """Получение истории переводов."""
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
        Получение балансов для конкретного субсчета.
        
        Полезно для:
        - Мониторинга рисков
        - Решений о ребалансировке
        - Отслеживания производительности
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
        Универсальный перевод, поддерживающий все типы счетов.
        
        Более гибкий, чем inter-transfer, но может иметь другие лимиты.
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

### 5.4 Преимущества изоляции рисков

```python
from dataclasses import dataclass
from typing import Dict, List
from decimal import Decimal

@dataclass
class RiskIsolationConfig:
    """
    Конфигурация изоляции рисков с использованием субсчетов.
    
    Преимущества изоляции рисков:
    1. Изоляция позиций - убытки в одной не влияют на другие
    2. Изоляция маржи - отдельные пулы маржи
    3. Изоляция API - отдельные API ключи для каждой стратегии
    4. Операционная изоляция - независимые контроли
    """
    
    subaccount_name: str
    max_allocation_pct: Decimal  # % от мастер-счета для выделения
    
    # Лимиты риска
    max_position_value: Decimal
    max_leverage: Decimal
    max_daily_loss: Decimal
    
    # Тип стратегии
    strategy_type: str  # например, "momentum", "arbitrage", "market_making"
    
    # Оповещения
    alert_threshold_pct: Decimal = Decimal("0.5")  # Оповещение при 50% лимита


class RiskIsolationManager:
    """
    Менеджер для архитектуры изоляции рисков.
    
    Рекомендуемая архитектура:
    - Мастер-счет: Только чтение мониторинга, распределение капитала
    - Субсчет 1: Консервативная стратегия (низкое плечо, жесткие стопы)
    - Субсчет 2: Агрессивная стратегия (больший допуск риска)
    - Субсчет 3: Экспериментальные/разработческие стратегии
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
        Настройка нового субсчета изолированной стратегии.
        
        Процесс:
        1. Создание субсчета
        2. Создание API ключей с соответствующими разрешениями
        3. Выделение капитала
        4. Настройка мониторинга
        """
        results = {}
        
        # 1. Создание субсчета
        subaccount = await self.sub_manager.create_subaccount(
            username=config.subaccount_name,
            is_unified=True,
            note=f"Изолированная {config.strategy_type} стратегия"
        )
        results["subaccount"] = subaccount
        
        # 2. Создание API ключей
        key_manager = APIKeyManager(self.master_auth, self.testnet)
        permissions = key_manager.create_trading_bot_permissions()
        
        api_keys = await key_manager.create_api_key(
            sub_id=subaccount.sub_id,
            permissions=permissions,
            note=f"API для {config.strategy_type}"
        )
        results["api_keys"] = api_keys
        
        return results
    
    async def get_consolidated_risk_report(
        self,
        subaccount_ids: List[str]
    ) -> Dict:
        """
        Получение консолидированного отчета по рискам по всем субсчетам.
        
        Предоставляет:
        - Общую экспозицию
        - Концентрацию риска
        - Анализ корреляции
        """
        account_manager = AccountManager(self.master_auth, self.testnet)
        
        total_equity = Decimal("0")
        total_position_value = Decimal("0")
        subaccount_reports = []
        
        for sub_id in subaccount_ids:
            try:
                # Это требует API ключей субсчета - упрощено здесь
                # На практике используйте аутентификацию субсчета
                report = {
                    "sub_id": sub_id,
                    "equity": Decimal("0"),  # Было бы получено от субсчета
                    "position_value": Decimal("0"),
                    "margin_ratio": Decimal("0")
                }
                subaccount_reports.append(report)
                
            except Exception as e:
                subaccount_reports.append({
                    "sub_id": sub_id,
                    "error": str(e)
                })
        
        # Расчет метрик концентрации
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
        Расчет оценки диверсификации (0-1).
        
        1 = Идеальная диверсификация
        0 = Полная концентрация
        """
        if not concentration:
            return Decimal("0")
        
        # Индекс Херфиндаля-Хиршмана
        hhi = sum(pct ** 2 for pct in concentration.values())
        
        # Конвертация в оценку диверсификации
        n = len(concentration)
        if n == 1:
            return Decimal("0")
        
        max_hhi = Decimal("1") / n  # Равномерное распределение
        diversification = (Decimal("1") - hhi) / (Decimal("1") - max_hhi)
        
        return max(Decimal("0"), min(Decimal("1"), diversification))
    
    async def emergency_liquidation(
        self,
        subaccount_id: str,
        reason: str = "Нарушение лимита риска"
    ) -> bool:
        """
        Экстренная ликвидация субсчета.
        
        Шаги:
        1. Заморозка субсчета (предотвращение новых ордеров)
        2. Отмена всех открытых ордеров
        3. Закрытие всех позиций
        4. Перевод оставшегося капитала на мастер
        """
        try:
            # 1. Заморозка субсчета
            await self.sub_manager.freeze_subaccount(subaccount_id)
            
            # 2. Отмена всех ордеров и закрытие позиций
            # (Требует API ключей субсчета)
            
            # 3. Перевод оставшегося баланса
            # (Реализация зависит от доступных балансов)
            
            return True
            
        except Exception as e:
            print(f"Экстренная ликвидация не удалась: {e}")
            return False
```

---

## 6. Обработка ошибок

### 6.1 Распространенные коды ошибок API

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Callable
import asyncio

class BybitErrorCode(int, Enum):
    """
    Распространенные коды ошибок Bybit API.
    
    Источник: Документация Bybit API
    """
    # Успех
    SUCCESS = 0
    
    # Ошибки запроса (1xxx)
    PARAM_ERROR = 10001
    INVALID_API_KEY = 10003
    INVALID_SIGN = 10004
    PERMISSION_DENIED = 10005
    TOO_MANY_VISITS = 10006  # Превышен лимит частоты
    
    # Ошибки торговли (11xxx)
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
    
    # Ошибки позиций (12xxx)
    POSITION_MODE_NOT_MODIFIED = 120001
    LEVERAGE_NOT_MODIFIED = 120002
    POSITION_IS_CROSS_MARGIN = 120003
    POSITION_SIZE_EXCEEDS_LIMIT = 120004
    
    # Ошибки счета (13xxx)
    ACCOUNT_NOT_FOUND = 130001
    BORROW_FAILED = 130002
    REPAY_FAILED = 130003


@dataclass
class BybitAPIError(Exception):
    """Исключение ошибки Bybit API."""
    code: int
    message: str
    
    def __str__(self):
        return f"BybitAPIError {self.code}: {self.message}"
    
    def is_retryable(self) -> bool:
        """Проверка, является ли ошибка потенциально повторяемой."""
        retryable_codes = [
            BybitErrorCode.TOO_MANY_VISITS,
            BybitErrorCode.ORDER_STATUS_NOT_MODIFIABLE,
            500,  # Ошибки сервера
            502,
            503,
            504,
        ]
        return self.code in retryable_codes
    
    def requires_user_action(self) -> bool:
        """Проверка, требует ли ошибка ручного вмешательства."""
        action_codes = [
            BybitErrorCode.INVALID_API_KEY,
            BybitErrorCode.INVALID_SIGN,
            BybitErrorCode.PERMISSION_DENIED,
            BybitErrorCode.LIQUIDATION_IN_PROGRESS,
        ]
        return self.code in action_codes


class ErrorCodeHelper:
    """Помощник для понимания и обработки кодов ошибок."""
    
    ERROR_DESCRIPTIONS = {
        BybitErrorCode.SUCCESS: "Успех",
        BybitErrorCode.PARAM_ERROR: "Ошибка параметра запроса - проверьте запрос",
        BybitErrorCode.INVALID_API_KEY: "Неверный API ключ - проверьте учетные данные",
        BybitErrorCode.INVALID_SIGN: "Неверная подпись - проверьте реализацию подписи",
        BybitErrorCode.PERMISSION_DENIED: "Доступ запрещен - проверьте разрешения API ключа",
        BybitErrorCode.TOO_MANY_VISITS: "Превышен лимит частоты - замедлите запросы",
        BybitErrorCode.ORDER_NOT_FOUND: "Ордер не найден - возможно, был отменен/исполнен",
        BybitErrorCode.ORDER_STATUS_NOT_MODIFIABLE: "Ордер нельзя изменить в текущем состоянии",
        BybitErrorCode.INSUFFICIENT_BALANCE: "Недостаточно баланса для ордера",
        BybitErrorCode.MARGIN_INSUFFICIENT: "Недостаточно маржи для позиции",
        BybitErrorCode.ORDER_PRICE_TOO_HIGH: "Цена ордера выше максимально допустимой",
        BybitErrorCode.ORDER_PRICE_TOO_LOW: "Цена ордера ниже минимально допустимой",
        BybitErrorCode.ORDER_QTY_TOO_LARGE: "Количество ордера превышает максимум",
        BybitErrorCode.ORDER_QTY_TOO_SMALL: "Количество ордера ниже минимума",
    }
    
    @classmethod
    def get_description(cls, code: int) -> str:
        """Получение читаемого описания кода ошибки."""
        return cls.ERROR_DESCRIPTIONS.get(code, f"Неизвестный код ошибки: {code}")
```

### 6.2 Стратегии повторных попыток

```python
import random
from typing import Type, Tuple

class RetryStrategy:
    """
    Настраиваемая стратегия повторных попыток для API вызовов.
    
    Реализует:
    - Экспоненциальную задержку
    - Джиттер для предотвращения thundering herd
    - Паттерн circuit breaker
    - Максимальные лимиты повторов
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
        
        # Состояние circuit breaker
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_threshold = 5
        self.circuit_reset_timeout = 60.0
    
    def calculate_delay(self, attempt: int) -> float:
        """Расчет задержки с экспоненциальной задержкой и джиттером."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Добавление случайного джиттера (0-50% от задержки)
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay
    
    async def execute(self, coro, *args, **kwargs):
        """
        Выполнение корутины с логикой повторных попыток.
        
        Использование:
            result = await retry_strategy.execute(api_call, param1, param2)
        """
        # Проверка circuit breaker
        if self.circuit_open:
            raise CircuitBreakerOpen("Circuit breaker открыт")
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await coro(*args, **kwargs)
                
                # Успех - сброс circuit breaker
                self.failure_count = 0
                
                return result
                
            except self.retryable_exceptions as e:
                last_exception = e
                
                # Проверка, является ли ошибка повторяемой
                if isinstance(e, BybitAPIError) and not e.is_retryable():
                    raise
                
                # Обновление circuit breaker
                self.failure_count += 1
                if self.failure_count >= self.circuit_threshold:
                    self.circuit_open = True
                    asyncio.create_task(self._reset_circuit())
                    raise CircuitBreakerOpen("Circuit breaker открыт из-за сбоев")
                
                # Не повторять на последней попытке
                if attempt == self.max_retries:
                    break
                
                # Расчет задержки и ожидание
                delay = self.calculate_delay(attempt)
                await asyncio.sleep(delay)
        
        # Все попытки исчерпаны
        raise MaxRetriesExceeded(f"Не удалось после {self.max_retries} попыток") from last_exception
    
    async def _reset_circuit(self):
        """Сброс circuit breaker после таймаута."""
        await asyncio.sleep(self.circuit_reset_timeout)
        self.circuit_open = False
        self.failure_count = 0


class CircuitBreakerOpen(Exception):
    """Circuit breaker открыт."""
    pass

class MaxRetriesExceeded(Exception):
    """Превышено максимальное количество попыток."""
    pass


class OrderRetryPolicy:
    """
    Специализированная политика повторных попыток для операций с ордерами.
    
    Разные стратегии повторов для разных типов ордеров:
    - Рыночные ордера: Быстрый повтор (чувствительность к цене)
    - Лимитные ордера: Стандартный повтор
    - Условные ордера: Большее окно повтора
    """
    
    @staticmethod
    def for_market_order() -> RetryStrategy:
        """Стратегия повторов для рыночных ордеров."""
        return RetryStrategy(
            max_retries=2,
            base_delay=0.5,
            max_delay=5.0
        )
    
    @staticmethod
    def for_limit_order() -> RetryStrategy:
        """Стратегия повторов для лимитных ордеров."""
        return RetryStrategy(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0
        )
    
    @staticmethod
    def for_cancel_order() -> RetryStrategy:
        """Стратегия повторов для операций отмены."""
        return RetryStrategy(
            max_retries=5,
            base_delay=0.5,
            max_delay=10.0
        )
```

### 6.3 Обработка частичного исполнения

```python
from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal

@dataclass
class PartialFillInfo:
    """Информация о частичном исполнении."""
    order_id: str
    filled_qty: Decimal
    remaining_qty: Decimal
    avg_fill_price: Decimal
    fill_count: int
    last_fill_time: Optional[int] = None
    
    @property
    def fill_percentage(self) -> Decimal:
        """Расчет процента исполнения."""
        total = self.filled_qty + self.remaining_qty
        if total == 0:
            return Decimal("0")
        return self.filled_qty / total
    
    def is_fully_filled(self) -> bool:
        """Проверка полного исполнения ордера."""
        return self.remaining_qty == 0
    
    def is_partially_filled(self) -> bool:
        """Проверка наличия частичных исполнений."""
        return self.filled_qty > 0 and self.remaining_qty > 0


class PartialFillHandler:
    """
    Обработчик сценариев частичного исполнения.
    
    Стратегии обработки частичных исполнений:
    1. Ожидание оставшегося исполнения
    2. Отмена оставшегося и повторная подача
    3. Принятие частичного и корректировка позиции
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
        Обработка частичного исполнения на основе стратегии.
        
        Стратегии:
        - "wait": Ожидание исполнения оставшегося количества
        - "cancel": Отмена оставшегося и принятие частичного
        - "resubmit": Отмена и повторная подача оставшегося количества
        """
        # Получение текущего статуса ордера
        order = await self.order_manager.get_order(order_id, symbol)
        
        fill_info = PartialFillInfo(
            order_id=order_id,
            filled_qty=Decimal(order.get("cumExecQty", "0")),
            remaining_qty=Decimal(order.get("leavesQty", "0")),
            avg_fill_price=Decimal(order.get("avgPrice", "0")),
            fill_count=int(order.get("cumExecQty", 0))
        )
        
        if strategy == "wait":
            # Ожидание оставшегося исполнения
            fill_info = await self._wait_for_fill(
                order_id, symbol, max_wait_seconds
            )
        
        elif strategy == "cancel":
            # Отмена оставшегося
            if fill_info.remaining_qty > 0:
                await self.order_manager.cancel_order(
                    symbol=symbol,
                    order_id=order_id
                )
        
        elif strategy == "resubmit":
            # Отмена и повторная подача
            if fill_info.remaining_qty > 0:
                await self.order_manager.cancel_order(
                    symbol=symbol,
                    order_id=order_id
                )
                # Повторная подача оставшегося количества
                # (Реализация зависит от деталей оригинального ордера)
        
        self.partial_fills[order_id] = fill_info
        return fill_info
    
    async def _wait_for_fill(
        self,
        order_id: str,
        symbol: str,
        max_wait_seconds: int
    ) -> PartialFillInfo:
        """Ожидание полного исполнения ордера."""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            order = await self.order_manager.get_order(order_id, symbol)
            
            filled_qty = Decimal(order.get("cumExecQty", "0"))
            remaining_qty = Decimal(order.get("leavesQty", "0"))
            
            if remaining_qty == 0:
                # Полностью исполнен
                return PartialFillInfo(
                    order_id=order_id,
                    filled_qty=filled_qty,
                    remaining_qty=remaining_qty,
                    avg_fill_price=Decimal(order.get("avgPrice", "0")),
                    fill_count=int(order.get("cumExecQty", 0))
                )
            
            # Проверка таймаута
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait_seconds:
                return PartialFillInfo(
                    order_id=order_id,
                    filled_qty=filled_qty,
                    remaining_qty=remaining_qty,
                    avg_fill_price=Decimal(order.get("avgPrice", "0")),
                    fill_count=int(order.get("cumExecQty", 0))
                )
            
            await asyncio.sleep(1)  # Опрос каждую секунду
```


### 6.4 Восстановление при сбое соединения

```python
import logging
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """Состояние WebSocket соединения."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class ConnectionRecoveryManager:
    """
    Менеджер для восстановления WebSocket соединения.
    
    Обрабатывает:
    - Автоматическое переподключение с задержкой
    - Восстановление состояния после переподключения
    - Синхронизацию состояния ордеров
    - Проверки целостности данных
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
        
        # Callbacks для изменений состояния
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_reconnect: Optional[Callable] = None
    
    async def connect_with_recovery(self):
        """Подключение с автоматическим восстановлением."""
        self.state = ConnectionState.CONNECTING
        
        try:
            await self.ws_client.connect()
            self.state = ConnectionState.CONNECTED
            self.reconnect_count = 0
            
            if self.on_connect:
                await self.on_connect()
            
            # Запуск мониторинга соединения
            asyncio.create_task(self._monitor_connection())
            
        except Exception as e:
            logger.error(f"Начальное подключение не удалось: {e}")
            await self._attempt_reconnect()
    
    async def _monitor_connection(self):
        """Мониторинг здоровья соединения."""
        while self.state == ConnectionState.CONNECTED:
            try:
                # Проверка, живо ли соединение
                if hasattr(self.ws_client, 'ws') and self.ws_client.ws:
                    if not self.ws_client.ws.open:
                        raise ConnectionError("WebSocket неожиданно закрыт")
                
                # Обновление времени последнего сообщения
                self.last_message_time = asyncio.get_event_loop().time()
                
                await asyncio.sleep(5)  # Проверка каждые 5 секунд
                
            except Exception as e:
                logger.error(f"Ошибка мониторинга соединения: {e}")
                await self._attempt_reconnect()
                break
    
    async def _attempt_reconnect(self):
        """Попытка переподключения с экспоненциальной задержкой."""
        self.state = ConnectionState.RECONNECTING
        
        while self.reconnect_count < self.max_reconnect_attempts:
            try:
                # Расчет задержки
                delay = min(
                    self.reconnect_base_delay * (2 ** self.reconnect_count),
                    self.max_reconnect_delay
                )
                
                logger.info(f"Переподключение через {delay:.1f}с (попытка {self.reconnect_count + 1})")
                await asyncio.sleep(delay)
                
                # Попытка переподключения
                await self.ws_client.connect()
                
                # Повторная подписка на каналы
                await self._resubscribe()
                
                self.state = ConnectionState.CONNECTED
                self.reconnect_count = 0
                
                if self.on_reconnect:
                    await self.on_reconnect()
                
                # Перезапуск мониторинга
                asyncio.create_task(self._monitor_connection())
                
                return
                
            except Exception as e:
                self.reconnect_count += 1
                logger.error(f"Попытка переподключения {self.reconnect_count} не удалась: {e}")
        
        # Превышено максимальное количество попыток переподключения
        self.state = ConnectionState.FAILED
        logger.critical("Превышено максимальное количество попыток переподключения. Требуется ручное вмешательство.")
    
    async def _resubscribe(self):
        """Повторная подписка на каналы после переподключения."""
        # Повторная подписка на ранее подписанные каналы
        if hasattr(self.ws_client, 'subscriptions'):
            for subscription in self.ws_client.subscriptions:
                try:
                    await self.ws_client.subscribe(subscription)
                except Exception as e:
                    logger.error(f"Не удалось повторно подписаться на {subscription}: {e}")


class OrderStateSynchronizer:
    """
    Синхронизирует состояние ордеров после восстановления соединения.
    
    Гарантирует, что ордера не теряются во время отключений.
    """
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
        self.pending_orders: Dict[str, Dict] = {}
    
    async def sync_orders(self, symbol: Optional[str] = None):
        """
        Синхронизация состояния ордеров с биржей.
        
        Шаги:
        1. Запрос всех открытых ордеров
        2. Сравнение с локальными ожидающими ордерами
        3. Обновление состояния при расхождениях
        4. Обработка неизвестных исполнений
        """
        # Получение открытых ордеров с биржи
        open_orders = await self.order_manager.get_open_orders(symbol)
        
        # Создание множества активных ID ордеров
        active_order_ids = {order["orderId"] for order in open_orders}
        
        # Проверка отсутствующих ордеров
        for order_id, local_order in self.pending_orders.items():
            if order_id not in active_order_ids:
                # Ордер не найден - проверка, исполнен или отменен
                order_history = await self.order_manager.get_order_history(
                    symbol=local_order.get("symbol"),
                    order_id=order_id
                )
                
                if order_history:
                    # Обновление локального состояния
                    self._update_order_state(order_id, order_history[0])
                else:
                    # Неизвестное состояние - логирование для расследования
                    logger.warning(f"Состояние ордера {order_id} неизвестно после синхронизации")
        
        # Обновление ожидающих ордеров текущим состоянием
        for order in open_orders:
            self.pending_orders[order["orderId"]] = order
        
        return self.pending_orders
    
    def _update_order_state(self, order_id: str, order_data: Dict):
        """Обновление локального состояния ордера."""
        self.pending_orders[order_id] = order_data
        
        # Удаление, если терминальное состояние
        if order_data.get("orderStatus") in ["Filled", "Cancelled", "Rejected"]:
            del self.pending_orders[order_id]
```

---

## Приложение: Полный пример интеграции

```python
"""
Полный пример интеграции с Bybit

Этот пример демонстрирует готовую к production интеграцию с Bybit API V5,
включая все концепции, рассмотренные в этой документации.
"""

import asyncio
import os
from decimal import Decimal
from typing import Optional
import structlog

# Настройка логирования
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
    Пример торгового бота для Bybit, готового к production.
    
    Возможности:
    - Безопасная аутентификация (HMAC/RSA)
    - Ограничение частоты запросов
    - Обработка ошибок с повторами
    - WebSocket для данных в реальном времени
    - Управление рисками позиций
    - Управление ордерами с обработкой частичных исполнений
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        use_rsa: bool = False
    ):
        self.testnet = testnet
        
        # Инициализация аутентификации
        if use_rsa:
            self.auth = BybitRSAAuth(api_key, api_secret)
        else:
            self.auth = BybitHMACAuth(api_key, api_secret)
        
        # Инициализация менеджеров
        self.account_manager = AccountManager(self.auth, testnet)
        self.order_manager = OrderManager(self.auth, testnet)
        self.batch_manager = BatchOrderManager(self.auth, testnet)
        self.trading_stop_manager = TradingStopManager(self.auth, testnet)
        
        # Инициализация rate limiter
        self.rate_limiter = RateLimiter()
        
        # Инициализация стратегий повторов
        self.market_order_retry = OrderRetryPolicy.for_market_order()
        self.limit_order_retry = OrderRetryPolicy.for_limit_order()
        
        # Состояние
        self.running = False
        self.ws_client: Optional[BybitPrivateWebSocket] = None
    
    async def initialize(self):
        """Инициализация бота."""
        logger.info("bot.initializing", testnet=self.testnet)
        
        # Проверка доступа к счету
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
        
        # Инициализация WebSocket
        self.ws_client = BybitPrivateWebSocket(
            self.auth.api_key,
            self.auth.api_secret,
            self.testnet
        )
        
        await self.ws_client.connect()
        
        # Подписка на обновления
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
        Размещение сделки с комплексным управлением рисками.
        
        Args:
            symbol: Торговая пара
            side: "Buy" или "Sell"
            qty: Количество ордера
            price: Лимитная цена (None для рыночного ордера)
            stop_loss_pct: Процент стоп-лосса (например, 0.02 для 2%)
            take_profit_pct: Процент тейк-профита (например, 0.06 для 6%)
        """
        try:
            # 1. Проверка баланса счета
            account = await self.account_manager.get_wallet_balance()
            
            # 2. Расчет стоимости позиции
            if price:
                position_value = qty * price
            else:
                # Получение текущей цены для рыночного ордера
                market_client = BybitMarketClient(testnet=self.testnet)
                async with market_client:
                    ticker = await market_client.get_ticker(symbol)
                    position_value = qty * ticker["last"]
            
            # 3. Проверка достаточности маржи
            if position_value > account.available_balance * Decimal("0.95"):
                raise ValueError("Недостаточно маржи для сделки")
            
            # 4. Размещение ордера
            if price:
                # Лимитный ордер
                result = await self.limit_order_retry.execute(
                    self.order_manager.place_limit_order,
                    symbol=symbol,
                    side=OrderSide(side),
                    qty=qty,
                    price=price,
                    post_only=True
                )
            else:
                # Рыночный ордер
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
            
            # 5. Установка стоп-лосс / тейк-профит, если указаны
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
        """Обработка обновлений ордеров от WebSocket."""
        logger.info(
            "order.update",
            order_id=order_data.get("orderId"),
            status=order_data.get("orderStatus"),
            filled_qty=order_data.get("cumExecQty"),
            remaining_qty=order_data.get("leavesQty")
        )
    
    def _on_position_update(self, position_data: Dict):
        """Обработка обновлений позиций от WebSocket."""
        logger.info(
            "position.update",
            symbol=position_data.get("symbol"),
            size=position_data.get("size"),
            unrealised_pnl=position_data.get("unrealisedPnl")
        )
    
    def _on_wallet_update(self, wallet_data: Dict):
        """Обработка обновлений кошелька от WebSocket."""
        logger.info(
            "wallet.update",
            coin=wallet_data.get("coin"),
            equity=wallet_data.get("equity")
        )
    
    async def shutdown(self):
        """Корректное завершение работы."""
        logger.info("bot.shutting_down")
        self.running = False
        
        if self.ws_client:
            await self.ws_client.close()
        
        logger.info("bot.shutdown_complete")


# Пример использования
async def main():
    """Точка входа."""
    
    # Загрузка учетных данных из окружения
    api_key = os.getenv("BYBIT_API_KEY", "your_api_key")
    api_secret = os.getenv("BYBIT_API_SECRET", "your_api_secret")
    testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
    
    # Создание бота
    bot = BybitTradingBot(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )
    
    try:
        # Инициализация
        await bot.initialize()
        
        # Пример: Размещение лимитного ордера на покупку со стоп-лоссом
        result = await bot.place_trade_with_risk_management(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("0.01"),
            price=Decimal("25000"),
            stop_loss_pct=Decimal("0.03"),  # 3% стоп-лосс
            take_profit_pct=Decimal("0.06")  # 6% тейк-профит
        )
        
        print(f"Ордер размещен: {result}")
        
        # Продолжение работы некоторое время
        await asyncio.sleep(60)
        
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Быстрый справочник

### Распространенные символы

| Символ | Описание |
|--------|----------|
| BTCUSDT | Биткоин бессрочный |
| ETHUSDT | Эфириум бессрочный |
| SOLUSDT | Солана бессрочный |

### Временные интервалы

| Интервал | Значение |
|----------|----------|
| 1 минута | 1 |
| 5 минут | 5 |
| 15 минут | 15 |
| 1 час | 60 |
| 4 часа | 240 |
| 1 день | D |

### Поток статусов ордера

```
Created -> New -> PartiallyFilled -> Filled
                      |
                      -> Cancelled
```

### Важные напоминания

1. **Всегда сначала используйте Testnet** - Тестируйте все стратегии на testnet перед live торговлей
2. **Внедряйте надлежащее управление рисками** - Никогда не рискуйте больше, чем можете позволить потерять
3. **Следите за лимитами частоты** - Уважайте API лимиты частоты, чтобы избежать банов
4. **Обрабатывайте ошибки корректно** - Всегда внедряйте логику повторов и обработку ошибок
5. **Используйте субсчета для изоляции** - Разделяйте разные стратегии с помощью субсчетов
6. **Защищайте свои API ключи** - Никогда не коммитьте API ключи в систему контроля версий
7. **Следите за ставками финансирования** - Высокое финансирование может быстро съесть прибыль
8. **Понимайте риски ликвидации** - Всегда знайте свою цену ликвидации

---

*Версия документа: 1.0.0*  
*По вопросам или обновлениям обращайтесь к официальной документации Bybit API*
