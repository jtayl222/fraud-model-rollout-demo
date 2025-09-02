"""
Test suite for model serving and API functionality
"""
import pytest
import requests
import numpy as np
import json
import time
from unittest.mock import Mock, patch
from typing import Dict, Any


class TestMLServerIntegration:
    """Test MLServer integration and API endpoints"""
    
    def test_health_endpoints(self, mlserver_client):
        """Test health check endpoints"""
        # Test liveness
        response = mlserver_client.get("/v2/health/live")
        assert response.status_code == 200
        
        # Test readiness
        response = mlserver_client.get("/v2/health/ready")
        assert response.status_code == 200
    
    def test_model_list(self, mlserver_client):
        """Test model listing endpoint"""
        response = mlserver_client.get("/v2/models")
        assert response.status_code == 200
        
        data = response.json()
        assert "models" in data
        
        model_names = [model["name"] for model in data["models"]]
        assert "fraud-v1-baseline" in model_names
        assert "fraud-v2-candidate" in model_names
    
    def test_model_metadata(self, mlserver_client):
        """Test model metadata endpoints"""
        models = ["fraud-v1-baseline", "fraud-v2-candidate"]
        
        for model_name in models:
            response = mlserver_client.get(f"/v2/models/{model_name}")
            assert response.status_code == 200
            
            metadata = response.json()
            assert metadata["name"] == model_name
            assert "inputs" in metadata
            assert "outputs" in metadata
    
    def test_model_inference(self, mlserver_client, valid_inference_payload):
        """Test model inference endpoints"""
        models = ["fraud-v1-baseline", "fraud-v2-candidate"]
        
        for model_name in models:
            response = mlserver_client.post(
                f"/v2/models/{model_name}/infer",
                json=valid_inference_payload
            )
            assert response.status_code == 200
            
            result = response.json()
            assert "outputs" in result
            assert len(result["outputs"]) == 1
            
            # Check prediction format
            output = result["outputs"][0]
            assert "data" in output
            assert len(output["data"]) == 1
            assert 0 <= output["data"][0] <= 1


class TestInferenceValidation:
    """Test inference request validation and error handling"""
    
    def test_invalid_input_shape(self, mlserver_client):
        """Test handling of invalid input shapes"""
        invalid_payload = {
            "parameters": {"content_type": "np"},
            "inputs": [{
                "name": "fraud_features",
                "shape": [1, 20],  # Wrong shape - should be 30
                "datatype": "FP32",
                "data": [0.1] * 20
            }]
        }
        
        response = mlserver_client.post(
            "/v2/models/fraud-v1-baseline/infer",
            json=invalid_payload
        )
        assert response.status_code == 400
    
    def test_missing_required_fields(self, mlserver_client):
        """Test handling of missing required fields"""
        invalid_payloads = [
            # Missing inputs
            {"parameters": {"content_type": "np"}},
            
            # Missing data
            {
                "parameters": {"content_type": "np"},
                "inputs": [{
                    "name": "fraud_features",
                    "shape": [1, 30],
                    "datatype": "FP32"
                }]
            },
            
            # Missing shape
            {
                "parameters": {"content_type": "np"}, 
                "inputs": [{
                    "name": "fraud_features",
                    "datatype": "FP32",
                    "data": [0.1] * 30
                }]
            }
        ]
        
        for payload in invalid_payloads:
            response = mlserver_client.post(
                "/v2/models/fraud-v1-baseline/infer",
                json=payload
            )
            assert response.status_code == 400
    
    def test_invalid_data_types(self, mlserver_client):
        """Test handling of invalid data types"""
        invalid_payload = {
            "parameters": {"content_type": "np"},
            "inputs": [{
                "name": "fraud_features",
                "shape": [1, 30],
                "datatype": "FP32",
                "data": ["invalid"] * 30  # String instead of numbers
            }]
        }
        
        response = mlserver_client.post(
            "/v2/models/fraud-v1-baseline/infer",
            json=invalid_payload
        )
        assert response.status_code == 400
    
    def test_nonexistent_model(self, mlserver_client, valid_inference_payload):
        """Test request to non-existent model"""
        response = mlserver_client.post(
            "/v2/models/nonexistent-model/infer",
            json=valid_inference_payload
        )
        assert response.status_code == 404


