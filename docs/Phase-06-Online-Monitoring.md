### Phase 6: Online Monitoring & Evaluation - Detailed Explanation

**Phase 6** focuses on monitoring and evaluating the performance of the baseline model (`fraud_v1`) and the candidate model (`fraud_v2`) during the Seldon A/B test in a production environment. By collecting real-time metrics via Prometheus and Grafana, this phase validates the offline performance improvements of `fraud_v2` (e.g., ≥5% recall increase, stable precision) under live transaction data over a 2–4 week evaluation window. The outcome determines whether `fraud_v2` should be promoted to 100% traffic or rolled back, ensuring robust decision-making and avoiding the deployment of low-value models as seen in the stock prediction case.

#### 1. Metrics Collected (Prometheus/Grafana)
- **Objective**: Track model performance and system health in real-time to compare `fraud_v1` (80% traffic) and `fraud_v2` (20% traffic) during the A/B test.
- **Per-Model Metrics**:
  - **Precision@production**:
    - Measures the proportion of predicted fraud cases that are actually fraudulent (true positives / (true positives + false positives)).
    - Target: `fraud_v2` maintains precision within ±1% of `fraud_v1` (e.g., ~0.91 for both, based on offline results).
    - Importance: Ensures false positives remain manageable to avoid overwhelming fraud investigation teams.
  - **Recall@production**:
    - Measures the proportion of actual fraud cases correctly identified (true positives / (true positives + false negatives)).
    - Target: `fraud_v2` achieves ≥5% recall improvement over `fraud_v1` (e.g., ~0.85 vs. ~0.80 from offline results).
    - Importance: Higher recall means catching more fraud, directly reducing financial losses.
  - **Fraud_detection_rate**:
    - Custom metric defined as the ratio of fraud cases caught (true positives) to total fraud cases (true positives + false negatives).
    - Formula: `fraud_detection_rate = true_positives / (true_positives + false_negatives)` (equivalent to recall but reported as a business-friendly metric).
    - Importance: Provides stakeholders with a clear view of fraud prevention effectiveness.
- **System Metrics**:
  - **Latency**:
    - Measures inference response time (e.g., p95 latency <100ms) for each model.
    - Importance: Ensures both models meet performance requirements for real-time fraud detection, avoiding delays in transaction processing.
  - **Additional Metrics**:
    - Traffic split accuracy (e.g., 80% ± 2% to `fraud_v1`, 20% ± 2% to `fraud_v2`).
    - Error rates (e.g., failed predictions due to input issues).
    - Resource utilization (e.g., CPU/memory usage per TensorFlow Serving container).
- **Implementation**:
  - **Prometheus**: Scrapes metrics from Seldon Core’s endpoints, which expose per-model predictions and feedback data (via the feedback API from Phase 5).
  - **Grafana Dashboards**:
    - Visualizes time-series metrics (e.g., precision, recall, latency) for both models.
    - Includes comparative charts (e.g., `fraud_v1` vs. `fraud_v2` recall over time) and alerts for anomalies (e.g., recall drop >5% or latency >100ms).
  - **Feedback Integration**: Ground truth labels from the feedback API (stored in Postgres/MLflow) are used to compute precision, recall, and fraud detection rate in real-time, updated as fraud labels arrive (often delayed due to manual investigations).

#### 2. Evaluation Window
- **Duration**: The A/B test runs for **2–4 weeks** to collect sufficient data for robust evaluation.
  - **Rationale**:
    - **2 weeks minimum**: Ensures enough transactions (e.g., ~100,000–200,000, assuming ~5,000–10,000 daily) to achieve statistical significance, especially for rare fraud events (~1–2% of transactions).
    - **4 weeks maximum**: Balances the need for data with the risk of prolonged exposure to a potentially underperforming candidate model.
  - **Data Volume**:
    - With 20% traffic to `fraud_v2`, approximately 20,000–40,000 transactions are processed by the candidate model over 2 weeks, providing a reliable sample for metrics like recall.
    - Fraud labels, arriving asynchronously via the feedback API, are aggregated daily to update performance metrics.
  - **Monitoring Cadence**:
    - Daily checks via Grafana dashboards to monitor trends and detect early issues.
    - Weekly reviews by the fraud analyst team to assess interim results and ensure alignment with business goals.

