# Infrastructure Requirements for Fraud Detection Application

This document outlines the infrastructure prerequisites required by the fraud detection application team.

## Required Infrastructure Components

### 1. Seldon Core v2 Installation

- **Version**: 2.9.1 or compatible
- **Namespace**: `seldon-system`
- **Components**:
  - Seldon v2 controller manager
  - Required CRDs: `models.mlops.seldon.io`, `servers.mlops.seldon.io`, `experiments.mlops.seldon.io`
  - Required webhooks and validation

### 2. ServerConfig Resource

Create the following ServerConfig in `seldon-system` namespace:

```yaml
apiVersion: mlops.seldon.io/v1alpha1
kind: ServerConfig
metadata:
  name: mlserver-config
  namespace: seldon-system  # MUST be in seldon-system
spec:
  # Copy spec from k8s/base/server-config-centralized.yaml
```

**Important**: The ServerConfig MUST be named `mlserver-config` and MUST be in the `seldon-system` namespace.

### 3. Operator Configuration

Configure the Seldon operator to watch the `fraud-detection` namespace:

```yaml
# In the operator deployment environment variables
env:
- name: WATCH_NAMESPACES
  value: "fraud-detection,<other-namespaces>"
```

Or use cluster-wide mode with appropriate RBAC.

### 4. RBAC Configuration

The operator needs permissions to:
1. Read ServerConfig resources from `seldon-system` namespace
2. Manage resources in `fraud-detection` namespace
3. Allow Server resources in `fraud-detection` to reference ServerConfig in `seldon-system`

Example RBAC (adjust based on your security requirements):

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: seldon-cross-namespace-access
rules:
- apiGroups: ["mlops.seldon.io"]
  resources: ["serverconfigs"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: seldon-cross-namespace-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: seldon-cross-namespace-access
subjects:
- kind: ServiceAccount
  name: seldon-manager
  namespace: seldon-system
```

### 5. Namespace Creation

Create the application namespace:

```bash
kubectl create namespace fraud-detection
```

## Verification Script

The application team will run `./scripts/test-k8s-deployment.sh` which verifies:

1. ✅ `seldon-system` namespace exists
2. ✅ Seldon Core v2 CRDs are installed
3. ✅ Seldon controller is running
4. ✅ ServerConfig `mlserver-config` exists in `seldon-system`
5. ✅ Operator is configured to watch `fraud-detection`

## Infrastructure Team Actions

1. **Install Seldon Core v2** in `seldon-system` namespace
2. **Apply ServerConfig** from `k8s/base/server-config-centralized.yaml` to `seldon-system`
3. **Configure operator** to watch `fraud-detection` namespace
4. **Set up RBAC** for cross-namespace ServerConfig access
5. **Create namespace** `fraud-detection`

## Testing Infrastructure Setup

After setup, verify with:

```bash
# Check Seldon controller is running
kubectl get pods -n seldon-system

# Verify ServerConfig exists
kubectl get serverconfig mlserver-config -n seldon-system

# Check operator configuration
kubectl get deployment -n seldon-system seldon-v2-controller-manager -o yaml | grep WATCH_NAMESPACES

# Test RBAC (as application team would)
kubectl auth can-i get serverconfig -n seldon-system --as=system:serviceaccount:fraud-detection:seldon-server
```

## Contact

If the application team encounters infrastructure issues, they will see error messages like:

- "PREREQUISITE FAILED: ServerConfig 'mlserver-config' not found in seldon-system"
- "PREREQUISITE FAILED: Operator not configured to watch fraud-detection namespace"
- "ServerConfig exists in seldon-system but Server cannot access it"

These indicate infrastructure configuration issues that need to be resolved by the infrastructure team.

## Pattern 3 Architecture

This setup follows Seldon's Pattern 3 architecture:
- **Centralized ServerConfig** in `seldon-system` (infrastructure managed)
- **Runtime components** in application namespaces (application managed)
- **Cross-namespace references** for ServerConfig access

This provides a good balance between centralized configuration management and namespace isolation.