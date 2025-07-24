# Pattern 3 Deployment Guide

This guide outlines the steps to deploy the fraud detection system using Pattern 3 (Standard Scoped Operator).

## Architecture Overview

Pattern 3 uses:
- Operator in `seldon-system` with `clusterwide=true` and `watchNamespaces=[fraud-detection]`
- ServerConfig centralized in `seldon-system`
- Runtime components (scheduler, envoy, gateways) in each application namespace

## Deployment Steps

### 1. Update Seldon Core Setup (Platform Team)

Update the Seldon Core v2 setup to use Pattern 3 configuration:

```bash
helm upgrade seldon-core-v2-setup seldon-core-v2-setup \
  --repo https://storage.googleapis.com/seldon-charts \
  --version 2.9.1 \
  --namespace seldon-system \
  --set controller.clusterwide=true \
  --set controller.watchNamespaces="fraud-detection" \
  --wait
```

### 2. Apply ServerConfig to seldon-system

```bash
kubectl apply -f k8s/base/server-config-centralized.yaml
```

### 3. Deploy Runtime Components to fraud-detection

```bash
helm install seldon-core-v2-runtime seldon-core-v2-runtime \
  --repo https://storage.googleapis.com/seldon-charts \
  --version 2.9.1 \
  --namespace fraud-detection \
  --create-namespace \
  --set seldonRuntime.seldonConfig=default \
  --set seldonRuntime.scheduler.enabled=true \
  --set image.pullSecrets[0].name=harbor \
  --set image.registry=harbor.test/library \
  --wait
```

### 4. Apply Application Resources

```bash
kubectl apply -k k8s/base/
```

### 5. Verify Deployment

```bash
# Check runtime components in fraud-detection
kubectl get pods -n fraud-detection | grep seldon

# Check ServerConfig in seldon-system
kubectl get serverconfig -n seldon-system

# Check Server and Models in fraud-detection
kubectl get servers,models -n fraud-detection

# Test inference
kubectl port-forward -n fraud-detection svc/mlserver 9000:9000
curl -X POST http://localhost:9000/v2/models/fraud-v1-baseline/infer \
  -H "Content-Type: application/json" \
  -d @test-payload.json
```

## Rollback to Pattern 4

If you need to rollback to Pattern 4:

1. Delete runtime components:
   ```bash
   helm uninstall seldon-core-v2-runtime -n fraud-detection
   ```

2. Delete ServerConfig from seldon-system:
   ```bash
   kubectl delete -f k8s/base/server-config-centralized.yaml
   ```

3. Restore Pattern 4 configuration in kustomization.yaml

4. Apply Pattern 4 resources with custom operator image

## Key Differences from Pattern 4

| Component | Pattern 4 | Pattern 3 |
|-----------|-----------|-----------|
| ServerConfig | fraud-detection namespace | seldon-system namespace |
| Scheduler | seldon-system (shared) | fraud-detection (dedicated) |
| Runtime | seldon-system | fraud-detection |
| Operator Config | clusterwide=false | clusterwide=true |
| Custom Fix | Required | Not required |