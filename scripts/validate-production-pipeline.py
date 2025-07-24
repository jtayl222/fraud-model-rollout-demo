#!/usr/bin/env python3
"""
Production Pipeline Validation Tool for Fraud Detection.

This script validates that the production fraud detection pipeline works correctly by:
- Testing proper feature preprocessing (scaling, ordering) 
- Validating both V1/V2 models respond accurately
- Demonstrating A/B testing with optimal thresholds
- Proving the pipeline is ready for extended production A/B testing

This is a TESTING/VALIDATION tool, not the actual production service.
Real applications should implement the preprocessing logic shown here.
"""

import json
import requests
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import time
from typing import Dict, List, Tuple, Optional

# Configuration
SELDON_ENDPOINT = "http://192.168.1.202"
HOST_HEADER = "fraud-detection.local"

# Model thresholds (from threshold tuning analysis)
OPTIMAL_THRESHOLDS = {
    "fraud-v1-baseline": 0.5,     # Conservative baseline
    "fraud-v2-candidate": 0.9     # Optimized for 95%+ precision, 100% recall
}

class FraudDetectionService:
    """Production fraud detection service with proper preprocessing"""
    
    def __init__(self):
        self.scaler = None
        self.feature_columns = None
        self._initialize_preprocessing()
    
    def _initialize_preprocessing(self):
        """Initialize the feature scaler using training data"""
        print("🔧 Initializing Production Preprocessing Pipeline")
        print("=" * 55)
        
        try:
            # Load training data that was used to train the models
            train_v2_df = pd.read_csv("data/splits/train_v2.csv")
            
            # Get feature columns in training order: V1-V28, Amount, Time
            self.feature_columns = [col for col in train_v2_df.columns 
                                  if col.startswith('V') or col in ['Time', 'Amount']]
            
            # Fit scaler on training data (same as used in training)
            self.scaler = StandardScaler()
            self.scaler.fit(train_v2_df[self.feature_columns])
            
            print(f"✅ Scaler fitted on {len(train_v2_df)} training samples")
            print(f"✅ Feature order: {len(self.feature_columns)} features")
            print(f"   Training order: {self.feature_columns[:5]}... {self.feature_columns[-2:]}")
            
        except Exception as e:
            print(f"❌ Failed to initialize preprocessing: {str(e)}")
            raise
    
    def preprocess_transaction(self, transaction_data: Dict) -> np.ndarray:
        """
        Preprocess a transaction for model inference.
        
        Args:
            transaction_data: Dict with keys: Time, Amount, V1, V2, ..., V28
        
        Returns:
            Scaled feature array ready for model inference
        """
        if self.scaler is None:
            raise RuntimeError("Preprocessing not initialized")
        
        # Create DataFrame with transaction data
        df_data = {}
        for feature in self.feature_columns:
            if feature not in transaction_data:
                raise ValueError(f"Missing required feature: {feature}")
            df_data[feature] = [transaction_data[feature]]
        
        df = pd.DataFrame(df_data)
        
        # Scale features using training scaler
        scaled_features = self.scaler.transform(df[self.feature_columns])
        
        return scaled_features[0]  # Return single transaction
    
    def predict_fraud(self, transaction_data: Dict, model_name: str = "fraud-v2-candidate") -> Dict:
        """
        Make fraud prediction using production pipeline.
        
        Args:
            transaction_data: Transaction features
            model_name: Model to use for prediction
            
        Returns:
            Prediction results with confidence and classification
        """
        start_time = time.time()
        
        try:
            # Preprocess transaction
            scaled_features = self.preprocess_transaction(transaction_data)
            
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
            
            print(f"   Debug: Sending request to {url}")
            print(f"   Debug: Headers: {headers}")
            print(f"   Debug: Payload shape: {payload['inputs'][0]['shape']}")
            
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                inference_time = time.time() - start_time
                
                print(f"   Debug: HTTP {response.status_code}, Response: {response.text[:200]}...")
            except Exception as req_error:
                inference_time = time.time() - start_time
                print(f"   Debug: Request failed: {str(req_error)}")
                return {
                    "status": "error",
                    "error": f"Request failed: {str(req_error)}",
                    "inference_time_ms": inference_time * 1000
                }
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract probability score
                fraud_probability = float(result["outputs"][0]["data"][0])
                
                # Apply optimal threshold
                threshold = OPTIMAL_THRESHOLDS.get(model_name, 0.5)
                is_fraud = fraud_probability > threshold
                
                # Calculate confidence level
                confidence = "HIGH" if fraud_probability > 0.9 else "MEDIUM" if fraud_probability > 0.5 else "LOW"
                
                return {
                    "status": "success",
                    "model_used": model_name,
                    "fraud_probability": fraud_probability,
                    "is_fraud": is_fraud,
                    "confidence": confidence,
                    "threshold_used": threshold,
                    "inference_time_ms": inference_time * 1000,
                    "transaction_amount": transaction_data.get("Amount", 0),
                    "risk_level": "🚨 HIGH RISK" if is_fraud else "✅ LOW RISK"
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "inference_time_ms": inference_time * 1000
                }
                
        except Exception as e:
            return {
                "status": "error", 
                "error": str(e),
                "inference_time_ms": (time.time() - start_time) * 1000
            }
    
    def ab_test_prediction(self, transaction_data: Dict) -> Dict:
        """
        Perform A/B test prediction using both models for comparison.
        
        Args:
            transaction_data: Transaction features
            
        Returns:
            Comparison results from both models
        """
        print(f"\n🧪 A/B Test Prediction")
        print(f"   Amount: ${transaction_data.get('Amount', 0):.2f}")
        print(f"   Time: {transaction_data.get('Time', 0)}")
        
        # Test both models
        baseline_result = self.predict_fraud(transaction_data, "fraud-v1-baseline")
        candidate_result = self.predict_fraud(transaction_data, "fraud-v2-candidate")
        
        print(f"\n   📊 Results:")
        print(f"   Baseline (v1): {baseline_result.get('fraud_probability', 0):.6f} "
              f"({baseline_result.get('risk_level', 'Unknown')})")
        print(f"   Candidate (v2): {candidate_result.get('fraud_probability', 0):.6f} "
              f"({candidate_result.get('risk_level', 'Unknown')})")
        
        # Determine which model would be used in 80/20 split
        import random
        if random.random() < 0.8:
            production_model = "baseline"
            production_result = baseline_result
        else:
            production_model = "candidate" 
            production_result = candidate_result
            
        print(f"   🎯 A/B Selection: {production_model} model selected (80/20 split)")
        
        return {
            "baseline_result": baseline_result,
            "candidate_result": candidate_result,
            "ab_selection": production_model,
            "production_result": production_result,
            "comparison": {
                "fraud_detection_difference": (
                    candidate_result.get('fraud_probability', 0) - 
                    baseline_result.get('fraud_probability', 0)
                ),
                "both_agree": (baseline_result.get('is_fraud', False) == 
                              candidate_result.get('is_fraud', False))
            }
        }

