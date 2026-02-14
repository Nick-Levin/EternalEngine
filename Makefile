# =============================================================================
# The Eternal Engine - Makefile
# 4-strategy autonomous trading system for Bybit
# =============================================================================

.PHONY: help setup test test-unit test-integration test-cov lint format format-check \
        type-check security check status run-paper run-live run-core run-trend \
        run-funding run-tactical init-db logs logs-tail clean clean-all update-deps \
        install-hooks verify-paper verify-live

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
PYTHON := python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTHON_VENV := $(VENV)/bin/python
VENV_BIN := $(VENV)/bin

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m # No Color

# ------------------------------------------------------------------------------
# Help
# ------------------------------------------------------------------------------
help: ## Show all available commands
	@echo "$(BLUE)The Eternal Engine - Available Commands$(NC)"
	@echo "========================================"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(setup|install-hooks|init-db)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(lint|format|type-check|security)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Testing:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'test' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Operations:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(check|status|logs|clean|update)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Trading - Paper Mode (Safe):$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'run-paper|run-.*-paper' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Trading - Live Mode (CAUTION!):$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'run-live|run-.*-live' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# ------------------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------------------
setup: ## Set up development environment (create venv, install deps, copy .env)
	@echo "$(BLUE)Setting up The Eternal Engine development environment...$(NC)"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env file from .env.example$(NC)"; \
		echo "$(YELLOW)⚠ Please edit .env with your API keys before running!$(NC)"; \
	fi
	mkdir -p logs data config
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Edit .env file with your API keys"
	@echo "  2. Run 'make init-db' to initialize the database"
	@echo "  3. Run 'make run-paper' to start in paper mode"

init-db: ## Initialize database schema
	@echo "$(BLUE)Initializing database...$(NC)"
	$(PYTHON_VENV) -c "from src.storage.database import init_db; init_db()"
	@echo "$(GREEN)✓ Database initialized$(NC)"

install-hooks: ## Install git pre-commit hooks
	@echo "$(BLUE)Installing pre-commit hooks...$(NC)"
	$(PIP) install pre-commit
	$(VENV_BIN)/pre-commit install
	@echo "$(GREEN)✓ Pre-commit hooks installed$(NC)"

# ------------------------------------------------------------------------------
# Testing
# ------------------------------------------------------------------------------
test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	$(PYTHON_VENV) -m pytest -v --tb=short

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	$(PYTHON_VENV) -m pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	$(PYTHON_VENV) -m pytest tests/integration/ -v --tb=short

test-cov: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	$(PYTHON_VENV) -m pytest --cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=70

# ------------------------------------------------------------------------------
# Code Quality
# ------------------------------------------------------------------------------
lint: ## Run all linters (flake8, mypy)
	@echo "$(BLUE)Running linters...$(NC)"
	$(PYTHON_VENV) -m flake8 src/ tests/ --max-line-length=88 --extend-ignore=E203,W503
	@echo "$(GREEN)✓ Linting passed$(NC)"

format: ## Format code with black and isort
	@echo "$(BLUE)Formatting code...$(NC)"
	$(PYTHON_VENV) -m black src/ tests/ --line-length=88
	$(PYTHON_VENV) -m isort src/ tests/ --profile=black --line-length=88
	@echo "$(GREEN)✓ Formatting complete$(NC)"

format-check: ## Check formatting without changes
	@echo "$(BLUE)Checking code formatting...$(NC)"
	$(PYTHON_VENV) -m black --check src/ tests/ --line-length=88
	$(PYTHON_VENV) -m isort --check-only src/ tests/ --profile=black --line-length=88

type-check: ## Run type checker (mypy)
	@echo "$(BLUE)Running type checks...$(NC)"
	$(PYTHON_VENV) -m mypy src/ --ignore-missing-imports --show-error-codes

security: ## Run security scan with bandit
	@echo "$(BLUE)Running security scan...$(NC)"
	$(PYTHON_VENV) -m bandit -r src/ -f json -o reports/security-report.json || true
	$(PYTHON_VENV) -m bandit -r src/ -ll
	@echo "$(GREEN)✓ Security scan complete$(NC)"

# ------------------------------------------------------------------------------
# Operations
# ------------------------------------------------------------------------------
check: ## Check configuration
	@echo "$(BLUE)Checking configuration...$(NC)"
	$(PYTHON_VENV) main.py --check

status: ## Show bot status
	@echo "$(BLUE)Checking Eternal Engine status...$(NC)"
	$(PYTHON_VENV) main.py --status

logs: ## Show recent logs (last 50 lines)
	@if [ -f logs/trading_bot.log ]; then \
		echo "$(BLUE)Recent logs:$(NC)"; \
		tail -n 50 logs/trading_bot.log | $(VENV_BIN)/python -m json.tool 2>/dev/null || tail -n 50 logs/trading_bot.log; \
	else \
		echo "$(YELLOW)No log file found at logs/trading_bot.log$(NC)"; \
	fi

