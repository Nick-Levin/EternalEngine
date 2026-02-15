# ADR 001: Using Pybit Over CCXT for Bybit Integration

**Status:** Accepted  
**Date:** 2026-02-13  
**Deciders:** Development Team  
**Context:** Bybit Demo Trading API integration

---

## Context and Problem Statement

The project initially planned to use CCXT (the standard cryptocurrency trading library) for exchange integration. However, Bybit's Demo Trading environment requires specific authentication and endpoint handling that CCXT doesn't fully support for demo trading mode.

## Decision Drivers

- Must support Bybit Demo Trading API (api-demo.bybit.com)
- Must handle subaccount isolation for 4-engine architecture
- Must support both spot and linear (perpetual) markets
- Async operation required for non-blocking trading

## Considered Options

### Option 1: CCXT (Original Plan)
**Pros:**
- Universal exchange abstraction
- Well-tested, large community
- Built-in rate limiting

**Cons:**
- Limited support for Bybit Demo Trading mode
- Subaccount handling requires workarounds
- Some Bybit-specific features not available

### Option 2: Pybit (Official Bybit SDK)
**Pros:**
- Official Bybit SDK, full API coverage
- Explicit support for Demo Trading (`demo=True`)
- Native subaccount handling
- Direct access to all Bybit features

**Cons:**
- Bybit-only (not portable to other exchanges)
- Sync-only (needs async wrapper)
- Different parameter naming (orderType vs type)

### Option 3: Direct HTTP API
**Pros:**
- Full control over requests
- No dependencies

**Cons:**
- Must implement authentication, rate limiting, error handling
- High maintenance burden

## Decision

**Chosen Option: Option 2 (Pybit with Async Wrapper)**

We created `PybitDemoClient` - an async wrapper around pybit that:
1. Handles Demo Trading mode with `demo=True`
2. Provides async interface via `asyncio.to_thread()`
3. Maps ccxt-style parameters to pybit format
4. Manages subaccount-specific clients

## Consequences

### Positive
- Full access to Bybit Demo Trading API
- Proper subaccount isolation
- Can use `marketUnit='quoteCoin'` for spot buys
- Direct control over order parameters

### Negative
- Exchange lock-in (Bybit only)
- Must maintain async wrapper
- Parameter naming differences from ccxt

## Implementation

```python
# src/exchange/bybit_client.py
class PybitDemoClient:
    def __init__(self, api_key, api_secret, demo=True):
        self.session = HTTP(
            api_key=api_key,
            api_secret=api_secret,
            demo=demo  # Demo trading mode
        )
    
    async def create_order(self, ...):
        # Async wrapper
        return await asyncio.to_thread(
            self._create_order_sync, ...
        )
```

## References
- [DEVLOG.md](../../DEVLOG.md) - PybitDemoClient Integration section
- [Bybit API Docs](https://bybit-exchange.github.io/docs/)
- [Pybit GitHub](https://github.com/bybit-exchange/pybit)
