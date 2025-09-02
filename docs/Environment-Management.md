# Environment Management with Kustomize Overlays

## Overview

This document describes how to use Kustomize overlays for environment-specific deployments of the fraud detection ML models across staging and production environments.

## Directory Structure

```
k8s/
├── base/                           # Base configuration (common across environments)
│   ├── kustomization.yaml
│   ├── flagger-canary.yaml
│   ├── model-config.yaml.example   # Template for sensitive values
│   └── ...
└── overlays/                       # Environment-specific configurations
    ├── staging/
    │   ├── kustomization.yaml      # Staging-specific settings
    │   └── staging-experiment-patch.yaml
    └── production/
        ├── kustomization.yaml      # Production-specific settings
        └── production-experiment-patch.yaml
```

## Environment Configurations

### Staging Environment
**Purpose**: Fast validation and testing of new models
- **Namespace**: `fraud-detection-staging`
- **A/B Traffic Split**: 50/50 (aggressive testing)
- **Replicas**: 1 (cost-efficient)
- **Model URIs**: Staging MLflow artifacts
- **Risk Tolerance**: High (can tolerate failures)

```bash
# Deploy to staging
kubectl apply -k k8s/overlays/staging/

# View what would be deployed
kubectl kustomize k8s/overlays/staging/
```

### Production Environment  
**Purpose**: Stable, reliable service for production traffic
- **Namespace**: `fraud-detection`
- **A/B Traffic Split**: 80/20 (conservative rollout)
- **Replicas**: 2+ (high availability)
- **Model URIs**: Production MLflow artifacts
- **Risk Tolerance**: Low (zero downtime required)

```bash
# Deploy to production
kubectl apply -k k8s/overlays/production/

# View what would be deployed
kubectl kustomize k8s/overlays/production/
```

## Configuration Management

### Model Configuration Template

The `k8s/base/model-config.yaml.example` provides a secure template:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fraud-model-config
  namespace: fraud-detection
data:
  # Replace with actual S3 URIs from MLflow artifacts
  fraud-v1-storage-uri: "s3://your-mlflow-bucket/experiments/baseline/artifacts"
  fraud-v2-storage-uri: "s3://your-mlflow-bucket/experiments/candidate/artifacts"
  
  # Traffic split configuration for A/B testing
  traffic-split-baseline: "80"
  traffic-split-candidate: "20"
  
  # Resource allocation for model serving
  cpu-request: 250m
  memory-request: 1Gi
  cpu-limit: 500m
  memory-limit: 2Gi
```

### Updating Configuration

Use the provided script to safely update model configurations:

```bash
# Update both model URIs
./scripts/update-model-config.py \
  --v1-uri "s3://mlflow-prod/exp123/run456/artifacts" \
  --v2-uri "s3://mlflow-prod/exp124/run789/artifacts"

# Update for staging environment  
./scripts/update-model-config.py \
  --config k8s/overlays/staging/model-config.yaml \
  --baseline-weight 50 \
  --candidate-weight 50

# Dry run to preview changes
./scripts/update-model-config.py --dry-run \
  --v2-uri "s3://new-model-uri" \
  --baseline-weight 90 \
  --candidate-weight 10
```

## GitOps Integration

### ArgoCD Applications

Each environment should have its own ArgoCD application:

```yaml
# argocd/fraud-detection-staging.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: fraud-detection-staging
  namespace: argocd
spec:
  project: mlops-fraud-detection
  source:
    repoURL: https://github.com/jtayl222/fraud-model-rollout-demo
    targetRevision: HEAD
    path: k8s/overlays/staging
  destination:
    server: https://kubernetes.default.svc
    namespace: fraud-detection-staging
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true

---
# argocd/fraud-detection-production.yaml  
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: fraud-detection-production
  namespace: argocd
spec:
  project: mlops-fraud-detection
  source:
    repoURL: https://github.com/jtayl222/fraud-model-rollout-demo
    targetRevision: HEAD
    path: k8s/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: fraud-detection
  syncPolicy:
    automated:
      prune: false  # Manual approval for production
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

### Deployment Workflow

1. **Development**: Make changes to base configurations
2. **Staging**: Automatic deployment via ArgoCD
3. **Validation**: Run tests against staging environment
4. **Production**: Manual sync after approval

