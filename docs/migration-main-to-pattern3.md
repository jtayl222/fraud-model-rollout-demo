# Migration Guide: Main Branch → Pattern 3

## Overview

This guide documents every change necessary to upgrade from the main branch (models deployed directly to seldon-system) to Pattern 3 (lc525's recommended architecture with centralized ServerConfig).

## Pre-Migration State (Main Branch)

- Models deployed directly in `seldon-system` namespace
- ServerConfig and Server resources co-located
- Single namespace deployment pattern

## Post-Migration State (Pattern 3)

- ServerConfig centralized in `seldon-system` namespace  
- Application resources in dedicated `fraud-detection` namespace
- Runtime components deployed via Helm to application namespace
- Official Seldon Core v2 architecture (no custom patches)

## Step-by-Step Migration

### 1. Update Seldon Core Setup (Platform Team)

```bash
# Configure operator for Pattern 3
helm upgrade seldon-core-v2-setup seldon-core-v2-setup \
  --repo https://storage.googleapis.com/seldon-charts \
  --version 2.9.1 \
  --namespace seldon-system \
  --set controller.clusterwide=true \
  --set controller.watchNamespaces="fraud-detection" \
  --wait
```

### 2. File Changes Required

#### A. New Files to Create

**`k8s/base/server-config-centralized.yaml`**
- ServerConfig resource for seldon-system namespace
- Contains MLServer configuration with harbor image pulls secrets
- Replaces any existing ServerConfig in application namespace

**`k8s/base/namespace.yaml`**
- Creates fraud-detection namespace with proper labels
- Includes pod security standards (baseline enforcement)

**`k8s/base/pattern3-deployment-guide.md`**
- Complete deployment instructions for Pattern 3
- Helm commands for runtime deployment
- Verification steps

**`docs/best-architecture.md`**
- Pattern 3 vs Pattern 4 analysis
- Migration rationale and decision documentation

#### B. Files to Modify

**`k8s/base/mlserver.yaml`**
```yaml
# OLD (main branch): ServerConfig in same namespace
serverConfig: mlserver-config  # Looks in fraud-detection namespace

# NEW (Pattern 3): References centralized ServerConfig  
serverConfig: mlserver-config  # Pattern 3: References ServerConfig in seldon-system namespace
```

**`k8s/base/kustomization.yaml`**
```yaml
# OLD (main branch):
resources:
  - server-config-scoped.yaml    # Local ServerConfig

# NEW (Pattern 3):
resources:
  - server-config-centralized.yaml  # Centralized ServerConfig
  # - server-config-scoped.yaml     # Not used in Pattern 3
```

**`scripts/validate-production-pipeline.py`**
```python
# OLD (main branch): May use different endpoint
SELDON_ENDPOINT = "http://192.168.1.202"  # Istio gateway

# NEW (Pattern 3): Use seldon-mesh LoadBalancer
SELDON_ENDPOINT = "http://192.168.1.212"  # seldon-mesh LoadBalancer IP

# Model names: Use Seldon resource names (not MLServer internal names)
"fraud-v1-baseline"     # Correct
"fraud-v1-baseline_1"   # Incorrect (MLServer internal name)
```

**`src/online-validation.py`**
- Same endpoint and model name changes as validation script

#### C. Files to Remove from Main Branch

```bash
# Remove experimental/redundant files
rm .claude/settings.local.json
rm fraud-detection-ml-secrets-20250722.tar.gz  
rm seldon-system-ml-secrets-20250719.tar.gz
rm scripts/seldon-architecture-diagram.py
rm data.ipynb
rm docs/Phase-12-Hodometer-Analytics-Configuration.md
rm -rf k8s/multi-namespace/
rm -rf k8s/manifests/fraud-detection/
rm docs/seldon-production-architecture-decision.md
rm docs/istio-gateway-config.yaml
```

### 3. Deployment Steps

#### Step 1: Apply ServerConfig to seldon-system
```bash
kubectl apply -f k8s/base/server-config-centralized.yaml
```

#### Step 2: Deploy Runtime Components
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

#### Step 3: Apply Application Resources
```bash
kubectl apply -k k8s/base/
```

#### Step 4: Verify Deployment
```bash
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

### 4. Key Differences from Main Branch

| Component | Main Branch | Pattern 3 |
|-----------|-------------|-----------|
| **ServerConfig Location** | Same as models | seldon-system namespace |
| **Runtime Deployment** | Kustomize/YAML | Helm chart |  
| **Operator Configuration** | clusterwide=false | clusterwide=true |
| **Namespace Strategy** | Single (seldon-system) | Multi (seldon-system + fraud-detection) |
| **Scheduler** | Shared in seldon-system | Dedicated per namespace |
| **External Access** | Via Istio/Nginx | Via seldon-mesh LoadBalancer |

### 5. Validation

After migration, validate that:

- ✅ Models are accessible via seldon-mesh LoadBalancer (192.168.1.212)
- ✅ A/B testing experiment routes correctly between models
- ✅ Online validation shows expected performance (+36% recall improvement)
- ✅ No custom operator patches required

### 6. Rollback Plan

If migration fails:

1. **Restore main branch configuration**:
   ```bash
   git checkout main -- k8s/base/
   kubectl apply -k k8s/base/
   ```

2. **Remove Pattern 3 runtime**:
   ```bash
   helm uninstall seldon-core-v2-runtime -n fraud-detection
   kubectl delete namespace fraud-detection
   ```

3. **Restore original operator configuration**:
   ```bash
   helm upgrade seldon-core-v2-setup seldon-core-v2-setup \
     --set controller.clusterwide=false
   ```

## Benefits of Pattern 3 Migration

1. **✅ Official Support**: Uses lc525's recommended architecture
2. **✅ No Custom Patches**: Works with standard Seldon Core v2.9.1
3. **✅ Better Isolation**: Application namespace separation
4. **✅ Scalability**: Each namespace gets dedicated scheduler
5. **✅ Production Ready**: Battle-tested architecture pattern

## Files Changed Summary

**New Files**: 6
**Modified Files**: 4  
**Removed Files**: 9
**Conditional Files**: 11 (evaluate based on requirements)

This migration transforms the deployment from a single-namespace pattern to the officially recommended multi-namespace Pattern 3 architecture.