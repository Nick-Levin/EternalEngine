#!/bin/bash
# Verification script for The Eternal Engine development environment

set -e

echo "=========================================="
echo "Eternal Engine - Environment Verification"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo "1. Python Environment"
echo "---------------------"
cd /home/valard/dev/AiProjects/EternalEngine
source venv/bin/activate

python --version && check_pass "Python available" || check_fail "Python not found"
pip --version && check_pass "pip available" || check_fail "pip not found"

echo ""
echo "2. Core Dependencies"
echo "--------------------"
python -c "import structlog, ccxt, pandas, numpy" && check_pass "Core packages" || check_fail "Core packages missing"
python -c "import sqlalchemy, influxdb_client, redis" && check_pass "Database packages" || check_fail "Database packages missing"
python -c "import pydantic, pydantic_settings" && check_pass "Config packages" || check_fail "Config packages missing"

echo ""
echo "3. Code Quality Tools"
echo "---------------------"
black --version && check_pass "black" || check_fail "black missing"
isort --version && check_pass "isort" || check_fail "isort missing"
flake8 --version && check_pass "flake8" || check_fail "flake8 missing"
mypy --version && check_pass "mypy" || check_fail "mypy missing"
bandit --version && check_pass "bandit" || check_fail "bandit missing"
pre-commit --version && check_pass "pre-commit" || check_fail "pre-commit missing"

echo ""
echo "4. Testing Framework"
echo "--------------------"
pytest --version && check_pass "pytest" || check_fail "pytest missing"

echo ""
echo "5. Docker Services"
echo "------------------"
docker ps | grep -q influxdb && check_pass "InfluxDB running (port 8086)" || check_fail "InfluxDB not running"
docker ps | grep -q grafana && check_pass "Grafana running (port 3000)" || check_fail "Grafana not running"
docker ps | grep -q redis && check_pass "Redis running (port 6379)" || check_fail "Redis not running"

echo ""
echo "6. Database"
echo "-----------"
python -c "import sqlite3; conn = sqlite3.connect('data/eternal_engine.db'); conn.close()" && check_pass "SQLite database accessible" || check_fail "Database error"

echo ""
echo "7. GitHub CLI"
echo "-------------"
gh auth status > /dev/null 2>&1 && check_pass "GitHub authenticated" || check_warn "GitHub not authenticated (run: gh auth login)"

echo ""
echo "8. MCP Servers Config"
echo "---------------------"
[ -f ~/.kimi/mcp.json ] && check_pass "MCP config exists" || check_fail "MCP config missing"

echo ""
echo "9. Project Structure"
echo "--------------------"
[ -d src/engines ] && check_pass "src/engines/" || check_fail "engines dir missing"
[ -d src/risk ] && check_pass "src/risk/" || check_fail "risk dir missing"
[ -d src/exchange ] && check_pass "src/exchange/" || check_fail "exchange dir missing"
[ -d tests/unit ] && check_pass "tests/unit/" || check_fail "tests dir missing"
[ -f .pre-commit-config.yaml ] && check_pass ".pre-commit-config.yaml" || check_fail "pre-commit config missing"
[ -f .kimi/kimi.md ] && check_pass ".kimi/kimi.md" || check_fail "kimi.md missing"
[ -f .kimi/skills/eternal-engine/SKILL.md ] && check_pass "Eternal Engine skill" || check_fail "skill missing"

echo ""
echo "10. Run Tests"
echo "-------------"
pytest tests/unit/ -q --tb=no 2>&1 | tail -1 | grep -q "passed" && check_pass "Tests passing" || check_warn "Some tests failing (check with: pytest tests/unit/ -v)"

echo ""
echo "=========================================="
echo "Verification Complete!"
echo "=========================================="
