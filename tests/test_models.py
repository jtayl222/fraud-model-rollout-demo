"""
Comprehensive test suite for fraud detection models
"""
import pytest
import numpy as np
import pandas as pd
import tensorflow as tf
import json
import os
from unittest.mock import Mock, patch
from typing import Dict, List, Any


class TestModelTraining:
    """Test model training pipeline"""
    
    def test_data_loading(self, sample_fraud_data):
        """Test that training data loads correctly"""
        train_data, val_data = sample_fraud_data
        
        assert len(train_data) > 0, "Training data should not be empty"
        assert len(val_data) > 0, "Validation data should not be empty"
        assert 'Class' in train_data.columns, "Should have Class column"
        assert train_data['Class'].nunique() == 2, "Should be binary classification"
        
        # Check fraud rate is reasonable
        fraud_rate = train_data['Class'].mean()
        assert 0.001 <= fraud_rate <= 0.1, f"Fraud rate {fraud_rate} seems unrealistic"
    
    def test_feature_preprocessing(self, sample_fraud_data):
        """Test feature preprocessing pipeline"""
        from src.preprocessing import preprocess_features
        
        train_data, _ = sample_fraud_data
        X_processed, feature_names = preprocess_features(train_data)
        
        assert X_processed.shape[1] == 30, "Should have 30 features after preprocessing"
        assert len(feature_names) == 30, "Feature names should match feature count"
        assert np.isfinite(X_processed).all(), "All features should be finite"
        assert not np.isnan(X_processed).any(), "No features should be NaN"
    
    def test_model_architecture(self):
        """Test model architecture is correct"""
        from src.model import create_fraud_model
        
        model = create_fraud_model(input_dim=30)
        
        # Check architecture
        assert len(model.layers) == 7, "Should have 7 layers (input + 6 hidden/output)"
        assert model.layers[-1].units == 1, "Output layer should have 1 unit"
        assert str(model.layers[-1].activation).endswith('sigmoid'), "Output should use sigmoid"
        
        # Check input/output shapes
        assert model.input_shape == (None, 30), "Input shape should be (None, 30)"
        assert model.output_shape == (None, 1), "Output shape should be (None, 1)"


class TestModelPredictions:
    """Test model prediction functionality"""
    
    def test_model_prediction_shape(self, trained_model):
        """Test prediction output shape"""
        model = trained_model
        sample_input = np.random.randn(5, 30).astype(np.float32)
        
        predictions = model.predict(sample_input)
        
        assert predictions.shape == (5, 1), "Predictions should match input batch size"
        assert np.all((predictions >= 0) & (predictions <= 1)), "Predictions should be probabilities"
    
    def test_model_prediction_consistency(self, trained_model):
        """Test prediction consistency"""
        model = trained_model
        sample_input = np.random.randn(1, 30).astype(np.float32)
        
        # Same input should give same prediction
        pred1 = model.predict(sample_input)
        pred2 = model.predict(sample_input)
        
        np.testing.assert_array_almost_equal(pred1, pred2, decimal=6)
    
    def test_edge_case_inputs(self, trained_model):
        """Test model handles edge case inputs"""
        model = trained_model
        
        # Test with zeros
        zero_input = np.zeros((1, 30), dtype=np.float32)
        pred = model.predict(zero_input)
        assert 0 <= pred[0][0] <= 1
        
        # Test with extreme values
        extreme_input = np.full((1, 30), 10.0, dtype=np.float32)
        pred = model.predict(extreme_input)
        assert 0 <= pred[0][0] <= 1
        
        # Test with negative values
        negative_input = np.full((1, 30), -5.0, dtype=np.float32)
        pred = model.predict(negative_input)
        assert 0 <= pred[0][0] <= 1


