# Testing Process Documentation

## Overview
This document outlines the comprehensive testing process for the fraud detection model rollout demonstration project. The testing ensures all components work correctly after code changes, including Black formatting.

## Prerequisites

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

### 2. Required Dependencies
The `requirements.txt` includes:
- Core ML libraries (TensorFlow, scikit-learn, pandas, numpy)
- MLflow for experiment tracking
- Black for code formatting
- Kagglehub for dataset download
- Additional utilities (matplotlib, seaborn, jupyter, etc.)

## Testing Process

### Phase 1: Data Preparation Testing ✅

**Status**: Completed

**Purpose**: Verify data download, enrichment, and temporal drift simulation

**Steps**:
1. Download the Kaggle credit card fraud dataset:
   ```bash
   python src/download.py
   ```
   This downloads the dataset to `~/.cache/kagglehub/`

2. Prepare and enrich the data:
   ```bash
   python src/data.py
   ```
   This script:
   - Creates project directories (`./data/`)
   - Copies dataset from Kaggle cache to project directory
   - Replicates data to reach ~1M transactions
   - Simulates temporal drift in Q1 2024
   - Creates training splits for v1 and v2 models
   - Saves enriched datasets

**Expected Output**:
- `./data/enriched/fraud_dataset.csv` (~1M rows)
- `./data/splits/train_v1.csv` (Jan-Dec 2023 data)
- `./data/splits/train_v2.csv` (Jan 2023-Mar 2024 data)  
- `./data/splits/holdout_test.csv` (Feb-Mar 2024 test data)

**Success Criteria**:
- Final dataset has ~1M rows
- Fraud rate is approximately 1%
- Temporal splits are created correctly
- Q1 2024 data contains injected drift patterns

### Phase 2: Baseline Model Training

**Status**: Pending

**Purpose**: Train the baseline fraud detection model (v1)

**Steps**:
```bash
python src/baseline.py
```

**Expected Behavior**:
- Loads `train_v1.csv` (Jan-Dec 2023 data)
- Trains TensorFlow MLP model
- Saves model as `models/fraud_v1.keras`
- Logs metrics to MLflow (if configured)
- Generates performance metrics

**Success Criteria**:
- Model trains without errors
- Model file is created in `models/` directory
- Training metrics show reasonable performance (AUC > 0.90)
- No memory or computational errors

### Phase 3: Candidate Model Training

**Status**: Pending

**Purpose**: Train the improved candidate model (v2)

**Steps**:
```bash
python src/candidate.py
```

**Expected Behavior**:
- Loads `train_v2.csv` (Jan 2023-Mar 2024 data)
- Trains TensorFlow MLP model with updated data
- Saves model as `models/fraud_v2.keras`
- Logs metrics to MLflow (if configured)
- Generates performance metrics

**Success Criteria**:
- Model trains without errors
- Model file is created in `models/` directory
- Shows improved recall compared to baseline
- Handles Q1 2024 drift patterns effectively

### Phase 4: Offline Validation

**Status**: Pending

**Purpose**: Comprehensive offline evaluation and comparison

**Steps**:
```bash
python src/offline-validation.py
```

**Expected Behavior**:
- Loads both trained models
- Evaluates on holdout test set
- Compares metrics (precision, recall, F1, AUC)
- Generates decision gate report
- Creates visualizations

**Success Criteria**:
- Both models load successfully
- Candidate shows ≥5% recall improvement
- Precision maintained within acceptable range
- Decision gate criteria met for promotion
- Visualization files generated

### Phase 5: Unified Training Script

**Status**: Pending

**Purpose**: Test parameterized model training

**Steps**:
```bash
# Train baseline model
python src/train_model.py --model-type baseline --model-version v1

# Train candidate model
python src/train_model.py --model-type candidate --model-version v2

# Or use environment variables
MODEL_TYPE=retrain MODEL_VERSION=v3 python src/train_model.py
```

