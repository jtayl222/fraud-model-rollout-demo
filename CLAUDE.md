# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a fraud detection model rollout demonstration that shows how to safely deploy new fraud detection models in production using A/B testing with Seldon Core. The project simulates a real-world scenario where a baseline model degrades due to concept drift, requiring a new candidate model to be trained and A/B tested before full deployment.

## Key Commands

### Data Preparation
```bash
# Download Kaggle dataset (if not already present)
python src/download.py

# Prepare and enrich data with temporal drift simulation
python src/data.py
```

### Model Training
```bash
# Train baseline model v1 (Jan-Dec 2023 data)
python src/baseline.py

# Train candidate model v2 (Jan 2023-Mar 2024 data)
python src/candidate.py
```

### Full Pipeline
```bash
# Run complete offline validation pipeline (phases 1-4)
python src/offline-validation.py
```

### Seldon Deployment (Phase 5+)
```bash
# Deploy A/B test in Kubernetes/Seldon
kubectl apply -f seldon/seldon-fraud-abtest.yaml

# Simulate transaction replay
python scripts/replay_transactions.py

# Send delayed feedback
python scripts/send_feedback.py
```

## Architecture Overview

### Data Flow
1. **Original Data**: `data/creditcard.csv` - Kaggle credit card fraud dataset
2. **Enriched Data**: `data/enriched/fraud_dataset.csv` - ~1M transactions with temporal drift
3. **Training Splits**: 
   - `data/splits/train_v1.csv` - Baseline training (Jan-Dec 2023)
   - `data/splits/train_v2.csv` - Candidate training (Jan 2023-Mar 2024)
   - `data/splits/holdout_test.csv` - Test set (Feb-Mar 2024)

### Model Architecture
Both models use identical TensorFlow MLP architecture:
- Input: 30 features (transaction attributes)
- Hidden layers: Dense(128) → Dense(64) → Dense(32)
- Output: Binary classification (fraud/legitimate)
- Training handles class imbalance with weighted loss

### Key Design Decisions
1. **Temporal Drift Simulation**: Q1 2024 data introduces new fraud patterns (merchant categories, transaction times, amounts)
2. **Model Versioning**: Models are saved as `fraud_v1.keras` and `fraud_v2.keras` for clear distinction
3. **Decision Gate**: Candidate model must improve recall by ≥5% while maintaining precision to be promoted
4. **A/B Testing**: 80/20 traffic split allows safe validation in production

### Project Structure
- `src/`: Core Python scripts for data processing and model training
- `models/`: Saved TensorFlow models
- `data/`: Dataset files and splits
- `docs/`: Phase-by-phase documentation of the rollout process
- `seldon/`: Kubernetes deployment configurations (not yet implemented)
- `scripts/`: Transaction replay and feedback simulation (not yet implemented)

## Development Environment & Workflow

### Platform Information
- **Development Machine**: MacBook (macOS)
- **Target Deployment**: Ubuntu machine with Harbor container registry
- **MLflow Setup**: 
  - Virtual environment at `.venv/bin/mlflow`
  - MLflow installed and configured with environment variables:
    ```bash
    MLFLOW_TRACKING_URI=http://mlflow.test:5000
    MLFLOW_ARTIFACT_ROOT=s3://mlflow-artifacts          # Auto-uploads to S3/MinIO
    MLFLOW_S3_ENDPOINT_URL=http://minio.test:9000
    MLFLOW_TRACKING_USERNAME=mlflow
    MLFLOW_TRACKING_PASSWORD=my-secure-mlflow-tracking-password
    MLFLOW_DB_USERNAME=mlflow
    MLFLOW_DB_PASSWORD=mlflow-secure-password-123
    MLFLOW_FLASK_SECRET_KEY=6EF6B30F9E557F948C402C89002C7C8A
    AWS_ACCESS_KEY_ID=minioadmin
    AWS_SECRET_ACCESS_KEY=minioadmin
    ```
- **MLflow Access**: Claude has access to MLflow CLI commands like `mlflow experiments search`, `mlflow models list`, etc.

### Development Workflow
1. **Local Development**: Make changes on MacBook
2. **Model Training**: Use parameterized training script
   ```bash
   # Train baseline model (v1)
   python src/train_model.py --model-type baseline --model-version v1
   
   # Train candidate model (v2) 
   python src/train_model.py --model-type candidate --model-version v2
   
   # Or use environment variables
   MODEL_TYPE=retrain MODEL_VERSION=v3 python src/train_model.py
   ```
3. **Update Model Configuration**: Script automatically updates K8s config with S3 URIs
   ```bash
   # Automatically reads URIs from training output files
   python scripts/update-model-config.py
   
   # Or specify URIs and traffic split manually
   python scripts/update-model-config.py \
     --v1-uri "s3://mlflow-artifacts/40/abc123/artifacts/fraud-v1-baseline" \
     --v2-uri "s3://mlflow-artifacts/41/def456/artifacts/fraud-v2-candidate" \
     --baseline-weight 70 --candidate-weight 30
   ```
5. **Commit & Push**: All changes must be committed and pushed to Git repository
6. **Remote Build**: User pulls changes on Ubuntu machine, builds container images, and pushes to Harbor registry  
7. **Kubernetes Deployment**: Deploy A/B test with real S3 URIs
   ```bash
   kubectl apply -k k8s/base/
   ```

### Key Commands Available to Claude

#### MLflow Integration
```bash
# Search experiments
mlflow experiments search

# List registered models
mlflow models list

# Get model versions
mlflow models get-version --name FraudDetectionModel_V1 --version 1

# Download model artifacts
mlflow artifacts download --run-id <run_id>
```

#### Kubernetes/Seldon Commands
```bash
# Apply k8s manifests
kubectl apply -k k8s/base/

# Check Seldon models
kubectl get models -n seldon-system

# Check Seldon experiments (A/B tests)
kubectl get experiments -n seldon-system
```

## Important Considerations

- **Seldon Core Version**: Cluster runs Seldon Core v2 (not v1 as shown in some documentation examples)
- **API Versions**: Use `mlops.seldon.io/v1alpha1` for Model and Experiment resources
- **Model Registry**: Models need to be registered in MLflow before Seldon deployment
- **Container Images**: All application containers must be built and pushed to Harbor registry
- The project currently implements phases 1-4 (offline validation). Phases 5-8 (Seldon deployment) are documented but not yet implemented.
- No explicit test suite exists - validation is done through the offline-validation.py script
- Requirements.txt is currently empty - the project uses standard data science libraries (pandas, numpy, tensorflow, scikit-learn)
- The enriched dataset simulates ~1% fraud rate to be realistic yet demo-friendly