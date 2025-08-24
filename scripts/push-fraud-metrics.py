#!/usr/bin/env python3
"""
Push fraud detection A/B test metrics to Prometheus Pushgateway.
"""

import requests
import json
import time
import random
import numpy as np
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    Counter,
    Histogram,
    push_to_gateway,
)

# Configuration
PUSHGATEWAY_URL = "192.168.1.209:9091"
SELDON_ENDPOINT = "http://192.168.1.202"
HOST_HEADER = "fraud-detection.local"
JOB_NAME = "fraud_ab_test"
INSTANCE_NAME = "demo"


def create_metrics_registry():
    """Create custom metrics registry for fraud detection"""
    registry = CollectorRegistry()

    # Model performance metrics
    model_accuracy = Gauge(
        "fraud_model_accuracy",
        "Model accuracy percentage",
        ["experiment", "model_name"],
        registry=registry,
    )

    model_precision = Gauge(
        "fraud_model_precision",
        "Model precision score",
        ["experiment", "model_name"],
        registry=registry,
    )

    model_recall = Gauge(
        "fraud_model_recall",
        "Model recall score",
        ["experiment", "model_name"],
        registry=registry,
    )

    # Traffic distribution metrics
    traffic_distribution = Gauge(
        "fraud_traffic_weight",
        "A/B test traffic weight percentage",
        ["experiment", "model_name"],
        registry=registry,
    )

    # Business impact metrics
    fraud_detection_rate = Gauge(
        "fraud_detection_rate",
        "Percentage of fraud transactions detected",
        ["experiment", "model_name"],
        registry=registry,
    )

    false_positive_rate = Gauge(
        "fraud_false_positive_rate",
        "Percentage of legitimate transactions flagged as fraud",
        ["experiment", "model_name"],
        registry=registry,
    )

    # Request metrics
    request_count = Counter(
        "fraud_model_requests_total",
        "Total number of prediction requests",
        ["experiment", "model_name", "status"],
        registry=registry,
    )

    response_time = Histogram(
        "fraud_model_response_time_seconds",
        "Response time in seconds",
        ["experiment", "model_name"],
        registry=registry,
    )

    return registry, {
        "accuracy": model_accuracy,
        "precision": model_precision,
        "recall": model_recall,
        "traffic": traffic_distribution,
        "fraud_detection_rate": fraud_detection_rate,
        "false_positive_rate": false_positive_rate,
        "requests": request_count,
        "response_time": response_time,
    }


def simulate_fraud_metrics(metrics):
    """Simulate realistic fraud detection metrics"""
    experiment = "fraud-ab-test-experiment"

    # Baseline model (v1) - current production performance
    baseline_metrics = {
        "accuracy": 85.2,  # Overall accuracy
        "precision": 98.1,  # High precision (few false positives)
        "recall": 73.4,  # Lower recall (misses some fraud)
        "traffic": 80.0,  # 80% of traffic
        "fraud_detection_rate": 73.4,  # Same as recall for fraud class
        "false_positive_rate": 1.9,  # 100 - precision
    }

    # Candidate model (v2) - new model under test
    candidate_metrics = {
        "accuracy": 87.8,  # Improved accuracy
        "precision": 97.2,  # Slightly lower precision
        "recall": 100.0,  # Perfect recall (catches all fraud)
        "traffic": 20.0,  # 20% of traffic
        "fraud_detection_rate": 100.0,  # Catches all fraud
        "false_positive_rate": 2.8,  # Slightly more false positives
    }

    models = [
        ("fraud-v1-baseline", baseline_metrics),
        ("fraud-v2-candidate", candidate_metrics),
    ]

    print(f"📊 Pushing fraud detection metrics to Pushgateway")
    print(f"   Experiment: {experiment}")

    for model_name, model_metrics in models:
        print(f"   📈 {model_name}:")

        # Set core performance metrics
        metrics["accuracy"].labels(experiment=experiment, model_name=model_name).set(
            model_metrics["accuracy"]
        )
        metrics["precision"].labels(experiment=experiment, model_name=model_name).set(
            model_metrics["precision"]
        )
        metrics["recall"].labels(experiment=experiment, model_name=model_name).set(
            model_metrics["recall"]
        )

        # Set traffic distribution
        metrics["traffic"].labels(experiment=experiment, model_name=model_name).set(
            model_metrics["traffic"]
        )

        # Set business metrics
        metrics["fraud_detection_rate"].labels(
            experiment=experiment, model_name=model_name
        ).set(model_metrics["fraud_detection_rate"])
        metrics["false_positive_rate"].labels(
            experiment=experiment, model_name=model_name
        ).set(model_metrics["false_positive_rate"])

        # Simulate some request activity
        request_count = random.randint(45, 55)  # ~50 requests per model
        success_rate = (
            0.95 if model_name == "fraud-v1-baseline" else 0.92
        )  # Baseline slightly more stable

        successful_requests = int(request_count * success_rate)
        failed_requests = request_count - successful_requests

        metrics["requests"].labels(
            experiment=experiment, model_name=model_name, status="success"
        )._value._value = successful_requests
        metrics["requests"].labels(
            experiment=experiment, model_name=model_name, status="failed"
        )._value._value = failed_requests

        # Simulate response times
        base_latency = (
            0.15 if model_name == "fraud-v1-baseline" else 0.18
        )  # Candidate slightly slower
        for _ in range(10):  # Sample some response times
            latency = abs(np.random.normal(base_latency, 0.03))
            metrics["response_time"].labels(
                experiment=experiment, model_name=model_name
            ).observe(latency)

        print(
            f"      Accuracy: {model_metrics['accuracy']:.1f}%, Precision: {model_metrics['precision']:.1f}%, Recall: {model_metrics['recall']:.1f}%"
        )
        print(
            f"      Traffic: {model_metrics['traffic']:.0f}%, Requests: {request_count} ({successful_requests} success)"
        )


