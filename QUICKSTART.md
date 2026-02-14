# The Eternal Engine - Quick Start Guide

> **Get running in 30 minutes** | A beginner-friendly guide to autonomous crypto wealth compounding

---

## ⚠️ CRITICAL SAFETY WARNINGS

**READ THIS BEFORE PROCEEDING:**

1. **NEVER trade with money you cannot afford to lose.** Start with paper trading for at least 2 weeks.
2. **Cryptocurrency trading carries substantial risk** including potential loss of entire capital.
3. **Minimum recommended capital:** $10,000 (smaller amounts may not justify the operational overhead).
4. **This is NOT financial advice.** Consult qualified professionals before investing.
5. **Understand the risks:** 35%+ drawdowns are expected. Can you handle seeing your portfolio down 35%?
6. **Prohibited jurisdictions:** Check local laws—crypto trading is banned in some countries.

**By proceeding, you acknowledge you have read and understood the [Risk Disclosure](docs/10-appendices/04-risk-disclosure.md).**

---

## 📋 Prerequisites

### Required Knowledge
- Basic Python familiarity
- Understanding of cryptocurrency markets
- Familiarity with exchange trading concepts (spot, futures, leverage)
- Basic command line / terminal usage

### Required Accounts & Capital
| Item | Requirement |
|------|-------------|
| **Python** | Version 3.11 or higher |
| **Bybit Account** | Verified account with UTA enabled |
| **Recommended Capital** | $10,000+ (minimum $5,000) |
| **Investment Horizon** | 5+ years recommended |
| **Operating System** | Linux, macOS, or Windows with WSL |

---

## Quick Installation (One-Liner)

The fastest way to get started:

```bash
# Clone and setup in one go
git clone https://github.com/Nick-Levin/BybitTrader.git
cd BybitTrader
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This will:
- ✅ Check Python version (3.11+)
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Create necessary directories (logs, data, config)
- ✅ Copy `.env.example` to `.env`
- ✅ Prompt for API keys (or use DEMO keys)
- ✅ Initialize the database
- ✅ Run configuration check

---

## Step 1: Clone and Setup (5 minutes)

### 1.1 Clone the Repository
```bash
# Clone the repository
git clone https://github.com/Nick-Levin/BybitTrader.git
cd BybitTrader

# Or download and extract the ZIP
```

### 1.2 Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 1.3 Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import ccxt, pandas, structlog; print('✓ Dependencies installed')"
```

### 1.4 Copy Environment Configuration
```bash
# Copy example environment file
cp .env.example .env

# Edit the .env file with your settings
# We'll configure API keys in Step 3
```

---

## Step 2: Bybit Account Setup (10 minutes)

