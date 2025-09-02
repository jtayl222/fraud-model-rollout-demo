# Pattern 3 Deployment Guide for Fraud Detection

## Overview

Pattern 3 architecture requires:
1. **ServerConfig** in `seldon-system` namespace (managed by infrastructure team)
2. **Runtime components** in each application namespace (`fraud-detection`)
3. **Application resources** (Models, Experiments, Server) in application namespace

## Infrastructure Prerequisites

The following MUST be configured by the infrastructure team before deploying this project:

### Required Infrastructure Setup
1. **Seldon Core v2** installed in `seldon-system` namespace
2. **ServerConfig** named `mlserver-config` in `seldon-system`
3. **Operator** configured to watch `fraud-detection` namespace
4. **RBAC** permissions for cross-namespace ServerConfig access

### Verification
Run the prerequisite check:
```bash
./scripts/test-k8s-deployment.sh
```

If prerequisites fail, contact your infrastructure team with the specific requirements shown.

## Application Deployment Steps

Once infrastructure prerequisites are met:

## 1. Clean Up Any Incorrect Resources

```bash
# Remove any ServerConfig incorrectly created in fraud-detection
# (ServerConfig should only exist in seldon-system, managed by infrastructure team)
kubectl delete serverconfig mlserver-config -n fraud-detection 2>/dev/null || true
```

## 2. Deploy Runtime Components to fraud-detection

Pattern 3 requires runtime components in each application namespace:

```bash
# Add Seldon Helm repo if not already added
helm repo add seldon-charts https://seldonio.github.io/seldon-core-v2-charts
helm repo update

# Deploy runtime to fraud-detection namespace
helm install seldon-runtime-fraud seldon-charts/seldon-core-v2-runtime \
  --version 2.9.1 \
  --namespace fraud-detection \
  --create-namespace \
  --set seldonRuntime.scheduler.enabled=true \
  --set seldonRuntime.envoy.enabled=true \
  --set seldonRuntime.modelGateway.enabled=true \
  --set seldonRuntime.pipelineGateway.enabled=true \
  --set seldonRuntime.dataflowEngine.enabled=true \
  --wait

# Verify runtime components are running
kubectl get pods -n fraud-detection -l app.kubernetes.io/name=seldon-scheduler
kubectl get pods -n fraud-detection -l app.kubernetes.io/name=seldon-mesh
```

## 3. Deploy Application Resources

```bash
# Apply kustomization (without ServerConfig)
kubectl apply -k k8s/base/

# Verify Server is created and references correct ServerConfig
kubectl get server mlserver -n fraud-detection -o jsonpath='{.spec.serverConfig}' && echo
# Should output: seldon-system/mlserver-config
```

## 4. Troubleshooting Infrastructure Issues

If Server shows "ServerConfig not found", this is an infrastructure issue:

**Contact your infrastructure team** to:
1. Verify cross-namespace RBAC permissions are configured
2. Check the operator can access ServerConfig in seldon-system
3. Restart the operator if needed (requires infrastructure team access)

## 5. Verify Deployment

Run the test script:

```bash
./scripts/test-k8s-deployment.sh
```

Expected output:
- Runtime components in `fraud-detection`: ✓
- ServerConfig in `seldon-system`: ✓
- Server Ready: ✓
- Models Ready: ✓

## Architecture Diagram

```
seldon-system namespace (INFRASTRUCTURE TEAM):
├── seldon-v2-controller (operator)
├── ServerConfig: mlserver-config (centralized)
├── RBAC rules for cross-namespace access
└── [NO runtime components here for Pattern 3]

fraud-detection namespace (APPLICATION TEAM):
├── Runtime Components:
│   ├── seldon-scheduler (deployed via Helm)
│   ├── seldon-mesh (envoy)
│   ├── model-gateway
│   ├── pipeline-gateway
│   └── dataflow-engine
├── Application Resources:
│   ├── Server: mlserver → references seldon-system/mlserver-config
│   ├── Model: fraud-v1-baseline
│   ├── Model: fraud-v2-candidate
│   └── Experiment: fraud-ab-test
└── Storage:
    └── PVCs for models and data
```

## Responsibilities

### Infrastructure Team
- Install and maintain Seldon Core v2 in `seldon-system`
- Create and manage ServerConfig resources
- Configure operator to watch application namespaces
- Set up RBAC for cross-namespace access
- Monitor and restart operator when needed

### Application Team (This Project)
- Deploy runtime components to `fraud-detection` via Helm
- Create and manage Models, Experiments, and Server resources
- Configure application-specific settings
- Monitor model performance and A/B tests

## Troubleshooting

### ServerConfig Not Found
- Ensure ServerConfig exists in `seldon-system`: `kubectl get serverconfig -n seldon-system`
- Check operator logs: `kubectl logs -n seldon-system deployment/seldon-v2-controller-manager`
- Verify RBAC allows cross-namespace access

### Runtime Components Missing
- Runtime must be in `fraud-detection` for Pattern 3
- Use Helm to deploy runtime components (see step 3)
- Do NOT use runtime components from `seldon-system`

### Models Not Ready
- Check Server is ready first: `kubectl get server mlserver -n fraud-detection`
- Verify runtime components are running: `kubectl get pods -n fraud-detection`
- Check scheduler logs: `kubectl logs -n fraud-detection -l app.kubernetes.io/name=seldon-scheduler`

## Notes

- Pattern 3 is the recommended approach by Seldon team
- Each namespace gets its own runtime components (higher resource usage but better isolation)
- ServerConfigs are centrally managed in `seldon-system`
- This pattern works with official Seldon Helm charts without custom patches