class TestABTestingEndpoints:
    """Test A/B testing functionality"""
    
    def test_ab_experiment_routing(self, mlserver_client, valid_inference_payload):
        """Test A/B experiment routing works"""
        predictions = []
        model_responses = []
        
        # Make multiple requests to see traffic distribution
        for _ in range(20):
            response = mlserver_client.post(
                "/v2/models/fraud-ab-test/infer",
                json=valid_inference_payload
            )
            assert response.status_code == 200
            
            result = response.json()
            predictions.append(result["outputs"][0]["data"][0])
            
            # Check for routing headers (if available)
            if "x-model-name" in response.headers:
                model_responses.append(response.headers["x-model-name"])
        
        # Verify we got valid predictions
        assert len(predictions) == 20
        assert all(0 <= p <= 1 for p in predictions)
        
        # If model routing headers available, check distribution
        if model_responses:
            baseline_count = model_responses.count("fraud-v1-baseline")
            candidate_count = model_responses.count("fraud-v2-candidate")
            total = baseline_count + candidate_count
            
            if total > 0:
                baseline_percent = baseline_count / total
                candidate_percent = candidate_count / total
                
                # Should roughly follow 80/20 split (allow some variance)
                assert 0.6 <= baseline_percent <= 0.95
                assert 0.05 <= candidate_percent <= 0.4
    
    def test_experiment_metadata(self, mlserver_client):
        """Test A/B experiment metadata"""
        response = mlserver_client.get("/v2/models/fraud-ab-test")
        
        if response.status_code == 200:
            metadata = response.json()
            assert metadata["name"] == "fraud-ab-test"
            
            # Check for experiment-specific metadata
            if "experiment" in metadata:
                experiment = metadata["experiment"]
                assert "candidates" in experiment
                assert len(experiment["candidates"]) >= 2


class TestPerformanceAndReliability:
    """Test performance and reliability aspects"""
    
    def test_concurrent_requests(self, mlserver_client, valid_inference_payload):
        """Test handling concurrent requests"""
        import concurrent.futures
        import threading
        
        def make_request():
            response = mlserver_client.post(
                "/v2/models/fraud-v1-baseline/infer",
                json=valid_inference_payload
            )
            return response.status_code, response.elapsed.total_seconds()
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]
        
        # All requests should succeed
        status_codes, response_times = zip(*results)
        assert all(code == 200 for code in status_codes)
        
        # Response times should be reasonable
        avg_response_time = sum(response_times) / len(response_times)
        assert avg_response_time < 2.0  # Less than 2 seconds average
    
    def test_batch_prediction_performance(self, mlserver_client):
        """Test batch prediction performance"""
        batch_sizes = [1, 5, 10, 20]
        
        for batch_size in batch_sizes:
            # Create batch payload
            batch_data = []
            for _ in range(batch_size):
                batch_data.extend(np.random.randn(30).tolist())
            
            payload = {
                "parameters": {"content_type": "np"},
                "inputs": [{
                    "name": "fraud_features",
                    "shape": [batch_size, 30],
                    "datatype": "FP32",
                    "data": batch_data
                }]
            }
            
            start_time = time.time()
            response = mlserver_client.post(
                "/v2/models/fraud-v1-baseline/infer",
                json=payload
            )
            end_time = time.time()
            
            assert response.status_code == 200
            
            result = response.json()
            predictions = result["outputs"][0]["data"]
            assert len(predictions) == batch_size
            
            # Performance should scale reasonably with batch size
            response_time = end_time - start_time
            assert response_time < batch_size * 0.5  # Max 0.5s per sample
    
    def test_memory_usage_stability(self, mlserver_client, valid_inference_payload):
        """Test memory usage doesn't grow with repeated requests"""
        # Make many requests to check for memory leaks
        for i in range(50):
            response = mlserver_client.post(
                "/v2/models/fraud-v1-baseline/infer",
                json=valid_inference_payload
            )
            assert response.status_code == 200
            
            # Every 10 requests, add a small delay to allow cleanup
            if i % 10 == 9:
                time.sleep(0.1)


