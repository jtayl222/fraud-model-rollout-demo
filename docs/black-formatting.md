# Black Code Formatting Integration

## Overview
This document describes the Black code formatter integration into the fraud detection model project. Black is "the uncompromising Python code formatter" that ensures consistent code style across the entire codebase.

## What Was Done

### 1. Added Black to Dependencies
**File**: `requirements.txt`
```
# Code formatting
black==24.10.0
```

### 2. Configuration Setup
**File**: `pyproject.toml`
```toml
[tool.black]
line-length = 88
target-version = ['py38', 'py39', 'py310', 'py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.git
  | \.venv
  | build
  | dist
  | data
  | models
  | \.ipynb_checkpoints
)/
'''
```

### 3. Files Formatted
All 15 Python files in the project were reformatted:

**Documentation**:
- `docs/fraud_model_rollout_diagram.py`

**Scripts**:
- `scripts/upload-existing-models.py`
- `scripts/update-model-config.py`
- `scripts/push-fraud-metrics.py`
- `scripts/setup-monitoring.py`
- `scripts/deploy-extended-ab-test.py`
- `scripts/validate-production-pipeline.py`

**Source Files**:
- `src/download.py`
- `src/data.py`
- `src/baseline.py`
- `src/candidate.py`
- `src/offline-validation.py`
- `src/online-validation.py`
- `src/threshold-tuning.py`
- `src/train_model.py`

## Black Formatting Changes

Black applies the following formatting rules:

1. **Line Length**: Maximum 88 characters (configurable)
2. **Quotes**: Prefers double quotes for strings
3. **Trailing Commas**: Adds trailing commas in multi-line structures
4. **Whitespace**: Consistent spacing around operators and after commas
5. **Indentation**: 4 spaces (Python standard)
6. **Line Breaks**: Intelligent line breaking for long expressions
7. **Import Sorting**: Groups and sorts imports

## Usage

### Check Formatting
```bash
# Check all files
black --check .

# Check specific file
black --check src/baseline.py

# Check with diff output
black --check --diff .
```

### Apply Formatting
```bash
# Format all files
black .

# Format specific file
black src/baseline.py

# Format specific directory
black src/
```

### Pre-commit Hook ✅ (Configured)
Pre-commit is now configured with Black and additional code quality tools.

#### Quick Setup
```bash
# Run the setup script
./scripts/setup-pre-commit.sh
```

Or manually:
```bash
# Install pre-commit
pip install pre-commit==3.8.0

# Install git hooks
pre-commit install

# Run initial check
pre-commit run --all-files
```

#### Configuration
The `.pre-commit-config.yaml` includes:
- **Black**: Code formatting (v24.10.0)
- **Flake8**: Python linting
- **isort**: Import sorting (Black-compatible)
- **mypy**: Static type checking
- **Standard hooks**: Trailing whitespace, YAML/JSON validation, etc.

#### Usage
```bash
# Hooks run automatically on commit
git commit -m "your message"

# Manual run on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black

# Update hook versions
pre-commit autoupdate

# Bypass hooks (emergency only)
git commit --no-verify -m "message"
```

## CI/CD Integration

### GitHub Actions
Add to `.github/workflows/black.yml`:
```yaml
name: Black Formatting Check

on: [push, pull_request]

jobs:
  black:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.x'
    - run: pip install black==24.10.0
    - run: black --check .
```

### GitLab CI
Add to `.gitlab-ci.yml`:
```yaml
black:
  stage: test
  script:
    - pip install black==24.10.0
    - black --check .
```

## VS Code Integration

Add to `.vscode/settings.json`:
```json
{
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length", "88"],
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter"
    }
}
```

## PyCharm Integration

1. Go to Settings → Tools → External Tools
2. Add new tool:
   - Name: Black
   - Program: `black`
   - Arguments: `$FilePath$`
   - Working directory: `$ProjectFileDir$`
3. Assign keyboard shortcut (e.g., Ctrl+Alt+L)

## Impact on Code

### Before Black
```python
def calculate_metrics(y_true,y_pred,threshold=0.5):
    predictions = (y_pred>threshold).astype(int)
    precision=precision_score(y_true,predictions)
    recall=recall_score(y_true,predictions)
    return {'precision':precision,'recall':recall}
```

### After Black
```python
def calculate_metrics(y_true, y_pred, threshold=0.5):
    predictions = (y_pred > threshold).astype(int)
    precision = precision_score(y_true, predictions)
    recall = recall_score(y_true, predictions)
    return {"precision": precision, "recall": recall}
```

## Benefits

1. **Consistency**: Uniform code style across the entire project
2. **No Debates**: Eliminates style discussions in code reviews
3. **Readability**: Improved code readability
4. **Automation**: No manual formatting needed
5. **Diffs**: Cleaner git diffs focused on logic, not style
6. **Speed**: Fast formatting of large codebases

## Verification

After Black formatting was applied:

1. ✅ All 15 Python files were successfully reformatted
2. ✅ No syntax errors introduced
3. ✅ Code functionality unchanged
4. ✅ Tests still pass (verified with `src/data.py`)

## Maintaining Formatting

### For Contributors
1. Install Black: `pip install black==24.10.0`
2. Format before committing: `black .`
3. Check formatting: `black --check .`

### For Reviewers
1. Ensure PR passes Black check
2. Request formatting if check fails
3. Focus reviews on logic, not style

## Rollback

If needed to rollback Black changes:
```bash
git checkout <commit-before-black> -- .
```

Note: This is not recommended as Black formatting improves code quality.

## FAQ

**Q: Will Black break my code?**
A: No, Black only changes formatting, not logic.

**Q: Can I disable Black for specific code?**
A: Yes, use `# fmt: off` and `# fmt: on` comments.

**Q: What if I don't like Black's style?**
A: Black is opinionated by design. The benefit is consistency.

**Q: Does Black support type hints?**
A: Yes, Black properly formats type annotations.

## Resources

- [Black Documentation](https://black.readthedocs.io/)
- [Black GitHub](https://github.com/psf/black)
- [Black Playground](https://black.vercel.app/)
- [PEP 8](https://www.python.org/dev/peps/pep-0008/)
