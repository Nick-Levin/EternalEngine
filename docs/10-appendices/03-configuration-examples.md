# THE ETERNAL ENGINE
## Appendix C: Configuration Examples

---

## 1. Main System Configuration

```yaml
# config/production.yaml
system:
  name: "The Eternal Engine"
  version: "1.0.0"
  environment: "production"
  timezone: "UTC"
  log_level: "INFO"
  dry_run: false
  auto_restart: true

# Capital allocation
allocation:
  core_hodl: 0.60
  trend: 0.20
  funding: 0.15
  tactical: 0.05

# Exchange configuration
exchange:
  name: "bybit"
  api_version: "v5"
  testnet: false
  rate_limits:
    rest: 120
    websocket: 1000
  timeout: 30
  retry_attempts: 3

# Risk management
risk_management:
  circuit_breakers:
    level_1:
      drawdown_threshold: 0.10
      action: "reduce_position_size"
      reduction_factor: 0.25
    level_2:
      drawdown_threshold: 0.15
      action: "reduce_and_pause"
      reduction_factor: 0.50
    level_3:
      drawdown_threshold: 0.20
      action: "close_directional"
      halt_trading: true
    level_4:
      drawdown_threshold: 0.25
      action: "emergency_liquidation"
      halt_trading: true
  position_sizing:
    method: "fractional_kelly"
    kelly_fraction: 0.125
    max_risk_per_trade: 0.01
    max_position_pct: 0.05
    max_leverage: 2.0

# Monitoring
monitoring:
  dashboard:
    enabled: true
    port: 8080
  alerts:
    enabled: true
    channels:
      - type: "telegram"
        bot_token: "${TELEGRAM_BOT_TOKEN}"
        chat_id: "${TELEGRAM_CHAT_ID}"
  reports:
    daily:
      enabled: true
      time: "00:00"
    weekly:
      enabled: true
      day: "sunday"
    monthly:
      enabled: true
      day: 1
```

## 2. CORE-HODL Configuration

```yaml
# config/engines/core_hodl.yaml
engine:
  name: "CORE-HODL"
  enabled: true
  allocation: 0.60

assets:
  btc:
    symbol: "BTC"
    target_allocation: 0.667
    min_allocation: 0.55
    max_allocation: 0.80
  eth:
    symbol: "ETH"
    target_allocation: 0.333
    min_allocation: 0.20
    max_allocation: 0.45

rebalancing:
  enabled: true
  frequency: "quarterly"
  threshold: 0.10
  execution:
    order_type: "limit"
    post_only: true

yield:
  enabled: true
  eth_staking:
    enabled: true
    min_apy: 2.0
```

## 3. TREND Engine Configuration

```yaml
# config/engines/trend.yaml
engine:
  name: "TREND"
  enabled: true
  allocation: 0.20

markets:
  - symbol: "BTC-PERP"
    allocation: 0.60
  - symbol: "ETH-PERP"
    allocation: 0.40

indicators:
  ema_fast:
    type: "ema"
    period: 50
  ema_slow:
    type: "ema"
    period: 200
  adx:
    type: "adx"
    period: 14
    threshold: 25
  atr:
    type: "atr"
    period: 14

entry:
  long:
    conditions:
      - indicator: "price"
        operator: ">"
        reference: "ema_slow"
      - indicator: "ema_fast"
        operator: ">"
        reference: "ema_slow"
      - indicator: "adx"
        operator: ">"
        value: 25

exit:
  long_exit:
    - condition: "price_crosses_below"
      indicator: "ema_slow"
  stop_loss:
    type: "atr_based"
    multiplier: 2.0
  trailing_stop:
    enabled: true
    activation_r_multiple: 1.0
    distance_atr_multiplier: 3.0

position_sizing:
  method: "risk_based"
  risk_per_trade: 0.01
  max_leverage: 2.0
```

## 4. Environment Variables

```bash
# .env.production
ENVIRONMENT=production
LOG_LEVEL=INFO

# Bybit API Keys
BYBIT_MASTER_API_KEY=your_key
BYBIT_MASTER_API_SECRET=your_secret

# Database
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://host:port/0

# Alerts
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# Security
ENCRYPTION_KEY=your_key
JWT_SECRET=your_secret
```

See full documentation in repository for complete configuration.
