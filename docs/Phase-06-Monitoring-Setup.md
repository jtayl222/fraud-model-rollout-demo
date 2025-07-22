# Phase 6: Online Monitoring & Evaluation

## Overview

With the A/B test infrastructure successfully deployed in Phase 5, Phase 6 focuses on setting up comprehensive monitoring and evaluation systems to track model performance, traffic distribution, and business metrics in real-time.

## 🎯 Monitoring Objectives

### **Primary Metrics**
- **Model Performance**: Precision, recall, F1-score per model
- **Traffic Distribution**: Verify 80/20 split between baseline/candidate
- **Response Latency**: Inference time and throughput
- **System Health**: Resource utilization, error rates

### **Business Metrics**
- **Fraud Detection Rate**: Percentage of fraud caught
- **False Positive Rate**: Legitimate transactions flagged as fraud
- **Financial Impact**: Estimated fraud losses prevented vs operational cost

## 📊 Available Metrics Endpoints

### **Seldon Core Metrics**
```bash
# Scheduler metrics
http://192.168.1.201:9006/metrics

# Model-specific metrics  
http://192.168.1.202/v2/models/fraud-v1-baseline/metrics
http://192.168.1.202/v2/models/fraud-v2-candidate/metrics

# Experiment metrics
http://192.168.1.202/v2/models/fraud-ab-test-experiment.experiment/metrics
```

### **MLServer Metrics**
```bash
# MLServer internal metrics
kubectl port-forward -n seldon-system mlserver-0 8082:8082
curl http://localhost:8082/metrics
```

## 🔧 Monitoring Stack Setup

### **Option A: Kubernetes Native (Recommended)**
Use existing cluster monitoring if available:

```bash
# Check for existing Prometheus
kubectl get prometheus -A

# Check for existing Grafana  
kubectl get grafana -A

# Check for ServiceMonitor CRDs
kubectl get servicemonitor -A
```

### **Option B: Standalone Deployment**
Deploy dedicated monitoring for this project:

```yaml
# prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fraud-detection-prometheus
  namespace: seldon-system
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
    - job_name: 'seldon-scheduler'
      static_configs:
      - targets: ['seldon-scheduler:9006']
    - job_name: 'seldon-models'
      kubernetes_sd_configs:
      - role: service
        namespaces:
          names: ['seldon-system']
      relabel_configs:
      - source_labels: [__meta_kubernetes_service_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

## 📈 Key Metrics to Track

### **1. Model Performance Metrics**
```promql
# Prediction accuracy per model
seldon_model_prediction_accuracy{model_name="fraud-v1-baseline"}
seldon_model_prediction_accuracy{model_name="fraud-v2-candidate"}

# Request rate per model
rate(seldon_model_requests_total[5m])

# Error rate per model
rate(seldon_model_requests_failed_total[5m])
```

### **2. A/B Traffic Distribution**
```promql
# Traffic split verification
seldon_experiment_traffic_weight{experiment="fraud-ab-test-experiment"}

# Request count per candidate
sum(rate(seldon_model_requests_total[5m])) by (model_name)
```

### **3. Latency Metrics**
```promql
# 95th percentile response time
histogram_quantile(0.95, seldon_model_request_duration_seconds_bucket)

# Average response time per model
rate(seldon_model_request_duration_seconds_sum[5m]) / 
rate(seldon_model_request_duration_seconds_count[5m])
```

### **4. Business Impact Metrics**
```promql
# Fraud detection rate
sum(rate(fraud_detected_total[5m])) / sum(rate(transactions_total[5m]))

# False positive rate  
sum(rate(false_positives_total[5m])) / sum(rate(legitimate_transactions_total[5m]))
```

## 🎨 Grafana Dashboard Setup

### **Dashboard Structure**
1. **Executive Summary**: High-level KPIs and trends
2. **A/B Test Performance**: Model comparison and traffic split
3. **System Health**: Infrastructure metrics and alerts
4. **Business Impact**: Financial metrics and fraud prevention stats

### **Key Visualizations**
- **Time Series**: Model performance over time
- **Pie Chart**: Traffic distribution (80/20 split)
- **Heatmap**: Response time distribution
- **Single Stats**: Current fraud detection rate, false positive rate

## 🚨 Alerting Rules

### **Critical Alerts**
```yaml
- alert: ModelDown
  expr: up{job="seldon-models"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Fraud detection model is down"

- alert: HighErrorRate
  expr: rate(seldon_model_requests_failed_total[5m]) > 0.05
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High error rate detected"

- alert: TrafficImbalance
  expr: abs(seldon_experiment_traffic_weight - 0.8) > 0.1
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "A/B traffic split deviation detected"
```

### **Business Alerts**
```yaml
- alert: FraudDetectionDrop
  expr: fraud_detection_rate < 0.7
  for: 15m
  labels:
    severity: critical
  annotations:
    summary: "Fraud detection rate below threshold"

- alert: HighFalsePositives
  expr: false_positive_rate > 0.05
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "False positive rate too high"
```

## 🔍 Evaluation Criteria

### **Model Promotion Decision**
Based on 2-4 weeks of A/B testing data:

```
Promote Candidate (v2) if:
✅ Recall improvement ≥ +5% vs baseline
✅ Precision maintained (±1%)
✅ Latency ≤ baseline + 10ms
✅ Error rate ≤ baseline
✅ No significant operational issues

Rollback Candidate if:
❌ Recall improvement < +5%
❌ Precision drop > 1%
❌ Latency increase > 10ms
❌ Error rate > baseline + 2%
❌ System instability detected
```

### **Statistical Significance**
- **Minimum Sample Size**: 10,000 transactions per model
- **Confidence Level**: 95%
- **A/A Test**: Run baseline vs baseline to validate measurement system

## 🚀 Implementation Steps

### **Phase 6.1: Metrics Collection (Current)**
1. ✅ Verify Seldon metrics endpoints
2. 🔧 Set up Prometheus scraping
3. 📊 Create basic Grafana dashboard
4. 🚨 Configure essential alerts

### **Phase 6.2: Traffic Simulation**
1. 📤 Create transaction replay script
2. 🎭 Simulate realistic fraud patterns
3. 📈 Generate sufficient data for analysis
4. 🔍 Validate A/B split accuracy

### **Phase 6.3: Performance Analysis**
1. 📊 Collect 1-2 weeks of data
2. 📈 Analyze model performance trends
3. 🎯 Calculate statistical significance
4. 📋 Generate promotion/rollback recommendation

## 💻 Quick Start Commands

```bash
# Check current metrics availability
curl -s http://192.168.1.201:9006/metrics | grep seldon

# Port forward for local monitoring
kubectl port-forward -n seldon-system seldon-scheduler-0 9006:9006

# Access Grafana (if deployed)
kubectl port-forward -n monitoring grafana-xxx 3000:3000

# View real-time logs
kubectl logs -f -n seldon-system seldon-scheduler-0
```

## 📋 Success Criteria for Phase 6

- ✅ **Metrics Collection**: All key metrics flowing to monitoring system
- ✅ **Dashboard Creation**: Real-time visibility into A/B test performance  
- ✅ **Alert Configuration**: Proactive notification of issues
- ✅ **Data Analysis**: Statistical analysis of model performance
- ✅ **Decision Framework**: Clear criteria for promotion/rollback

---

*Previous: [Phase 5 - Deployment Success](Phase-05-Deployment-Success.md)*  
*Next: [Phase 7 - Model Promotion Decision](Phase-07-Promotion-Decision.md)*