# Fraud Model Rollout Demo & Tutorial

## Overview

This demo showcases a complete MLOps/GitOps platform for fraud detection model deployment, featuring automated training, canary deployments, monitoring, and rollback capabilities. The system demonstrates enterprise-grade ML model lifecycle management with GitOps principles.

## Prerequisites

Before starting the demo, ensure you have:
- Kubernetes cluster (minikube, kind, or cloud provider)
- kubectl configured
- Docker registry (Harbor recommended)
- MLflow tracking server
- ArgoCD installed
- Argo Workflows installed
- Flagger installed
- Prometheus & Grafana for monitoring

## Demo Scenario

**Context**: Your company's fraud detection team has developed a new ML model (v2) that shows 15% better precision than the current production model (v1). You need to safely deploy this new model with zero downtime and automatic rollback if performance degrades.

---

## Part 1: Initial Setup and Baseline Deployment

### Step 1: Setup the GitOps Environment
**What you'll do:** Initialize the platform and deploy baseline infrastructure

```bash
# Clone the repository
git clone https://github.com/jtayl222/fraud-model-rollout-demo
cd fraud-model-rollout-demo

# Initialize GitOps platform
./scripts/setup-gitops.sh
```

**What this does:**
- Installs ArgoCD, Argo Workflows, and Flagger
- Sets up monitoring with Prometheus and Grafana
- Creates necessary namespaces and RBAC
- Configures GitOps applications for automatic sync

**Demo talking points:**
- "This script sets up our entire MLOps platform as code"
- "Everything is declarative and version-controlled"
- "Self-healing infrastructure that automatically syncs with Git"

### Step 2: Deploy the Baseline Model (v1)
**What you'll do:** Deploy the current production fraud model

```bash
# Check ArgoCD applications
kubectl get applications -n argocd

# Watch the deployment
argocd app sync fraud-detection
argocd app get fraud-detection
```

**What this does:**
- Deploys fraud-v1-baseline model as a Kubernetes service
- Sets up health checks and monitoring
- Configures service mesh routing (100% traffic to v1)

**Demo talking points:**
- "Our baseline model is now serving production traffic"
- "ArgoCD ensures the deployment matches our Git repository"
- "Health checks confirm the model is responding correctly"

---

## Part 2: ML Training Pipeline

### Step 3: Trigger Model Training
**What you'll do:** Start the ML pipeline to train the new fraud model

```bash
# Trigger training pipeline for new model version
./scripts/trigger-ml-pipeline.sh --model-version v2 --follow

# Monitor the workflow
argo list -n argowf
argo get fraud-model-training-v2 -n argowf
```

**What this does:**
- Launches Argo Workflows for model training
- Fetches training data from data lake
- Trains the new fraud detection model
- Validates model performance against baseline
- Pushes model artifacts to MLflow registry
- Builds containerized model serving image

**Demo talking points:**
- "This pipeline runs our complete ML training workflow"
- "Data validation ensures training data quality"
- "Model validation compares against production baseline"
- "All artifacts are versioned and tracked in MLflow"

### Step 4: Review Training Results
**What you'll do:** Examine the training metrics and model performance

```bash
# Check MLflow for model metrics
echo "Visit MLflow UI: http://mlflow.local/experiments"

# View training logs
argo logs fraud-model-training-v2 -n argowf

# Check model artifacts
kubectl get configmap model-metrics-v2 -n fraud-detection -o yaml
```

**What this does:**
- Shows training metrics (accuracy, precision, recall, F1)
- Compares v2 performance against v1 baseline
- Validates model is ready for deployment

**Demo talking points:**
- "New model shows 15% better precision: 0.92 vs 0.80"
- "Recall maintained at 0.88 (acceptable tradeoff)"
- "Model artifacts are automatically versioned"
- "Training pipeline includes automated validation gates"

---

## Part 3: Safe Canary Deployment

### Step 5: Initiate Canary Deployment
**What you'll do:** Deploy the new model using canary deployment strategy

