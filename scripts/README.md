# Scripts Directory

Utility scripts for The Eternal Engine.

## Available Scripts

### `setup.sh`
Interactive setup script for first-time installation.

```bash
./scripts/setup.sh
```

**What it does:**
- Checks Python version (3.11+)
- Creates virtual environment
- Installs dependencies
- Creates directory structure
- Sets up .env configuration
- Initializes database

### `verify_setup.sh`
Verifies the development environment is correctly configured.

```bash
./scripts/verify_setup.sh
```

**Checks:**
- Python environment
- Core dependencies
- Code quality tools
- Testing framework
- Docker services
- Database connectivity
- Project structure

### `trigger_dca_purchase.py`
Simulates what the next DCA purchase would look like (dry run).

```bash
# Simulate with defaults
python scripts/trigger_dca_purchase.py

# Custom symbols
python scripts/trigger_dca_purchase.py --symbols BTCUSDT,ETHUSDT

# Custom amount
python scripts/trigger_dca_purchase.py --amount 500
```

**Note:** This is a simulation only - no actual orders are placed.

## Archive

One-time use scripts are stored in `archive/`:
- `fix_dca_missed_purchase.py` - Historical fix for Feb 2026 issue
