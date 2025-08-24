### Phase 7: Model Promotion or Rollback - Detailed Explanation

**Phase 7** finalizes the A/B test by deciding whether to promote the candidate model (`fraud_v2`) to handle 100% of production traffic or to retain the baseline model (`fraud_v1`) based on the results from Phase 6 (Online Monitoring & Evaluation). This phase ensures a smooth transition in the production environment using Seldon Core, updates the MLflow Model Registry, and documents the decision for traceability and future reference. If the candidate model fails, an investigation into the reasons for underperformance is conducted to inform future iterations, addressing the lessons from the stock prediction case where low-value models were deployed without clear resolution.

#### 1. If Candidate Wins
- **Criteria for Winning**:
  - Based on Phase 6 results, `fraud_v2` is considered the winner if:
    - **Recall Improvement**: Achieves a recall increase of ≥5% over `fraud_v1` in production (e.g., ~0.85 vs. ~0.80).
    - **Precision Stability**: Maintains precision within ±1% of `fraud_v1` (e.g., ~0.91, within 0.90–0.92).
    - **Stability**: Exhibits no significant performance degradation (e.g., no latency spikes >100ms p95, no error rate anomalies) over the 2–4 week evaluation window.
    - **Statistical Significance**: Recall improvement is statistically significant (e.g., p<0.05 using McNemar’s test).