class TestModelPerformance:
    """Test model performance metrics"""
    
    def test_baseline_performance_thresholds(self, baseline_model, test_data):
        """Test baseline model meets minimum performance thresholds"""
        model, metrics = baseline_model
        X_test, y_test = test_data
        
        predictions = model.predict(X_test)
        y_pred = (predictions > 0.5).astype(int)
        
        from sklearn.metrics import precision_score, recall_score, f1_score
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        
        # Performance thresholds
        assert precision >= 0.80, f"Precision {precision:.3f} below threshold 0.80"
        assert recall >= 0.60, f"Recall {recall:.3f} below threshold 0.60"
        assert f1 >= 0.70, f"F1-score {f1:.3f} below threshold 0.70"
    
    def test_candidate_improvement(self, baseline_model, candidate_model, test_data):
        """Test candidate model shows improvement over baseline"""
        baseline_model_obj, baseline_metrics = baseline_model
        candidate_model_obj, candidate_metrics = candidate_model
        X_test, y_test = test_data
        
        # Get predictions from both models
        baseline_pred = baseline_model_obj.predict(X_test)
        candidate_pred = candidate_model_obj.predict(X_test)
        
        baseline_y_pred = (baseline_pred > 0.5).astype(int)
        candidate_y_pred = (candidate_pred > 0.5).astype(int)
        
        from sklearn.metrics import recall_score, f1_score
        baseline_recall = recall_score(y_test, baseline_y_pred)
        candidate_recall = recall_score(y_test, candidate_y_pred)
        
        baseline_f1 = f1_score(y_test, baseline_y_pred)
        candidate_f1 = f1_score(y_test, candidate_y_pred)
        
        # Candidate should improve recall
        recall_improvement = candidate_recall - baseline_recall
        assert recall_improvement > 0.05, f"Recall improvement {recall_improvement:.3f} too small"
        
        # F1 should not degrade significantly
        f1_change = candidate_f1 - baseline_f1
        assert f1_change > -0.10, f"F1-score degraded too much: {f1_change:.3f}"


class TestModelServing:
    """Test model serving functionality"""
    
    def test_model_loading_from_disk(self, temp_model_path):
        """Test loading saved model from disk"""
        loaded_model = tf.keras.models.load_model(temp_model_path)
        
        assert loaded_model is not None
        assert hasattr(loaded_model, 'predict')
        
        # Test prediction works
        sample_input = np.random.randn(1, 30).astype(np.float32)
        prediction = loaded_model.predict(sample_input)
        assert prediction.shape == (1, 1)
    
    @patch('mlflow.tensorflow.load_model')
    def test_model_loading_from_mlflow(self, mock_mlflow_load):
        """Test loading model from MLflow"""
        from src.serving import load_model_from_mlflow
        
        # Mock MLflow model
        mock_model = Mock()
        mock_model.predict.return_value = np.array([[0.8]])
        mock_mlflow_load.return_value = mock_model
        
        model = load_model_from_mlflow("models:/fraud-v1/1")
        
        assert model is not None
        mock_mlflow_load.assert_called_once_with("models:/fraud-v1/1")
    
    def test_batch_prediction(self, trained_model):
        """Test batch prediction performance"""
        model = trained_model
        batch_sizes = [1, 10, 100, 1000]
        
        for batch_size in batch_sizes:
            sample_input = np.random.randn(batch_size, 30).astype(np.float32)
            predictions = model.predict(sample_input)
            
            assert predictions.shape == (batch_size, 1)
            assert np.all((predictions >= 0) & (predictions <= 1))