logs-tail: ## Follow log output in real-time
	@if [ -f logs/trading_bot.log ]; then \
		echo "$(BLUE)Following logs (Ctrl+C to exit)...$(NC)"; \
		tail -f logs/trading_bot.log | $(VENV_BIN)/python -m json.tool 2>/dev/null || tail -f logs/trading_bot.log; \
	else \
		echo "$(YELLOW)No log file found at logs/trading_bot.log$(NC)"; \
	fi

# ------------------------------------------------------------------------------
# Verification (safety checks)
# ------------------------------------------------------------------------------
verify-paper:
	@echo "$(GREEN)Verifying paper trading mode...$(NC)"
	@grep -q "TRADING_MODE=paper" .env || (echo "$(YELLOW)Warning: TRADING_MODE not set to paper in .env$(NC)"; exit 1)
	@echo "$(GREEN)✓ Paper mode verified$(NC)"

verify-live:
	@echo "$(RED)╔══════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(RED)║  WARNING: You are about to run in LIVE trading mode!         ║$(NC)"
	@echo "$(RED)║  Real money will be at risk.                                 ║$(NC)"
	@echo "$(RED)╚══════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@read -p "Type 'LIVE' to confirm (or press Ctrl+C to cancel): " confirm; \
	if [ "$$confirm" != "LIVE" ]; then \
		echo "$(YELLOW)Aborted. Expected 'LIVE', got '$$confirm'$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Live trading confirmed$(NC)"

# ------------------------------------------------------------------------------
# Trading - Paper Mode (Safe for testing)
# ------------------------------------------------------------------------------
run-paper: verify-paper ## Run in paper trading mode (with DEMO keys)
	@echo "$(GREEN)╔══════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║  Starting The Eternal Engine in PAPER trading mode           ║$(NC)"
	@echo "$(GREEN)║  No real funds will be used                                  ║$(NC)"
	@echo "$(GREEN)╚══════════════════════════════════════════════════════════════╝$(NC)"
	$(PYTHON_VENV) main.py --mode paper

run-core: verify-paper ## Run only CORE-HODL engine (paper mode)
	@echo "$(GREEN)Starting CORE-HODL engine (DCA + HODL strategy)...$(NC)"
	$(PYTHON_VENV) main.py --mode paper --engine core

run-trend: verify-paper ## Run only TREND engine (paper mode)
	@echo "$(GREEN)Starting TREND engine (trend following strategy)...$(NC)"
	$(PYTHON_VENV) main.py --mode paper --engine trend

run-funding: verify-paper ## Run only FUNDING engine (paper mode)
	@echo "$(GREEN)Starting FUNDING engine (funding rate arbitrage)...$(NC)"
	$(PYTHON_VENV) main.py --mode paper --engine funding

run-tactical: verify-paper ## Run only TACTICAL engine (paper mode)
	@echo "$(GREEN)Starting TACTICAL engine (extreme value deployment)...$(NC)"
	$(PYTHON_VENV) main.py --mode paper --engine tactical

# ------------------------------------------------------------------------------
# Trading - Live Mode (CAUTION!)
# ------------------------------------------------------------------------------
run-live: verify-live ## Run in live trading mode (CAUTION!)
	@echo "$(RED)╔══════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(RED)║  LIVE MODE ACTIVATED                                         ║$(NC)"
	@echo "$(RED)║  All four engines will start with real capital               ║$(NC)"
	@echo "$(RED)╚══════════════════════════════════════════════════════════════╝$(NC)"
	$(PYTHON_VENV) main.py --mode live

run-core-live: verify-live ## Run only CORE-HODL engine (live)
	@echo "$(RED)Starting CORE-HODL engine in LIVE mode...$(NC)"
	$(PYTHON_VENV) main.py --mode live --engine core

run-trend-live: verify-live ## Run only TREND engine (live)
	@echo "$(RED)Starting TREND engine in LIVE mode...$(NC)"
	$(PYTHON_VENV) main.py --mode live --engine trend

run-funding-live: verify-live ## Run only FUNDING engine (live)
	@echo "$(RED)Starting FUNDING engine in LIVE mode...$(NC)"
	$(PYTHON_VENV) main.py --mode live --engine funding

run-tactical-live: verify-live ## Run only TACTICAL engine (live)
	@echo "$(RED)Starting TACTICAL engine in LIVE mode...$(NC)"
	$(PYTHON_VENV) main.py --mode live --engine tactical

# ------------------------------------------------------------------------------
# Maintenance
# ------------------------------------------------------------------------------
clean: ## Clean up generated files
	@echo "$(BLUE)Cleaning generated files...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	find . -type f -name "*.log" -delete
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: clean ## Clean everything including venv
	@echo "$(RED)Removing virtual environment...$(NC)"
	rm -rf $(VENV)/
	rm -f trading_bot.db
	rm -f reports/security-report.json
	@echo "$(GREEN)✓ Full cleanup complete$(NC)"

update-deps: ## Update dependencies
	@echo "$(BLUE)Updating dependencies...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install --upgrade -r requirements.txt
	@echo "$(GREEN)✓ Dependencies updated$(NC)"

# ------------------------------------------------------------------------------
# Default Target
# ------------------------------------------------------------------------------
.DEFAULT_GOAL := help
