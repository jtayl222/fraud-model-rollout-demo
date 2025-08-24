# Fraud Model Rollout Demo

**End-to-end fraud detection demo with TensorFlow models, concept drift simulation, and Seldon Core A/B testing.**

This project demonstrates how to safely roll out **new fraud detection models** in production using **A/B testing** with [Seldon Core](https://github.com/SeldonIO/seldon-core).

It simulates a **real-world model lifecycle**:

1. **Baseline model (v1)** trained on historical transactions (Jan–Dec 2023)
2. **Concept drift in Q1 2024** introduces new fraud patterns → baseline performance drops
3. **Candidate model (v2)** retrained on updated data (Jan–Mar 2024)
4. **A/B test in Seldon Core** (80% traffic → v1, 20% → v2)
5. **Feedback loop** confirms v2 improves recall → promote v2 to 100%

---

## 📌 Why This Demo?

In production fraud detection:

* **Fraud patterns evolve** → models become stale (concept drift)
* You can’t blindly replace a model → you risk blocking legit customers
* **A/B testing lets you safely validate a new model on real traffic before full rollout**

This repo shows how to:

✅ Detect **model drift**
✅ Retrain candidate models with **new data**
✅ Deploy **baseline & candidate models side-by-side** in Seldon
✅ Collect **online feedback** and compare **precision/recall per model**
✅ Decide when to **promote or rollback models**

---

## 🗂️ Project Structure

```
fraud-model-rollout-demo/
├── data/
│   ├── raw/                     # Original Kaggle dataset
│   ├── enriched/                # Expanded ~1M-row dataset with temporal drift
│   └── splits/                  # Train/val/test temporal splits
│
├── notebooks/
│   ├── 01_data_enrichment.ipynb # Expand Kaggle dataset & inject drift
│   ├── 02_baseline_training.ipynb # Train baseline v1 (Jan–Dec 2023)
│   ├── 03_candidate_training.ipynb # Retrain candidate v2 (Jan–Mar 2024)
│   ├── 04_evaluation.ipynb      # Compare v1 vs v2 offline
│
├── models/
│   ├── fraud_v1/                # Baseline SavedModel
│   └── fraud_v2/                # Candidate SavedModel
│
├── seldon/
│   ├── seldon-fraud-abtest.yaml # A/B test deployment spec
│   └── traffic-promotion.yaml   # Example promotion config
│
├── scripts/
│   ├── replay_transactions.py   # Fast replay simulator for A/B testing
│   ├── send_feedback.py         # Simulated delayed feedback loop
│
└── README.md                    # You are here
```

---

## 📊 Dataset

This demo uses the **[Kaggle Credit Card Fraud Dataset](https://www.kaggle.com/mlg-ulb/creditcardfraud)** as a base and **enriches it** to simulate:

* **\~1M transactions**
* **Fraud rate \~1%** (close to reality but demo-friendly)
* **Temporal drift in Q1 2024**:

  * New fraud merchant categories
  * Changed transaction times (more nighttime fraud)
  * Higher average fraud amounts

**Temporal Splits**

* **Baseline v1 Training:** Jan–Dec 2023 (\~700k rows)
* **Candidate v2 Training:** Jan–Dec 2023 + Jan–Mar 2024 (\~900k rows)
* **Holdout Test:** Feb–Mar 2024 (\~100k rows unseen)

---

## 🤖 Model

A simple **TensorFlow MLP** for tabular fraud detection:

* **Input:** 30–50 features (amount, merchant, geo risk, account age, etc.)
* **Architecture:**

  ```
  Dense(128) → ReLU → Dropout(0.3)
  Dense(64)  → ReLU → Dropout(0.2)
  Dense(32)  → ReLU
  Dense(1)   → Sigmoid
  ```
* **Loss:** Binary Crossentropy (with class weights for imbalance)
* **Optimizer:** Adam

**Expected Metrics**

| Metric    | Baseline (v1) | Candidate (v2) |
| --------- | ------------- | -------------- |
| Precision | 0.91          | 0.91           |
| Recall    | 0.80          | 0.85           |
| F1-score  | 0.85          | 0.88           |
| AUC-ROC   | 0.92          | 0.95           |

---

## 🚀 Workflow

1. **Detect Drift**

   * Baseline v1 recall drops on Q1 2024 data

2. **Retrain Candidate**

   * v2 trained with updated Jan–Mar 2024 data

3. **Offline Validation**

   * v2 improves recall (+5%) on holdout Feb–Mar 2024

4. **Deploy A/B Test in Seldon**

   * 80% traffic → v1
   * 20% traffic → v2

5. **Fast Replay Simulation**

   * Replay \~10k transactions via Seldon REST API
   * Simulate feedback delay → post labels

6. **Online Metrics**

   * Compare per-model precision/recall in Prometheus/Grafana

7. **Promote or Rollback**

   * If v2 wins → 100% traffic
   * Else → keep v1

---

## 🏗️ Seldon Deployment

The A/B test is deployed with a **SeldonDeployment** spec:

```yaml
apiVersion: machinelearning.seldon.io/v1
kind: SeldonDeployment
metadata:
  name: fraud-abtest
  namespace: fraud-demo
spec:
  predictors:
  - name: baseline
    replicas: 1
    traffic: 80
    componentSpecs:
    - spec:
        containers:
        - name: fraud-v1
          image: seldonio/tfserving:1.15.0
          env:
          - name: MODEL_NAME
            value: fraud_v1
  - name: candidate
    replicas: 1
    traffic: 20
    componentSpecs:
    - spec:
        containers:
        - name: fraud-v2
          image: seldonio/tfserving:1.15.0
          env:
          - name: MODEL_NAME
            value: fraud_v2
```

---

## 🔄 Feedback Loop

During replay, we simulate delayed ground truth:

```bash
python scripts/replay_transactions.py --speed 500req/sec
python scripts/send_feedback.py --delay 30s
```

Seldon stores feedback for **online metric comparison**:

* `precision@production`
* `recall@production`
* latency

---

## 📈 Expected Outcome

* Baseline v1 misses new fraud patterns → lower recall in Q1
* Candidate v2 improves recall +5% while keeping precision stable
* Grafana shows **candidate outperforming baseline**
* Promote v2 to 100%

---

## 🛠️ Tech Stack

* **Data:** Kaggle Credit Card Fraud + enrichment
* **Model:** TensorFlow 2.x MLP
* **Serving:** Seldon Core + TensorFlow Serving
* **Metrics:** Prometheus + Grafana
* **Simulation:** Python transaction replay + feedback API

---

## 🏃 Quickstart

```bash
# 1. Enrich Kaggle dataset + inject drift
jupyter notebook notebooks/01_data_enrichment.ipynb

# 2. Train baseline & candidate models
jupyter notebook notebooks/02_baseline_training.ipynb
jupyter notebook notebooks/03_candidate_training.ipynb

# 3. Deploy models in Seldon
kubectl apply -f seldon/seldon-fraud-abtest.yaml

# 4. Fast replay transactions & send feedback
python scripts/replay_transactions.py
python scripts/send_feedback.py

# 5. View metrics in Grafana
kubectl port-forward svc/grafana 3000:80 -n monitoring
```

---

## 📚 Learn More

* [Seldon Core A/B Testing Docs](https://docs.seldon.io/projects/seldon-core/en/latest/analytics/ab_tests.html)
* [Concept Drift in Fraud Detection](https://arxiv.org/abs/2007.14604)
* [TensorFlow Serving](https://www.tensorflow.org/tfx/guide/serving)

---

## ✅ Roadmap

* [ ] Add **Argo Rollouts** for automated traffic shifting
* [ ] Integrate **MLflow** for experiment tracking
* [ ] Add **explainability (SHAP/Alibi)** for fraud decisions

---

**Author:** *Jeff Taylor*
📧 Contact: *[jtayl22@gmail.com](mailto:jtayl22@gmail.com)*
⭐ *If this helps, star the repo!*
