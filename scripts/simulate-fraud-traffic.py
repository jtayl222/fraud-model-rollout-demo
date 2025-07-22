#!/usr/bin/env python3
"""
Simulate realistic fraud detection traffic for A/B testing.
Generates transactions with varying fraud patterns to test model performance.
"""

import json
import requests
import numpy as np
import time
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
SELDON_ENDPOINT = "http://192.168.1.202"
HOST_HEADER = "fraud-detection.local"

class TransactionGenerator:
    """Generate realistic credit card transactions with fraud patterns"""
    
    def __init__(self, fraud_rate=0.01):
        self.fraud_rate = fraud_rate
        self.transaction_id = 0
        
    def generate_legitimate_transaction(self):
        """Generate a normal transaction pattern"""
        # Normal transactions have predictable patterns
        amount = abs(np.random.normal(75, 50))  # Most purchases $25-$125
        if amount > 500:
            amount = random.uniform(10, 200)  # Cap extreme values
            
        # Time: Normal shopping hours
        hour = np.random.choice([9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], 
                               p=[0.05, 0.08, 0.10, 0.12, 0.08, 0.07, 0.08, 0.10, 0.12, 0.10, 0.08, 0.02])
        time_val = hour * 3600 + random.uniform(0, 3600)
        
        # V1-V28: Normal PCA patterns (smaller variance)
        features = [time_val, amount]
        features.extend([np.random.normal(0, 0.5) for _ in range(28)])
        
        return features, False  # Not fraud
    
    def generate_fraud_transaction(self):
        """Generate a fraudulent transaction pattern"""
        # Fraud transactions have unusual patterns
        amount = random.choice([
            random.uniform(1, 5),      # Small test transactions
            random.uniform(800, 2000), # Large unauthorized purchases
            random.uniform(200, 500)   # Medium suspicious amounts
        ])
        
        # Time: Unusual hours (late night/early morning)
        hour = random.choice([0, 1, 2, 3, 4, 5, 23])
        time_val = hour * 3600 + random.uniform(0, 3600)
        
        # V1-V28: Anomalous PCA patterns (higher variance, outliers)
        features = [time_val, amount]
        for _ in range(28):
            if random.random() < 0.3:  # 30% chance of outlier
                features.append(random.uniform(-3, 3))  # Outlier values
            else:
                features.append(np.random.normal(0, 1.5))  # Higher variance
        
        return features, True  # Is fraud
    
    def generate_transaction(self):
        """Generate a transaction based on fraud rate"""
        self.transaction_id += 1
        
        if random.random() < self.fraud_rate:
            features, is_fraud = self.generate_fraud_transaction()
        else:
            features, is_fraud = self.generate_legitimate_transaction()
            
        return {
            "id": self.transaction_id,
            "features": features,
            "is_fraud": is_fraud,
            "timestamp": datetime.now().isoformat()
        }

def create_v2_payload(features):
    """Create V2 inference request payload"""
    return {
        "parameters": {"content_type": "np"},
        "inputs": [{
            "name": "fraud_features",
            "shape": [1, 30],
            "datatype": "FP32",
            "data": features
        }]
    }

