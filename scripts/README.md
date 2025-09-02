# Fraud Detection Scripts

This directory contains scripts for deploying and managing the fraud detection application on Kubernetes with Seldon Core v2.

## Scripts Overview

### 🔍 Health & Prerequisites

| Script | Purpose | Usage |
|--------|---------|-------|
| `check-prerequisites.sh` | Verify infrastructure prerequisites | `./scripts/check-prerequisites.sh [--namespace fraud-detection]` |
| `health-check.sh` | Quick application health overview | `./scripts/health-check.sh [--namespace fraud-detection]` |

### 🚀 Deployment

| Script | Purpose | Usage |
|--------|---------|-------|
| `deploy-runtime-pattern3.sh` | Deploy runtime components for Pattern 3 | `./scripts/deploy-runtime-pattern3.sh` |
| `test-k8s-deployment.sh` | Full deployment test and diagnostics | `./scripts/test-k8s-deployment.sh [--force]` |

### 🧪 Production Testing

| Script | Purpose | Usage |
|--------|---------|-------|
| `replay_transactions.py` | A/B test transaction replay with confusion matrix analysis | `python scripts/replay_transactions.py` |
| `validate-production-pipeline.py` | Production pipeline validation with preprocessing | `python scripts/validate-production-pipeline.py` |

## Typical Workflow

### 1. Check Infrastructure Prerequisites
```bash
# Quick check
./scripts/health-check.sh

# Detailed prerequisites check
./scripts/check-prerequisites.sh
```

### 2. Deploy Runtime Components (if needed)
```bash
# For Pattern 3 architecture (runtime in application namespace)
./scripts/deploy-runtime-pattern3.sh
```

### 3. Deploy Application
```bash
# Deploy models, server, and experiment
kubectl apply -k k8s/base/
```

### 4. Test Full Deployment
```bash
# Comprehensive deployment test
./scripts/test-k8s-deployment.sh
```

## Script Details

### check-prerequisites.sh

Verifies that the infrastructure team has properly configured:
- ✅ Seldon Core v2 installed in `seldon-system`
- ✅ Required CRDs and controller running
- ✅ ServerConfig `mlserver-config` in `seldon-system`
- ✅ Operator configured to watch application namespace

**Options:**
- `--namespace NAMESPACE`: Specify application namespace (default: fraud-detection)
- `--quiet`: Minimal output for use in other scripts

**Exit codes:**
- `0`: All prerequisites met
- `1`: Prerequisites failed

### health-check.sh

Provides a quick status overview of all components:
- Infrastructure prerequisites
- Runtime components status
- MLServer status
- Models readiness
- A/B test experiment status

**Options:**
- `--namespace NAMESPACE`: Specify application namespace (default: fraud-detection)

### deploy-runtime-pattern3.sh

Deploys Seldon Core v2 runtime components to the application namespace using Helm. This is required for Pattern 3 architecture where:
- ServerConfig is centralized in `seldon-system` (managed by infrastructure team)
- Runtime components are in application namespace (managed by application team)

**Components deployed:**
- seldon-scheduler
- seldon-mesh (Envoy)
- model-gateway
- pipeline-gateway
- dataflow-engine

### test-k8s-deployment.sh

Comprehensive deployment testing that:
1. Runs prerequisites check
2. Deploys application resources via kustomize
3. Checks runtime components
4. Verifies server and model status
5. Tests model endpoints
6. Analyzes logs for errors

**Options:**
- `--force`: Force redeployment even if resources are up to date

## Prerequisites

Before running any deployment scripts, ensure:

1. **Infrastructure Team Setup** (see `k8s/base/INFRASTRUCTURE-REQUIREMENTS.md`):
   - Seldon Core v2 installed in `seldon-system`
   - ServerConfig created in `seldon-system`
   - Operator configured to watch your namespace

2. **Local Tools**:
   - `kubectl` configured and connected to cluster
   - `helm` installed (for runtime deployment)

3. **Namespace**:
   - Application namespace exists or scripts have permission to create it

## Troubleshooting

### Common Issues

**Prerequisites Failed:**
- Contact infrastructure team with specific error messages
- See `k8s/base/INFRASTRUCTURE-REQUIREMENTS.md` for requirements

**Runtime Components Missing:**
```bash
# Deploy runtime for Pattern 3
./scripts/deploy-runtime-pattern3.sh
```

**Models Not Ready:**
- Check server status first: `kubectl get server -n fraud-detection`
- Verify runtime components: `kubectl get pods -n fraud-detection`
- Run full diagnostics: `./scripts/test-k8s-deployment.sh`

**ServerConfig Not Found:**
- This is an infrastructure issue
- Contact infrastructure team to create ServerConfig in `seldon-system`

### Debug Commands

```bash
# Quick status
./scripts/health-check.sh

# Check logs
kubectl logs -n fraud-detection -l app.kubernetes.io/name=seldon-scheduler
kubectl logs -n fraud-detection deployment/mlserver

# Check resources
kubectl get models,servers,experiments -n fraud-detection
kubectl describe server mlserver -n fraud-detection
```

## Architecture

These scripts support **Pattern 3** architecture:
- **seldon-system**: Infrastructure team manages operator and ServerConfig
- **fraud-detection**: Application team manages runtime components and models
- **Cross-namespace**: Server references ServerConfig via `seldon-system/mlserver-config`

This provides the best balance of centralized configuration with namespace isolation.