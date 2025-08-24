# Interacting with MLServer Models in Seldon Deployments

This document outlines the correct method for sending inference requests to MLServer models deployed within a Seldon deployment, based on recent debugging sessions.

## Key Findings

1.  **Direct Pod Port-Forwarding:** To directly interact with the MLServer instance, port-forwarding should target the `mlserver-0` pod (or the specific `mlserver` pod running your model) on its HTTP port, which is typically `8080`.

    ```bash
    kubectl port-forward -n fraud-detection pod/mlserver-0 8080:8080
    ```

2.  **Model ID Versioning:** MLServer loads MLflow models with a version suffix (e.g., `fraud-v1-baseline_1`, `fraud-v2-candidate_1`). Ensure you use the full model ID including this suffix in your inference requests.

3.  **Correct Payload Format:** The `mlserver-mlflow` runtime expects a specific KServe V2 `InferenceRequest` payload structure that includes a `parameters` field with `"content_type": "np"`. This parameter is crucial for the runtime to correctly interpret the input data as a NumPy array.

    **Do NOT** send just the raw array or other simplified JSON structures, as the MLServer API layer expects the full KServe V2 format.

## Working `curl` Example

Here's an example `curl` command to send a prediction request to the `fraud-v1-baseline_1` model:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
        "parameters": {
          "content_type": "np"
        },
        "inputs": [{
          "name": "fraud_features",
          "shape": [1, 30],
          "datatype": "FP32",
          "data": [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]]
        }]
      }' \
  http://localhost:8080/v2/models/fraud-v1-baseline_1/infer
```

Replace `fraud-v1-baseline_1` with `fraud-v2-candidate_1` to test the candidate model.

## Interacting via Istio Ingress Gateway

After successfully interacting with the MLServer directly via port-forwarding, the next step was to route traffic through the Istio Ingress Gateway. Initial attempts resulted in `HTTP/1.1 503 Service Unavailable` errors from `istio-envoy`.

### Root Cause of 503 Error

The `503 Service Unavailable` error indicated that while the request was reaching the Istio Ingress Gateway, it could not be routed to the `seldon-mesh` service. The primary reason for this was a network policy misconfiguration.

Specifically, the `financial-mlops-app-policy` in the `fraud-detection` namespace had a critical misconfiguration in its egress rule targeting the `istio-system` namespace.

**Key Lesson Learned:** The `namespaceSelector` was looking for `name: istio-system`, but Kubernetes namespaces typically use `kubernetes.io/metadata.name: <namespace-name>` as their default label. This mismatch meant the network policy was *not* applying the intended egress rule, effectively blocking communication.

**Always verify the exact labels on target namespaces when using `namespaceSelector` in NetworkPolicies.**

This prevented the `istio-proxy` sidecar (in the `seldon-envoy` pods) from communicating with `istiod` (Istio's control plane) to obtain necessary workload certificates, thus preventing the `seldon-envoy` pods from fully joining the mesh and becoming ready.

### Resolution

The network policy was updated to correctly target the `istio-system` namespace:

```yaml
# Excerpt from network-policy.yaml
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: istio-system # Corrected label
      podSelector:
        matchLabels:
          app: istiod
    ports:
    - protocol: TCP
      port: 15012 # Port for istiod
```

After applying this corrected network policy and restarting the `seldon-envoy` deployment, the pods became `2/2` ready, indicating successful sidecar injection and communication with `istiod`.

## Working `curl` Example (via Istio Ingress Gateway)

Once the Istio `Gateway` and `VirtualService` are configured (as detailed in `docs/istio-gateway-config.yaml`) and your `/etc/hosts` file is updated (e.g., `192.168.1.240 fraud-detection.local`), you can send requests through the Istio Ingress Gateway:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Host: fraud-detection.local" \
  -d '{
        "parameters": {
          "content_type": "np"
        },
        "inputs": [{
          "name": "fraud_features",
          "shape": [1, 30],
          "datatype": "FP32",
          "data": [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]]
        }]
      }' \
  http://fraud-detection.local/v2/models/fraud-v1-baseline_1/infer
```

This command should now successfully route through the Istio Ingress Gateway to your Seldon model.

## Summary


By correctly port-forwarding to the `mlserver` pod and using the KServe V2 `InferenceRequest` format with the `parameters: {"content_type": "np"}` field, you can successfully send inference requests to your MLflow models deployed via Seldon's MLServer.

**Important Note on Pod Security Standards:**
During debugging, the `fraud-detection` namespace was temporarily set to `privileged` Pod Security Standard to resolve deployment issues related to `seldon-envoy` not being compliant with `baseline` policies. This is generally not recommended for production environments.

To revert these changes and restore the `baseline` Pod Security Standard, execute the following commands:

```bash
kubectl label namespace fraud-detection pod-security.kubernetes.io/enforce=baseline --overwrite
kubectl label namespace fraud-detection pod-security.kubernetes.io/audit=baseline --overwrite
kubectl label namespace fraud-detection pod-security.kubernetes.io/warn=baseline --overwrite
```