```bash
# Check application status
argocd app get fraud-detection-staging
argocd app get fraud-detection-production

# Sync staging (automatic)
argocd app sync fraud-detection-staging

# Sync production (manual approval required)
argocd app sync fraud-detection-production --confirm
```

## Environment Differences

| Configuration | Staging | Production |
|---------------|---------|------------|
| **Namespace** | `fraud-detection-staging` | `fraud-detection` |
| **Traffic Split** | 50/50 (fast validation) | 80/20 (safe rollout) |
| **Replicas** | 1 (cost-effective) | 2+ (high availability) |
| **Auto-sync** | Enabled | Manual approval |
| **S3 Bucket** | `mlflow-artifacts-staging` | `mlflow-artifacts-prod` |
| **Monitoring** | Basic | Full alerting |
| **Resource Limits** | Lower | Higher |

## Best Practices

### Security
- Never commit actual S3 URIs or credentials to Git
- Use `.example` files as templates
- Inject sensitive values via ArgoCD or external secrets

### Testing
- Always test changes in staging first
- Use different traffic splits for each environment
- Monitor metrics before promoting to production

### Rollback
- Keep previous configurations in Git history
- Use ArgoCD's rollback functionality
- Have automated rollback triggers for production

## Monitoring and Observability

### Staging Monitoring
```bash
# Check staging deployment status
kubectl get pods -n fraud-detection-staging
kubectl get canary fraud-v2-candidate-canary -n fraud-detection-staging

# View staging metrics
kubectl port-forward svc/grafana 3000:3000 -n monitoring
# Visit: http://localhost:3000/d/staging-ml-models
```

### Production Monitoring
```bash
# Check production deployment status
kubectl get pods -n fraud-detection
kubectl get canary fraud-v2-candidate-canary -n fraud-detection

# View production metrics
kubectl port-forward svc/grafana 3000:3000 -n monitoring  
# Visit: http://localhost:3000/d/production-ml-models
```

## Troubleshooting

### Common Issues

**1. Image Pull Errors**
```bash
# Check image tags in kustomization
grep -r "newTag:" k8s/overlays/

# Verify Harbor registry access
kubectl get secret harbor-docker-config -n fraud-detection
```

**2. Configuration Drift**
```bash
# Compare what's deployed vs what's in Git
argocd app diff fraud-detection-staging
argocd app diff fraud-detection-production
```

**3. Resource Conflicts**
```bash
# Check for resource conflicts between environments
kubectl get all -n fraud-detection-staging
kubectl get all -n fraud-detection

# Ensure proper namespace isolation
kubectl get networkpolicies -A
```

### Emergency Procedures

**Staging Issues**: 
- Safe to experiment and fix
- Can reset environment completely

**Production Issues**:
- Immediate rollback via ArgoCD
- Alert on-call team
- Document incident for post-mortem

```bash
# Emergency production rollback
argocd app rollback fraud-detection-production --revision=previous

# Emergency traffic routing (bypass candidate model)
kubectl patch canary fraud-v2-candidate-canary -n fraud-detection \
  --type='json' -p='[{"op": "replace", "path": "/spec/analysis/interval", "value": "10s"}]'
```

## Migration Guide

### From Single Environment to Multi-Environment

1. **Backup Current Configuration**
```bash
kubectl get all -n fraud-detection -o yaml > backup-current-config.yaml
```

2. **Create Environment-Specific Configs**
```bash
# Copy base to overlays
cp -r k8s/base/ k8s/overlays/staging/
cp -r k8s/base/ k8s/overlays/production/

# Customize each overlay
vim k8s/overlays/staging/kustomization.yaml
vim k8s/overlays/production/kustomization.yaml
```

3. **Test Staging First**
```bash
# Deploy to staging namespace
kubectl apply -k k8s/overlays/staging/ --dry-run=client
kubectl apply -k k8s/overlays/staging/
```

4. **Migrate Production** 
```bash
# Validate production config
kubectl apply -k k8s/overlays/production/ --dry-run=client

# Deploy (zero downtime)
kubectl apply -k k8s/overlays/production/
```

This overlay-based approach provides the foundation for safe, scalable, multi-environment ML model deployments with proper GitOps practices.
