Here’s a **high-level project plan** for a **fraud detection A/B testing demo with Seldon**, using **TensorFlow models** and **temporal drift**. It’s structured like a real production ML lifecycle, but scoped to stay manageable on CPU hardware.

---

# ✅ **Fraud Detection A/B Testing Demo – Project Plan**

## **Phase 0: Scoping & Goals**

🎯 **Objective**

* Demonstrate **Seldon A/B testing** for fraud detection
* Baseline model (v1) vs. Candidate model (v2) → same architecture, different weights
* Show how temporal concept drift triggers retraining, and how v2 improves recall on newer fraud patterns

📌 **Key Outcomes**

* Baseline trained on **Jan–Dec 2023** → slight drop in Q1 2024 recall
* Candidate retrained with **Jan–Mar 2024 data** → improved recall, stable precision
* Deploy both models with **80/20 split** in Seldon
* Collect feedback, evaluate online metrics, decide whether to promote v2

---

## **Phase 1: Dataset Strategy**

1. **Dataset Selection**

   * Base: Kaggle Credit Card Fraud dataset OR fully synthetic
   * Scale: \~1M rows (fraud rate \~1%)

2. **Temporal Drift Creation**

   * Partition into time windows:

     * **Jan–Dec 2023 → v1 training data (\~700k rows)**
     * **Jan–Mar 2024 → additional \~200k rows (contains new fraud patterns)**
     * **Holdout Feb–Mar 2024 → \~100k rows for validation/test**
   * Inject drift in Q1 2024:

     * New fraudulent merchant categories
     * Different transaction time-of-day patterns
     * Slightly higher fraud transaction values

3. **Feature Schema**

   * 30–50 tabular features:

     * `amount`, `merchant_category_encoded`, `time_of_day`, `geo_risk_score`, `device_fingerprint_score`, `account_age_days`, `customer_txn_frequency`, etc.

✅ **Deliverable:** A **single clean dataset** with timestamp + label + features, ready for temporal splitting.

---

## **Phase 2: Baseline Model Training (v1)**

1. **Architecture**

   * TensorFlow MLP:

     * Input: \~30–50 features
     * Hidden: 3 layers (e.g., 128 → 64 → 32 neurons, ReLU + dropout)
     * Output: 1 sigmoid neuron for fraud probability

2. **Training**

   * Train on **Jan–Dec 2023 (\~700k rows)**
   * Optimizer: Adam, lr=0.001
   * Loss: Binary cross-entropy
   * Class weights to handle fraud imbalance (\~1%)

3. **Expected Offline Metrics (holdout test on Dec 2023)**

   * Precision: \~0.91
   * Recall: \~0.80
   * F1: \~0.85

4. **Expected Drift**

   * When tested on Q1 2024 data:

     * Precision stays stable
     * Recall drops to \~0.75 → triggers retraining

✅ **Deliverable:** SavedModel `fraud_v1` + baseline metrics report

---

## **Phase 3: Candidate Model Training (v2)**

1. **Architecture**

   * Same TensorFlow MLP, same hyperparams
   * Different weights due to new data

2. **Training**

   * Train on **Jan–Dec 2023 + Jan–Mar 2024 (\~900k rows)**

3. **Expected Offline Metrics (holdout Feb–Mar 2024)**

   * Precision: \~0.91 (unchanged)
   * Recall: \~0.85 (improved)
   * F1: \~0.88

✅ **Deliverable:** SavedModel `fraud_v2` + candidate metrics report

---

## **Phase 4: Offline Validation & Deployment Decision Gate**

1. **Offline Comparison (v1 vs v2)**

   * Evaluate both models on the **same Feb–Mar 2024 holdout set**
   * Verify:

     * v2 improves recall ≥ +5%
     * v2 precision stable (±1%)

2. **Human Approval Gate**

   * Fraud analyst review of confusion matrix & business impact
   * If acceptable → proceed to **Seldon deployment as Candidate**

✅ **Deliverable:** Decision report confirming **Candidate v2 → deploy as 20% traffic**

---

## **Phase 5: Seldon A/B Test Deployment**

1. **Deployment Config**

   * Deploy both models side by side:

     ```yaml
     traffic:
       - baseline: 80%
       - candidate: 20%
     ```
   * TensorFlow Serving container for each model

2. **Request Routing**

   * Transactions go through the same inference API
   * Seldon Envoy splits traffic according to weights

3. **Feedback API**

   * As ground truth fraud labels come in later, POST:

     ```json
     { "response": {...}, "truth": 1 }
     ```
   * Store in feedback DB (Postgres/MLflow)

✅ **Deliverable:** SeldonDeployment YAML for `fraud-abtest`

---

## **Phase 6: Online Monitoring & Evaluation**

1. **Metrics Collected (Prometheus/Grafana)**

   * Per-model:

     * `precision@production`
     * `recall@production`
     * `fraud_detection_rate` (fraud caught vs missed)
   * Latency

2. **Evaluation Window**

   * Run A/B test for **2–4 weeks**

3. **Decision Rule**

   * If v2 recall ↑ ≥5% and precision stable → **promote v2 to 100%**
   * If v2 worse or unstable → **rollback v2**

✅ **Deliverable:** Online A/B metrics report, recommendation for promotion/rollback

---

## **Phase 7: Model Promotion or Rollback**

1. **If Candidate Wins**

   * Redeploy Seldon with **v2 → 100% traffic**
   * Retire v1

2. **If Candidate Loses**

   * Keep v1
   * Investigate why v2 failed (data issue? overfitting?)

✅ **Deliverable:** Final promotion decision + updated model lifecycle docs

---

## **Phase 8: Full Lifecycle Automation (Optional)**

Later, automate with:

* **Scheduled drift detection** → triggers retrain pipeline
* **MLflow** for experiment tracking + artifact versioning
* **GitOps (ArgoCD)** for automatic Seldon updates
* **Argo Rollouts** for progressive traffic shifting

---

# ✅ **Timeline & Effort Estimate**

| Phase | Task                                        | Effort    |
| ----- | ------------------------------------------- | --------- |
| 0     | Define problem, goals, and success metrics  | 0.5 day   |
| 1     | Build/enrich dataset (\~1M rows with drift) | 1–2 days  |
| 2     | Train Baseline v1 (TF MLP)                  | 0.5 day   |
| 3     | Train Candidate v2 (TF MLP)                 | 0.5 day   |
| 4     | Offline validation + gate decision          | 0.5 day   |
| 5     | Seldon A/B deployment setup                 | 1 day     |
| 6     | Collect & monitor online feedback           | 2–4 weeks |
| 7     | Promotion/rollback decision                 | 0.5 day   |

So **Phase 0–5** can be done in **\~1 week** (excluding A/B runtime).

---

# ✅ **Final Demo Flow**

1. Show **Baseline model** underperforming on new fraud patterns
2. Retrain → **Candidate model** improves recall offline
3. Deploy **Seldon A/B test** with 80/20 split
4. Show **online metrics dashboard** → Candidate wins
5. **Promote Candidate → 100%**

This gives a **clear narrative** of:

* **Why retraining was needed (drift)**
* **Why v2 is better (offline & online metrics)**
* **How Seldon safely manages the rollout**

---
