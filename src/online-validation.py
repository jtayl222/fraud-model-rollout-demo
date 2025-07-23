#!/usr/bin/env python3
"""
Online Validation Script for Production Fraud Detection Models

This script monitors deployed models in real-time by:
1. Sending test transactions to both baseline and candidate models
2. Collecting ground truth feedback from delayed labels
3. Computing live performance metrics (precision, recall, F1, AUC)
4. Detecting model drift and performance degradation
5. Triggering alerts for model retraining or rollback

Usage:
    python src/online-validation.py --duration 3600  # Run for 1 hour
    python src/online-validation.py --batch-size 100 --interval 300  # Batch validation every 5 minutes
"""

import argparse
import time
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from sklearn.preprocessing import StandardScaler
import logging
from dataclasses import dataclass
import threading
from collections import deque
import warnings

# Configuration
SELDON_ENDPOINT = "http://192.168.1.202"
HOST_HEADER = "fraud-detection.local"
FEEDBACK_DELAY_MINUTES = 15  # Simulate real-world feedback delay

# Thresholds for alerts
PERFORMANCE_THRESHOLDS = {
    "min_precision": 0.85,
    "min_recall": 0.75,
    "min_f1": 0.80,
    "min_auc": 0.85,
    "max_drift_score": 0.15
}

@dataclass
class ValidationResult:
    """Container for model validation results"""
    timestamp: datetime
    model_name: str
    precision: float
    recall: float
    f1_score: float
    auc_score: float
    confusion_matrix: np.ndarray
    sample_size: int
    drift_score: float = 0.0

@dataclass
class TransactionResult:
    """Container for individual transaction results"""
    transaction_id: str
    timestamp: datetime
    model_name: str
    prediction_prob: float
    prediction_class: int
    actual_class: Optional[int] = None
    feedback_received: bool = False
    features: List[float] = None

