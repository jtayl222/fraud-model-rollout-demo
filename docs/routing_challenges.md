# Routing Challenges: Nginx Ingress, Istio, and Seldon Core

## Summary of the Problem
We are encountering persistent HTTP 404 errors when attempting to route external traffic through Nginx Ingress to Seldon Core v2 models, even though direct `port-forward` to the Seldon service works. The key observation is that the 404 response originates from Seldon's internal Envoy proxy, indicating the request is reaching Seldon but is not being routed correctly internally.

## Why This is Hard (and Common)
This complexity arises from a multi-layered routing setup involving:
1.  **Nginx Ingress Controller:** Handles external traffic, host matching, and initial path processing (rewriting/stripping).
2.  **Istio Ingress Gateway:** Acts as an entry point for the Istio service mesh, with its own `Gateway` and `VirtualService` resources for routing within the mesh.
3.  **Seldon Core's Internal Envoy Proxy:** Each Seldon deployment includes an Envoy proxy that handles internal routing to MLServer instances based on paths and host headers.

The challenge lies in ensuring perfect alignment of path handling and host header propagation across all three layers. A mismatch at any point leads to a 404.

## Root Cause (Likely)
The most probable cause of the 404 is a discrepancy in the **path** or **host header** that Seldon's Envoy proxy receives.
*   **Path Mismatch:** Nginx Ingress might be stripping or rewriting the path in a way that Istio's `VirtualService` or Seldon's Envoy does not expect. For example, if Nginx strips `/v2`, but Seldon expects `/v2/models/...`, it will result in a 404.
*   **Host Header Mismatch:** Seldon's Envoy relies on the `Host` header for routing. If Nginx or Istio modify or fail to propagate the `Host: fraud-detection.local` header correctly, Seldon won't recognize the request.

The fact that `port-forward` works perfectly confirms that Seldon itself is capable of serving the models when it receives the expected request format directly.

## Recommendation: Pivot to Istio Ingress Gateway

Given the presence of Istio in your environment, a strong recommendation is to **simplify the routing chain by making the Istio Ingress Gateway the primary external entry point.**

### Why Pivot?
1.  **Reduced Complexity:** Eliminates one layer of routing (Nginx Ingress) from the critical path. All external traffic would flow directly into Istio, and all routing logic would be consolidated within Istio's `Gateway` and `VirtualService` resources.
2.  **Native Integration:** Seldon Core is designed to integrate seamlessly with Istio. By using Istio's Ingress Gateway, you leverage its native capabilities for traffic management, observability (tracing, metrics), and security policies across your ML services.
3.  **Consistent Path Handling:** With a single ingress point, managing path rewriting and host headers becomes more straightforward, as you only need to configure it once at the Istio Gateway level, and then ensure your `VirtualService` matches what Seldon expects.
4.  **Advanced Traffic Management:** Istio provides powerful features like A/B testing, canary deployments, and traffic shifting directly at the service mesh level, which can be highly beneficial for ML model rollouts.

### How to Pivot (High-Level Steps):
1.  **Expose Istio Ingress Gateway Externally:** Ensure your Istio Ingress Gateway service (e.g., `istio-ingressgateway` in `istio-system` namespace) is exposed via a LoadBalancer or NodePort, making it accessible from outside the cluster.
2.  **Configure Istio Gateway:** Define an Istio `Gateway` resource that listens on the desired host (e.g., `fraud-detection.local`) and ports.
3.  **Configure Istio VirtualService:** Define an Istio `VirtualService` that routes traffic from the `Gateway` to your Seldon Core services (e.g., `seldon-mesh.fraud-detection.svc.cluster.local`). This is where you would define the path matching (e.g., `/v2/models/...`) that Seldon expects.
4.  **Decommission Nginx Ingress:** Once the Istio-based routing is verified, you can remove the Nginx Ingress resources that were handling traffic for `fraud-detection.local`.

By consolidating to Istio, you can streamline your routing, improve debugging, and leverage the full power of the service mesh for your MLOps infrastructure.