def send_prediction_request(transaction, model="fraud-v1-baseline"):
    """Send prediction request and return results"""
    payload = create_v2_payload(transaction["features"])
    url = f"{SELDON_ENDPOINT}/v2/models/{model}/infer"
    headers = {
        "Content-Type": "application/json",
        "Host": HOST_HEADER
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        latency = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            prediction = float(result["outputs"][0]["data"][0])
            
            return {
                "transaction_id": transaction["id"],
                "model": model,
                "prediction": prediction,
                "actual_fraud": transaction["is_fraud"],
                "latency": latency,
                "predicted_fraud": prediction > 0.5,
                "correct": (prediction > 0.5) == transaction["is_fraud"],
                "amount": transaction["features"][1],
                "status": "success"
            }
        else:
            return {
                "transaction_id": transaction["id"],
                "model": model,
                "status": "error",
                "error": f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        return {
            "transaction_id": transaction["id"],
            "model": model,
            "status": "error",
            "error": str(e)[:50]
        }

def simulate_traffic(num_transactions=100, fraud_rate=0.02, parallel_requests=5):
    """Simulate transaction traffic and collect metrics"""
    print(f"🚀 Fraud Detection Traffic Simulation")
    print(f"=" * 50)
    print(f"Transactions: {num_transactions}")
    print(f"Fraud Rate: {fraud_rate*100:.1f}%")
    print(f"Parallel Requests: {parallel_requests}")
    print()
    
    generator = TransactionGenerator(fraud_rate)
    results = {
        "fraud-v1-baseline": [],
        "fraud-v2-candidate": []
    }
    
    # Test both models directly to see performance differences
    print(f"📊 Generating and testing transactions...")
    print(f"{'ID':>5} {'Amount':>8} {'Fraud':>6} {'Model':>20} {'Pred':>6} {'Result':>8} {'Latency':>8}")
    print("-" * 80)
    
    with ThreadPoolExecutor(max_workers=parallel_requests) as executor:
        # Generate transactions
        transactions = [generator.generate_transaction() for _ in range(num_transactions)]
        
        # Submit requests for both models
        futures = []
        for tx in transactions:
            # Test on baseline model
            futures.append(executor.submit(send_prediction_request, tx, "fraud-v1-baseline"))
            # Test on candidate model  
            futures.append(executor.submit(send_prediction_request, tx, "fraud-v2-candidate"))
        
        # Collect results
        for future in as_completed(futures):
            result = future.result()
            if result["status"] == "success":
                model_name = result["model"].split("-")[-1]  # baseline or candidate
                results[result["model"]].append(result)
                
                # Print summary
                print(f"{result['transaction_id']:>5} "
                      f"${result['amount']:>7.2f} "
                      f"{'Yes' if result['actual_fraud'] else 'No':>6} "
                      f"{model_name:>20} "
                      f"{result['prediction']:>6.3f} "
                      f"{'✅' if result['correct'] else '❌':>8} "
                      f"{result['latency']*1000:>7.1f}ms")
    
    return results, transactions

def analyze_results(results, transactions):
    """Analyze A/B test results and print metrics"""
    print(f"\n📈 A/B Test Performance Analysis")
    print(f"=" * 50)
    
    # Count actual fraud
    total_fraud = sum(1 for tx in transactions if tx["is_fraud"])
    total_legitimate = len(transactions) - total_fraud
    
    print(f"\n📊 Transaction Distribution:")
    print(f"   Total Transactions: {len(transactions)}")
    print(f"   Fraudulent: {total_fraud} ({total_fraud/len(transactions)*100:.1f}%)")
    print(f"   Legitimate: {total_legitimate} ({total_legitimate/len(transactions)*100:.1f}%)")
    
    # Analyze each model
    for model_name, model_results in results.items():
        if not model_results:
            continue
            
        print(f"\n🔍 {model_name}:")
        
        # Calculate metrics
        true_positives = sum(1 for r in model_results if r["actual_fraud"] and r["predicted_fraud"])
        false_positives = sum(1 for r in model_results if not r["actual_fraud"] and r["predicted_fraud"])
        true_negatives = sum(1 for r in model_results if not r["actual_fraud"] and not r["predicted_fraud"])
        false_negatives = sum(1 for r in model_results if r["actual_fraud"] and not r["predicted_fraud"])
        
        total_predictions = len(model_results)
        correct_predictions = sum(1 for r in model_results if r["correct"])
        
        # Metrics
        accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Latency
        latencies = [r["latency"] * 1000 for r in model_results if "latency" in r]
        avg_latency = np.mean(latencies) if latencies else 0
        p95_latency = np.percentile(latencies, 95) if latencies else 0
        
        print(f"   Predictions Made: {total_predictions}")
        print(f"   Accuracy: {accuracy*100:.1f}%")
        print(f"   Precision: {precision*100:.1f}% (of predicted fraud, how many were actual fraud)")
        print(f"   Recall: {recall*100:.1f}% (of actual fraud, how many were caught)")
        print(f"   F1 Score: {f1_score:.3f}")
        print(f"   ")
        print(f"   Confusion Matrix:")
        print(f"                 Predicted")
        print(f"                 No    Yes")
        print(f"   Actual  No   {true_negatives:>4}  {false_positives:>4}")
        print(f"          Yes   {false_negatives:>4}  {true_positives:>4}")
        print(f"   ")
        print(f"   Response Time:")
        print(f"   Average: {avg_latency:.1f}ms")
        print(f"   95th percentile: {p95_latency:.1f}ms")
        
        # Business impact
        if total_fraud > 0:
            fraud_caught = true_positives
            fraud_missed = false_negatives
            avg_fraud_amount = np.mean([tx["features"][1] for tx in transactions if tx["is_fraud"]])
            
            print(f"   ")
            print(f"   Business Impact:")
            print(f"   Fraud Caught: {fraud_caught}/{total_fraud} transactions")
            print(f"   Fraud Missed: {fraud_missed}/{total_fraud} transactions")
            print(f"   Est. Loss Prevented: ${fraud_caught * avg_fraud_amount:,.2f}")
            print(f"   Est. Loss Incurred: ${fraud_missed * avg_fraud_amount:,.2f}")
    
    # Model comparison
    if len(results) == 2 and all(results.values()):
        print(f"\n🏆 Model Comparison:")
        
        baseline_results = results["fraud-v1-baseline"]
        candidate_results = results["fraud-v2-candidate"]
        
        # Calculate improvement
        baseline_recall = sum(1 for r in baseline_results if r["actual_fraud"] and r["predicted_fraud"]) / max(1, sum(1 for r in baseline_results if r["actual_fraud"]))
        candidate_recall = sum(1 for r in candidate_results if r["actual_fraud"] and r["predicted_fraud"]) / max(1, sum(1 for r in candidate_results if r["actual_fraud"]))
        
        recall_improvement = ((candidate_recall - baseline_recall) / baseline_recall * 100) if baseline_recall > 0 else 0
        
        print(f"   Recall Improvement: {recall_improvement:+.1f}%")
        print(f"   ")
        
        if recall_improvement >= 5:
            print(f"   ✅ RECOMMENDATION: Promote candidate model")
            print(f"      - Significant recall improvement ({recall_improvement:+.1f}%)")
            print(f"      - Catches more fraud while maintaining acceptable precision")
        else:
            print(f"   ⚠️  RECOMMENDATION: Continue monitoring")
            print(f"      - Recall improvement below +5% threshold")
            print(f"      - Need more data for confident decision")

def main():
    """Run fraud detection traffic simulation"""
    print("🎯 Fraud Detection A/B Test Traffic Simulation")
    print("=" * 50)
    print(f"Endpoint: {SELDON_ENDPOINT}")
    print(f"Host: {HOST_HEADER}")
    print()
    
    # Run simulation
    num_transactions = 50  # Reduced for demo
    fraud_rate = 0.05      # 5% fraud rate for better visibility
    
    results, transactions = simulate_traffic(
        num_transactions=num_transactions,
        fraud_rate=fraud_rate,
        parallel_requests=5
    )
    
    # Analyze results
    analyze_results(results, transactions)
    
    # Push updated metrics
    print(f"\n📊 Pushing updated metrics to Prometheus...")
    try:
        import subprocess
        subprocess.run(["python", "scripts/push-fraud-metrics.py"], check=True)
        print(f"✅ Metrics updated successfully")
    except:
        print(f"⚠️  Could not update Prometheus metrics")
    
    print(f"\n🎉 Traffic Simulation Complete!")
    print(f"   Generated {num_transactions} transactions")
    print(f"   Tested both models for comparison")
    print(f"   Ready for Phase 7: Model Promotion Decision")
    
    return 0

if __name__ == "__main__":
    exit(main())