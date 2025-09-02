# Seldon Core v2.9.1 Bug Workaround

## Critical Bug Alert
**Seldon Core v2.9.1 has a bug** where Server resources cannot reference ServerConfig resources in different namespaces. This affects our Pattern 3 architecture deployment.

## The Problem
```yaml
# This SHOULD work but DOESN'T in v2.9.1:
spec:
  serverConfig: seldon-system/mlserver-config  # ❌ Bug: operator can't parse namespace/name
```

## Our Workaround

### Step 1: Copy ServerConfig to Application Namespace
Run the provided workaround script BEFORE deploying:

```bash
# Copy ServerConfig from seldon-system to fraud-detection
./scripts/copy-serverconfig-workaround.sh fraud-detection
```

This script will:
1. Copy `mlserver-config` from `seldon-system` to `fraud-detection` namespace
2. Adjust the namespace metadata appropriately
3. Verify the copy was successful

### Step 2: Deploy with Local Reference
The `mlserver.yaml` has been updated to use a local reference:

```yaml
spec:
  serverConfig: mlserver-config  # ✅ Works: local reference (no namespace prefix)
```

### Step 3: Deploy Application
```bash
# Now deploy normally
kubectl apply -k k8s/base/
```

## Complete Deployment Sequence

```bash
# 1. Ensure prerequisites are met
./scripts/check-prerequisites.sh

# 2. Apply ServerConfig workaround (REQUIRED for v2.9.1)
./scripts/copy-serverconfig-workaround.sh fraud-detection

# 3. Deploy application
kubectl apply -k k8s/base/

# 4. Verify deployment
./scripts/health-check.sh
```

## When This Will Be Fixed
- **Current Status**: Known bug in v2.9.0 and v2.9.1
- **Expected Fix**: Seldon Core v2.10.0 or later
- **Workaround Required Until**: Infrastructure team upgrades Seldon Core

## What Happens Without the Workaround
Without copying ServerConfig to the local namespace:
- Server will show status: `NOT READY`
- Error: `ServerConfig.mlops.seldon.io "mlserver-config" not found`
- No MLServer pods will be created
- Models cannot be deployed

## Verification
After applying the workaround:
```bash
# Check ServerConfig exists in application namespace
kubectl get serverconfig -n fraud-detection

# Check Server is ready
kubectl get server mlserver -n fraud-detection

# Check pods are running
kubectl get pods -n fraud-detection | grep mlserver
```

## Notes for CI/CD
Include the workaround in your deployment pipeline:

```yaml
deploy:
  script:
    - ./scripts/copy-serverconfig-workaround.sh $NAMESPACE
    - kubectl apply -k k8s/base/
```

---
**Remember**: This is a temporary workaround for a Seldon Core bug, not a design choice.