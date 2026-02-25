# =============================================================================
# The Eternal Engine - Makefile
# 4-strategy autonomous trading system for Bybit
# =============================================================================
# Usage: make <command>
#        make help  - Show all available commands
# =============================================================================

.PHONY: help setup install test test-unit test-integration test-cov lint format type-check security \
        check status logs logs-tail clean update-deps run-paper run-live verify-paper verify-live \
        backtest backtest-3y backtest-5y backtest-8y backtest-multi backtest-report

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
PYTHON := python3
VENV := venv
PIP := $(VENV)/bin/pip
PYTHON_VENV := $(VENV)/bin/python

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m

# ------------------------------------------------------------------------------
# Help (Default Target)
# ------------------------------------------------------------------------------
help: ## Show all available commands
	@echo "$(BLUE)The Eternal Engine - Available Commands$(NC)"
	@echo "========================================"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@echo "  $(BLUE)make setup$(NC)       - Set up development environment"
	@echo "  $(BLUE)make install$(NC)     - Install dependencies"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  $(BLUE)make format$(NC)      - Format code with black & isort"
	@echo "  $(BLUE)make lint$(NC)        - Run linters (flake8)"
	@echo "  $(BLUE)make type-check$(NC)  - Run type checker (mypy)"
	@echo "  $(BLUE)make security$(NC)    - Run security scan (bandit)"
	@echo ""
	@echo "$(GREEN)Testing:$(NC)"
	@echo "  $(BLUE)make test$(NC)        - Run all tests"
	@echo "  $(BLUE)make test-unit$(NC)   - Run unit tests only"
	@echo "  $(BLUE)make test-cov$(NC)    - Run tests with coverage report"
	@echo ""
	@echo "$(GREEN)Operations:$(NC)"
	@echo "  $(BLUE)make status$(NC)      - Show bot status"
	@echo "  $(BLUE)make logs$(NC)        - Show recent logs"
	@echo "  $(BLUE)make logs-tail$(NC)   - Follow logs in real-time"
	@echo "  $(BLUE)make clean$(NC)       - Clean generated files"
	@echo ""
	@echo "$(GREEN)Trading - Paper Mode (Safe):$(NC)"
	@echo "  $(GREEN)make run-paper$(NC)   - Start in paper trading mode"
	@echo ""
	@echo "$(RED)Trading - Live Mode (Real Money!):$(NC)"
	@echo "  $(RED)make run-live$(NC)    - Start in LIVE trading mode"
	@echo ""
	@echo "$(GREEN)Backtesting:$(NC)"
	@echo "  $(BLUE)make backtest$(NC)       - Run backtest (default 3 years)"
	@echo "  $(BLUE)make backtest-3y$(NC)     - Run 3-year backtest"
	@echo "  $(BLUE)make backtest-5y$(NC)     - Run 5-year backtest"
	@echo "  $(BLUE)make backtest-multi$(NC)  - Multi-period comparison"
	@echo ""
	@echo "For more details, see README.md and QUICKSTART.md"

# ------------------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------------------
setup: ## Set up development environment (create venv, install deps)
	@echo "$(BLUE)Setting up The Eternal Engine...$(NC)"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt
	@if [ ! -f .env ]; then \
		echo "$(RED)✗ .env file not found!$(NC)"; \
		echo "$(YELLOW)The .env file should exist with your configuration.$(NC)"; \
		echo "$(YELLOW)Please ensure .env is present in the project root.$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ .env file found$(NC)"
	mkdir -p logs data config
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo "Next steps:"
	@echo "  1. Edit .env file with your API keys"
	@echo "  2. Run 'make test' to verify installation"
	@echo "  3. Run 'make run-paper' to start in paper mode"

install: ## Install/update dependencies
	@echo "$(BLUE)Installing dependencies...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

# ------------------------------------------------------------------------------
# Testing
# ------------------------------------------------------------------------------
test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	$(PYTHON_VENV) -m pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	$(PYTHON_VENV) -m pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	$(PYTHON_VENV) -m pytest tests/integration/ -v --tb=short

test-cov: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	$(PYTHON_VENV) -m pytest tests/ --cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=80

# ------------------------------------------------------------------------------
# Code Quality
# ------------------------------------------------------------------------------
lint: ## Run linters (flake8)
	@echo "$(BLUE)Running linters...$(NC)"
	$(PYTHON_VENV) -m flake8 src/ tests/ --max-line-length=88 --extend-ignore=E203,W503 || true
	@echo "$(GREEN)✓ Linting complete$(NC)"

format: ## Format code with black and isort
	@echo "$(BLUE)Formatting code...$(NC)"
	$(PYTHON_VENV) -m black src/ tests/ --line-length=88 --quiet
	$(PYTHON_VENV) -m isort src/ tests/ --profile=black --line-length=88
	@echo "$(GREEN)✓ Formatting complete$(NC)"

type-check: ## Run type checker (mypy)
	@echo "$(BLUE)Running type checks...$(NC)"
	$(PYTHON_VENV) -m mypy src/ --ignore-missing-imports || true