#### 3. Decision Rule
- **Objective**: Determine whether `fraud_v2` should be promoted to 100% traffic or rolled back based on production performance.
- **Criteria**:
  - **Promotion to 100% Traffic**:
    - **Recall Improvement**: `fraud_v2` achieves a recall increase of **≥5%** over `fraud_v1` (e.g., ≥0.84 vs. ~0.80), confirming offline results in production.
    - **Precision Stability**: `fraud_v2` precision remains within **±1%** of `fraud_v1` (e.g., 0.90–0.92 vs. ~0.91), ensuring no significant increase in false positives.
    - **Stability**: No significant performance degradation (e.g., no spikes in latency or error rates) over the evaluation window.
    - **Action**: Transition `fraud_v2` to the Production stage in the MLflow Model Registry using:
      ```python
      client = MlflowClient()
      client.transition_model_version_stage(
          name="fraud_v2",
          version="2",
          stage="Production",
          archive_existing_versions=True  # Archives fraud_v1
      )
      ```
      Update the SeldonDeployment YAML to route 100% traffic to `fraud_v2`:
      ```yaml
      spec:
        predictors:
        - name: fraud-predictor
          componentSpecs:
          - spec:
              containers:
              - name: fraud-v2
                image: tensorflow/serving:latest
                env:
                - name: MODEL_NAME
                  value: fraud_v2
                - name: MODEL_URI
                  value: models:/fraud_v2/Production
          traffic: 100
      ```
  - **Rollback**:
    - **Conditions**: `fraud_v2` fails to meet recall improvement (e.g., <5% increase), precision drops significantly (>1% below `fraud_v1`), or performance is unstable (e.g., latency spikes, inconsistent metrics).
    - **Action**: Revert to 100% traffic for `fraud_v1` by updating the SeldonDeployment YAML:
      ```yaml
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
          traffic: 100
      ```
      Rollback is executed instantly (<30 seconds) using:
      ```bash
      kubectl apply -f k8s/fraud-baseline-deployment.yaml
      ```
      `fraud_v2` is archived in the MLflow Model Registry for future analysis.
- **Statistical Significance**:
  - Use a statistical test (e.g., McNemar’s test for paired nominal data) to confirm that `fraud_v2`’s recall improvement is significant (p<0.05).
  - Monitor fraud detection rate trends to ensure consistent business impact (e.g., catching 5% more fraud cases translates to measurable savings).

#### ✅ Deliverable
- **Online A/B Metrics Report**:
  - **Content**:
    - **Performance Metrics**:
      - `fraud_v1`: Precision@production, Recall@production, Fraud_detection_rate (e.g., ~0.91, ~0.80, ~0.80).
      - `fraud_v2`: Precision@production, Recall@production, Fraud_detection_rate (e.g., ~0.91, ~0.85, ~0.85).
      - Comparison showing recall improvement (e.g., +5%) and precision stability (e.g., ±1%).
    - **System Metrics**:
      - Latency (e.g., p95 <100ms for both models).
      - Traffic split accuracy (e.g., 80% ± 2% to `fraud_v1`, 20% ± 2% to `fraud_v2`).
      - Error rates and resource utilization.
    - **Confusion Matrices**: Detailed breakdown of true positives, false positives, true negatives, and false negatives for both models, aggregated from feedback API data.
    - **Business Impact**: Estimated financial savings from improved fraud detection (e.g., $X per month from catching additional fraud cases) and operational impact (e.g., false positive workload).
    - **Statistical Analysis**: Confirmation of significant recall improvement (p-value) and stability of metrics over the 2–4 week period.
  - **Format**: A report stored in MLflow as an artifact, linked to the A/B test experiment run, with visualizations from Grafana (e.g., precision/recall trends, latency graphs).
- **Recommendation for Promotion/Rollback**:
  - **Promotion**: If `fraud_v2` meets the decision rule (recall ↑ ≥5%, precision stable), recommend transitioning to 100% traffic, including updated SeldonDeployment YAML and MLflow stage transition script.
  - **Rollback**: If `fraud_v2` underperforms or is unstable, recommend reverting to `fraud_v1`, including rollback YAML and analysis of failure causes (e.g., data drift, model degradation).
  - **Documentation**: Includes rationale, supporting metrics, and next steps (e.g., iterate on `fraud_v2` or explore new features if rolled back).

#### Why This Works for Seldon A/B Testing
This phase effectively showcases Seldon Core’s A/B testing capabilities, addressing the shortcomings of the stock prediction case:
- **High Accuracy and Measurable Improvement**: `fraud_v2`’s expected ~0.85 recall (vs. ~0.80 for `fraud_v1`) and ~0.91 precision provide a clear performance delta, unlike the near-random 52–53% accuracy in stock prediction, making the A/B test results meaningful.
- **Unified Feature Set**: Identical input shapes (~50 features) ensure seamless traffic routing and comparison, avoiding the shape incompatibility issues that plagued stock prediction.
- **Clear Business Value**: Improved recall directly translates to reduced fraud losses (e.g., $X savings per month), aligning with stakeholder needs and justifying the A/B test, unlike the ambiguous value of stock predictions.
- **Robust Monitoring**: Prometheus/Grafana integration provides real-time insights into model performance and system health, enabling confident decision-making and rapid incident response (e.g., rollback in <30 seconds).
- **Feedback-Driven Evaluation**: The feedback API and Postgres/MLflow storage enable accurate production metrics, ensuring the A/B test reflects real-world performance, unlike the stock prediction case where business value was unclear.

By rigorously monitoring and evaluating `fraud_v2` against `fraud_v1`, Phase 6 demonstrates Seldon Core’s ability to manage production A/B tests, validate model improvements, and deliver actionable business outcomes in a controlled, scalable manner.