```bash
# Deploy v2 model (triggers canary deployment)
kubectl apply -f k8s/overlays/canary/

# Watch the canary deployment
kubectl get canary fraud-v2-candidate-canary -n fraud-detection -w
```

**What this does:**
- Flagger automatically starts canary deployment
- Deploys v2 model alongside v1 (0% traffic initially)
- Begins automated traffic shifting: 0% → 5% → 10% → 50% → 100%
- Monitors success metrics during each phase

**Demo talking points:**
- "Flagger orchestrates the safe rollout automatically"
- "Traffic shifts gradually while monitoring key metrics"
- "Zero downtime - v1 continues serving during rollout"
- "Automatic rollback if any metrics degrade"

### Step 6: Monitor Canary Progress
**What you'll do:** Watch real-time metrics during the canary deployment

```bash
# Monitor canary status
kubectl describe canary fraud-v2-candidate-canary -n fraud-detection

# Watch service mesh traffic distribution
kubectl get vs fraud-detection-vs -n fraud-detection -o yaml

# Check custom metrics
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1/namespaces/fraud-detection/services/*/model-precision
```

**What this does:**
- Shows current traffic split (e.g., 90% v1, 10% v2)
- Displays real-time success rate, latency metrics
- Monitors custom ML metrics (precision, recall)
- Tracks fraud detection accuracy

**Demo talking points:**
- "Currently 10% of traffic going to v2, 90% to v1"
- "Success rate: 99.8% (above 99% threshold)"
- "Average latency: 45ms (below 100ms threshold)"
- "Model precision: 0.91 (above 0.85 threshold)"

---

## Part 4: Monitoring and Observability

### Step 7: View Monitoring Dashboard
**What you'll do:** Show comprehensive monitoring across the platform

```bash
# Open Grafana dashboard
echo "Visit Grafana: http://grafana.local/d/ml-model-monitoring"

# Check Prometheus metrics
kubectl port-forward svc/prometheus 9090:9090 -n monitoring &
echo "Visit Prometheus: http://localhost:9090"
```

**What this does:**
- Displays real-time model performance metrics
- Shows infrastructure health (CPU, memory, network)
- Tracks business metrics (fraud detection rate)
- Visualizes canary deployment progress

**Demo talking points:**
- "Real-time visibility into model performance"
- "Infrastructure metrics ensure healthy deployment"
- "Business impact: 12% improvement in fraud detection"
- "Automated alerting if thresholds are breached"

### Step 8: Simulate Performance Issue (Optional)
**What you'll do:** Demonstrate automatic rollback capabilities

```bash
# Simulate model degradation (for demo purposes)
kubectl patch deployment fraud-v2-candidate -n fraud-detection \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"mlserver","env":[{"name":"SIMULATE_ERROR","value":"true"}]}]}}}}'

# Watch automatic rollback
kubectl get canary fraud-v2-candidate-canary -n fraud-detection -w
```

**What this does:**
- Triggers model performance degradation
- Flagger detects metric threshold breach
- Automatically rolls back to v1 (100% traffic)
- Sends alerts to operations team

**Demo talking points:**
- "Model precision dropped below 0.85 threshold"
- "Flagger automatically detected the issue"
- "Traffic immediately shifted back to v1"
- "Zero customer impact from the failed deployment"

---

## Part 5: Successful Deployment Completion

### Step 9: Complete Successful Rollout
**What you'll do:** Show successful completion of canary deployment

```bash
# Reset any demo issues
kubectl rollout restart deployment fraud-v2-candidate -n fraud-detection

# Watch completion
kubectl get canary fraud-v2-candidate-canary -n fraud-detection -w

# Verify final state
kubectl get pods -n fraud-detection
kubectl get svc fraud-detection -n fraud-detection
```

**What this does:**
- Completes traffic migration (100% to v2)
- Scales down v1 deployment
- Updates service endpoints
- Finalizes the deployment

**Demo talking points:**
- "Canary deployment successfully completed"
- "100% traffic now routing to v2 model"
- "15% improvement in fraud detection accuracy"
- "Zero downtime during the entire process"

---

## Part 6: GitOps Workflow

