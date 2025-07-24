# Phase 11: Scoped Operator Pattern with Seldon Core v2

## Overview
This phase implements the Scoped Operator Pattern for ML workloads, enabling namespace-scoped ServerConfig lookup while maintaining centralized operator management. This pattern allows teams to manage their own ML deployments with custom configurations while the platform team maintains the core Seldon infrastructure.

## Architecture

### Before: Monolithic Approach
```
seldon-system namespace
├── Seldon Core Components
├── All ServerConfigs
├── All Models
└── All Experiments
```

### After: Scoped Operator Pattern
```
┌─────────────────────────────────────────────────────────────┐
│ seldon-system namespace (Platform Team)                     │
│ ├── seldon-v2-controller-manager (watches all namespaces)  │
│ ├── seldon-scheduler                                        │
│ └── Core Seldon components                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ fraud-detection namespace (Application Team)                │
│ ├── ServerConfig: mlserver-config (namespace-scoped)       │
│ ├── Server: mlserver (references local ServerConfig)       │
│ ├── Models: fraud-v1-baseline, fraud-v2-candidate         │
│ └── Experiments: fraud-ab-test-experiment                  │
└─────────────────────────────────────────────────────────────┘
```

The key innovation of the Scoped Operator Pattern is that the Server resource looks for ServerConfig in its own namespace first, enabling true configuration isolation while the operator remains centralized.

## Key Changes

### 1. Namespace Creation
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: fraud-detection
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/audit: restricted
```

### 2. Resource Quotas & Limits
- CPU: 20 cores request, 40 cores limit
- Memory: 40Gi request, 80Gi limit
- PVCs: 10 maximum
- Load Balancers: 2 maximum

### 3. RBAC Configuration
- ServiceAccounts created in fraud-detection namespace
- Roles scoped to fraud-detection namespace
- No cross-namespace permissions required

### 4. ServerConfig with Namespace Scoping
```yaml
apiVersion: mlops.seldon.io/v1alpha1
kind: ServerConfig
metadata:
  name: mlserver-config
  namespace: fraud-detection  # Local to team namespace
```

### 5. Server References Namespace-Scoped ServerConfig
```yaml
apiVersion: mlops.seldon.io/v1alpha1
kind: Server
metadata:
  name: mlserver
  namespace: fraud-detection
spec:
  serverConfig: mlserver-config  # References local ServerConfig
```

## Why Scoped Operator Pattern?

The Scoped Operator Pattern solves a critical limitation in Seldon Core v2.9.1 where the operator would only look for ServerConfig in the seldon-system namespace. With this pattern:

1. **Operator remains centralized** in seldon-system (managed by platform team)
2. **ServerConfigs are namespace-scoped** (managed by application teams)
3. **Server resources find their ServerConfig locally** (enabling true isolation)

## Benefits

### 1. **True Multi-Tenancy**
- Teams fully isolated in their namespaces
- No accidental interference between teams
- Clear ownership boundaries

### 2. **Security**
- Network policies enforce namespace boundaries
- RBAC prevents cross-namespace access
- Pod security standards enforced

### 3. **Resource Management**
- Per-namespace quotas prevent resource hogging
- Teams can't exceed allocated resources
- Platform stability guaranteed

### 4. **Operational Independence**
- Teams deploy on their own schedule
- Custom configurations per team
- Independent scaling decisions

### 5. **Simplified Troubleshooting**
- Issues isolated to namespace
- Clear audit trails
- Reduced blast radius

## Scoped Operator Pattern Implementation

### Clean Deployment Process

1. **Delete Old Namespace** (Platform Team)
```bash
kubectl delete namespace seldon-system
```

2. **Fresh Ansible Deployment** (Platform Team)
```bash
cd ~/REPOS/ml-platform/ansible
ansible-playbook -i inventory.yml playbooks/seldon-deploy.yml
```

3. **Create Application Namespace**
```bash
kubectl apply -k k8s/base/
```

4. **Verify Deployment**
```bash
# Check namespace resources
kubectl get all -n fraud-detection

# Verify ServerConfig
kubectl get serverconfig -n fraud-detection

# Check models
kubectl get models -n fraud-detection

# Test inference
kubectl port-forward -n fraud-detection svc/mlserver 9000:9000
curl -X POST http://localhost:9000/v2/models/fraud-v1-baseline/infer \
  -H "Content-Type: application/json" \
  -d @test-payload.json
```

## Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: fraud-detection-network-policy
  namespace: fraud-detection
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/part-of: fraud-detection-system
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: seldon-system  # Allow Seldon core components
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx  # Allow ingress
    - podSelector: {}  # Allow intra-namespace
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: seldon-system
    - namespaceSelector:
        matchLabels:
          name: mlflow  # MLflow access
    - namespaceSelector:
        matchLabels:
          name: minio  # S3 storage
  - to:
    - podSelector: {}
  - ports:  # DNS
    - protocol: UDP
      port: 53
```

## Monitoring Integration

Each namespace gets its own:
- Prometheus ServiceMonitor
- Grafana dashboard folder
- Alert routing rules

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: fraud-detection-models
  namespace: fraud-detection
spec:
  selector:
    matchLabels:
      app.kubernetes.io/part-of: fraud-detection-system
  endpoints:
  - port: metrics
    path: /metrics
```

## Best Practices

1. **Namespace Naming**: Use descriptive names (e.g., `fraud-detection`, `recommendation-engine`)
2. **Resource Limits**: Always set appropriate quotas
3. **RBAC**: Follow principle of least privilege
4. **Labels**: Consistent labeling for resource discovery
5. **Documentation**: Each namespace should have README

## Troubleshooting

### Common Issues

1. **ServerConfig Not Found**
   - Ensure ServerConfig is in same namespace as Server
   - Check for typos in serverConfig reference

2. **Permission Denied**
   - Verify ServiceAccount has proper roles
   - Check namespace in RoleBindings

3. **Resource Quota Exceeded**
   - Review current usage: `kubectl describe resourcequota -n fraud-detection`
   - Request increase from platform team if needed

## Success Metrics

- Zero cross-namespace dependencies
- 100% of models deployed in team namespaces
- No permissions errors in logs
- Resource utilization within quotas

The Scoped Operator Pattern provides the foundation for true multi-tenant ML operations at scale, combining the benefits of centralized operator management with namespace-level configuration flexibility!