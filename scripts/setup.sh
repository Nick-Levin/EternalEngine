#!/bin/bash
# =============================================================================
# The Eternal Engine - Setup Script
# =============================================================================
# This script sets up the environment for The Eternal Engine trading system.
# It is idempotent - safe to run multiple times.
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
#
# Or run directly:
#   bash <(curl -sSL https://raw.githubusercontent.com/yourusername/eternal-engine/main/scripts/setup.sh)
# =============================================================================

set -euo pipefail

# =============================================================================
# Color Definitions
# =============================================================================
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly NC='\033[0m' # No Color
readonly BOLD='\033[1m'

# =============================================================================
# Logging Functions
# =============================================================================
log_info() { echo -e "${BLUE}ℹ${NC}  $1"; }
log_success() { echo -e "${GREEN}✓${NC}  $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC}  $1"; }
log_error() { echo -e "${RED}✗${NC}  $1"; }
log_step() { echo -e "\n${CYAN}${BOLD}▶${NC} ${BOLD}$1${NC}"; }
log_header() {
    echo -e "\n${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${MAGENTA}${BOLD}  $1${NC}"
    echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════════${NC}\n"
}

# =============================================================================
# Script Configuration
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REQUIRED_PYTHON_VERSION="3.11"
VENV_DIR="${PROJECT_ROOT}/venv"
DEMO_KEY="hyDYLLz8FWyTABq620"
DEMO_SECRET="bUh5xWS8aXVmARXa7Bj5AC6jliuOfCfTyshP"

# =============================================================================
# Utility Functions
# =============================================================================

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Compare version strings (returns 0 if $1 >= $2)
version_ge() {
    printf '%s
%s
' "$2" "$1" | sort -V -C
}

# Get Python version
get_python_version() {
    python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2
}

# Check if we're in the right directory
verify_project_root() {
    if [[ ! -f "${PROJECT_ROOT}/main.py" ]]; then
        log_error "Cannot find main.py. Please run this script from the project root or scripts/ directory."
        exit 1
    fi
    
    if [[ ! -f "${PROJECT_ROOT}/requirements.txt" ]]; then
        log_error "Cannot find requirements.txt. Please run this script from the project root."
        exit 1
    fi
}

# =============================================================================
# Setup Steps
# =============================================================================

check_python_version() {
    log_step "Checking Python version..."
    
    if ! command_exists python3; then
        log_error "Python 3 is not installed. Please install Python ${REQUIRED_PYTHON_VERSION}+ first."
        log_info "Visit: https://www.python.org/downloads/"
        exit 1
    fi
    
    local python_version
    python_version=$(get_python_version)
    
    if version_ge "${python_version}" "${REQUIRED_PYTHON_VERSION}"; then
        log_success "Python version: ${python_version} (required: ${REQUIRED_PYTHON_VERSION}+)"
    else
        log_error "Python ${REQUIRED_PYTHON_VERSION}+ is required, but found ${python_version}"
        log_info "Please upgrade Python: https://www.python.org/downloads/"
        exit 1
    fi
}

create_virtual_environment() {
    log_step "Setting up virtual environment..."
    
    if [[ -d "${VENV_DIR}" ]]; then
        log_warning "Virtual environment already exists at ${VENV_DIR}"
        read -rp "Recreate it? [y/N]: " response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            rm -rf "${VENV_DIR}"
            log_info "Removed old virtual environment"
        else
            log_success "Using existing virtual environment"
            return 0
        fi
    fi
    
    log_info "Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
    log_success "Virtual environment created at ${VENV_DIR}"
}

activate_virtual_environment() {
    log_step "Activating virtual environment..."
    
    # shellcheck source=/dev/null
    source "${VENV_DIR}/bin/activate"
    
    log_success "Virtual environment activated"
    log_info "Python: $(which python)"
    log_info "Pip: $(which pip)"
}

upgrade_pip() {
    log_step "Upgrading pip..."
    pip install --quiet --upgrade pip setuptools wheel
    log_success "Pip upgraded to $(pip --version | awk '{print $2}')"
}

install_dependencies() {
    log_step "Installing dependencies..."
    
    if [[ ! -f "${PROJECT_ROOT}/requirements.txt" ]]; then
        log_error "requirements.txt not found!"
        exit 1
    fi
    
    log_info "This may take a few minutes..."
    
    if pip install -r "${PROJECT_ROOT}/requirements.txt" >/dev/null 2>&1; then
        log_success "All dependencies installed successfully"
    else
        log_warning "Some dependencies failed to install (this is normal for optional packages)"
        log_info "Core functionality should still work. Run tests to verify."
    fi
}

create_directories() {
    log_step "Creating necessary directories..."
    
    local dirs=("logs" "data" "data/market_data" "data/backtests" "config")
    
    for dir in "${dirs[@]}"; do
        local full_path="${PROJECT_ROOT}/${dir}"
        if [[ ! -d "$full_path" ]]; then
            mkdir -p "$full_path"
            log_info "Created: ${dir}/"
        else
            log_info "Exists: ${dir}/"
        fi
    done
    
    log_success "Directory structure ready"
}

setup_environment_file() {
    log_step "Checking environment configuration..."
    
    local env_file="${PROJECT_ROOT}/.env"
    
    if [[ -f "$env_file" ]]; then
        log_success ".env configuration file found"
        
        # Verify it has been customized
        if grep -q "your_demo_key_here\|your_prod_key_here" "$env_file" 2>/dev/null; then
            log_warning "API keys not configured yet (still have placeholders)"
            log_info "For paper trading: No changes needed (starts in demo mode)"
            log_info "For live trading: Edit .env and add your Bybit API keys"
        else
            log_success "API keys appear to be configured"
        fi
        
        return 0
    else
        log_error ".env file not found!"
        log_error "The .env file should be present with default configuration."
        log_info "Please ensure the .env file exists in: ${PROJECT_ROOT}"
        exit 1
    fi
}

