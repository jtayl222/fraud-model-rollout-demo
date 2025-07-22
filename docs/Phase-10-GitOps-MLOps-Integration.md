# Phase 10: GitOps + MLOps Integration with ArgoCD & Argo Workflows

## Overview
This phase demonstrates enterprise-grade ML deployment using GitOps principles with ArgoCD for declarative deployments and Argo Workflows for ML pipelines, creating a fully automated, auditable, and scalable MLOps platform.

## Architecture

```
GitHub Repository
    ↓
GitHub Actions (CI)
    ↓
Container Registry (Harbor)
    ↓
ArgoCD (GitOps)
    ↓
Kubernetes Cluster
    ↑
Argo Workflows (ML Pipelines)
```

## Implementation

### 1. ArgoCD Application for Fraud Detection Models

```yaml
# argocd/fraud-detection-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: fraud-detection-models
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: mlops
  source:
    repoURL: https://github.com/yourusername/fraud-model-rollout-demo
    targetRevision: HEAD
    path: k8s/base
  destination:
    server: https://kubernetes.default.svc
    namespace: seldon-system
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
    - CreateNamespace=true
    - PrunePropagationPolicy=foreground
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### 2. Argo Workflows ML Training Pipeline

```yaml
# argo-workflows/ml-training-pipeline.yaml
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: fraud-model-training
  namespace: argowf
spec:
  entrypoint: ml-pipeline
  arguments:
    parameters:
    - name: model-version
      value: "v2"
    - name: git-repo
      value: "https://github.com/yourusername/fraud-model-rollout-demo"
    - name: git-branch
      value: "main"
  
  templates:
  - name: ml-pipeline
    dag:
      tasks:
      - name: clone-repo
        template: git-clone
        arguments:
          parameters:
          - name: repo
            value: "{{workflow.parameters.git-repo}}"
          - name: branch
            value: "{{workflow.parameters.git-branch}}"
      
      - name: validate-data
        dependencies: [clone-repo]
        template: data-validation
      
      - name: train-baseline
        dependencies: [validate-data]
        template: train-model
        arguments:
          parameters:
          - name: model-type
            value: "baseline"
      
      - name: train-candidate
        dependencies: [validate-data]
        template: train-model
        arguments:
          parameters:
          - name: model-type
            value: "candidate"
      
      - name: evaluate-models
        dependencies: [train-baseline, train-candidate]
        template: model-evaluation
      
      - name: update-manifest
        dependencies: [evaluate-models]
        template: update-k8s-manifest
      
      - name: trigger-deployment
        dependencies: [update-manifest]
        template: argocd-sync

  - name: train-model
    inputs:
      parameters:
      - name: model-type
    container:
      image: harbor.test/mlops/ml-trainer:latest
      command: [python]
      args: 
      - src/train_model.py
      - --model-type
      - "{{inputs.parameters.model-type}}"
      env:
      - name: MLFLOW_TRACKING_URI
        value: "http://mlflow.test:5000"
      - name: AWS_ACCESS_KEY_ID
        valueFrom:
          secretKeyRef:
            name: mlflow-s3-secret
            key: AWS_ACCESS_KEY_ID
      volumeMounts:
      - name: work
        mountPath: /work

  - name: argocd-sync
    container:
      image: argoproj/argocd:v2.8.4
      command: [argocd]
      args:
      - app
      - sync
      - fraud-detection-models
      - --force
      - --prune
```

### 3. ArgoCD MLOps Project

```yaml
# argocd/mlops-project.yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: mlops
  namespace: argocd