### Step 10: Demonstrate GitOps Principles
**What you'll do:** Show how configuration changes trigger automatic deployments

```bash
# Make a configuration change
git checkout -b demo/update-model-config
sed -i 's/max_batch_size: 100/max_batch_size: 150/' k8s/base/fraud-detection-config.yaml

# Commit and push
git add k8s/base/fraud-detection-config.yaml
git commit -m "Increase batch size for better throughput"
git push origin demo/update-model-config

# Create pull request (in GitHub UI)
# After merge, watch ArgoCD sync
argocd app sync fraud-detection
```

**What this does:**
- Demonstrates Git-driven deployments
- Shows configuration drift detection
- Automatic synchronization with repository
- Audit trail for all changes

**Demo talking points:**
- "All changes go through Git workflow"
- "Peer review and approval process"
- "Automatic deployment after merge"
- "Complete audit trail of who changed what when"

---

## Part 7: Advanced Features

### Step 11: Blue-Green Deployment (Alternative Strategy)
**What you'll do:** Show alternative deployment strategy

```bash
# Switch to blue-green strategy
kubectl apply -f k8s/overlays/blue-green/

# Monitor blue-green deployment
kubectl get rollout fraud-detection-rollout -n fraud-detection -w
```

**What this does:**
- Deploys v2 to separate environment (blue)
- Runs validation tests against blue environment  
- Instant traffic switch when validation passes
- Immediate rollback capability

### Step 12: Multi-Region Deployment
**What you'll do:** Show geographic distribution

```bash
# Deploy to multiple regions
kubectl apply -f k8s/overlays/multi-region/

# Check cross-region status
kubectl get applications -n argocd | grep region
```

**What this does:**
- Replicates deployment across regions
- Ensures consistent configuration
- Handles regional failover
- Compliance with data locality requirements

---

## Conclusion & Key Takeaways

### What We Demonstrated:
1. **Zero-Downtime Deployments**: Canary strategy ensures no service interruption
2. **Automated Safety**: Automatic rollback based on metrics
3. **GitOps Principles**: All changes version-controlled and auditable  
4. **Comprehensive Monitoring**: Real-time visibility into model and infrastructure
5. **ML-Specific Features**: Model performance metrics and validation
6. **Enterprise Ready**: RBAC, security, compliance built-in

### Business Value:
- **Risk Reduction**: Safe deployment of ML models with automatic rollback
- **Faster Time-to-Market**: Automated pipelines reduce deployment time from weeks to hours
- **Improved Reliability**: GitOps ensures consistent, reproducible deployments
- **Better Observability**: Real-time monitoring of model performance
- **Compliance**: Full audit trail and approval workflows

### Technical Excellence:
- **Cloud Native**: Kubernetes-native tools and patterns
- **Declarative**: Infrastructure and applications as code
- **Scalable**: Supports multiple models, environments, regions
- **Extensible**: Pluggable components and custom metrics

---

## Troubleshooting Common Issues

### Canary Stuck in Progressing State
```bash
# Check Flagger logs
kubectl logs -f deployment/flagger -n flagger-system

# Verify metrics are available
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1
```

### ArgoCD Out of Sync
```bash
# Force sync
argocd app sync fraud-detection --force

# Check for configuration drift
argocd app diff fraud-detection
```

### Model Performance Issues
```bash
# Check model logs
kubectl logs deployment/fraud-v2-candidate -n fraud-detection

# Verify MLflow connectivity
kubectl exec -it deployment/fraud-v2-candidate -n fraud-detection -- curl http://mlflow.test:5000/health
```

---

## Next Steps

After the demo, participants can:
1. **Customize**: Adapt the platform for their specific ML use cases
2. **Extend**: Add additional deployment strategies or metrics
3. **Scale**: Deploy across multiple environments and regions
4. **Integrate**: Connect to existing ML/data infrastructure
5. **Operationalize**: Set up production monitoring and alerting

For more information, see:
- [Implementation Guide](Phase-10-Implementation-Guide.md)
- [Architecture Overview](Architecture-Overview.md)
- [Best Practices](Best-Practices.md)