**Success Criteria**:
- Script accepts parameters correctly
- Models saved with appropriate names
- MLflow tracking works
- S3 URIs generated for model artifacts

### Phase 6: Online Validation (Optional)

**Status**: Pending

**Purpose**: Test Seldon deployment simulation

**Steps**:
```bash
python src/online-validation.py
```

**Expected Behavior**:
- Simulates A/B test traffic split
- Processes transactions in real-time
- Tracks online metrics
- Simulates feedback loop

### Phase 7: Threshold Tuning (Optional)

**Status**: Pending

**Purpose**: Optimize decision thresholds

**Steps**:
```bash
python src/threshold-tuning.py
```

**Expected Behavior**:
- Analyzes precision-recall trade-offs
- Finds optimal thresholds
- Generates threshold recommendations

## Quick Test Suite

For rapid validation after code changes:

```bash
# Run all core tests sequentially
./scripts/run-tests.sh
```

Or manually:
```bash
# 1. Data preparation (takes ~2-3 minutes)
python src/data.py

# 2. Model training (takes ~5-10 minutes each)
python src/baseline.py
python src/candidate.py

# 3. Validation (takes ~2 minutes)
python src/offline-validation.py
```

## Troubleshooting

### Common Issues and Solutions

1. **ModuleNotFoundError: kagglehub**
   ```bash
   pip install kagglehub==0.3.12
   ```

2. **File not found: creditcard.csv**
   - Run `python src/download.py` first
   - Check `~/.cache/kagglehub/` for downloaded file
   - Ensure `./data/` directory exists

3. **Memory Error during training**
   - Reduce batch size in model training scripts
   - Use subset of data for testing
   - Ensure sufficient RAM available (8GB+ recommended)

4. **MLflow connection errors**
   - Check MLflow environment variables are set
   - Verify MLflow server is running
   - Use local file tracking as fallback

5. **TensorFlow GPU issues**
   - Install CPU version: `pip install tensorflow-cpu`
   - Or configure GPU properly with CUDA/cuDNN

## Performance Benchmarks

Expected execution times on standard hardware (8 CPU cores, 16GB RAM):

| Phase | Script | Execution Time | Memory Usage |
|-------|--------|---------------|--------------|
| Data Download | `download.py` | 10-30 seconds | < 500 MB |
| Data Preparation | `data.py` | 2-3 minutes | 2-3 GB |
| Baseline Training | `baseline.py` | 5-10 minutes | 3-4 GB |
| Candidate Training | `candidate.py` | 5-10 minutes | 3-4 GB |
| Offline Validation | `offline-validation.py` | 1-2 minutes | 2 GB |

## Validation Checklist

Before considering the system ready for deployment:

- [ ] All scripts run without errors
- [ ] Data preparation generates expected file sizes
- [ ] Both models train successfully
- [ ] Offline validation shows improved metrics
- [ ] MLflow tracking captures experiments
- [ ] Code passes Black formatting checks
- [ ] No memory leaks or performance issues
- [ ] Documentation is up to date

## Code Quality Checks

### Black Formatting
```bash
# Check formatting
black --check .

# Apply formatting
black .

# Check specific file
black --check src/baseline.py
```

### Running Tests with Black Applied
After Black formatting (completed), all scripts should run identically as before. The formatting changes are purely cosmetic and don't affect functionality.

## Next Steps

After successful testing:

1. **Containerization**: Build Docker images for model serving
2. **Kubernetes Deployment**: Deploy to Seldon Core v2
3. **Monitoring Setup**: Configure Prometheus/Grafana
4. **A/B Test Execution**: Run live traffic split
5. **Feedback Collection**: Implement delayed feedback loop
6. **Model Promotion**: Automate promotion based on metrics

## Support

For issues or questions:
- Check logs in `logs/` directory (if configured)
- Review MLflow UI for experiment details
- Consult CLAUDE.md for project-specific guidance
- Reference phase documentation in `docs/`