spec:
  description: MLOps applications and models
  sourceRepos:
  - 'https://github.com/yourusername/*'
  destinations:
  - namespace: 'seldon-system'
    server: 'https://kubernetes.default.svc'
  - namespace: 'mlflow'
    server: 'https://kubernetes.default.svc'
  - namespace: 'monitoring'
    server: 'https://kubernetes.default.svc'
  clusterResourceWhitelist:
  - group: 'mlops.seldon.io'
    kind: '*'
  - group: 'machinelearning.seldon.io'
    kind: '*'
  namespaceResourceWhitelist:
  - group: '*'
    kind: '*'
  roles:
  - name: ml-engineer
    policies:
    - p, proj:mlops:ml-engineer, applications, *, mlops/*, allow
    - p, proj:mlops:ml-engineer, logs, get, mlops/*, allow
    - p, proj:mlops:ml-engineer, exec, create, mlops/*, allow
```

### 4. Progressive Delivery with Flagger

```yaml
# k8s/base/flagger-canary.yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: fraud-model-canary
  namespace: seldon-system
spec:
  targetRef:
    apiVersion: mlops.seldon.io/v1alpha1
    kind: Model
    name: fraud-v2-candidate
  progressDeadlineSeconds: 3600
  service:
    port: 9000
    targetPort: 9000
  analysis:
    interval: 1m
    threshold: 5
    maxWeight: 50
    stepWeight: 10
    metrics:
    - name: precision
      thresholdRange:
        min: 0.9
      interval: 1m
    - name: recall
      thresholdRange:
        min: 0.85
      interval: 1m
    - name: latency
      thresholdRange:
        max: 500
      interval: 30s
    webhooks:
    - name: acceptance-test
      type: pre-rollout
      url: http://flagger-loadtester.seldon-system/
      timeout: 10s
      metadata:
        type: bash
        cmd: "curl -X POST http://fraud-v2-candidate:9000/v2/models/fraud-v2/infer -d @test-payload.json"
```

### 5. Automated Rollback with ArgoCD

```yaml
# k8s/base/argo-rollback-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rollback-config
  namespace: argocd
data:
  rollback-rules.yaml: |
    rules:
    - name: model-performance-degradation
      condition: |
        app.status.health.status == "Degraded" && 
        app.status.operationState.finishedAt > "10m"
      action: |
        argocd app rollback fraud-detection-models --revision HEAD~1
    - name: high-error-rate
      condition: |
        metrics.error_rate > 0.05
      action: |
        argocd app sync fraud-detection-models --revision stable
```

## Benefits

### 1. **Full Automation**
- Push to Git triggers entire pipeline
- No manual intervention required
- Self-healing deployments

### 2. **Observability**
- Complete audit trail in Git
- ArgoCD UI for deployment status
- Argo Workflows UI for pipeline visualization

### 3. **Safety**
- Automated rollback on failures
- Progressive rollout with Flagger
- Git as single source of truth

### 4. **Scalability**
- Parallel model training
- Multiple environments (dev/staging/prod)
- Easy to add new models

### 5. **Compliance**
- All changes tracked in Git
- RBAC with ArgoCD projects
- Immutable deployment history

## Integration with Existing Platform

Your platform already has:
- ✅ ArgoCD (192.168.1.204)
- ✅ Argo Workflows (192.168.1.205)
- ✅ MLflow tracking
- ✅ Harbor registry
- ✅ Seldon Core v2
- ✅ Monitoring stack

This makes you ready for enterprise MLOps!

## Setup Instructions

1. **Create ArgoCD Application**
```bash
kubectl apply -f argocd/mlops-project.yaml
kubectl apply -f argocd/fraud-detection-app.yaml
```

2. **Deploy Workflow Template**
```bash
kubectl apply -f argo-workflows/ml-training-pipeline.yaml
```

3. **Configure GitHub Webhook**
```bash
# In GitHub repo settings, add webhook:
# URL: http://argo-workflows.yourdomain/api/v1/events/argowf/ml-trigger
# Events: Push, Pull Request
```

4. **Test End-to-End**
```bash
# Make a change to model code
git add src/train_model.py
git commit -m "Improve model architecture"
git push

# Watch the magic happen!
argocd app list
argo list -n argowf
```

## Monitoring Integration

```yaml
# Grafana Dashboard for GitOps metrics
{
  "dashboard": {
    "title": "MLOps GitOps Metrics",
    "panels": [
      {
        "title": "Deployment Frequency",
        "targets": [{
          "expr": "rate(argocd_app_sync_total[5m])"
        }]
      },
      {
        "title": "Lead Time for Changes",
        "targets": [{
          "expr": "histogram_quantile(0.95, argocd_app_sync_duration)"
        }]
      },
      {
        "title": "Model Training Success Rate",
        "targets": [{
          "expr": "sum(rate(argo_workflow_status{status='Succeeded'}[5m])) / sum(rate(argo_workflow_status[5m]))"
        }]
      }
    ]
  }
}
```

## Success Metrics

- **Deployment Frequency**: >10 per day
- **Lead Time**: <15 minutes from commit to production
- **MTTR**: <5 minutes with automated rollback
- **Change Failure Rate**: <5% with progressive delivery
- **Model Drift Detection**: Automated within 1 hour

This completes the enterprise MLOps story with full GitOps integration!