initialize_database() {
    log_step "Initializing database..."
    
    local db_file="${PROJECT_ROOT}/data/eternal_engine.db"
    
    # Check if Python and required modules are available
    if python -c "import sqlalchemy" 2>/dev/null; then
        log_info "Creating database schema..."
        
        # Create a simple initialization script
        python << 'EOF'
import sys
sys.path.insert(0, '.')

try:
    from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime
    import os

    os.makedirs('data', exist_ok=True)
    
    engine = create_engine('sqlite:///./data/eternal_engine.db', echo=False)
    Base = declarative_base()

    class Trade(Base):
        __tablename__ = 'trades'
        id = Column(Integer, primary_key=True)
        symbol = Column(String)
        side = Column(String)
        amount = Column(Float)
        price = Column(Float)
        timestamp = Column(DateTime, default=datetime.utcnow)
        strategy = Column(String)
        status = Column(String)

    class Position(Base):
        __tablename__ = 'positions'
        id = Column(Integer, primary_key=True)
        symbol = Column(String)
        side = Column(String)
        amount = Column(Float)
        entry_price = Column(Float)
        open_time = Column(DateTime, default=datetime.utcnow)
        strategy = Column(String)
        is_open = Column(Boolean, default=True)

    Base.metadata.create_all(engine)
    print("✓ Database initialized successfully")
except Exception as e:
    print(f"⚠ Database initialization skipped: {e}")
    print("  The application will create tables on first run")
EOF
    else
        log_warning "SQLAlchemy not installed yet. Database will be initialized on first run."
    fi
}

run_configuration_check() {
    log_step "Running configuration check..."
    
    cd "$PROJECT_ROOT"
    
    if [[ -f "main.py" ]]; then
        log_info "Testing Python imports..."
        
        if python -c "import sys; sys.path.insert(0, 'src'); from core.config import TradingConfig; print('✓ Core modules importable')" 2>/dev/null; then
            log_success "Core modules are importable"
        else
            log_warning "Some modules may not be fully configured yet"
        fi
        
        # Check if --check flag is supported
        if python main.py --help 2>/dev/null | grep -q -- "\-\-check"; then
            log_info "Running: python main.py --check"
            if python main.py --check; then
                log_success "Configuration check passed!"
            else
                log_warning "Configuration check returned warnings (this is normal for initial setup)"
            fi
        else
            log_info "main.py --check not available, skipping detailed check"
        fi
    else
        log_warning "main.py not found, skipping configuration check"
    fi
}

print_next_steps() {
    log_header "Setup Complete! 🎉"
    
    echo -e "${BOLD}Your Eternal Engine is ready!${NC}\n"
    
    echo -e "${CYAN}Next Steps:${NC}\n"
    
    echo -e "1. ${BOLD}Review your configuration:${NC}"
    echo -e "   ${YELLOW}nano .env${NC} or ${YELLOW}code .env${NC}\n"
    
    echo -e "2. ${BOLD}Start in paper trading mode (recommended):${NC}"
    echo -e "   ${GREEN}python main.py --mode paper${NC}\n"
    
    echo -e "3. ${BOLD}Check system status:${NC}"
    echo -e "   ${GREEN}python main.py --status${NC}\n"
    
    echo -e "4. ${BOLD}View logs:${NC}"
    echo -e "   ${GREEN}tail -f logs/eternal_engine.log${NC}\n"
    
    echo -e "${CYAN}Documentation:${NC}"
    echo -e "   • Quick Start: ${YELLOW}QUICKSTART.md${NC}"
    echo -e "   • Full Docs:  ${YELLOW}docs/README.md${NC}"
    echo -e "   • Risk Guide: ${YELLOW}docs/05-risk-management/01-risk-framework.md${NC}\n"
    
    echo -e "${CYAN}Important Commands:${NC}"
    echo -e "   ${GREEN}make run-paper${NC}  # Run in paper mode"
    echo -e "   ${GREEN}make run-live${NC}   # Run in live mode (real money!)"
    echo -e "   ${GREEN}make status${NC}     # Check status"
    echo -e "   ${GREEN}make test${NC}       # Run tests\n"
    
    echo -e "${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}⚠️  IMPORTANT:${NC} Always test thoroughly in paper mode before going live!"
    echo -e "${YELLOW}⚠️  RISK WARNING:${NC} Cryptocurrency trading involves substantial risk."
    echo -e "${MAGENTA}═══════════════════════════════════════════════════════════════${NC}\n"
}

# =============================================================================
# Main Script
# =============================================================================

main() {
    log_header "The Eternal Engine - Setup"
    
    echo -e "A 4-strategy autonomous trading system for Bybit\n"
    echo -e "This script will:"
    echo "  • Check Python version (3.11+)"
    echo "  • Create virtual environment"
    echo "  • Install dependencies"
    echo "  • Create necessary directories"
    echo "  • Set up environment configuration"
    echo "  • Initialize database"
    echo "  • Run configuration check"
    echo ""
    
    read -rp "Continue? [Y/n]: " confirm
    confirm=${confirm:-Y}
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Setup cancelled"
        exit 0
    fi
    
    # Run all setup steps
    verify_project_root
    check_python_version
    create_virtual_environment
    activate_virtual_environment
    upgrade_pip
    install_dependencies
    create_directories
    setup_environment_file
    initialize_database
    run_configuration_check
    
    print_next_steps
}

# Handle script interruption
trap 'log_error "Setup interrupted"; exit 1' INT TERM

# Run main function
main "$@"
