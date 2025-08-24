#!/bin/bash

# Fraud Model Testing Script
# This script runs all core tests to validate the system after changes
# Usage: ./scripts/run-tests.sh [--force]
#   --force: Re-run all steps even if outputs already exist

set -e  # Exit on error

# Check for --force flag
FORCE_RUN=false
if [ "$1" == "--force" ]; then
    FORCE_RUN=true
    echo "Force mode enabled - will re-run all steps"
fi

echo "========================================="
echo "Fraud Model Rollout - Comprehensive Test"
echo "========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2 completed successfully${NC}"
    else
        echo -e "${RED}✗ $2 failed with exit code $1${NC}"
        exit $1
    fi
}

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not activated${NC}"
    echo "Attempting to activate .venv..."
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        echo -e "${GREEN}Virtual environment activated${NC}"
    else
        echo -e "${RED}Error: .venv not found. Please create virtual environment first.${NC}"
        exit 1
    fi
fi

echo ""
echo "Phase 1: Data Preparation"
echo "-------------------------"

# Check if data already exists
if [ "$FORCE_RUN" = false ] && [ -f "./data/enriched/fraud_dataset.csv" ] && [ -f "./data/splits/train_v1.csv" ] && [ -f "./data/splits/train_v2.csv" ]; then
    echo -e "${GREEN}✓ Data files already exist, skipping preparation${NC}"
else
    if [ "$FORCE_RUN" = true ]; then
        echo "Force mode: Re-running data preparation..."
    fi
    
    # Check if creditcard.csv exists in cache
    if [ "$FORCE_RUN" = false ] && [ -f "$HOME/.cache/kagglehub/datasets/mlg-ulb/creditcardfraud/versions/3/creditcard.csv" ]; then
        echo -e "${GREEN}✓ Dataset already downloaded, skipping download${NC}"
    else
        echo "Downloading dataset..."
        python src/download.py
        print_status $? "Dataset download"
    fi
    
    echo ""
    echo "Preparing and enriching data (this may take 2-3 minutes)..."
    python src/data.py
    print_status $? "Data preparation"
fi

echo ""
echo "Phase 2: Model Training"
echo "-----------------------"

# Check if baseline model exists
if [ "$FORCE_RUN" = false ] && [ -f "./models/fraud_v1.keras" ]; then
    echo -e "${GREEN}✓ Baseline model already exists, skipping training${NC}"
else
    if [ "$FORCE_RUN" = true ] && [ -f "./models/fraud_v1.keras" ]; then
        echo "Force mode: Re-training baseline model..."
    fi
    echo "Training baseline model v1 (this may take 5-10 minutes)..."
    python src/baseline.py
    print_status $? "Baseline model training"
fi

echo ""

# Check if candidate model exists
if [ "$FORCE_RUN" = false ] && [ -f "./models/fraud_v2.keras" ]; then
    echo -e "${GREEN}✓ Candidate model already exists, skipping training${NC}"
else
    if [ "$FORCE_RUN" = true ] && [ -f "./models/fraud_v2.keras" ]; then
        echo "Force mode: Re-training candidate model..."
    fi
    echo "Training candidate model v2 (this may take 5-10 minutes)..."
    python src/candidate.py
    print_status $? "Candidate model training"
fi

echo ""
echo "Phase 3: Offline Validation"
echo "---------------------------"
echo "Running offline validation..."
python src/offline-validation.py
print_status $? "Offline validation"

echo ""
echo "Phase 4: Code Quality Check"
echo "---------------------------"
echo "Running Black formatter check..."
black --check . > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All Python files are properly formatted${NC}"
else
    echo -e "${YELLOW}⚠ Some files need formatting. Run 'black .' to fix.${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}All tests completed successfully!${NC}"
echo "========================================="
echo ""
echo "Summary:"
echo "- Dataset downloaded and prepared (or already exists)"
echo "- Both models trained successfully (or already exist)"
echo "- Offline validation completed"
echo "- Code formatting verified"
echo ""

# Show what files were created/exist
echo "Generated artifacts:"
[ -f "./data/enriched/fraud_dataset.csv" ] && echo -e "${GREEN}✓${NC} ./data/enriched/fraud_dataset.csv"
[ -f "./data/splits/train_v1.csv" ] && echo -e "${GREEN}✓${NC} ./data/splits/train_v1.csv"
[ -f "./data/splits/train_v2.csv" ] && echo -e "${GREEN}✓${NC} ./data/splits/train_v2.csv"
[ -f "./data/splits/holdout_test.csv" ] && echo -e "${GREEN}✓${NC} ./data/splits/holdout_test.csv"
[ -f "./models/fraud_v1.keras" ] && echo -e "${GREEN}✓${NC} ./models/fraud_v1.keras"
[ -f "./models/fraud_v2.keras" ] && echo -e "${GREEN}✓${NC} ./models/fraud_v2.keras"

echo ""
echo "Next steps:"
echo "1. Review metrics in offline-validation output"
echo "2. Check MLflow UI for experiment tracking (if configured)"
echo "3. Proceed with containerization and deployment"