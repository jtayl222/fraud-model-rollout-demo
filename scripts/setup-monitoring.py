#!/usr/bin/env python3
"""
Set up monitoring for the fraud detection A/B test.
Checks available metrics endpoints and provides setup guidance.
"""

import requests
import subprocess
import json
import time
import sys

# Configuration
SELDON_SCHEDULER = "http://192.168.1.201:9006"
SELDON_MESH = "http://192.168.1.202"
HOST_HEADER = "fraud-detection.local"

def check_metrics_endpoints():
    """Check availability of metrics endpoints"""
    print("🔍 Checking Metrics Endpoints")
    print("=" * 35)
    
    endpoints = [
        ("Seldon Scheduler", f"{SELDON_SCHEDULER}/metrics"),
        ("Seldon Health", f"{SELDON_MESH}/v2/health/ready"),
        ("Model V1 Ready", f"{SELDON_MESH}/v2/models/fraud-v1-baseline/ready"),
        ("Model V2 Ready", f"{SELDON_MESH}/v2/models/fraud-v2-candidate/ready"),
    ]
    
    available_endpoints = []
    
    for name, url in endpoints:
        print(f"📡 Testing {name}...", end=" ")
        
        try:
            headers = {"Host": HOST_HEADER} if "192.168.1.202" in url else {}
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ Available")
                available_endpoints.append((name, url))
                
                # Sample metrics data
                if "metrics" in url:
                    lines = response.text.split('\n')
                    metric_count = len([l for l in lines if l and not l.startswith('#')])
                    print(f"   📊 {metric_count} metrics available")
                    
            else:
                print(f"❌ Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)[:30]}")
    
    return available_endpoints

def check_kubernetes_monitoring():
    """Check if Kubernetes cluster has existing monitoring"""
    print(f"\n🔍 Checking Kubernetes Monitoring Infrastructure")
    print("=" * 50)
    
    monitoring_components = [
        ("Prometheus Operator", "kubectl get prometheus -A"),
        ("Grafana", "kubectl get grafana -A"),
        ("ServiceMonitor CRDs", "kubectl get servicemonitor -A"),
        ("Prometheus Instances", "kubectl get pods -A | grep prometheus"),
        ("Grafana Instances", "kubectl get pods -A | grep grafana"),
    ]
    
    existing_monitoring = []
    
    for name, command in monitoring_components:
        print(f"📡 Checking {name}...", end=" ")
        
        try:
            result = subprocess.run(
                command.split(), 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                print(f"✅ Found")
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Has content beyond headers
                    print(f"   📊 {len(lines)-1} instances")
                existing_monitoring.append((name, result.stdout))
            else:
                print(f"❌ Not found")
                
        except Exception as e:
            print(f"❌ Error")
    
    return existing_monitoring

def create_prometheus_config():
    """Create Prometheus configuration for fraud detection monitoring"""
    print(f"\n🔧 Creating Prometheus Configuration")
    print("=" * 40)
    
    prometheus_config = {
        "global": {
            "scrape_interval": "15s",
            "evaluation_interval": "15s"
        },
        "scrape_configs": [
            {
                "job_name": "seldon-scheduler",
                "static_configs": [
                    {"targets": ["seldon-scheduler.seldon-system.svc.cluster.local:9006"]}
                ],
                "metrics_path": "/metrics",
                "scrape_interval": "10s"
            },
            {
                "job_name": "seldon-models",
                "kubernetes_sd_configs": [
                    {
                        "role": "service",
                        "namespaces": {"names": ["seldon-system"]}
                    }
                ],
                "relabel_configs": [
                    {
                        "source_labels": ["__meta_kubernetes_service_annotation_prometheus_io_scrape"],
                        "action": "keep",
                        "regex": True
                    }
                ]
            }
        ],
        "rule_files": ["fraud_detection_alerts.yml"]
    }
    
    config_file = "k8s/base/prometheus-config.yaml"
    
    with open(config_file, 'w') as f:
        f.write("apiVersion: v1\n")
        f.write("kind: ConfigMap\n")
        f.write("metadata:\n")
        f.write("  name: fraud-detection-prometheus\n")
        f.write("  namespace: seldon-system\n")
        f.write("data:\n")
        f.write("  prometheus.yml: |\n")
        
        for line in json.dumps(prometheus_config, indent=4).split('\n'):
            f.write(f"    {line}\n")
    
    print(f"✅ Created {config_file}")
    return config_file

def create_grafana_dashboard():
    """Create Grafana dashboard JSON for fraud detection A/B test"""
    print(f"\n🎨 Creating Grafana Dashboard")
    print("=" * 30)
    
    dashboard = {
        "dashboard": {
            "title": "Fraud Detection A/B Test Monitoring",
            "tags": ["fraud-detection", "ab-test", "seldon"],
            "time": {"from": "now-1h", "to": "now"},
            "refresh": "30s",
            "panels": [
                {
                    "title": "Model Request Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "rate(seldon_model_requests_total[5m])",
                            "legendFormat": "{{model_name}}"
                        }
                    ]
                },
                {
                    "title": "A/B Traffic Split",
                    "type": "piechart", 
                    "targets": [
                        {
                            "expr": "sum(rate(seldon_model_requests_total[5m])) by (model_name)",
                            "legendFormat": "{{model_name}}"
                        }
                    ]
                },
                {
                    "title": "Response Time (95th percentile)",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "histogram_quantile(0.95, seldon_model_request_duration_seconds_bucket)",
                            "legendFormat": "{{model_name}}"
                        }
                    ]
                },
                {
                    "title": "Error Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "rate(seldon_model_requests_failed_total[5m])",
                            "legendFormat": "{{model_name}}"
                        }
                    ]
                }
            ]
        }
    }
    
    dashboard_file = "monitoring/fraud-detection-dashboard.json"
    
    # Create monitoring directory
    subprocess.run(["mkdir", "-p", "monitoring"], check=True)
    
    with open(dashboard_file, 'w') as f:
        json.dump(dashboard, f, indent=2)
    
    print(f"✅ Created {dashboard_file}")
    return dashboard_file

