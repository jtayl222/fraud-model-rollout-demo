### Phase 3: Candidate Model Training (v2) - Detailed Explanation

**Phase 3** focuses on training a candidate model (`fraud_v2`) to serve as the challenger in an A/B test against the baseline model from Phase 2, leveraging Seldon Core for deployment and comparison. This phase uses the same TensorFlow MLP architecture as the baseline but incorporates newer data to capture evolving patterns in fraud detection, aiming to improve performance metrics, particularly recall, while maintaining precision.

#### 1. Architecture
- **Model Type**: TensorFlow Multi-Layer Perceptron (MLP), identical to the baseline model from Phase 2.
- **Hyperparameters**: Same as the baseline, including:
  - Number of layers and units (e.g., 3 layers with 128, 64, 32 units).
  - Activation functions (e.g., ReLU for hidden layers, sigmoid for output).
  - Learning rate, optimizer (e.g., Adam), and regularization settings (e.g., dropout rate, L2 regularization).
- **Key Difference**: The model is trained on a newer dataset, resulting in different weights that reflect updated patterns in the data. This allows `fraud_v2` to potentially better capture recent fraud behaviors without altering the architecture, ensuring a fair A/B test comparison focused on data-driven improvements.

#### 2. Training
- **Dataset**: The training data spans **January 2023 to March 2024**, comprising approximately **900,000 rows** of transaction data. This includes:
  - **Jan–Dec 2023**: Full-year data to capture annual trends and seasonality in fraud patterns.
  - **Jan–Mar 2024**: Recent data to reflect emerging fraud behaviors, ensuring the model adapts to current trends.
- **Data Preprocessing**: Consistent with Phase 2, including feature engineering (e.g., transaction amount, frequency, time-based features, and categorical encodings) to maintain compatibility for A/B testing. The unified feature set ensures identical input shapes for both baseline and candidate models, avoiding the shape incompatibility issues seen in the stock prediction case.
- **Training Process**:
  - **Environment**: Executed in a Kubernetes cluster using an automated training pipeline (e.g., Argo Workflows) with MLflow for experiment tracking.
  - **Model Registration**: Post-training, the model is logged to the MLflow Model Registry as `fraud_v2` with a unique version (e.g., `v2`) and linked to the training run for lineage tracking.
  - **Training Objective**: Optimize for binary classification (fraud vs. non-fraud), minimizing binary cross-entropy loss while prioritizing recall to catch more fraud cases.
- **Resource Configuration**: Training jobs are configured with adequate resources (e.g., 4 CPUs, 16GB memory) to avoid contention issues, with S3/MinIO credentials properly set up via rclone or Kubernetes service accounts to ensure artifact storage.

#### 3. Expected Offline Metrics (Holdout: Feb–Mar 2024)
- **Holdout Dataset**: A subset of data from **February to March 2024** is reserved for offline evaluation to simulate real-world performance on recent transactions.
- **Metrics**:
  - **Precision**: ~0.91 (unchanged from baseline), indicating the model maintains a low false positive rate, correctly identifying fraud among predicted positives.
  - **Recall**: ~0.85 (improved from baseline, e.g., ~0.80), reflecting better detection of actual fraud cases due to the inclusion of newer data capturing recent fraud patterns.
  - **F1 Score**: ~0.88, balancing precision and recall, showing overall improvement in model performance while maintaining stability.
- **Evaluation Process**:
  - Metrics are computed on the holdout set using standard evaluation scripts integrated with MLflow for reproducibility.
  - Results are documented in a candidate metrics report, comparing `fraud_v2` against the baseline to justify promotion to staging for A/B testing.

#### ✅ Deliverable
- **SavedModel**: The trained model is saved as a TensorFlow `SavedModel` format, stored in the MLflow Model Registry under `models:/fraud_v2/Staging` for deployment preparation.
- **Candidate Metrics Report**: A detailed report including:
  - Precision, recall, and F1 scores on the holdout set (Feb–Mar 2024).
  - Comparison with baseline metrics to highlight improvements (e.g., +0.05 in recall).
  - Training metadata (e.g., dataset details, hyperparameters, training duration).
  - Lineage information linking the model to the training run and data artifacts in S3/MinIO.

#### Why This Works for Seldon A/B Testing
Unlike the stock prediction case, fraud detection is well-suited for demonstrating Seldon A/B testing due to:
- **High Accuracy**: Expected metrics (~0.91 precision, ~0.85 recall) are significantly better than random, showcasing meaningful model performance.
- **Unified Feature Set**: Both baseline and candidate models use identical input shapes, simplifying A/B test setup and ensuring compatibility.
- **Clear Business Value**: Improved recall directly translates to catching more fraud cases, delivering measurable ROI (e.g., reduced financial losses).
- **Stable Pipeline**: The fraud detection pipeline has consistent preprocessing and fewer dependencies, keeping the focus on Seldon’s A/B testing capabilities.
- **Actionable Outcomes**: Predictions (fraud vs. non-fraud) are directly actionable for business decisions, making A/B test results impactful for stakeholders.

This phase sets up `fraud_v2` as a strong candidate for A/B testing, leveraging Seldon Core to compare its performance against the baseline in a production-like environment, with clear metrics and business relevance.