- **Actions**:
  - **Redeploy Seldon with v2 → 100% Traffic**:
    - Update the `SeldonDeployment` YAML to route all traffic to `fraud_v2`:
      ```yaml
      apiVersion: machinelearning.seldon.io/v1
      kind: SeldonDeployment
      metadata:
        name: fraud-predictor
        namespace: seldon-system
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
    - Apply the updated configuration:
      ```bash
      kubectl apply -f k8s/fraud-v2-deployment.yaml
      ```
    - Verify deployment via Prometheus/Grafana, ensuring 100% traffic routes to `fraud_v2` with latency <100ms p95 and no errors.
  - **Update MLflow Model Registry**:
    - Promote `fraud_v2` to the Production stage:
      ```python
      from mlflow.tracking import MlflowClient
      client = MlflowClient()
      client.transition_model_version_stage(
          name="fraud_v2",
          version="2",
          stage="Production",
          archive_existing_versions=True  # Archives fraud_v1
      )
      ```
    - This archives `fraud_v1` in the MLflow Model Registry, maintaining a clear audit trail and enabling potential future rollbacks.
  - **Retire v1**:
    - Remove `fraud_v1` from the SeldonDeployment configuration to free up resources.
    - Archive `fraud_v1` artifacts in S3/MinIO, ensuring they remain accessible for analysis or rollback if needed.
    - Update monitoring dashboards to focus solely on `fraud_v2` metrics (e.g., precision@production, recall@production, fraud_detection_rate).
- **Business Impact**:
  - Communicate to stakeholders that `fraud_v2`’s improved recall (e.g., catching 5% more fraud cases) translates to measurable savings (e.g., $X per month) with minimal operational disruption due to stable precision.
  - Update user-facing documentation to reflect the new production model, emphasizing enhanced fraud detection capabilities.

#### 2. If Candidate Loses
- **Criteria for Losing**:
  - `fraud_v2` fails if:
    - **Recall Improvement**: Does not achieve ≥5% recall increase (e.g., <0.84 vs. ~0.80 for `fraud_v1`).
    - **Precision Instability**: Precision falls outside ±1% of `fraud_v1` (e.g., <0.90 or >0.92), leading to excessive false positives or reduced reliability.
    - **Instability**: Exhibits performance issues (e.g., latency spikes, inconsistent metrics, high error rates) during the 2–4 week evaluation window.
- **Actions**:
  - **Keep v1**:
    - Retain the current SeldonDeployment configuration routing 100% traffic to `fraud_v1`:
      ```yaml
      apiVersion: machinelearning.seldon.io/v1
      kind: SeldonDeployment
      metadata:
        name: fraud-predictor
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
          traffic: 100
      ```
    - Apply the configuration if not already active:
      ```bash
      kubectl apply -f k8s/fraud-v1-deployment.yaml
      ```
    - Verify via Prometheus/Grafana that `fraud_v1` handles all traffic with stable performance (e.g., latency <100ms p95).
  - **Archive v2**:
    - Transition `fraud_v2` to the Archived stage in the MLflow Model Registry:
      ```python
      client.transition_model_version_stage(
          name="fraud_v2",
          version="2",
          stage="Archived"
      )
      ```
    - Retain `fraud_v2` artifacts in S3/MinIO for future analysis.
  - **Investigate Why v2 Failed**:
    - **Data Issues**:
      - Analyze feedback data (from Postgres/MLflow) for signs of data drift, e.g., changes in transaction patterns between training (Jan 2023–Mar 2024) and production (post-A/B test).
      - Check for feature distribution shifts (e.g., transaction amounts, frequency) using statistical tests (e.g., Kolmogorov-Smirnov test).
      - Verify holdout set (Feb–Mar 2024) was representative of production data.
    - **Overfitting**:
      - Re-evaluate offline metrics (Phase 4) to check if `fraud_v2` overfit to the training/holdout data, e.g., inflated recall (~0.85) not replicated in production.
      - Compare training vs. validation loss curves in MLflow to identify overfitting signs (e.g., diverging losses).
    - **Model Issues**:
      - Investigate if `fraud_v2`’s weights, trained on newer data (Jan–Mar 2024), failed to generalize due to insufficient regularization or architectural limitations.
      - Review hyperparameter settings (e.g., dropout rate, learning rate) for potential optimization.
    - **Pipeline Issues**:
      - Check for preprocessing mismatches between training and inference (e.g., inconsistent feature scaling), a common issue in the stock prediction case.
      - Verify S3/MinIO artifact integrity and correct model loading in TensorFlow Serving containers.
    - **Investigation Process**:
      - Conduct a root cause analysis (RCA) using MLflow logs, Prometheus metrics, and Grafana visualizations.
      - Document findings in a failure report, e.g., “`fraud_v2` recall only 0.81 in production due to data drift in transaction volume features.”
      - Propose next steps, such as retraining with updated data, adjusting features, or exploring alternative architectures (e.g., gradient boosting instead of MLP).
- **Business Impact**:
  - Communicate to stakeholders that retaining `fraud_v1` ensures operational stability while the team addresses `fraud_v2`’s shortcomings.
  - Highlight proactive investigation to prevent future failures, building trust in the MLOps process.

#### ✅ Deliverable
- **Final Promotion Decision**:
  - A decision document detailing:
    - **Outcome**: Whether `fraud_v2` is promoted to 100% traffic or `fraud_v1` is retained.
    - **Evidence**: Summary of Phase 6 metrics (e.g., `fraud_v2`: recall ~0.85, precision ~0.91; `fraud_v1`: recall ~0.80, precision ~0.91), statistical significance (p-value), and stability (latency, error rates).
    - **Business Impact**: For promotion, quantify savings (e.g., $X/month from 5% more fraud detection); for rollback, outline operational continuity and investigation plan.
    - **Actions Taken**: Updated SeldonDeployment YAML, MLflow stage transitions, and monitoring adjustments.
  - Stored as an MLflow artifact linked to the A/B test experiment run.
- **Updated Model Lifecycle Docs**:
  - **Content**:
    - **Model History**: Updated lifecycle for `fraud_v1` and `fraud_v2`, including stage transitions (e.g., `fraud_v2` → Production or Archived).
    - **A/B Test Summary**: Traffic split (80/20), evaluation window (2–4 weeks), and key metrics.
    - **Failure Analysis (if applicable)**: Detailed RCA for `fraud_v2` underperformance, with data drift, overfitting, or pipeline issue findings.
    - **Future Recommendations**: For promotion, outline monitoring plan for `fraud_v2`; for rollback, propose retraining or feature engineering improvements.
  - **Format**: Markdown or YAML file stored in the project repository (e.g., `docs/model_lifecycle.md`) and linked in MLflow for traceability.
  - Example snippet:
    ```yaml
    model_lifecycle:
      fraud_v1:
        status: "Retained (Production)"
        metrics: { precision: 0.91, recall: 0.80, fraud_detection_rate: 0.80 }
        last_updated: "2025-07-21"
      fraud_v2:
        status: "Promoted (Production)"  # or "Archived"
        metrics: { precision: 0.91, recall: 0.85, fraud_detection_rate: 0.85 }
        ab_test:
          duration: "3 weeks"
          traffic_split: { baseline: 80%, candidate: 20% }
          outcome: "Promoted due to +5% recall, stable precision"
        failure_analysis: null  # or "Data drift in transaction volume features"
    ```

#### Why This Works for Seldon A/B Testing
This phase effectively concludes the Seldon A/B test, addressing the shortcomings of the stock prediction case:
- **Clear Decision Criteria**: The ≥5% recall improvement and ±1% precision stability provide a robust, data-driven basis for promotion or rollback, unlike the ambiguous outcomes in stock prediction (52–53% accuracy).
- **Seamless Deployment Management**: Seldon Core’s rapid redeployment (<30 seconds) and MLflow’s stage transitions ensure smooth transitions, avoiding manual errors like UUID mismatches in the stock prediction case.
- **Business Alignment**: Promotion of `fraud_v2` delivers measurable value (e.g., reduced fraud losses), while rollback protects operational stability, addressing the stock prediction case’s lack of business value.
- **Proactive Failure Analysis**: Investigating `fraud_v2` failures (e.g., data drift, overfitting) ensures continuous improvement, unlike the stock prediction case where issues were not systematically addressed.
- **Traceable Documentation**: Comprehensive lifecycle docs and MLflow integration provide transparency and auditability, enabling future iterations and stakeholder confidence.

Phase 7 demonstrates Seldon Core’s ability to manage production model transitions, validate A/B test outcomes, and maintain a robust MLOps pipeline, delivering both technical reliability and business value.
