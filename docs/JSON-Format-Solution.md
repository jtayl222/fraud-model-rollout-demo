# JSON Format Solution - RESOLVED ✅

## Problem Summary

When using Seldon Core v2 with MLflow models, we encountered 422 validation errors because:
- **Seldon Core v2 enforces V2 Inference Protocol** for all requests
- **No bypass available** - even with `MLSERVER_MODEL_INPUT_FORMAT=mlflow`
- **V2 validation happens before MLServer** sees the request

## Working Solution

### ✅ Correct V2 Format for Fraud Detection Models

```json
{
  "parameters": {"content_type": "np"},
  "inputs": [{
    "name": "fraud_features",
    "shape": [1, 30],
    "datatype": "FP32",
    "data": [12345.0, 150.5, /* 28 more float values */]
  }]
}
```

### Key Components

1. **`parameters.content_type`**: Tells MLServer how to decode the data
   - `"np"` = NumPy array format (what our TensorFlow models expect)
   - Alternative: `"dict,np"` for named columns

2. **`inputs` array**: Required by V2 protocol
   - `name`: Arbitrary identifier for the input tensor
   - `shape`: `[batch_size, features]` = `[1, 30]` for single transaction
   - `datatype`: `"FP32"` for float32 values
   - `data`: Flat array of 30 features

3. **Feature Order**: `[time, amount, v1, v2, ..., v28]`

## Working Examples

### Single Transaction Inference

```bash
curl -X POST http://192.168.1.202/v2/models/fraud-v1-baseline/infer \
  -H "Content-Type: application/json" \
  -H "Host: fraud-detection.local" \
  -d '{
    "parameters": {"content_type": "np"},
    "inputs": [{
      "name": "fraud_features",
      "shape": [1, 30],
      "datatype": "FP32",
      "data": [12345.0, 150.5, 0.497, -0.138, 0.648, 1.523, -0.234, -0.234, 
               1.579, 0.767, -0.469, 0.543, -0.466, 0.242, -1.913, -1.725,
               0.820, 0.744, 0.124, 0.402, -0.685, 0.903, 1.993, 0.413,
               0.665, -0.379, 0.762, 0.421, 0.895, 0.965]
    }]
  }'
```

### Batch Inference (Multiple Transactions)

```json
{
  "parameters": {"content_type": "np"},
  "inputs": [{
    "name": "fraud_features",
    "shape": [3, 30],
    "datatype": "FP32",
    "data": [
      /* Transaction 1 */ 12345.0, 150.5, ...,
      /* Transaction 2 */ 12445.0, 200.0, ...,
      /* Transaction 3 */ 12545.0, 75.25, ...
    ]
  }]
}
```

## Response Format

```json
{
  "outputs": [{
    "name": "output-0",
    "shape": [1, 1],
    "datatype": "FP32",
    "data": [0.0234]  // Fraud probability (0.0 - 1.0)
  }]
}
```

## What Didn't Work

### ❌ MLflow Native Format
```json
{"instances": [[12345.0, 150.5, ...]]}
```
Error: "Field required", "loc": ["body", "inputs"]

### ❌ Simple Inputs Array
```json
{"inputs": [[12345.0, 150.5, ...]]}
```
Error: "Input should be a valid dictionary"

### ❌ Environment Variable Bypass
Setting `MLSERVER_MODEL_INPUT_FORMAT=mlflow` does NOT bypass V2 validation

## Implementation Details

### ServerConfig Update
We added the environment variable to help with internal MLServer processing:
```yaml
- name: MLSERVER_MODEL_INPUT_FORMAT
  value: "mlflow"
```

However, this only affects how MLServer decodes the payload AFTER V2 validation passes.

### Model Configuration
No changes needed to Model CRDs - they remain as:
```yaml
spec:
  storageUri: "s3://mlflow-artifacts/..."
  requirements:
  - mlflow
  server: mlserver
```

## Python Client Example

```python
import requests
import json

def predict_fraud(features):
    """Send fraud detection request using V2 format"""
    
    payload = {
        "parameters": {"content_type": "np"},
        "inputs": [{
            "name": "fraud_features",
            "shape": [1, 30],
            "datatype": "FP32",
            "data": features
        }]
    }
    
    response = requests.post(
        "http://192.168.1.202/v2/models/fraud-v1-baseline/infer",
        headers={
            "Content-Type": "application/json",
            "Host": "fraud-detection.local"
        },
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        prediction = result["outputs"][0]["data"][0]
        return prediction
    else:
        raise Exception(f"Inference failed: {response.status_code}")

# Example usage
features = [12345.0, 150.5] + [0.1] * 28  # time, amount, v1-v28
fraud_score = predict_fraud(features)
print(f"Fraud probability: {fraud_score:.4f}")
```

## Key Learnings

1. **Seldon Core v2 = V2 Protocol Only**: No MLflow `/invocations` endpoint
2. **V2 Validation is Mandatory**: Happens before MLServer runtime
3. **Use `content_type` Parameter**: Tells MLServer how to decode V2 data
4. **Flat Data Array**: MLServer reshapes based on `shape` metadata

## Next Steps

For legacy MLflow clients that can't be updated:
1. **Option A**: Deploy a lightweight adapter service
2. **Option B**: Use MLServer custom runtime/codec
3. **Option C**: Consider Seldon Core v1 for MLflow compatibility

---

**Status**: ✅ RESOLVED - Models accepting V2 inference requests successfully