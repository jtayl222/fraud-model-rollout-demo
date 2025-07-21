### Phase 5: Seldon A/B Test Deployment - Detailed Explanation

**Phase 5** involves deploying the baseline model (`fraud_v1`) and the candidate model (`fraud_v2`) in a production environment using Seldon Core to conduct an A/B test. The goal is to evaluate the candidate model’s performance under real-world conditions by routing live transaction data to both models, splitting traffic 80% to the baseline and 20% to the candidate, while collecting feedback for performance analysis. This phase leverages Seldon’s robust A/B testing capabilities to ensure reliable model comparison, avoiding the pitfalls of the stock prediction case where low accuracy and incompatible feature sets undermined the demonstration.

#### 1. Deployment Config
- **Objective**: Deploy both `fraud_v1` and `fraud_v2` side by side in a production-like environment to compare their performance on live transaction data.
- **Traffic Split**:
  ```yaml
  traffic:
    - baseline: 80%  # fraud_v1 (Production)
    - candidate: 20% # fraud_v2 (Staging)
  ```
  - **Baseline (80%)**: The majority of traffic goes to `fraud_v1`, the current production model, to minimize risk while maintaining operational stability.
  - **Candidate (20%)**: A smaller portion of traffic is routed to `fraud_v2` to test its performance safely, allowing real-world validation without significant disruption.
- **Model Hosting**:
  - Each model is served using a **TensorFlow Serving container**, ensuring compatibility with the TensorFlow `SavedModel` format used for `fraud_v1` and `fraud_v2`.
  - Containers are configured with identical resources (e.g., 2 CPUs, 4GB memory) to ensure fair comparison, avoiding resource contention issues seen in the stock prediction case.
  - Models are registered in the MLflow Model Registry:
    - `fraud_v1`: `models:/fraud_v1/Production`
    - `fraud_v2`: `models:/fraud_v2/Staging`
  - Seldon resolves these model URIs to their respective S3/MinIO artifact paths (e.g., `s3://mlflow-artifacts/...`) via the MLflow API, abstracting UUID complexity.
- **SeldonDeployment Configuration**:
  - A `SeldonDeployment` YAML defines the A/B test setup, specifying the traffic split, container images, and model endpoints.
  - Example configuration snippet:
    ```yaml
    apiVersion: machinelearning.seldon.io/v1
    kind: SeldonDeployment
    metadata:
      name: fraud-abtest
      namespace: seldon-system
    spec:
      predictors:
      - name: fraud-predictor
        componentSpecs:
        - spec:
            containers:
            - name: fraud-v1
              image: tensorflow/serving:latest
              env:
              - name: MODEL_NAME
                value: fraud_v1
              - name: MODEL_URI
                value: models:/fraud_v1/Production
            - name: fraud-v2
              image: tensorflow/serving:latest
              env:
              - name: MODEL_NAME
                value: fraud_v2
              - name: MODEL_URI
                value: models:/fraud_v2/Staging
        traffic: 80
        name: baseline
      - name: candidate
        componentSpecs:
        - spec:
            containers:
            - name: fraud-v2
              image: tensorflow/serving:latest
              env:
              - name: MODEL_NAME
                value: fraud_v2
              - name: MODEL_URI
                value: models:/fraud_v2/Staging
        traffic: 20
    ```
  - **Key Features**:
    - **Traffic Weights**: Explicitly set to 80% (`fraud_v1`) and 20% (`fraud_v2`) for controlled experimentation.
    - **Model Isolation**: Each model runs in its own container, ensuring independent execution and monitoring.
    - **Scalability**: Seldon Core handles scaling of containers based on traffic load, with Kubernetes auto-scaling configured if needed.

#### 2. Request Routing
- **Inference API**:
  - All transactions are sent to a single inference endpoint (e.g., `http://ml-api.local/fraud-abtest/v2/models/predict`), simplifying integration for client applications.
  - The API expects a standardized payload matching the unified feature set (~50 features, e.g., transaction amount, frequency, time-based features), ensuring compatibility with both models, unlike the stock prediction case where feature shape mismatches caused issues.
  - Example payload:
    ```json
    {
      "inputs": [
        {
          "shape": [1, 50],
          "data": [0.23, 1.45, ..., 0.89]  // Normalized transaction features
        }
      ]
    }
  ```
