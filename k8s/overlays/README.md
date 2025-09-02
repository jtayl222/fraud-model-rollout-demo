# GitOps Overlays

This directory contains environment-specific Kustomize overlays for the fraud detection application.

## Structure

```
overlays/
├── staging/
│   ├── kustomization.yaml           # Staging configuration
│   └── staging-experiment-patch.yaml # 50/50 A/B test for faster validation
└── production/
    ├── kustomization.yaml           # Production configuration
    └── production-experiment-patch.yaml # Conservative 80/20 A/B test
```

## Usage

### Staging Environment
```bash
# Deploy to staging namespace
kubectl apply -k k8s/overlays/staging/

# Validate without applying
kubectl kustomize k8s/overlays/staging/ --dry-run=client
```

### Production Environment
```bash
# Deploy to production namespace  
kubectl apply -k k8s/overlays/production/

# Validate without applying
kubectl kustomize k8s/overlays/production/ --dry-run=client
```

## Environment Differences

| Configuration | Staging | Production |
|---------------|---------|------------|
| **Namespace** | `fraud-detection-staging` | `fraud-detection` |
| **A/B Split** | 50/50 (faster validation) | 80/20 (conservative) |
| **Replicas** | 1 (resource efficient) | 2 (high availability) |
| **S3 URIs** | `s3://mlflow-artifacts-staging/` | `s3://mlflow-artifacts/production/` |
| **Image Tags** | `staging` | `latest` (or specific SHA) |

## GitOps Integration

### Current State (GitHub Actions)
- CI builds models and containers
- Artifacts uploaded to GitHub Actions
- Manual deployment via kubectl

### Future State (ArgoCD)
```yaml
# argocd/fraud-detection-staging.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: fraud-detection-staging
spec:
  source:
    path: k8s/overlays/staging
```

## Development Workflow

1. **Make Changes**: Update base configuration or overlay patches
2. **Validate Locally**: `kubectl kustomize k8s/overlays/staging/`
3. **Commit to Git**: Changes trigger CI/CD pipeline
4. **Staging Deploy**: Automatic deployment to staging environment
5. **Production Deploy**: Manual approval required for production

## Troubleshooting

### Common Issues

**"no matches for kind" errors**:
- Ensure Seldon Core v2 CRDs are installed
- Check that the target cluster has required operators

**Image pull errors**:
- Verify Harbor registry credentials
- Check image tags match what's built in CI

**Configuration errors**:
- Validate with `kubectl kustomize --dry-run=client`
- Check that base resources exist

### Debug Commands
```bash
# Check what would be deployed
kubectl kustomize k8s/overlays/staging/ | kubectl apply --dry-run=client -f -

# Compare staging vs production
diff <(kubectl kustomize k8s/overlays/staging/) <(kubectl kustomize k8s/overlays/production/)
```