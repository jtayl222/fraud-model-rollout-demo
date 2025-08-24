# Kubernetes Base Configuration

This directory contains the base Kubernetes configurations for the fraud detection model rollout demo.

## Files Overview

### ✅ Ready to Commit (Generic/Safe)
- `namespace.yaml` - Kubernetes namespace definition
- `mlserver.yaml` - MLServer capabilities configuration
- `training-pipeline.yaml` - Model training workflow
- `fraud-model-pvc.yaml` - Persistent Volume Claims for storage
- `kustomization.yaml` - Kustomize configuration file
- `nginx-ingress.yaml` - Ingress routing rules
- `network-policy.yaml` - Network security policies
- `sensor.yaml` - Argo Events sensor configuration
- `event-source.yaml` - Argo Events source configuration
- `fraud-model-data-pipeline.yaml` - Data preparation workflow

### 🔒 Environment-Specific (Use .example Templates)
These files contain environment-specific values and should be created from their `.example` counterparts:

- `model-config.yaml` → Use `model-config.yaml.example`
- `fraud-model-ab-test.yaml` → Use `fraud-model-ab-test.yaml.example`
- `server-config-scoped.yaml` → Use `server-config-scoped.yaml.example`
- `rbac.yaml` → Use `rbac.yaml.example`

## Setup Instructions

### 1. Create Environment-Specific Files

Copy the example files and customize for your environment:

```bash
cp k8s/base/model-config.yaml.example k8s/base/model-config.yaml
cp k8s/base/fraud-model-ab-test.yaml.example k8s/base/fraud-model-ab-test.yaml
cp k8s/base/server-config-scoped.yaml.example k8s/base/server-config-scoped.yaml
cp k8s/base/rbac.yaml.example k8s/base/rbac.yaml
```

### 2. Customize Configuration Values

#### `model-config.yaml`
Update the S3 URIs with actual MLflow artifact paths:
```yaml
data:
  fraud-v1-storage-uri: "s3://your-mlflow-bucket/40/models/m-xxxxxxxxx/artifacts"
  fraud-v2-storage-uri: "s3://your-mlflow-bucket/42/models/m-yyyyyyyyy/artifacts"
```

#### `fraud-model-ab-test.yaml`
Update the storageUri fields with the same S3 paths.

#### `server-config-scoped.yaml`
- Replace `your-registry.com` with your container registry (e.g., `harbor.your-domain.com`)
- Replace `your-s3-credentials-secret` with your actual S3 credentials secret name

#### `rbac.yaml`
Adjust ResourceQuota values based on your cluster capacity:
```yaml
spec:
  hard:
    requests.cpu: "24"          # Adjust for your cluster size
    requests.memory: 96Gi       # Adjust for available memory
    count/pods: "150"           # Adjust based on cluster capacity
```

### 3. Deploy

```bash
kubectl apply -k k8s/base/
```

## Finding MLflow S3 Paths

To find the correct S3 paths for your models:

1. **List experiments:**
   ```bash
   mlflow experiments search
   ```

2. **Find model artifacts:**
   ```bash
   mc ls minio/mlflow-artifacts/{experiment_id}/models/ -r
   # or with AWS CLI:
   aws s3 ls s3://mlflow-artifacts/{experiment_id}/models/ --recursive
   ```

3. **Use the path format:**
   ```
   s3://mlflow-artifacts/{experiment_id}/models/{model_id}/artifacts
   ```

## Security Notes

- The `.example` files contain placeholder values and are safe to commit
- Never commit the actual configuration files as they contain environment-specific secrets and URIs
- Use Kubernetes secrets for sensitive data like S3 credentials
- Consider using external secret management tools like External Secrets Operator

## Directory Structure

```
k8s/base/
├── README.md                              # This file
├── *.yaml                                 # Generic configurations (safe to commit)
├── *.yaml.example                         # Templates for environment-specific configs
└── .gitignore                             # Excludes environment-specific files
```
