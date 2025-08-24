# Pre-commit Configuration Guide

## Overview
This project uses pre-commit hooks to ensure code quality and consistency. The primary tool is Black for code formatting, supplemented by additional linters and validators.

## Quick Start

### Installation
```bash
# Option 1: Use the setup script
./scripts/setup-pre-commit.sh

# Option 2: Manual installation
pip install pre-commit==3.8.0
pre-commit install
```

### First Run
```bash
# Check all files
pre-commit run --all-files
```

## Configured Hooks

### 1. Black (Python Formatter)
- **Purpose**: Enforces consistent Python code style
- **Config**: Line length 88, Python 3.8-3.11
- **Auto-fix**: Yes

### 2. Flake8 (Python Linter)
- **Purpose**: Checks for Python errors and style issues
- **Config**: Compatible with Black settings
- **Auto-fix**: No (reports issues only)

### 3. isort (Import Sorter)
- **Purpose**: Sorts and organizes Python imports
- **Config**: Black-compatible profile
- **Auto-fix**: Yes

### 4. mypy (Type Checker)
- **Purpose**: Static type checking for Python
- **Config**: Ignores missing imports
- **Auto-fix**: No (reports issues only)

### 5. Standard Hooks
- `trailing-whitespace`: Removes trailing spaces
- `end-of-file-fixer`: Ensures files end with newline
- `check-yaml`: Validates YAML syntax
- `check-json`: Validates JSON syntax
- `check-toml`: Validates TOML syntax
- `check-added-large-files`: Prevents large files (>1MB)
- `check-merge-conflict`: Detects merge conflict markers
- `debug-statements`: Finds forgotten debug code
- `mixed-line-ending`: Normalizes line endings to LF

## Usage Scenarios

### Normal Development
```bash
# Code as usual - hooks run automatically
git add .
git commit -m "Add new feature"
# Pre-commit runs and fixes/reports issues
```

### Manual Checks
```bash
# Run all hooks
pre-commit run --all-files

# Run specific hook
pre-commit run black
pre-commit run flake8

# Run on specific files
pre-commit run --files src/baseline.py src/candidate.py
```

### Fixing Issues

#### Black Formatting Issues
```bash
# Auto-fix with Black
black .
# Or let pre-commit fix on commit
```

#### Flake8 Warnings
```bash
# View specific issues
flake8 src/baseline.py

# Common fixes:
# - E501: Line too long (Black should handle)
# - F401: Unused import (remove the import)
# - E302: Expected 2 blank lines (add blank line)
```

#### Import Order Issues
```bash
# Auto-fix with isort
isort .
# Or let pre-commit fix on commit
```

#### Type Checking Issues
```bash
# Run mypy directly for details
mypy src/baseline.py

# Add type hints or ignore with:
# type: ignore
```

### Bypassing Hooks (Emergency Only)
```bash
# Skip all hooks
git commit --no-verify -m "Emergency fix"

# Skip specific hooks in config
# Edit .pre-commit-config.yaml and comment out hooks
```

## Troubleshooting

### Hook Installation Issues
```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install

# Clear cache and retry
pre-commit clean
pre-commit install
```

### Black Conflicts
```bash
# Ensure Black version matches
pip install black==24.10.0

# Check Black config
black --check --diff .
```

### Performance Issues
```bash
# Run hooks in parallel
pre-commit run --all-files --jobs 4

# Skip slow hooks during development
SKIP=mypy git commit -m "message"
```

## CI/CD Integration

### GitHub Actions
```yaml
# .github/workflows/pre-commit.yml
name: pre-commit

on:
  pull_request:
  push:
    branches: [main]

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
    - uses: pre-commit/action@v3.0.0
```

### GitLab CI
```yaml
# .gitlab-ci.yml
pre-commit:
  stage: test
  image: python:3.11
  script:
    - pip install pre-commit
    - pre-commit run --all-files
```

## Best Practices

1. **Run before pushing**: `pre-commit run --all-files`
2. **Keep hooks updated**: `pre-commit autoupdate` (monthly)
3. **Don't skip hooks**: Maintain code quality
4. **Fix immediately**: Don't accumulate formatting debt
5. **Configure IDE**: Set up Black in your editor

## Hook Maintenance

### Update Hook Versions
```bash
# Update all hooks to latest versions
pre-commit autoupdate

# Commit the changes
git add .pre-commit-config.yaml
git commit -m "Update pre-commit hooks"
```

### Add New Hooks
Edit `.pre-commit-config.yaml` and add new repository:
```yaml
- repo: https://github.com/new/hook
  rev: v1.0.0
  hooks:
    - id: new-hook
```

### Remove Hooks
```bash
# Uninstall from git
pre-commit uninstall

# Remove configuration
rm .pre-commit-config.yaml
```

## Summary

Pre-commit ensures:
- ✅ Consistent code formatting (Black)
- ✅ Clean imports (isort)
- ✅ No syntax errors (Flake8)
- ✅ Type safety (mypy)
- ✅ Clean repository (no trailing spaces, valid configs)

This automation saves time in code reviews and maintains high code quality standards across the team.
