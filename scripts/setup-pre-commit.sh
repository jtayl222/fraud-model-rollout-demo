#!/bin/bash

# Setup pre-commit hooks for the project
# This script installs and configures pre-commit with Black and other code quality tools

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Pre-commit Setup for Fraud Model${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo -e "${RED}Error: pip is not installed${NC}"
    exit 1
fi

# Install pre-commit if not already installed
echo "1. Installing pre-commit..."
pip install pre-commit==3.8.0
echo -e "${GREEN}✓ Pre-commit installed${NC}"
echo ""

# Install the git hook scripts
echo "2. Installing git hooks..."
pre-commit install
echo -e "${GREEN}✓ Git hooks installed${NC}"
echo ""

# Install hooks for commit messages (optional)
echo "3. Installing commit message hooks..."
pre-commit install --hook-type commit-msg
echo -e "${GREEN}✓ Commit message hooks installed${NC}"
echo ""

# Run against all files to check current status
echo "4. Running initial check on all files..."
echo -e "${YELLOW}This may take a minute...${NC}"
if pre-commit run --all-files; then
    echo -e "${GREEN}✓ All files pass pre-commit checks!${NC}"
else
    echo -e "${YELLOW}⚠ Some files need fixes. Pre-commit will auto-fix on next commit.${NC}"
    echo -e "${YELLOW}  Run 'pre-commit run --all-files' to see details.${NC}"
fi
echo ""

# Show what hooks are installed
echo "5. Installed hooks:"
pre-commit run --list
echo ""

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Pre-commit setup complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Pre-commit will now run automatically on every commit."
echo ""
echo "Useful commands:"
echo "  pre-commit run --all-files    # Run on all files"
echo "  pre-commit run <hook-id>      # Run specific hook"
echo "  pre-commit autoupdate          # Update hook versions"
echo "  pre-commit uninstall           # Remove hooks"
echo ""
echo "To bypass hooks temporarily (not recommended):"
echo "  git commit --no-verify -m 'message'"