security: ## Run security scan with bandit
	@echo "$(BLUE)Running security scan...$(NC)"
	$(PYTHON_VENV) -m bandit -r src/ -ll || true
	@echo "$(GREEN)✓ Security scan complete$(NC)"

check: ## Run all code quality checks
	@echo "$(BLUE)Running all checks...$(NC)"
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) security
	@echo "$(GREEN)✓ All checks complete$(NC)"

# ------------------------------------------------------------------------------
# Operations
# ------------------------------------------------------------------------------
status: ## Show bot status
	@echo "$(BLUE)Checking Eternal Engine status...$(NC)"
	$(PYTHON_VENV) main.py --status 2>/dev/null || echo "$(YELLOW)Bot not running or status unavailable$(NC)"

logs: ## Show recent logs (last 50 lines)
	@if [ -f logs/eternal_engine.log ]; then \
		echo "$(BLUE)Recent logs:$(NC)"; \
		tail -n 50 logs/eternal_engine.log; \
	else \
		echo "$(YELLOW)No log file found at logs/eternal_engine.log$(NC)"; \
	fi

logs-tail: ## Follow log output in real-time
	@if [ -f logs/eternal_engine.log ]; then \
		echo "$(BLUE)Following logs (Ctrl+C to exit)...$(NC)"; \
		tail -f logs/eternal_engine.log; \
	else \
		echo "$(YELLOW)No log file found at logs/eternal_engine.log$(NC)"; \
	fi

# ------------------------------------------------------------------------------
# Safety Verification
# ------------------------------------------------------------------------------
verify-paper:
	@echo "$(GREEN)Verifying paper trading mode...$(NC)"
	@grep -q "TRADING_MODE=paper" .env 2>/dev/null || (echo "$(YELLOW)Warning: TRADING_MODE not set to paper in .env$(NC)"; exit 1)
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
# Trading - Paper Mode (Safe for Testing)
# ------------------------------------------------------------------------------
run-paper: verify-paper ## Run in paper trading mode
	@echo "$(GREEN)╔══════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║  Starting The Eternal Engine in PAPER trading mode           ║$(NC)"
	@echo "$(GREEN)║  No real funds will be used                                  ║$(NC)"
	@echo "$(GREEN)╚══════════════════════════════════════════════════════════════╝$(NC)"
	$(PYTHON_VENV) main.py --mode paper

# ------------------------------------------------------------------------------
# Trading - Live Mode (Real Money!)
# ------------------------------------------------------------------------------
run-live: verify-live ## Run in live trading mode (CAUTION! Real Money!)
	@echo "$(RED)╔══════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(RED)║  REAL LIVE MODE ACTIVATED                                    ║$(NC)"
	@echo "$(RED)║  Real money will be at risk!                                 ║$(NC)"
	@echo "$(RED)╚══════════════════════════════════════════════════════════════╝$(NC)"
	$(PYTHON_VENV) main.py --mode live

# ------------------------------------------------------------------------------
# Backtesting
# ------------------------------------------------------------------------------
backtest: ## Run backtest (use YEARS=3 to specify period, default 3 years)
	@echo "$(BLUE)Running Eternal Engine backtest...$(NC)"
	$(PYTHON_VENV) -m src.backtest.runner --years $(or $(YEARS),3)

backtest-3y: ## Run 3-year backtest
	@echo "$(BLUE)Running 3-year backtest...$(NC)"
	$(PYTHON_VENV) -m src.backtest.runner --years 3

backtest-5y: ## Run 5-year backtest
	@echo "$(BLUE)Running 5-year backtest...$(NC)"
	$(PYTHON_VENV) -m src.backtest.runner --years 5

backtest-8y: ## Run 8-year backtest
	@echo "$(BLUE)Running 8-year backtest...$(NC)"
	$(PYTHON_VENV) -m src.backtest.runner --years 8

backtest-multi: ## Run multi-period comparison (3/5/8 years)
	@echo "$(BLUE)Running multi-period backtest comparison...$(NC)"
	$(PYTHON_VENV) -m src.backtest.runner --multi-year

backtest-report: ## Generate markdown backtest report
	@echo "$(BLUE)Generating backtest report...$(NC)"
	mkdir -p reports
	$(PYTHON_VENV) -m src.backtest.runner --years $(or $(YEARS),3) --output reports/backtest_$(shell date +%Y%m%d).md

# ------------------------------------------------------------------------------
# Maintenance
# ------------------------------------------------------------------------------
clean: ## Clean up generated files
	@echo "$(BLUE)Cleaning generated files...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

update-deps: ## Update dependencies
	@echo "$(BLUE)Updating dependencies...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install --upgrade -r requirements.txt
	@echo "$(GREEN)✓ Dependencies updated$(NC)"

# ------------------------------------------------------------------------------
# Default Target
# ------------------------------------------------------------------------------
.DEFAULT_GOAL := help
