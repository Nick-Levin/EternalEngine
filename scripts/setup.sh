#!/bin/bash
# Setup script for ByBit Trading Bot

set -e

echo "================================"
echo "ByBit Trading Bot Setup"
echo "================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo "Error: Python 3.8 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "✓ Python version: $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

echo "✓ Dependencies installed"

# Create .env file
echo ""
echo "Setting up configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ Created .env file from template"
    echo ""
    echo "IMPORTANT: Please edit .env file and add your API credentials"
else
    echo "✓ .env file already exists"
fi

# Create directories
echo ""
echo "Creating directories..."
mkdir -p logs data

echo "✓ Directories created"

# Run configuration check
echo ""
echo "Checking configuration..."
if python main.py --check; then
    echo ""
    echo "================================"
    echo "Setup complete!"
    echo "================================"
    echo ""
    echo "Next steps:"
    echo "  1. Edit .env file with your API credentials"
    echo "  2. Run: python main.py --check"
    echo "  3. Test in paper mode: python main.py --mode paper"
    echo ""
else
    echo ""
    echo "Please fix configuration errors and run:"
    echo "  python main.py --check"
fi