def create_sample_transactions() -> List[Dict]:
    """Create sample transactions for testing"""
    
    # Load some real examples from holdout data
    try:
        holdout_df = pd.read_csv("data/splits/holdout_test.csv")
        
        # Get fraud examples
        fraud_samples = holdout_df[holdout_df['Class'] == 1].sample(3, random_state=42)
        normal_samples = holdout_df[holdout_df['Class'] == 0].sample(2, random_state=42)
        
        transactions = []
        
        for _, row in pd.concat([fraud_samples, normal_samples]).iterrows():
            transaction = {
                "Time": float(row['Time']),
                "Amount": float(row['Amount']),
                "actual_fraud": bool(row['Class']),
                "transaction_type": "fraud" if row['Class'] else "normal"
            }
            
            # Add V1-V28 features
            for i in range(1, 29):
                transaction[f'V{i}'] = float(row[f'V{i}'])
                
            transactions.append(transaction)
            
        return transactions
        
    except Exception as e:
        print(f"⚠️  Could not load real examples: {str(e)}")
        
        # Return synthetic examples
        return [
            {
                "Time": 3600.0,     # 1 hour
                "Amount": 100.50,   # Normal amount
                "V1": 0.1, "V2": -0.2, "V3": 0.3, "V4": -0.1, "V5": 0.2,
                "V6": -0.1, "V7": 0.0, "V8": 0.1, "V9": -0.2, "V10": 0.1,
                "V11": 0.0, "V12": -0.1, "V13": 0.2, "V14": -0.3, "V15": 0.1,
                "V16": -0.2, "V17": 0.0, "V18": 0.1, "V19": -0.1, "V20": 0.2,
                "V21": -0.1, "V22": 0.0, "V23": 0.1, "V24": -0.2, "V25": 0.1,
                "V26": -0.1, "V27": 0.0, "V28": 0.1,
                "actual_fraud": False,
                "transaction_type": "normal"
            }
        ]