- **Seldon Envoy Proxy**:
  - Seldon’s Envoy proxy handles traffic splitting, routing 80% of requests to `fraud_v1` and 20% to `fraud_v2` based on the configured weights.
  - **Randomized Routing**: Envoy uses a random selection mechanism to assign requests, ensuring unbiased distribution across models.
  - **Performance Optimization**: Seldon caches model artifact resolutions (from `models:/...` to S3 paths) to minimize latency, and Envoy’s load balancing ensures efficient request handling.
  - **Monitoring**: Seldon integrates with Prometheus/Grafana to track routing metrics (e.g., traffic split accuracy, response times <100ms p95), ensuring the A/B test operates as expected.

#### 3. Feedback API
- **Objective**: Collect ground truth fraud labels as they become available (often delayed in fraud detection due to manual investigations) to evaluate model performance in production.
- **Feedback Mechanism**:
  - As fraud labels are confirmed (e.g., via analyst reviews or chargeback reports), they are submitted to a feedback API endpoint:
    ```json
    {
      "response": {
        "model_name": "fraud_v2",
        "prediction": 1,  // Predicted fraud (1) or non-fraud (0)
        "request_id": "abc123",
        "timestamp": "2025-07-21T12:26:00Z"
      },
      "truth": 1  // Ground truth: fraud (1) or non-fraud (0)
    }
  ```
  - The API supports POST requests to log feedback, with `request_id` linking predictions to ground truth for tracking.
- **Storage**:
  - Feedback is stored in a **Postgres database** for structured querying and analysis, integrated with MLflow for experiment tracking.
  - Schema example:
    ```sql
    CREATE TABLE feedback (
      request_id VARCHAR(50),
      model_name VARCHAR(50),
      prediction INT,
      truth INT,
      timestamp TIMESTAMP,
      PRIMARY KEY (request_id, model_name)
    );
    ```
  - MLflow logs feedback as part of the experiment run, linking predictions to model versions (`fraud_v1`, `fraud_v2`) for traceability.
- **Analysis**:
  - Feedback data enables real-time computation of production metrics (e.g., precision, recall, F1) for both models.
  - Automated scripts aggregate feedback daily, updating confusion matrices and comparing `fraud_v2`’s performance against `fraud_v1` to validate offline results (e.g., ~0.85 recall, ~0.91 precision for `fraud_v2`).
  - Alerts are configured via Prometheus for significant performance deviations (e.g., recall drop >5%).

#### ✅ Deliverable
- **SeldonDeployment YAML for `fraud-abtest`**:
  - A complete YAML file defining the A/B test deployment, as shown above, including:
    - Traffic split (80% baseline, 20% candidate).
    - TensorFlow Serving containers for `fraud_v1` and `fraud_v2`.
    - Model URIs referencing MLflow Model Registry (`models:/fraud_v1/Production`, `models:/fraud_v2/Staging`).
    - Integration with Seldon’s Envoy proxy for routing and Prometheus for monitoring.
  - Deployed to Kubernetes via:
    ```bash
    kubectl apply -f k8s/fraud-abtest-deployment.yaml
    ```
  - **Additional Outputs**:
    - Verification of traffic splitting accuracy (e.g., 80% ± 2% to `fraud_v1`, 20% ± 2% to `fraud_v2`) via Prometheus metrics.
    - Setup of feedback API and Postgres/MLflow integration for real-time performance tracking.
    - Documentation of deployment steps, monitoring setup, and rollback procedures (e.g., revert to 100% `fra_suffix_1` if `fraud_v2` underperforms).

#### Why This Works for Seldon A/B Testing
This phase effectively demonstrates Seldon Core’s A/B testing capabilities, addressing the shortcomings of the stock prediction case:
- **High Accuracy and Clear Improvement**: `fraud_v2`’s expected ~0.85 recall and ~0.91 precision (vs. ~0.80 recall for `fraud_v1`) provide a meaningful comparison, unlike the near-random 52-53% accuracy in stock prediction.
- **Unified Feature Set**: Both models use identical input shapes (~50 features), ensuring seamless routing and avoiding shape incompatibility issues.
- **Clear Business Value**: Improved fraud detection reduces financial losses, making A/B test outcomes directly relevant to stakeholders, unlike the ambiguous value of stock predictions.
- **Robust Infrastructure**: Seldon’s Envoy proxy, TensorFlow Serving, and MLflow integration provide reliable traffic splitting and monitoring, showcasing production-ready capabilities.
- **Feedback Loop**: The feedback API and Postgres/MLflow storage enable real-time evaluation, ensuring actionable insights from the A/B test, unlike the stock prediction case where business value was unclear.

This phase positions Seldon Core as a powerful tool for production ML, enabling controlled experimentation, reliable model comparison, and data-driven decision-making for fraud detection.