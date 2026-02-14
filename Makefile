# ByBit Trading Bot - Makefile

.PHONY: help setup test lint format check clean run-paper run-live

PYTHON := python
VENV := venv
PIP := $(VENV)/bin/pip
PYTHON_VENV := $(VENV)/bin/python

help: ## Show this help message
	@echo "ByBit Trading Bot - Available Commands"
	@echo "======================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Set up development environment
	@echo "Setting up development environment..."
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install black isort flake8 mypy pytest pytest-asyncio
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file"; fi
	mkdir -p logs data
	@echo "Setup complete! Edit .env file with your API keys."

test: ## Run all tests
	$(PYTHON_VENV) -m pytest -v

test-unit: ## Run unit tests only
	$(PYTHON_VENV) -m pytest tests/unit/ -v

test-cov: ## Run tests with coverage report
	$(PYTHON_VENV) -m pytest --cov=src --cov-report=html --cov-report=term

lint: ## Run linter (flake8)
	$(PYTHON_VENV) -m flake8 src/ tests/

format: ## Format code with black and isort
	$(PYTHON_VENV) -m black src/ tests/
	$(PYTHON_VENV) -m isort src/ tests/

format-check: ## Check code formatting without changes
	$(PYTHON_VENV) -m black --check src/ tests/
	$(PYTHON_VENV) -m isort --check-only src/ tests/

type-check: ## Run type checker (mypy)
	$(PYTHON_VENV) -m mypy src/

check: ## Check configuration
	$(PYTHON_VENV) main.py --check

status: ## Show bot status
	$(PYTHON_VENV) main.py --status

run-paper: ## Run bot in paper trading mode
	$(PYTHON_VENV) main.py --mode paper

run-live: ## Run bot in live trading mode (CAUTION!)
	@echo "⚠️  WARNING: Running in LIVE mode!"
	@read -p "Are you sure? (yes/no): " confirm && [ $$confirm = yes ] && $(PYTHON_VENV) main.py --mode live

clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	@echo "Cleanup complete"

clean-all: clean ## Clean everything including virtual environment
	rm -rf $(VENV)/
	rm -f trading_bot.db
	@echo "Full cleanup complete"

logs: ## Show recent logs
	@if [ -f logs/trading_bot.log ]; then tail -n 50 logs/trading_bot.log | jq . 2>/dev/null || tail -n 50 logs/trading_bot.log; else echo "No log file found"; fi

logs-tail: ## Follow log output in real-time
	@tail -f logs/trading_bot.log | jq . 2>/dev/null || tail -f logs/trading_bot.log

install-hooks: ## Install git pre-commit hooks
	@echo "Installing pre-commit hooks..."
	$(PIP) install pre-commit
	pre-commit install

update-deps: ## Update dependencies
	$(PIP) install --upgrade -r requirements.txt

.DEFAULT_GOAL := help