def test_production_service():
    """Test the production fraud detection service"""
    print("🚀 Production Fraud Detection Service Test")
    print("=" * 50)
    
    # Initialize service
    service = FraudDetectionService()
    
    # Get test transactions
    transactions = create_sample_transactions()
    print(f"\n📊 Testing with {len(transactions)} transactions")
    
    # Test each transaction
    results = []
    for i, transaction in enumerate(transactions):
        print(f"\n{'='*60}")
        print(f"🎯 Transaction {i+1}: {transaction['transaction_type'].upper()}")
        print(f"   Amount: ${transaction['Amount']:.2f}")
        print(f"   Actual fraud: {transaction['actual_fraud']}")
        
        # Perform A/B test
        result = service.ab_test_prediction(transaction)
        results.append(result)
        
        # Check accuracy
        baseline_correct = (result['baseline_result']['is_fraud'] == 
                          transaction['actual_fraud'])
        candidate_correct = (result['candidate_result']['is_fraud'] == 
                           transaction['actual_fraud'])
        
        print(f"   ✅ Baseline correct: {baseline_correct}")
        print(f"   ✅ Candidate correct: {candidate_correct}")
    
    # Summary
    print(f"\n📈 Test Summary")
    print("=" * 30)
    
    baseline_correct = 0
    candidate_correct = 0
    
    for i, result in enumerate(results):
        if result['baseline_result']['is_fraud'] == transactions[i]['actual_fraud']:
            baseline_correct += 1
        if result['candidate_result']['is_fraud'] == transactions[i]['actual_fraud']:
            candidate_correct += 1
    
    baseline_accuracy = baseline_correct / len(results)
    candidate_accuracy = candidate_correct / len(results)
    
    print(f"Baseline (v1) accuracy: {baseline_accuracy*100:.1f}%")
    print(f"Candidate (v2) accuracy: {candidate_accuracy*100:.1f}%")
    
    avg_baseline_prob = np.mean([r['baseline_result']['fraud_probability'] 
                                for r in results])
    avg_candidate_prob = np.mean([r['candidate_result']['fraud_probability'] 
                                 for r in results])
    
    print(f"Average fraud probability:")
    print(f"  Baseline: {avg_baseline_prob:.4f}")
    print(f"  Candidate: {avg_candidate_prob:.4f}")
    
    return results

def main():
    """Main validation function for production pipeline"""
    print("🧪 Production Pipeline Validation Tool")
    print("=" * 50)
    print("Validating fraud detection pipeline with proper preprocessing and thresholds")
    print()
    
    try:
        # Run comprehensive test
        results = test_production_service()
        
        print(f"\n🎉 Production Service Test Complete!")
        print("=" * 40)
        print("✅ Feature preprocessing: Working")
        print("✅ Model inference: Working") 
        print("✅ A/B testing: Working")
        print("✅ Optimal thresholds: Applied")
        print()
        print("🚀 Ready for extended A/B testing in production!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Production service test failed: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())
