#!/usr/bin/env python3
"""
Transaction Replay Simulation for Fraud Detection A/B Testing.

Simulates realistic production traffic by replaying transactions from holdout test data
with timing patterns similar to real payment processing systems. Demonstrates:
- 80/20 A/B test traffic split via Seldon experiment
- Real-time performance monitoring
- Production-like transaction volumes and patterns
- Fraud detection accuracy tracking
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler


class TransactionReplayService:
    """Service for replaying transactions against the A/B testing fraud detection pipeline"""

    def __init__(self):
        # Seldon configuration
        self.seldon_endpoint = "http://192.168.1.210"
        self.host_header = "fraud-detection.local"

        # A/B test configuration - client-side routing (industry standard)
        self.baseline_endpoint = (
            f"{self.seldon_endpoint}/v2/models/fraud-v1-baseline/infer"
        )
        self.candidate_endpoint = (
            f"{self.seldon_endpoint}/v2/models/fraud-v2-candidate/infer"
        )

        # A/B test weights (80% baseline, 20% candidate)
        self.baseline_weight = 0.8
        self.candidate_weight = 0.2

        # Performance tracking
        self.results = []
        self.scaler = None
        self.feature_columns = None

        # Initialize preprocessing
        self._initialize_preprocessing()

    def _initialize_preprocessing(self):
        """Initialize feature preprocessing pipeline"""
        print("🔧 Initializing Transaction Processing Pipeline")
        try:
            # Load training data for scaler
            train_df = pd.read_csv("data/splits/train_v2.csv")

            # Feature columns in training order
            self.feature_columns = [
                col
                for col in train_df.columns
                if col.startswith("V") or col in ["Time", "Amount"]
            ]

            # Fit scaler
            self.scaler = StandardScaler()
            self.scaler.fit(train_df[self.feature_columns])

            print(f"✅ Preprocessing ready: {len(self.feature_columns)} features")

        except Exception as e:
            print(f"❌ Preprocessing setup failed: {e}")
            raise

    def load_test_transactions(self, sample_size: Optional[int] = None) -> pd.DataFrame:
        """Load test transactions for replay"""
        print("📊 Loading Test Transactions")

        try:
            holdout_df = pd.read_csv("data/splits/holdout_test.csv")

            if sample_size and sample_size < len(holdout_df):
                # Sample transactions to maintain fraud ratio
                fraud_samples = holdout_df[holdout_df["Class"] == 1].sample(
                    min(sample_size // 10, len(holdout_df[holdout_df["Class"] == 1])),
                    random_state=42,
                )
                normal_samples = holdout_df[holdout_df["Class"] == 0].sample(
                    sample_size - len(fraud_samples), random_state=42
                )
                holdout_df = pd.concat([fraud_samples, normal_samples]).reset_index(
                    drop=True
                )

            # Shuffle transactions to simulate realistic ordering
            holdout_df = holdout_df.sample(frac=1, random_state=42).reset_index(
                drop=True
            )

            fraud_count = (holdout_df["Class"] == 1).sum()
            print(
                f"✅ Loaded {len(holdout_df)} transactions ({fraud_count} fraud, {len(holdout_df) - fraud_count} normal)"
            )
            print(f"   Fraud rate: {fraud_count/len(holdout_df)*100:.2f}%")

            return holdout_df

        except Exception as e:
            print(f"❌ Failed to load test data: {e}")
            raise

    def preprocess_transaction(
        self, transaction_row: pd.Series
    ) -> Tuple[np.ndarray, Dict]:
        """Preprocess transaction for inference"""
        # Extract features in training order
        transaction_data = {
            col: float(transaction_row[col]) for col in self.feature_columns
        }

        # Scale features
        df = pd.DataFrame([transaction_data])
        scaled_features = self.scaler.transform(df[self.feature_columns])[0]

        # Create inference payload
        payload = {
            "parameters": {"content_type": "np"},
            "inputs": [
                {
                    "name": "input_0",
                    "shape": [1, 30],
                    "datatype": "FP32",
                    "data": [scaled_features.tolist()],
                }
            ],
        }

        return scaled_features, payload

    def send_transaction(self, transaction_row: pd.Series, transaction_id: int) -> Dict:
        """Send single transaction with client-side A/B routing"""
        start_time = time.time()

        try:
            # Preprocess transaction
            scaled_features, payload = self.preprocess_transaction(transaction_row)

            # Client-side A/B test routing (industry standard approach)
            # Use transaction_id as consistent hash for deterministic routing
            route_hash = hash(str(transaction_id)) % 100
            if route_hash < (self.baseline_weight * 100):
                endpoint = self.baseline_endpoint
                model_variant = "fraud-v1-baseline"
            else:
                endpoint = self.candidate_endpoint
                model_variant = "fraud-v2-candidate"

            headers = {"Content-Type": "application/json", "Host": self.host_header}

            response = requests.post(
                endpoint, json=payload, headers=headers, timeout=10
            )

            inference_time = time.time() - start_time

            if response.status_code == 200:
                result = response.json()

                # Extract prediction
                fraud_probability = float(result["outputs"][0]["data"][0])
                model_used = result.get(
                    "model_name", model_variant
                )  # Use client-side variant

                # Apply model-specific thresholds (production pattern)
                if model_variant == "fraud-v2-candidate":
                    is_fraud_pred = fraud_probability > 0.9  # High precision threshold
                else:
                    is_fraud_pred = fraud_probability > 0.5  # Conservative baseline

                # Ground truth
                is_fraud_actual = bool(transaction_row["Class"])

                return {
                    "transaction_id": transaction_id,
                    "timestamp": datetime.now().isoformat(),
                    "status": "success",
                    "model_used": model_used,
                    "model_variant": model_variant,  # Track client-side routing
                    "fraud_probability": fraud_probability,
                    "prediction": is_fraud_pred,
                    "actual": is_fraud_actual,
                    "amount": float(transaction_row["Amount"]),
                    "inference_time_ms": inference_time * 1000,
                    "correct": is_fraud_pred == is_fraud_actual,
                }
            else:
                return {
                    "transaction_id": transaction_id,
                    "timestamp": datetime.now().isoformat(),
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "inference_time_ms": inference_time * 1000,
                }

        except Exception as e:
            return {
                "transaction_id": transaction_id,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
                "inference_time_ms": (time.time() - start_time) * 1000,
            }

    def replay_transactions_batch(
        self,
        transactions_df: pd.DataFrame,
        batch_size: int = 50,
        delay_seconds: float = 0.1,
        max_workers: int = 10,
    ) -> List[Dict]:
        """Replay transactions in batches with realistic timing"""
        print("\n🚀 Starting Transaction Replay")
        print(f"   Transactions: {len(transactions_df)}")
        print(f"   Batch size: {batch_size}")
        print(f"   Delay: {delay_seconds}s between batches")
        print(f"   Workers: {max_workers}")
        print("=" * 50)

        all_results = []
        start_time = time.time()

        # Process in batches
        for batch_start in range(0, len(transactions_df), batch_size):
            batch_end = min(batch_start + batch_size, len(transactions_df))
            batch_df = transactions_df.iloc[batch_start:batch_end]

            batch_start_time = time.time()
            print(
                f"\n📦 Batch {batch_start//batch_size + 1}: Transactions {batch_start+1}-{batch_end}"
            )

            # Process batch in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self.send_transaction, row, batch_start + i): i
                    for i, (_, row) in enumerate(batch_df.iterrows())
                }

                batch_results = []
                for future in as_completed(futures):
                    result = future.result()
                    batch_results.append(result)
                    all_results.append(result)

            # Batch summary
            batch_time = time.time() - batch_start_time
            success_count = sum(1 for r in batch_results if r["status"] == "success")
            error_count = len(batch_results) - success_count

            if success_count > 0:
                correct_count = sum(1 for r in batch_results if r.get("correct", False))
                avg_inference_time = np.mean(
                    [
                        r["inference_time_ms"]
                        for r in batch_results
                        if r["status"] == "success"
                    ]
                )
                accuracy = correct_count / success_count * 100

                print(f"   ✅ Success: {success_count}/{len(batch_results)}")
                print(f"   🎯 Accuracy: {accuracy:.1f}%")
                print(f"   ⏱️  Avg inference: {avg_inference_time:.1f}ms")
                print(f"   📊 Batch time: {batch_time:.2f}s")

            if error_count > 0:
                print(f"   ❌ Errors: {error_count}")

            # Delay between batches
            if batch_end < len(transactions_df):
                time.sleep(delay_seconds)

        total_time = time.time() - start_time
        print("\n🏁 Transaction Replay Complete!")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Transactions/sec: {len(transactions_df)/total_time:.2f}")

        return all_results

    def analyze_results(self, results: List[Dict]) -> Dict:
        """Analyze A/B test results"""
        print("\n📈 A/B Test Analysis")
        print("=" * 30)

        # Filter successful results
        successful_results = [r for r in results if r["status"] == "success"]

        if not successful_results:
            print("❌ No successful transactions to analyze")
            return {}

        # Overall metrics
        total_transactions = len(successful_results)
        correct_predictions = sum(
            1 for r in successful_results if r.get("correct", False)
        )
        accuracy = correct_predictions / total_transactions * 100

        # Model usage distribution (A/B split analysis by variant)
        model_usage = {}
        for result in successful_results:
            variant = result.get("model_variant", "unknown")
            model_usage[variant] = model_usage.get(variant, 0) + 1

        # Performance by model variant
        model_performance = {}
        for variant in model_usage:
            model_results = [
                r for r in successful_results if r.get("model_variant") == variant
            ]
            if model_results:
                model_correct = sum(1 for r in model_results if r.get("correct", False))
                model_accuracy = model_correct / len(model_results) * 100
                avg_prob = np.mean([r["fraud_probability"] for r in model_results])
                avg_inference = np.mean([r["inference_time_ms"] for r in model_results])

                model_performance[variant] = {
                    "transactions": len(model_results),
                    "accuracy": model_accuracy,
                    "avg_fraud_probability": avg_prob,
                    "avg_inference_time_ms": avg_inference,
                }

        # Detailed fraud detection metrics with confusion matrix
        y_actual = [r.get("actual", False) for r in successful_results]
        y_predicted = [r.get("prediction", False) for r in successful_results]

        # Overall confusion matrix
        cm_overall = confusion_matrix(y_actual, y_predicted)

        # Model-specific confusion matrices
        model_confusion_matrices = {}
        for variant in model_usage:
            model_results = [
                r for r in successful_results if r.get("model_variant") == variant
            ]
            if model_results:
                y_actual_model = [r.get("actual", False) for r in model_results]
                y_predicted_model = [r.get("prediction", False) for r in model_results]
                model_confusion_matrices[variant] = confusion_matrix(
                    y_actual_model, y_predicted_model
                )

        # Calculate metrics from confusion matrix
        tn_overall, fp_overall, fn_overall, tp_overall = cm_overall.ravel()

        precision = (
            tp_overall / (tp_overall + fp_overall)
            if (tp_overall + fp_overall) > 0
            else 0
        )
        recall = (
            tp_overall / (tp_overall + fn_overall)
            if (tp_overall + fn_overall) > 0
            else 0
        )
        specificity = (
            tn_overall / (tn_overall + fp_overall)
            if (tn_overall + fp_overall) > 0
            else 0
        )
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0
        )

        fraud_actual = sum(y_actual)
        fraud_detected = sum(y_predicted)

        # Print summary
        print("📊 Overall Performance:")
        print(f"   Total transactions: {total_transactions}")
        print(f"   Overall accuracy: {accuracy:.2f}%")
        print(
            f"   Avg inference time: {np.mean([r['inference_time_ms'] for r in successful_results]):.1f}ms"
        )

        print("\n🎯 Fraud Detection Metrics:")
        print(f"   Precision: {precision:.3f}")
        print(f"   Recall: {recall:.3f}")
        print(f"   Specificity: {specificity:.3f}")
        print(f"   F1-score: {f1_score:.3f}")
        print(f"   True fraud cases: {fraud_actual}")
        print(f"   Detected as fraud: {fraud_detected}")

        print("\n📋 Overall Confusion Matrix:")
        print("                 Predicted")
        print("                Normal  Fraud")
        print(f"   Actual Normal  {tn_overall:4d}   {fp_overall:4d}")
        print(f"   Actual Fraud   {fn_overall:4d}   {tp_overall:4d}")
        print("")
        print(f"   True Negatives: {tn_overall}")
        print(f"   False Positives: {fp_overall}")
        print(f"   False Negatives: {fn_overall}")
        print(f"   True Positives: {tp_overall}")

        # Model-specific confusion matrices
        for variant, cm in model_confusion_matrices.items():
            if cm.size == 4:  # 2x2 matrix
                tn, fp, fn, tp = cm.ravel()
                model_precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                model_recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                model_specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

                print(f"\n📋 {variant} Confusion Matrix:")
                print("                 Predicted")
                print("                Normal  Fraud")
                print(f"   Actual Normal  {tn:4d}   {fp:4d}")
                print(f"   Actual Fraud   {fn:4d}   {tp:4d}")
                print("")
                print(f"   Precision: {model_precision:.3f}")
                print(f"   Recall: {model_recall:.3f}")
                print(f"   Specificity: {model_specificity:.3f}")

        # Classification report for detailed analysis
        print("\n📊 Detailed Classification Report:")
        print(
            classification_report(
                y_actual, y_predicted, target_names=["Normal", "Fraud"], digits=3
            )
        )

        print("\n🔄 A/B Test Distribution (Client-Side Routing):")
        for variant, count in model_usage.items():
            percentage = count / total_transactions * 100
            expected = "80.0%" if "baseline" in variant else "20.0%"
            print(
                f"   {variant}: {count} transactions ({percentage:.1f}% - expected {expected})"
            )

        print("\n🏆 Model Performance Comparison:")
        for variant, perf in model_performance.items():
            print(f"   {variant}:")
            print(f"     Accuracy: {perf['accuracy']:.2f}%")
            print(f"     Avg fraud probability: {perf['avg_fraud_probability']:.4f}")
            print(f"     Avg inference time: {perf['avg_inference_time_ms']:.1f}ms")

        return {
            "total_transactions": total_transactions,
            "overall_accuracy": accuracy,
            "fraud_metrics": {
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score,
            },
            "model_usage": model_usage,
            "model_performance": model_performance,
        }


def main():
    """Main function for transaction replay simulation"""
    print("🎮 Fraud Detection Transaction Replay Simulation")
    print("=" * 55)

    # Initialize service
    replay_service = TransactionReplayService()

    # Load test transactions (use smaller sample for demo)
    transactions_df = replay_service.load_test_transactions(sample_size=200)

    # Run transaction replay
    results = replay_service.replay_transactions_batch(
        transactions_df,
        batch_size=25,  # Process 25 transactions per batch
        delay_seconds=1.0,  # 1 second between batches
        max_workers=5,  # 5 concurrent requests
    )

    # Analyze results
    analysis = replay_service.analyze_results(results)

    # Save results for feedback simulation
    output_file = (
        f"transaction_replay_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_file, "w") as f:
        json.dump(
            {
                "replay_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_transactions": len(results),
                    "successful_transactions": len(
                        [r for r in results if r["status"] == "success"]
                    ),
                },
                "results": results,
                "analysis": analysis,
            },
            f,
            indent=2,
        )

    print(f"\n💾 Results saved to: {output_file}")
    print("\n✅ Transaction replay simulation complete!")

    return results, analysis


if __name__ == "__main__":
    main()