class TestDataValidation:
    """Test data validation and quality checks"""
    
    def test_data_schema_validation(self, sample_fraud_data):
        """Test data schema validation"""
        train_data, _ = sample_fraud_data
        
        # Required columns
        required_columns = ['Class'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
        for col in required_columns:
            assert col in train_data.columns, f"Missing required column: {col}"
        
        # Data types
        assert train_data['Class'].dtype in ['int64', 'int32'], "Class should be integer"
        assert train_data['Amount'].dtype in ['float64', 'float32'], "Amount should be float"
        
        # Value ranges
        assert train_data['Class'].isin([0, 1]).all(), "Class should be binary (0/1)"
        assert (train_data['Amount'] >= 0).all(), "Amount should be non-negative"
    
    def test_data_quality_checks(self, sample_fraud_data):
        """Test data quality metrics"""
        train_data, _ = sample_fraud_data
        
        # Check for missing values
        missing_percent = train_data.isnull().sum().sum() / (len(train_data) * len(train_data.columns))
        assert missing_percent < 0.01, f"Too many missing values: {missing_percent:.2%}"
        
        # Check for duplicates
        duplicate_percent = train_data.duplicated().sum() / len(train_data)
        assert duplicate_percent < 0.10, f"Too many duplicates: {duplicate_percent:.2%}"
        
        # Check class balance
        fraud_rate = train_data['Class'].mean()
        assert 0.001 <= fraud_rate <= 0.10, f"Unusual fraud rate: {fraud_rate:.3%}"
    
    def test_temporal_data_integrity(self, sample_fraud_data):
        """Test temporal aspects of data"""
        train_data, val_data = sample_fraud_data
        
        if 'datetime' in train_data.columns:
            # Check date ranges
            train_dates = pd.to_datetime(train_data['datetime'])
            val_dates = pd.to_datetime(val_data['datetime'])
            
            assert train_dates.min() <= val_dates.min(), "Validation should come after training"
            assert not train_dates.isna().any(), "No missing dates in training"
            assert not val_dates.isna().any(), "No missing dates in validation"


# Fixtures
@pytest.fixture
def sample_fraud_data():
    """Generate sample fraud data for testing"""
    np.random.seed(42)
    
    # Generate synthetic data
    n_samples = 1000
    n_features = 30
    
    X = np.random.randn(n_samples, n_features)
    # Make fraud cases have slightly different distributions
    fraud_indices = np.random.choice(n_samples, size=int(0.01 * n_samples), replace=False)
    X[fraud_indices, :5] += 2  # Shift first 5 features for fraud cases
    
    y = np.zeros(n_samples)
    y[fraud_indices] = 1
    
    # Create DataFrame
    columns = [f'V{i}' for i in range(1, n_features)] + ['Amount']
    df = pd.DataFrame(X, columns=columns)
    df['Class'] = y.astype(int)
    
    # Split into train/val
    split_idx = int(0.8 * len(df))
    train_data = df[:split_idx].copy()
    val_data = df[split_idx:].copy()
    
    return train_data, val_data

@pytest.fixture
def trained_model():
    """Create a simple trained model for testing"""
    from src.model import create_fraud_model
    
    model = create_fraud_model(input_dim=30)
    
    # Quick training with dummy data
    X_dummy = np.random.randn(100, 30)
    y_dummy = np.random.randint(0, 2, (100, 1))
    model.compile(optimizer='adam', loss='binary_crossentropy')
    model.fit(X_dummy, y_dummy, epochs=1, verbose=0)
    
    return model

@pytest.fixture
def baseline_model(trained_model):
    """Baseline model with metrics"""
    metrics = {
        'precision': 0.85,
        'recall': 0.75,
        'f1': 0.80,
        'auc': 0.92
    }
    return trained_model, metrics

@pytest.fixture
def candidate_model(trained_model):
    """Candidate model with improved metrics"""
    metrics = {
        'precision': 0.83,
        'recall': 0.85,  # Better recall
        'f1': 0.84,
        'auc': 0.94
    }
    return trained_model, metrics

@pytest.fixture
def test_data():
    """Generate test data"""
    np.random.seed(123)
    X_test = np.random.randn(200, 30)
    y_test = np.random.randint(0, 2, 200)
    return X_test, y_test

@pytest.fixture
def temp_model_path(tmp_path, trained_model):
    """Save model to temporary path"""
    model_path = tmp_path / "test_model.keras"
    trained_model.save(str(model_path))
    return str(model_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