### 2.1 Create Bybit Account
1. Visit [bybit.com](https://www.bybit.com)
2. Sign up and complete identity verification (KYC)
3. **Enable 2FA** (Google Authenticator recommended)

### 2.2 Enable UTA (Unified Trading Account)
1. Log in to Bybit
2. Go to **Assets** → **Unified Trading Account**
3. Click **Upgrade to UTA**
4. Complete the upgrade process

### 2.3 Create Subaccounts (Recommended)
The Eternal Engine uses subaccount isolation for risk management:

| Subaccount | Purpose | Suggested Allocation |
|------------|---------|---------------------|
| **CORE** | Spot HODL (BTC/ETH) | 60% of capital |
| **TREND-1** | Primary trend following | 15% of capital |
| **TREND-2** | Alternative trend params | 5% of capital |
| **FUNDING** | Funding rate arbitrage | 15% of capital |
| **TACTICAL** | Crisis deployment | 5% of capital |

**To create subaccounts:**
1. Go to **Account & Security** → **Subaccount**
2. Click **Create Subaccount**
3. Create each subaccount with the names above
4. Enable **Asset Transfer** permissions between subaccounts

### 2.4 Generate API Keys

**⚠️ SECURITY WARNING: Treat API keys like passwords!**

For each subaccount (and master account):
1. Switch to the subaccount
2. Go to **Account & Security** → **API Management**
3. Click **Create New Key**
4. Select **System-Generated API Keys** (HMAC recommended for beginners)
5. Enable these permissions:
   - ✅ **Read** (required)
   - ✅ **Trade** (required)
   - ❌ Withdraw (KEEP DISABLED for security)
6. Add **IP Whitelist** (strongly recommended):
   - Get your IP: `curl ifconfig.me`
   - Add your server's IP address
7. Save the **API Key** and **API Secret** securely

### 2.5 Fund Your Accounts

**Start with Paper/Demo Trading!**

When ready for live trading:
1. Transfer USDT to master account
2. Distribute to subaccounts per allocation table above
3. Ensure each subaccount has sufficient margin for its strategy

---

## Step 3: Configuration (5 minutes)

### 3.1 Configure Environment Variables

Edit your `.env` file:

```bash
# Bybit API Configuration (Master Account)
BYBIT_API_KEY=your_master_api_key_here
BYBIT_API_SECRET=your_master_api_secret_here
BYBIT_TESTNET=true  # Set to false for live trading

# Trading Mode
TRADING_MODE=paper  # Options: paper, live

# Default Trading Pairs
DEFAULT_SYMBOLS=BTCUSDT,ETHUSDT

# Risk Management (Conservative Defaults)
MAX_POSITION_PCT=5          # Max 5% per position
MAX_DAILY_LOSS_PCT=2        # Stop trading after 2% daily loss
MAX_WEEKLY_LOSS_PCT=5       # Stop trading after 5% weekly loss
ENABLE_STOP_LOSS=true
STOP_LOSS_PCT=3
ENABLE_TAKE_PROFIT=true
TAKE_PROFIT_PCT=6
MAX_CONCURRENT_POSITIONS=3

# Strategy Settings
DEFAULT_STRATEGY=dca
DCA_INTERVAL_HOURS=24
DCA_AMOUNT_USDT=100

# Notifications (Optional but Recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
NOTIFY_ON_TRADE=true
NOTIFY_ON_ERROR=true

# Database
DATABASE_URL=sqlite:///./trading_bot.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading_bot.log
```

### 3.2 Configure Subaccount API Keys (Advanced)

For multi-engine operation, create a config file:

```yaml
# config/subaccounts.yaml
subaccounts:
  core:
    api_key: "CORE_API_KEY"
    api_secret: "CORE_API_SECRET"
    allocation: 0.60
    strategy: core_hodl
    
  trend_1:
    api_key: "TREND1_API_KEY"
    api_secret: "TREND1_API_SECRET"
    allocation: 0.15
    strategy: trend_following
    
  trend_2:
    api_key: "TREND2_API_KEY"
    api_secret: "TREND2_API_SECRET"
    allocation: 0.05
    strategy: trend_following_alt
    
  funding:
    api_key: "FUNDING_API_KEY"
    api_secret: "FUNDING_API_SECRET"
    allocation: 0.15
    strategy: funding_arbitrage
    
  tactical:
    api_key: "TACTICAL_API_KEY"
    api_secret: "TACTICAL_API_SECRET"
    allocation: 0.05
    strategy: tactical_deployment
```

### 3.3 Adjust Risk Parameters (Optional)

**Conservative Profile** (Recommended for beginners):
```bash
MAX_POSITION_PCT=3
MAX_DAILY_LOSS_PCT=1
MAX_WEEKLY_LOSS_PCT=3
MAX_CONCURRENT_POSITIONS=2
```

**Aggressive Profile** (For experienced traders only):
```bash
MAX_POSITION_PCT=10
MAX_DAILY_LOSS_PCT=3
MAX_WEEKLY_LOSS_PCT=8
MAX_CONCURRENT_POSITIONS=5
```

---

## Step 4: First Run (2 minutes)

### 4.1 Initialize Database
```bash
python main.py --init-db
```

### 4.2 Run Configuration Check
```bash
python main.py --check
```

**Expected output:**
```
✓ Configuration valid
  - API keys configured
  - Database connection OK
  - Risk parameters within bounds
```

### 4.3 Test API Connectivity
```bash
# Run in paper mode to test connectivity
python main.py --mode paper
```

**Watch for:**
- Successful connection messages
- Balance information display
- No error messages

**Press Ctrl+C to exit after confirming connectivity**

---

## Step 5: Understanding the 4 Engines

### CORE-HODL (60% of capital)
- **What it does:** Buys and holds BTC/ETH
- **When it works:** Always - long term wealth accumulation
- **Risk level:** Minimal
- **Typical activity:** DCA purchases, quarterly rebalancing

### TREND (20% of capital)
- **What it does:** Follows market trends with leverage
- **When it works:** Strong directional markets
- **Risk level:** Moderate
- **Typical activity:** Enters on 50/200 SMA crossovers, exits on reversals

### FUNDING (15% of capital)
- **What it does:** Market-neutral arbitrage between spot and futures
- **When it works:** When funding rates are positive
- **Risk level:** Low
- **Typical activity:** Collects funding payments every 8 hours

### TACTICAL (5% of capital)
- **What it does:** Waits for market crashes to deploy capital
- **When it works:** During major drawdowns (-50% to -70%)
- **Risk level:** Opportunistic
- **Typical activity:** Mostly idle, deploys on extreme fear

---

## Step 6: Paper Trading (START HERE!)

### 6.1 Enable Bybit Demo Trading
1. Log in to Bybit
2. Go to **Trade** → **Demo Trading**
3. Claim demo funds (usually 100,000 USDT)
4. Use demo trading API keys in `.env`

### 6.2 Run Paper Trading Mode
```bash
# Run the bot in paper trading mode
python main.py --mode paper
```

### 6.3 Monitor Paper Trading
**Check the logs:**
```bash
tail -f logs/trading_bot.log
```

**Expected behavior:**
- Bot initializes and connects to exchange
- Strategies start analyzing markets
- Orders are placed (simulated or real in demo)
- Logs show regular heartbeat/status updates

### 6.4 Paper Trading Checklist

Run paper trading for **at least 1-2 weeks** and verify:

- [ ] Bot starts without errors
- [ ] All engines initialize correctly
- [ ] Orders are being placed and filled (in demo)
- [ ] Risk management triggers work
- [ ] Telegram notifications arrive (if configured)
- [ ] Circuit breaker logic responds correctly
- [ ] You understand the daily P&L reports

---

## Step 7: Go Live (When Ready)

### 7.1 Pre-Flight Checklist

**DO NOT SKIP THIS:**

- [ ] Paper traded successfully for 1+ weeks
- [ ] You understand every strategy being used
- [ ] You've tested circuit breaker scenarios
- [ ] Telegram alerts are working
- [ ] You have emergency procedures documented
- [ ] You accept that 35%+ drawdowns are possible
- [ ] You have 6+ months living expenses saved separately

### 7.2 Start Small

**Begin with minimal capital:**
1. Transfer only $5,000-$10,000 to live subaccounts
2. Run for 1 month minimum
3. Monitor daily during first week
4. Gradually increase capital as confidence builds

### 7.3 Switch to Live Trading
```bash
# Edit .env
TRADING_MODE=live
BYBIT_TESTNET=false

# Run with live mode explicitly
python main.py --mode live
```

**⚠️ WARNING: This will use REAL money!**

### 7.4 Initial Live Monitoring

**First Week - Daily Checks:**
```bash
# Check status
python main.py --status

# View logs
tail -f logs/trading_bot.log

# Check positions on Bybit directly
```

**What to watch for:**
- Unexpected large positions
- Excessive trading frequency
- Failed orders or errors
- Drawdown approaching 10% (first circuit breaker)

### 7.5 Gradual Scaling

| Phase | Capital | Monitoring Frequency | Duration |
|-------|---------|---------------------|----------|
| **Phase 1** | $5K-$10K | Daily | 1 month |
| **Phase 2** | $20K-$30K | Every 2-3 days | 2 months |
| **Phase 3** | $50K-$100K | Weekly | 3 months |
| **Full Scale** | $100K+ | Monthly | Ongoing |

---

## 🛠️ Monitoring the System

### Basic Operations
```bash
# Run in paper trading mode (recommended for testing)
python main.py --mode paper

# Run in live trading mode (real money!)
python main.py --mode live

# Check current status
python main.py --status

# Validate configuration
python main.py --check
```

### Using Make (if Makefile exists)
```bash
# Paper trading
make run-paper

# Live trading
make run-live

# Check status
make status

# View logs
make logs

# Stop the bot
make stop

# Run tests
make test
```

### Monitoring Commands
```bash
# Real-time log monitoring
tail -f logs/trading_bot.log | grep "trade"

# Check database records
sqlite3 trading_bot.db "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;"

# Check system resources
htop  # or top on macOS

# Check network connectivity to Bybit
ping api.bybit.com
```

---

## 🔧 Troubleshooting

### API Key Issues
**Symptom:** "Invalid API key" or "Authentication failed"

**Solutions:**
1. Verify API key and secret are copied correctly (no extra spaces)
2. Check `BYBIT_TESTNET` setting matches your API key type
3. Ensure API key has "Trade" permission enabled
4. Verify IP whitelist includes your server IP
5. Try regenerating the API key

```bash
# Test API connectivity
python -c "
import ccxt
exchange = ccxt.bybit({
    'apiKey': 'YOUR_KEY',
    'secret': 'YOUR_SECRET',
    'sandbox': True,  # or False for live
})
print(exchange.fetch_balance())
"
```

### Rate Limiting
**Symptom:** "Rate limit exceeded" errors

**Solutions:**
1. Reduce polling frequency in configuration
2. Implement request batching
3. Check if you're running multiple instances
4. Wait 1 minute and retry

### Circuit Breaker Triggers
**Symptom:** "Circuit breaker activated - trading halted"

**What to do:**
1. **Don't panic** - this is the system protecting your capital
2. Review the drawdown level that triggered it
3. Assess market conditions
4. Decide whether to:
   - Wait for auto-recovery (Level 1-2)
   - Manually review and restart (Level 3-4)

### Connection Errors
**Symptom:** "Connection timeout" or "Network error"

**Solutions:**
1. Check internet connectivity
2. Verify Bybit status at [status.bybit.com](https://status.bybit.com)
3. Restart the bot: `python main.py --mode paper`
4. Check firewall settings

### Database Errors
**Symptom:** "Database locked" or "Unable to connect to database"

**Solutions:**
```bash
# Reset database (WARNING: Clears all history!)
rm trading_bot.db

# Or create backup first
cp trading_bot.db trading_bot_backup.db
```

### Telegram Alerts Not Working
**Solutions:**
1. Verify bot token is correct
2. Check chat ID is correct (get it from @userinfobot)
3. Ensure you've started the bot: `/start`
4. Check bot privacy settings in group chats

---

## 📚 Next Steps

### Essential Reading
1. **Full Documentation**: Read the complete [docs/](docs/) folder
2. **Risk Management**: Study [docs/05-risk-management/](docs/05-risk-management/)
3. **Strategy Details**: Review [docs/04-trading-strategies/](docs/04-trading-strategies/)

### Advanced Configuration
1. **Custom Strategies**: See [docs/10-appendices/03-configuration-examples.md](docs/10-appendices/03-configuration-examples.md)
2. **Backtesting**: Use `python -m src.utils.backtest`
3. **Docker Deployment**: See deployment guide

### Monitoring & Maintenance
1. Set up automated daily/weekly reports
2. Configure PagerDuty or similar for critical alerts
3. Schedule monthly strategy review sessions
4. Keep a trading journal of system observations

---

## 📞 Emergency Contacts & Support

**If you encounter critical issues:**
1. Check logs: `tail -100 logs/trading_bot.log`
2. Stop the bot: `Ctrl+C` or `make stop`
3. Review position status on Bybit directly
4. Join community Discord/Telegram for help

**Exchange Support:**
- Bybit Support: [support.bybit.com](https://support.bybit.com)

---

## 🎯 Success Metrics

After 90 days, you should see:

| Metric | Target | Notes |
|--------|--------|-------|
| **System Uptime** | >99% | Bot running consistently |
| **Max Drawdown** | <20% | Within expected range |
| **Sharpe Ratio** | >1.0 | Risk-adjusted returns |
| **Trade Count** | Varies | Depends on market conditions |
| **Emotional Involvement** | Minimal | Trust the system |

---

## 📝 Daily Checklist (First Month)

```markdown
## Daily Review (5 minutes)
- [ ] Check overnight P&L via Telegram/email
- [ ] Verify bot is running: `python main.py --status`
- [ ] Review any error notifications
- [ ] Check Bybit for unexpected positions
- [ ] Log any observations in trading journal

## Weekly Review (30 minutes)
- [ ] Review performance vs benchmarks
- [ ] Check drawdown status
- [ ] Verify circuit breaker status
- [ ] Review position sizing
- [ ] Check correlation metrics
- [ ] Read strategy logs for anomalies
```

---

## 💡 Pro Tips

1. **Start conservative** - Lower risk limits initially, increase gradually
2. **Keep a trading journal** - Document your observations and emotions
3. **Don't micromanage** - The system is designed to be autonomous
4. **Have an emergency fund** - 6+ months expenses completely separate
5. **Tax planning** - Consult a tax professional about crypto trading in your jurisdiction
6. **Regular backups** - Backup your database and config files weekly
7. **Security first** - Use IP whitelisting, strong passwords, 2FA everywhere

---

## ⚖️ Legal Notice

This software is provided for educational purposes only. Cryptocurrency trading carries substantial risk. Past performance does not guarantee future results. The authors are not responsible for any financial losses incurred through use of this system.

**Full Risk Disclosure**: [docs/10-appendices/04-risk-disclosure.md](docs/10-appendices/04-risk-disclosure.md)

---

**Welcome to The Eternal Engine. May your compounding be eternal.**

*Version 1.0 | February 2026*
