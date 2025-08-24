# Comprehensive Testing Checklist

## Overview
This document provides a complete testing checklist to ensure the fraud detection system works correctly after code formatting changes (Black, isort, pre-commit).

## Testing Phases

### Phase 1: Local Python Code Testing ✅

#### 1.1 Data Pipeline
```bash
# Already tested and working
python src/data.py
```
- ✅ Downloads dataset from Kaggle
- ✅ Creates enriched dataset (~1M rows)
- ✅ Generates temporal splits
- ✅ Simulates Q1 2024 drift

**Status**: PASSED

#### 1.2 Model Training
```bash
# Test baseline model
python src/baseline.py

# Test candidate model  
python src/candidate.py

# Test parameterized training
python src/train_model.py --model-type baseline --model-version v1
python src/train_model.py --model-type candidate --model-version v2
```

**Expected Results**:
- Models train without errors
- Models saved to `models/` directory
- Metrics logged to MLflow
- S3 URIs generated

#### 1.3 Offline Validation
```bash
python src/offline-validation.py
```

**Expected Results**:
- Both models evaluated
- Comparison metrics generated
- Decision gate criteria checked
- Visualizations created

#### 1.4 Quick Test Script
```bash
# Run all local tests
./scripts/run-tests.sh

# Force re-run everything
./scripts/run-tests.sh --force
```

### Phase 2: Code Quality Validation

#### 2.1 Black Formatting
```bash
# Check formatting
black --check .

# Apply formatting if needed
black .
```

#### 2.2 Import Sorting (isort)
```bash
# Check import sorting
isort --check-only . --profile=black

# Sort imports if needed
isort . --profile=black
```

#### 2.3 Pre-commit Hooks
```bash
# Run all pre-commit checks
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run isort --all-files
pre-commit run flake8 --all-files
```

### Phase 3: Kubernetes Deployment Testing

#### 3.1 Pre-deployment Validation
```bash
# Check KUBECONFIG
echo $KUBECONFIG
kubectl cluster-info

# Verify Seldon Core v2
kubectl get crd models.mlops.seldon.io
kubectl get pods -n seldon-system
```

#### 3.2 Deploy to K8s
```bash
# Deploy using Kustomize
kubectl apply -k k8s/base/

# Or deploy individual files
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/model-config.yaml
kubectl apply -f k8s/base/fraud-model-ab-test.yaml
```

#### 3.3 Run K8s Test Script
```bash
# Comprehensive K8s deployment test
./scripts/test-k8s-deployment.sh

# With specific namespace
NAMESPACE=financial-ml ./scripts/test-k8s-deployment.sh
```

#### 3.4 Verify Deployment
```bash
# Check models
kubectl get models -A | grep fraud

# Check pods
kubectl get pods -A | grep -E "(fraud|mlserver)"

# Check services
kubectl get svc -A | grep -E "(fraud|mlserver)"

# Check logs
kubectl logs -n <namespace> <pod-name> --tail=100
```

### Phase 4: Integration Testing

#### 4.1 Model Endpoint Testing
```bash
# Port-forward to model service
kubectl port-forward -n <namespace> svc/fraud-mlserver 8080:8080

# In another terminal, test prediction
curl -X POST http://localhost:8080/v2/models/fraud-model/infer \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [{
      "name": "predict",
      "shape": [1, 30],
      "datatype": "FP32",
      "data": [/* 30 feature values */]
    }]
  }'
```

#### 4.2 A/B Testing Validation
```bash
# Run production pipeline validation
python scripts/validate-production-pipeline.py

# Check traffic distribution
python scripts/check-ab-split.py
```

#### 4.3 Monitoring Validation
```bash
# Check Prometheus metrics
curl http://prometheus:9090/api/v1/query?query=seldon_model_requests_total

# Check Grafana dashboards
# Access Grafana UI and verify dashboards load
```

### Phase 5: End-to-End Testing

#### 5.1 Full Pipeline Test
```bash
# 1. Generate new test data
python src/generate-test-batch.py

# 2. Send batch predictions
python scripts/batch-inference.py

# 3. Verify results
python scripts/verify-predictions.py
```

#### 5.2 Performance Testing
```bash
# Load test with multiple concurrent requests
python scripts/load-test.py --concurrent 10 --requests 100

# Check response times
python scripts/measure-latency.py
```

## Testing Matrix

| Component | Local Test | K8s Test | Status |
|-----------|------------|----------|--------|
| Data Pipeline | `src/data.py` | N/A | ✅ PASSED |
| Baseline Model | `src/baseline.py` | Model CRD | ⏳ PENDING |
| Candidate Model | `src/candidate.py` | Model CRD | ⏳ PENDING |
| Offline Validation | `src/offline-validation.py` | N/A | ⏳ PENDING |
| Model Serving | N/A | MLServer pods | ⏳ PENDING |
| A/B Testing | `validate-production-pipeline.py` | Experiment CRD | ⏳ PENDING |
| Monitoring | N/A | Prometheus/Grafana | ⏳ PENDING |

## Rollback Plan

If issues are discovered:

### 1. Code Rollback
```bash
# Revert Black/isort changes
git checkout <commit-before-formatting> -- .

# Or revert specific files
git checkout HEAD~1 -- src/
```

### 2. K8s Rollback
```bash
# Delete current deployment
kubectl delete -k k8s/base/

# Apply previous version
git checkout <previous-version> -- k8s/
kubectl apply -k k8s/base/
```

### 3. Emergency Fix
```bash
# Route all traffic to baseline model
kubectl patch experiment fraud-ab-test -n <namespace> \
  --type='json' -p='[{"op": "replace", "path": "/spec/candidates/0/weight", "value": 0}]'
```

## Success Criteria

The system is considered fully tested when:

1. ✅ All Python scripts run without errors
2. ✅ Black and isort formatting applied without breaking functionality
3. ✅ Pre-commit hooks pass on all files
4. ✅ Models deploy successfully to K8s
5. ✅ Model endpoints respond with valid predictions
6. ✅ A/B traffic split works correctly (80/20)
7. ✅ Monitoring shows expected metrics
8. ✅ No errors in pod logs
9. ✅ Response time < 2 seconds
10. ✅ Memory usage stable over time

## Test Automation

To run all tests automatically:

```bash
# Create master test script
cat > scripts/run-all-tests.sh << 'EOF'
#!/bin/bash
set -e

echo "Running comprehensive test suite..."

# 1. Local tests
./scripts/run-tests.sh

# 2. Code quality
pre-commit run --all-files

# 3. K8s deployment (if connected)
if kubectl cluster-info &>/dev/null; then
    ./scripts/test-k8s-deployment.sh
else
    echo "Skipping K8s tests (not connected to cluster)"
fi

echo "All tests completed!"
EOF

chmod +x scripts/run-all-tests.sh
./scripts/run-all-tests.sh
```

## Continuous Testing

For ongoing validation:

1. **Pre-commit**: Runs automatically on every commit
2. **CI/CD Pipeline**: Add `.github/workflows/test.yml`
3. **Scheduled Tests**: Cron job for nightly validation
4. **Monitoring Alerts**: Real-time issue detection

## Documentation

After testing, update:
- [ ] README.md with test results
- [ ] CHANGELOG.md with formatting changes
- [ ] docs/testing-process.md with any new findings
- [ ] k8s/base/README.md with deployment notes