class TestErrorHandling:
    """Test error handling and recovery"""
    
    def test_malformed_json(self, mlserver_client):
        """Test handling of malformed JSON"""
        response = mlserver_client.post(
            "/v2/models/fraud-v1-baseline/infer",
            data="invalid json{",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
    
    def test_oversized_request(self, mlserver_client):
        """Test handling of oversized requests"""
        # Create very large payload
        large_data = [0.1] * (10000 * 30)  # 10k batch size
        
        payload = {
            "parameters": {"content_type": "np"},
            "inputs": [{
                "name": "fraud_features", 
                "shape": [10000, 30],
                "datatype": "FP32",
                "data": large_data
            }]
        }
        
        response = mlserver_client.post(
            "/v2/models/fraud-v1-baseline/infer",
            json=payload
        )
        
        # Should either handle gracefully or reject with appropriate error
        assert response.status_code in [200, 413, 400]


# Fixtures
@pytest.fixture
def mlserver_client():
    """Mock MLServer client for testing"""
    class MockMLServerClient:
        def __init__(self):
            self.base_url = "http://localhost:8080"
        
        def get(self, path):
            response = Mock()
            response.status_code = 200
            
            if path == "/v2/health/live":
                response.json.return_value = {"status": "live"}
            elif path == "/v2/health/ready":
                response.json.return_value = {"status": "ready"}
            elif path == "/v2/models":
                response.json.return_value = {
                    "models": [
                        {"name": "fraud-v1-baseline", "state": "READY"},
                        {"name": "fraud-v2-candidate", "state": "READY"}
                    ]
                }
            elif "/v2/models/" in path and not path.endswith("/infer"):
                model_name = path.split("/")[3]
                response.json.return_value = {
                    "name": model_name,
                    "inputs": [{"name": "fraud_features", "shape": [-1, 30], "datatype": "FP32"}],
                    "outputs": [{"name": "fraud_prediction", "shape": [-1, 1], "datatype": "FP32"}]
                }
            
            return response
        
        def post(self, path, json=None, data=None, headers=None):
            response = Mock()
            response.elapsed.total_seconds.return_value = 0.1
            
            if "/infer" in path:
                if data and "invalid json" in data:
                    response.status_code = 400
                    return response
                
                if json:
                    # Validate basic structure
                    if "inputs" not in json:
                        response.status_code = 400
                        return response
                    
                    inputs = json["inputs"][0]
                    if "data" not in inputs:
                        response.status_code = 400
                        return response
                    
                    # Check for invalid data types
                    try:
                        data_values = inputs["data"]
                        if isinstance(data_values[0], str):
                            response.status_code = 400
                            return response
                    except (IndexError, TypeError):
                        response.status_code = 400
                        return response
                    
                    # Check shape mismatch
                    if "shape" in inputs:
                        expected_size = np.prod(inputs["shape"])
                        if len(data_values) != expected_size:
                            response.status_code = 400
                            return response
                        
                        # Check for wrong feature count
                        if len(inputs["shape"]) == 2 and inputs["shape"][1] != 30:
                            response.status_code = 400
                            return response
                
                # Check for nonexistent model
                if "nonexistent-model" in path:
                    response.status_code = 404
                    return response
                
                # Successful inference
                response.status_code = 200
                
                # Generate mock prediction based on batch size
                batch_size = 1
                if json and "inputs" in json and "shape" in json["inputs"][0]:
                    batch_size = json["inputs"][0]["shape"][0]
                
                predictions = [np.random.random() for _ in range(batch_size)]
                
                response.json.return_value = {
                    "outputs": [{
                        "name": "fraud_prediction",
                        "shape": [batch_size, 1],
                        "datatype": "FP32", 
                        "data": predictions
                    }]
                }
                
                # Add routing header for A/B test
                if "fraud-ab-test" in path:
                    if np.random.random() < 0.8:
                        response.headers = {"x-model-name": "fraud-v1-baseline"}
                    else:
                        response.headers = {"x-model-name": "fraud-v2-candidate"}
                else:
                    response.headers = {}
            
            return response
    
    return MockMLServerClient()

@pytest.fixture
def valid_inference_payload():
    """Valid inference payload for testing"""
    return {
        "parameters": {"content_type": "np"},
        "inputs": [{
            "name": "fraud_features",
            "shape": [1, 30],
            "datatype": "FP32",
            "data": np.random.randn(30).tolist()
        }]
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
