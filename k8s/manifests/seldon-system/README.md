# ML Secrets Package: seldon-system

**Generated:** Sat Jul 19 03:06:33 PM EDT 2025  
**Requestor:** financial-team@company.com  
**Environments:** dev,production

## Quick Start

### 1. Apply Secrets to Your Namespaces

**dev environment (namespace: `seldon-system-dev`):**
```bash
kubectl apply -k dev/
```

**production environment (namespace: `seldon-system`):**
```bash
kubectl apply -k production/
```

### 2. Reference in Your Applications

**Recommended approach using envFrom:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: your-ml-app
spec:
  template:
    spec:
      containers:
      - name: ml-container
        image: your-image
        envFrom:
        - secretRef:
            name: ml-platform  # Simple name!
      imagePullSecrets:
      - name: ghcr  # Simple name!
```

See `secret-reference-template.yaml` for more examples.

## What's Included

### dev/ 
- `ml-platform-sealed-secret.yaml` - Secret name: `ml-platform`
- `ghcr-sealed-secret.yaml` - Secret name: `ghcr`
- `seldon-rclone-sealed-secret.yaml` - Secret name: `seldon-rclone-gs-public`
- `kustomization.yaml` - Ready-to-apply kustomization

### production/ 
- `ml-platform-sealed-secret.yaml` - Secret name: `ml-platform`
- `ghcr-sealed-secret.yaml` - Secret name: `ghcr`
- `seldon-rclone-sealed-secret.yaml` - Secret name: `seldon-rclone-gs-public`
- `kustomization.yaml` - Ready-to-apply kustomization

## Available Environment Variables

When using `envFrom` with the `ml-platform` secret, these variables are automatically available:

- `AWS_ACCESS_KEY_ID` - MinIO access key
- `AWS_SECRET_ACCESS_KEY` - MinIO secret key  
- `AWS_ENDPOINT_URL` - MinIO endpoint
- `AWS_DEFAULT_REGION` - AWS region (us-east-1)
- `MLFLOW_S3_ENDPOINT_URL` - MLflow S3 endpoint
- `MLFLOW_TRACKING_USERNAME` - MLflow username
- `MLFLOW_TRACKING_PASSWORD` - MLflow password
- `MLFLOW_FLASK_SERVER_SECRET_KEY` - MLflow server secret
- `MLFLOW_TRACKING_URI` - MLflow tracking server URL

## Your Application Structure Recommendation

```
your-app-repo/
├── k8s/
│   ├── base/
│   │   ├── kustomization.yaml
│   │   └── deployment.yaml  # Uses envFrom: secretRef: ml-platform
│   └── overlays/
│       ├── dev/
│       │   ├── kustomization.yaml
│       │   └── (secrets applied separately)
│       └── production/
│           ├── kustomization.yaml
│           └── (secrets applied separately)
```

**Deploy Process:**
1. Apply secrets: `kubectl apply -k path/to/secrets/dev/`
2. Deploy app: `kubectl apply -k k8s/overlays/dev/`

## Support

- **Requestor:** financial-team@company.com
- **Infrastructure Team:** infrastructure-team@company.com
- **Platform Docs:** [Internal ML Platform Wiki]

## Secret Rotation

When secrets need rotation, contact the infrastructure team. We'll generate new sealed secrets and deliver them the same way.