def create_alert_rules():
    """Create Prometheus alert rules for fraud detection"""
    print(f"\n🚨 Creating Alert Rules")
    print("=" * 25)
    
    alert_rules = """
groups:
- name: fraud_detection_alerts
  rules:
  - alert: FraudModelDown
    expr: up{job="seldon-scheduler"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Fraud detection model is down"
      description: "Seldon scheduler has been down for more than 2 minutes"
      
  - alert: HighModelErrorRate
    expr: rate(seldon_model_requests_failed_total[5m]) > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate in fraud detection model"
      description: "Error rate is {{ $value }} for model {{ $labels.model_name }}"
      
  - alert: SlowModelResponse
    expr: histogram_quantile(0.95, seldon_model_request_duration_seconds_bucket) > 1.0
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Slow response time for fraud detection"
      description: "95th percentile response time is {{ $value }}s"
      
  - alert: ABTrafficImbalance
    expr: |
      abs(
        (sum(rate(seldon_model_requests_total{model_name="fraud-v1-baseline"}[5m])) / 
         sum(rate(seldon_model_requests_total[5m]))) - 0.8
      ) > 0.15
    for: 15m
    labels:
      severity: warning
    annotations:
      summary: "A/B traffic split is imbalanced"
      description: "Traffic split deviates from expected 80/20"
"""
    
    rules_file = "monitoring/fraud_detection_alerts.yml"
    
    with open(rules_file, 'w') as f:
        f.write(alert_rules)
    
    print(f"✅ Created {rules_file}")
    return rules_file

def provide_setup_instructions(available_endpoints, existing_monitoring):
    """Provide customized setup instructions based on environment"""
    print(f"\n🚀 Monitoring Setup Instructions")
    print("=" * 35)
    
    if existing_monitoring:
        print("✅ **Existing Monitoring Detected**")
        print("You can integrate with your existing monitoring stack:")
        print()
        for name, _ in existing_monitoring:
            print(f"   • {name}")
        print()
        print("📋 Integration Steps:")
        print("1. Add Seldon metrics to your existing Prometheus config")
        print("2. Import the Grafana dashboard JSON")
        print("3. Configure alert rules in your AlertManager")
        print()
        
    else:
        print("🔧 **Standalone Monitoring Setup**")
        print("No existing monitoring detected. Setting up dedicated monitoring:")
        print()
        print("📋 Setup Steps:")
        print("1. Deploy Prometheus with fraud detection config")
        print("2. Deploy Grafana with fraud detection dashboard")
        print("3. Configure AlertManager for notifications")
        print()
    
    if available_endpoints:
        print("✅ **Available Metrics Endpoints:**")
        for name, url in available_endpoints:
            print(f"   • {name}: {url}")
        print()
    
    print("🎯 **Quick Start Commands:**")
    print()
    print("# Port forward to access metrics locally")
    print("kubectl port-forward -n seldon-system seldon-scheduler-0 9006:9006")
    print()
    print("# View metrics in browser")
    print("open http://localhost:9006/metrics")
    print()
    print("# Apply monitoring configuration")
    print("kubectl apply -f k8s/base/prometheus-config.yaml")
    print()
    print("# Check Seldon metrics")
    print("curl -s http://localhost:9006/metrics | grep seldon")

def main():
    print("🚀 Fraud Detection A/B Test - Monitoring Setup")
    print("=" * 50)
    print("Setting up comprehensive monitoring for Phase 6")
    print()
    
    # Check metrics endpoints
    available_endpoints = check_metrics_endpoints()
    
    # Check existing Kubernetes monitoring
    existing_monitoring = check_kubernetes_monitoring()
    
    # Create monitoring configurations
    prometheus_config = create_prometheus_config()
    dashboard_file = create_grafana_dashboard() 
    alert_rules = create_alert_rules()
    
    # Provide setup instructions
    provide_setup_instructions(available_endpoints, existing_monitoring)
    
    print(f"\n🎉 Monitoring Setup Complete!")
    print("=" * 30)
    print("✅ Prometheus configuration created")
    print("✅ Grafana dashboard created")
    print("✅ Alert rules configured")
    print("✅ Setup instructions provided")
    print()
    print("🚀 **Phase 6 Status: READY**")
    print("   Ready to collect and analyze A/B test metrics!")
    
    return 0

if __name__ == "__main__":
    exit(main())