def check_model_health():
    """Check if fraud detection models are accessible"""
    models = ["fraud-v1-baseline", "fraud-v2-candidate"]
    health_status = {}

    headers = {"Host": HOST_HEADER}

    for model in models:
        try:
            url = f"{SELDON_ENDPOINT}/v2/models/{model}/ready"
            response = requests.get(url, headers=headers, timeout=5)
            health_status[model] = response.status_code == 200
            print(
                f"   🔍 {model}: {'✅ Ready' if health_status[model] else '❌ Not Ready'}"
            )
        except Exception as e:
            health_status[model] = False
            print(f"   🔍 {model}: ❌ Error - {str(e)[:30]}")

    return health_status


def main():
    print("🚀 Fraud Detection A/B Test - Metrics Collection")
    print("=" * 50)
    print(f"Pushgateway: {PUSHGATEWAY_URL}")
    print(f"Job: {JOB_NAME}")
    print()

    # Check model health first
    print("🔍 Checking Model Health:")
    health_status = check_model_health()
    healthy_models = sum(health_status.values())
    print(f"   {healthy_models}/2 models are healthy")
    print()

    # Create metrics registry
    registry, metrics = create_metrics_registry()

    # Simulate and push metrics
    simulate_fraud_metrics(metrics)

    # Push to gateway
    try:
        push_to_gateway(
            gateway=PUSHGATEWAY_URL,
            job=JOB_NAME,
            registry=registry,
            grouping_key={"instance": INSTANCE_NAME},
        )
        print(f"\n✅ Successfully pushed metrics to Pushgateway!")
        print(f"   View at: http://{PUSHGATEWAY_URL}")

    except Exception as e:
        print(f"\n❌ Failed to push metrics: {str(e)}")
        return 1

    # Provide monitoring URLs
    print(f"\n🎯 Monitoring Endpoints:")
    print(f"   📊 Pushgateway: http://{PUSHGATEWAY_URL}")
    print(f"   📈 Metrics: http://{PUSHGATEWAY_URL}/metrics")
    print(f"   🎭 Demo: View fraud detection A/B test metrics")

    print(f"\n📋 Key Metrics Available:")
    print(f"   • fraud_model_accuracy - Overall model accuracy")
    print(f"   • fraud_model_recall - Fraud detection rate (key metric)")
    print(f"   • fraud_model_precision - False positive control")
    print(f"   • fraud_traffic_weight - A/B traffic distribution")
    print(f"   • fraud_detection_rate - Business impact metric")

    print(f"\n🎉 Phase 6 Metrics Collection: OPERATIONAL")
    return 0


if __name__ == "__main__":
    exit(main())
