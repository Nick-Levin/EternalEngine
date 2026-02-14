# The Eternal Engine - Test Suite

This directory contains comprehensive tests for The Eternal Engine trading system.

## Structure

```
tests/
├── conftest.py                 # Shared fixtures and test configuration
├── README.md                   # This file
├── unit/                       # Unit tests
│   ├── test_models.py          # Data model tests
│   ├── test_config.py          # Configuration tests
│   ├── test_risk_manager.py    # Risk manager tests
│   ├── test_exchange.py        # Bybit client tests
│   ├── test_database.py        # Database tests
│   └── test_engines.py         # All 4 engine tests
└── integration/                # Integration tests
    └── test_engine.py          # Full system integration tests
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run unit tests only:
```bash
pytest tests/unit/
```

### Run integration tests only:
```bash
pytest tests/integration/
```

### Run with verbose output:
```bash
pytest -v
```

### Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

### Run specific test file:
```bash
pytest tests/unit/test_risk_manager.py
```

### Run specific test:
```bash
pytest tests/unit/test_risk_manager.py::TestCircuitBreakers::test_circuit_breaker_level_1_trigger
```

## Test Categories

### Unit Tests

- **test_models.py**: Tests for all Pydantic models (Order, Position, Trade, etc.)
- **test_config.py**: Tests for configuration classes and validation
- **test_risk_manager.py**: Tests for risk management, circuit breakers, position sizing
- **test_exchange.py**: Tests for Bybit client, retry logic, error handling
- **test_database.py**: Tests for database CRUD operations
- **test_engines.py**: Tests for all 4 engines (CORE-HODL, TREND, FUNDING, TACTICAL)

### Integration Tests

- **test_engine.py**: Tests for complete trading cycles, signal flow, state persistence

## Fixtures

Common fixtures are defined in `conftest.py`:

- `test_database`: In-memory SQLite database
- `risk_manager`: Fresh RiskManager instance
- `sample_order`, `sample_position`, `sample_trade`: Sample model instances
- `sample_portfolio`: Sample portfolio for testing
- `mock_exchange`: Mocked BybitClient
- Various configuration fixtures

## Writing Tests

When adding new tests:

1. Place unit tests in `tests/unit/`
2. Place integration tests in `tests/integration/`
3. Use fixtures from `conftest.py` where possible
4. Follow the existing naming conventions:
   - Test class: `Test<ClassName>` or `Test<Feature>`
   - Test method: `test_<description>`
5. Add docstrings to test methods explaining what is being tested
6. Use `@pytest.mark.asyncio` for async tests
