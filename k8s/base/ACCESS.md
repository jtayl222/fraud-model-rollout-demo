# Accessing Fraud Detection Models

Since we're using the Scoped Operator Pattern with namespace isolation, here are the ways to access your models:

## Option 1: Port Forwarding (Recommended for Testing)

```bash
# Forward the MLServer service
kubectl port-forward -n fraud-detection svc/mlserver 9000:9000

# Test inference endpoint
curl -X POST http://localhost:9000/v2/models/fraud-v1-baseline/infer \
  -H "Content-Type: application/json" \
  -d @test-payload.json

# Check model status
curl http://localhost:9000/v2/models/fraud-v1-baseline/ready
```

## Option 2: In-Cluster Access

From within the cluster, services can access models directly:

```
http://mlserver.fraud-detection.svc.cluster.local:9000/v2/models/fraud-v1-baseline/infer
```

## Option 3: Create Namespace-Specific Ingress

Create your own ingress with unique paths:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fraud-detection-ingress
  namespace: fraud-detection
spec:
  ingressClassName: nginx
  rules:
  - host: fraud.example.com
    http:
      paths:
      - path: /v2/models
        pathType: Prefix
        backend:
          service:
            name: mlserver
            port:
              number: 9000
```

## Test Payload Example

```json
{
  "inputs": [{
    "name": "predict",
    "shape": [1, 30],
    "datatype": "FP32",
    "data": [[0.5, -1.2, 0.3, 0.8, -0.5, 1.1, -0.2, 0.7, -0.9, 0.4,
              0.1, -0.6, 0.9, -0.3, 0.5, -0.8, 0.2, -0.4, 0.6, -0.1,
              0.7, -0.5, 0.3, -0.7, 0.4, -0.2, 0.8, -0.6, 100.0, 0.5]]
  }]
}
```