class OnlineValidator:
    """Real-time validation system for deployed fraud detection models"""
    
    def __init__(self):
        self.scaler = None
        self.feature_columns = None
        self.transaction_buffer = deque(maxlen=10000)  # Store recent transactions
        self.performance_history = {
            "fraud-v1-baseline": deque(maxlen=100),
            "fraud-v2-candidate": deque(maxlen=100)
        }
        self.baseline_stats = None  # For drift detection
        self._setup_logging()
        self._initialize_preprocessing()
    
    def _setup_logging(self):
        """Configure logging for online validation"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/online-validation.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _initialize_preprocessing(self):
        """Initialize preprocessing pipeline from training data"""
        try:
            # Use the same preprocessing as production
            train_v2_df = pd.read_csv("data/splits/train_v2.csv")
            self.feature_columns = [col for col in train_v2_df.columns 
                                  if col.startswith('V') or col in ['Time', 'Amount']]
            
            self.scaler = StandardScaler()
            self.scaler.fit(train_v2_df[self.feature_columns])
            
            # Store baseline statistics for drift detection
            self.baseline_stats = {
                'mean': train_v2_df[self.feature_columns].mean(),
                'std': train_v2_df[self.feature_columns].std()
            }
            
            self.logger.info(f"Preprocessing initialized with {len(self.feature_columns)} features")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize preprocessing: {e}")
            raise
    
    def send_test_transaction(self, transaction_data: Dict, model_name: str) -> TransactionResult:
        """Send a test transaction to deployed model and record result"""
        transaction_id = f"{model_name}_{int(time.time() * 1000)}"
        
        try:
            # Preprocess transaction
            scaled_features = self._preprocess_transaction(transaction_data)
            
            # Create V2 inference payload
            payload = {
                "parameters": {"content_type": "np"},
                "inputs": [{
                    "name": "fraud_features",
                    "shape": [1, 30],
                    "datatype": "FP32",
                    "data": scaled_features.tolist()
                }]
            }
            
            # Send inference request
            url = f"{SELDON_ENDPOINT}/v2/models/{model_name}/infer"
            headers = {
                "Content-Type": "application/json",
                "Host": HOST_HEADER
            }
            
            start_time = time.time()
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            latency = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                prediction_prob = float(result["outputs"][0]["data"][0])
                prediction_class = int(prediction_prob > 0.5)
                
                # Store transaction result
                transaction_result = TransactionResult(
                    transaction_id=transaction_id,
                    timestamp=datetime.now(),
                    model_name=model_name,
                    prediction_prob=prediction_prob,
                    prediction_class=prediction_class,
                    actual_class=transaction_data.get("actual_class"),
                    features=scaled_features.tolist()
                )
                
                self.transaction_buffer.append(transaction_result)
                
                self.logger.info(f"Transaction {transaction_id}: {model_name} predicted {prediction_prob:.4f} "
                               f"(class={prediction_class}) in {latency*1000:.1f}ms")
                
                return transaction_result
                
            else:
                self.logger.error(f"Model {model_name} returned {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error sending transaction to {model_name}: {e}")
            return None
    
    def _preprocess_transaction(self, transaction_data: Dict) -> np.ndarray:
        """Preprocess transaction using production pipeline"""
        # Create DataFrame with transaction data
        df_data = {}
        for feature in self.feature_columns:
            if feature not in transaction_data:
                raise ValueError(f"Missing required feature: {feature}")
            df_data[feature] = [transaction_data[feature]]
        
        df = pd.DataFrame(df_data)
        scaled_features = self.scaler.transform(df[self.feature_columns])
        return scaled_features[0]
    
    def collect_delayed_feedback(self) -> int:
        """Simulate collecting delayed ground truth labels"""
        feedback_count = 0
        current_time = datetime.now()
        
        for transaction in self.transaction_buffer:
            if (not transaction.feedback_received and 
                transaction.actual_class is not None and
                current_time - transaction.timestamp > timedelta(minutes=FEEDBACK_DELAY_MINUTES)):
                
                transaction.feedback_received = True
                feedback_count += 1
        
        return feedback_count
    
    def calculate_drift_score(self, recent_features: List[List[float]]) -> float:
        """Calculate feature drift score using statistical distance"""
        if not recent_features or self.baseline_stats is None:
            return 0.0
        
        try:
            recent_df = pd.DataFrame(recent_features, columns=self.feature_columns)
            recent_mean = recent_df.mean()
            recent_std = recent_df.std()
            
            # Calculate normalized drift score (simplified PSI)
            drift_scores = []
            for col in self.feature_columns:
                baseline_mean = self.baseline_stats['mean'][col]
                baseline_std = self.baseline_stats['std'][col]
                
                if baseline_std > 0:
                    mean_drift = abs(recent_mean[col] - baseline_mean) / baseline_std
                    drift_scores.append(mean_drift)
            
            return np.mean(drift_scores)
            
        except Exception as e:
            self.logger.warning(f"Error calculating drift score: {e}")
            return 0.0
    
    def validate_model_performance(self, model_name: str, lookback_minutes: int = 60) -> Optional[ValidationResult]:
        """Calculate performance metrics for a model over recent time window"""
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
        
        # Filter transactions for this model with feedback
        model_transactions = [
            t for t in self.transaction_buffer
            if (t.model_name == model_name and 
                t.feedback_received and 
                t.timestamp >= cutoff_time and
                t.actual_class is not None)
        ]
        
        if len(model_transactions) < 10:  # Minimum sample size
            self.logger.warning(f"Insufficient samples for {model_name}: {len(model_transactions)}")
            return None
        
        # Extract predictions and ground truth
        y_true = [t.actual_class for t in model_transactions]
        y_pred = [t.prediction_class for t in model_transactions]
        y_prob = [t.prediction_prob for t in model_transactions]
        
        # Calculate metrics
        try:
            precision = precision_score(y_true, y_pred, zero_division=0)
            recall = recall_score(y_true, y_pred, zero_division=0)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            
            # Only calculate AUC if both classes are present
            if len(set(y_true)) > 1:
                auc = roc_auc_score(y_true, y_prob)
            else:
                auc = 0.0
                self.logger.warning(f"Cannot calculate AUC for {model_name}: only one class present")
            
            conf_matrix = confusion_matrix(y_true, y_pred)
            
            # Calculate drift score
            recent_features = [t.features for t in model_transactions if t.features]
            drift_score = self.calculate_drift_score(recent_features)
            
            validation_result = ValidationResult(
                timestamp=datetime.now(),
                model_name=model_name,
                precision=precision,
                recall=recall,
                f1_score=f1,
                auc_score=auc,
                confusion_matrix=conf_matrix,
                sample_size=len(model_transactions),
                drift_score=drift_score
            )
            
            # Store in performance history
            self.performance_history[model_name].append(validation_result)
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics for {model_name}: {e}")
            return None
    
    def check_performance_alerts(self, result: ValidationResult) -> List[str]:
        """Check if model performance triggers any alerts"""
        alerts = []
        
        if result.precision < PERFORMANCE_THRESHOLDS["min_precision"]:
            alerts.append(f"LOW PRECISION: {result.precision:.3f} < {PERFORMANCE_THRESHOLDS['min_precision']}")
        
        if result.recall < PERFORMANCE_THRESHOLDS["min_recall"]:
            alerts.append(f"LOW RECALL: {result.recall:.3f} < {PERFORMANCE_THRESHOLDS['min_recall']}")
        
        if result.f1_score < PERFORMANCE_THRESHOLDS["min_f1"]:
            alerts.append(f"LOW F1-SCORE: {result.f1_score:.3f} < {PERFORMANCE_THRESHOLDS['min_f1']}")
        
        if result.auc_score > 0 and result.auc_score < PERFORMANCE_THRESHOLDS["min_auc"]:
            alerts.append(f"LOW AUC: {result.auc_score:.3f} < {PERFORMANCE_THRESHOLDS['min_auc']}")
        
        if result.drift_score > PERFORMANCE_THRESHOLDS["max_drift_score"]:
            alerts.append(f"HIGH DRIFT: {result.drift_score:.3f} > {PERFORMANCE_THRESHOLDS['max_drift_score']}")
        
        return alerts
    
    def generate_test_transactions(self, num_transactions: int = 50, fraud_ratio: float = 0.3) -> List[Dict]:
        """
        Generate test transactions from UNSEEN holdout data (Feb-Mar 2024)
        
        This data contains:
        - New fraud patterns introduced in Q1 2024 (unseen by baseline v1)
        - Temporal drift that candidate v2 was trained to handle
        - Real ground truth labels for validation
        
        Args:
            num_transactions: Number of transactions to sample
            fraud_ratio: Desired ratio of fraud cases (0.3 = 30% fraud for better testing)
        """
        try:
            # Load the UNSEEN holdout test data (Feb-Mar 2024)
            holdout_df = pd.read_csv("data/splits/holdout_test.csv")
            
            self.logger.info(f"Loaded holdout data: {len(holdout_df)} transactions from Feb-Mar 2024")
            fraud_count = (holdout_df['Class'] == 1).sum()
            self.logger.info(f"Holdout fraud rate: {fraud_count/len(holdout_df)*100:.2f}% ({fraud_count} fraud cases)")
            
            # Sample with desired fraud ratio for better validation
            fraud_samples = int(num_transactions * fraud_ratio)
            normal_samples = num_transactions - fraud_samples
            
            # Get fraud and normal transactions separately
            fraud_df = holdout_df[holdout_df['Class'] == 1]
            normal_df = holdout_df[holdout_df['Class'] == 0]
            
            transactions = []
            
            # Sample fraud cases (these contain NEW patterns unseen by v1)
            if len(fraud_df) >= fraud_samples:
                fraud_sample = fraud_df.sample(n=fraud_samples, random_state=int(time.time()))
                self.logger.info(f"Sampled {len(fraud_sample)} fraud transactions with NEW Q1 2024 patterns")
            else:
                fraud_sample = fraud_df
                self.logger.warning(f"Only {len(fraud_df)} fraud cases available, using all")
            
            # Sample normal cases
            if len(normal_df) >= normal_samples:
                normal_sample = normal_df.sample(n=normal_samples, random_state=int(time.time()) + 1)
            else:
                normal_sample = normal_df.sample(n=normal_samples, replace=True, random_state=int(time.time()) + 1)
            
            # Combine and shuffle
            combined_sample = pd.concat([fraud_sample, normal_sample]).sample(frac=1, random_state=int(time.time()) + 2)
            
            for _, row in combined_sample.iterrows():
                transaction = {
                    "Time": float(row['Time']),
                    "Amount": float(row['Amount']),
                    "actual_class": int(row['Class']),  # Ground truth for validation
                    "transaction_type": "fraud" if row['Class'] == 1 else "normal",
                    "is_q1_2024": True  # Mark as containing potential drift patterns
                }
                
                # Add V1-V28 features
                for i in range(1, 29):
                    transaction[f'V{i}'] = float(row[f'V{i}'])
                
                transactions.append(transaction)
            
            final_fraud_rate = sum(1 for t in transactions if t['actual_class'] == 1) / len(transactions)
            self.logger.info(f"Generated {len(transactions)} test transactions with {final_fraud_rate*100:.1f}% fraud rate")
            self.logger.info("These transactions contain:")
            self.logger.info("  - New fraud patterns from Q1 2024 (unseen by baseline v1)")
            self.logger.info("  - Temporal drift that candidate v2 was trained to handle")
            self.logger.info("  - Real ground truth labels for accurate validation")
            
            return transactions
            
        except Exception as e:
            self.logger.error(f"Error generating test transactions from holdout data: {e}")
            return []
    
    def run_validation_cycle(self, batch_size: int = 100):
        """Run one complete validation cycle using UNSEEN holdout data"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"STARTING VALIDATION CYCLE - UNSEEN DATA TEST")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Batch size: {batch_size}")
        
        # Generate test transactions from UNSEEN holdout data
        test_transactions = self.generate_test_transactions(batch_size, fraud_ratio=0.3)
        if not test_transactions:
            self.logger.error("No test transactions generated from holdout data")
            return
        
        # Send transactions to both models and track results
        baseline_results = []
        candidate_results = []
        
        self.logger.info(f"\nSending {len(test_transactions)} transactions to both models...")
        
        for i, transaction in enumerate(test_transactions):
            if i % 10 == 0:
                self.logger.info(f"Processing transaction {i+1}/{len(test_transactions)}")
            
            # Send to baseline model
            baseline_result = self.send_test_transaction(transaction, "fraud-v1-baseline")
            if baseline_result:
                baseline_result.feedback_received = True  # Immediate feedback for testing
                baseline_results.append(baseline_result)
            
            # Send to candidate model
            candidate_result = self.send_test_transaction(transaction, "fraud-v2-candidate")
            if candidate_result:
                candidate_result.feedback_received = True  # Immediate feedback for testing
                candidate_results.append(candidate_result)
            
            time.sleep(0.05)  # Small delay to avoid overwhelming the service
        
        self.logger.info(f"✅ Completed inference on {len(baseline_results)} baseline + {len(candidate_results)} candidate transactions")
        
        # Immediate validation with ground truth (simulating collected feedback)
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"PERFORMANCE VALIDATION ON UNSEEN Q1 2024 DATA")
        self.logger.info(f"{'='*50}")
        
        # Validate performance for both models
        baseline_result = self.validate_model_performance("fraud-v1-baseline", lookback_minutes=1)
        candidate_result = self.validate_model_performance("fraud-v2-candidate", lookback_minutes=1)
        
        if baseline_result and candidate_result:
            # Display detailed comparison
            self.logger.info(f"\n📊 MODEL COMPARISON ON UNSEEN HOLDOUT DATA")
            self.logger.info(f"{'='*55}")
            self.logger.info(f"{'Metric':<12} | {'Baseline (v1)':<13} | {'Candidate (v2)':<14} | {'Improvement':<12}")
            self.logger.info(f"{'-'*55}")
            self.logger.info(f"{'Precision':<12} | {baseline_result.precision:<13.4f} | {candidate_result.precision:<14.4f} | {candidate_result.precision - baseline_result.precision:+12.4f}")
            self.logger.info(f"{'Recall':<12} | {baseline_result.recall:<13.4f} | {candidate_result.recall:<14.4f} | {candidate_result.recall - baseline_result.recall:+12.4f}")
            self.logger.info(f"{'F1-Score':<12} | {baseline_result.f1_score:<13.4f} | {candidate_result.f1_score:<14.4f} | {candidate_result.f1_score - baseline_result.f1_score:+12.4f}")
            self.logger.info(f"{'AUC':<12} | {baseline_result.auc_score:<13.4f} | {candidate_result.auc_score:<14.4f} | {candidate_result.auc_score - baseline_result.auc_score:+12.4f}")
            self.logger.info(f"{'Drift':<12} | {baseline_result.drift_score:<13.4f} | {candidate_result.drift_score:<14.4f} | {candidate_result.drift_score - baseline_result.drift_score:+12.4f}")
            
            # Calculate improvement percentages
            recall_improvement = ((candidate_result.recall - baseline_result.recall) / baseline_result.recall * 100) if baseline_result.recall > 0 else 0
            precision_change = ((candidate_result.precision - baseline_result.precision) / baseline_result.precision * 100) if baseline_result.precision > 0 else 0
            
            self.logger.info(f"\n🎯 KEY INSIGHTS:")
            self.logger.info(f"   Recall Improvement: {recall_improvement:+.1f}% (v2 vs v1)")
            self.logger.info(f"   Precision Change:   {precision_change:+.1f}% (v2 vs v1)")
            
            # Validation against expected behavior
            if recall_improvement >= 5:
                self.logger.info(f"✅ EXPECTED: Candidate v2 shows >5% recall improvement on NEW fraud patterns")
            else:
                self.logger.warning(f"⚠️  UNEXPECTED: Candidate v2 recall improvement is only {recall_improvement:.1f}%")
            
            if abs(precision_change) <= 5:
                self.logger.info(f"✅ EXPECTED: Precision remains stable (±5%)")
            else:
                self.logger.warning(f"⚠️  UNEXPECTED: Precision changed by {precision_change:.1f}%")
            
            # Check for alerts on both models
            baseline_alerts = self.check_performance_alerts(baseline_result)
            candidate_alerts = self.check_performance_alerts(candidate_result)
            
            if baseline_alerts:
                self.logger.warning(f"\n🚨 BASELINE (v1) ALERTS:")
                for alert in baseline_alerts:
                    self.logger.warning(f"   - {alert}")
            
            if candidate_alerts:
                self.logger.warning(f"\n🚨 CANDIDATE (v2) ALERTS:")
                for alert in candidate_alerts:
                    self.logger.warning(f"   - {alert}")
            
            if not baseline_alerts and not candidate_alerts:
                self.logger.info(f"\n✅ Both models performing within acceptable ranges on unseen data")
        
        else:
            self.logger.error("Failed to validate performance - insufficient data or errors")
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"VALIDATION CYCLE COMPLETED")
        self.logger.info(f"{'='*60}")
    
    def run_continuous_validation(self, duration_seconds: int, interval_seconds: int = 300):
        """Run continuous validation for specified duration"""
        self.logger.info(f"Starting continuous validation for {duration_seconds}s (interval: {interval_seconds}s)")
        
        start_time = time.time()
        cycle_count = 0
        
        while time.time() - start_time < duration_seconds:
            cycle_count += 1
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"VALIDATION CYCLE {cycle_count}")
            self.logger.info(f"{'='*50}")
            
            self.run_validation_cycle()
            
            # Wait for next cycle (or exit if duration exceeded)
            remaining_time = duration_seconds - (time.time() - start_time)
            sleep_time = min(interval_seconds, remaining_time)
            
            if sleep_time > 0:
                self.logger.info(f"Waiting {sleep_time:.0f}s until next validation cycle...")
                time.sleep(sleep_time)
        
        self.logger.info(f"Continuous validation completed after {cycle_count} cycles")

def main():
    parser = argparse.ArgumentParser(description="Online validation for deployed fraud detection models")
    parser.add_argument("--duration", type=int, default=3600, help="Validation duration in seconds (default: 3600)")
    parser.add_argument("--interval", type=int, default=300, help="Validation interval in seconds (default: 300)")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of test transactions per cycle (default: 50)")
    parser.add_argument("--single-cycle", action="store_true", help="Run single validation cycle and exit")
    
    args = parser.parse_args()
    
    # Create logs directory
    import os
    os.makedirs('logs', exist_ok=True)
    
    try:
        validator = OnlineValidator()
        
        if args.single_cycle:
            validator.run_validation_cycle(args.batch_size)
        else:
            validator.run_continuous_validation(args.duration, args.interval)
            
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
    except Exception as e:
        print(f"Validation failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())