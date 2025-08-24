Here’s a **detailed breakdown of Phase 2: Baseline Model Training (v1)**.

---

# ✅ **Phase 2: Baseline Model Training (v1)**

The **Baseline Model (v1)** represents the *currently deployed production model* trained on **historical fraud data (Jan–Dec 2023)**. It will be **deployed at 80% traffic** during the A/B test and serves as the *control model* against which the **Candidate Model (v2)** will be compared.

---

## **1. Model Architecture**

We’re using a **simple TensorFlow Multi-Layer Perceptron (MLP)**, which works well for tabular fraud data while keeping the model lightweight enough for CPU inference.

**Layers**

```
Input: 30–50 features (normalized/encoded tabular features)
Dense(128) → ReLU → Dropout(0.3)
Dense(64)  → ReLU → Dropout(0.2)
Dense(32)  → ReLU
Dense(1)   → Sigmoid → Fraud probability ∈ [0,1]
```

**Why an MLP for baseline?**
✅ Works with **tabular data** (amounts, categorical merchants, risk scores)
✅ **Lightweight** for CPU-only training and inference
✅ Simple enough to **train fast (\~10–15 min)** on \~700k rows

---

## **2. Training Setup**

### **Training Data**

* **Time window:** Jan–Dec 2023
* **Size:** \~700k transactions (\~7k fraud cases, \~1% fraud rate)
* **Features:** \~30–50 tabular features (preprocessed with normalization + encoding)

### **Training Parameters**

* **Optimizer:** Adam (learning rate = 0.001)
* **Loss:** Binary Cross-Entropy (with class weights to handle class imbalance)
* **Batch size:** 4096 (large batches for faster CPU training)
* **Epochs:** 10–15 (early stopping on validation loss)

### **Class Imbalance Handling**

Fraud rate is \~1%, so we **compute class weights dynamically**:

```python
weight_for_0 = (num_legit / total_samples)
weight_for_1 = (num_fraud / total_samples)^-1
```

Pass into `model.fit(..., class_weight=class_weights)` so the model doesn’t ignore fraud cases.

---

### **Training Pipeline**

1. **Load Train Set** → Jan–Nov 2023 (\~630k rows)
2. **Validation Set** → Dec 2023 (\~70k rows)
3. **Preprocess**

   * Normalize continuous features
   * Encode categorical features (merchant\_category, time\_of\_day)
   * Standardize feature order → consistent input shape
4. **Train TensorFlow MLP**

   * Monitor validation **Precision/Recall**
   * Save best weights based on **F1-score**
5. **Export Baseline Model**

   * Save as `fraud_v1` in TensorFlow `SavedModel` format → ready for TF Serving

---

## **3. Expected Offline Metrics**

After training **v1** on Jan–Dec 2023 data:

| Dataset                   | Precision | Recall | F1     | AUC-ROC |
| ------------------------- | --------- | ------ | ------ | ------- |
| **Validation (Dec 2023)** | \~0.91    | \~0.80 | \~0.85 | \~0.92  |

✅ **Interpretation:**

* **Precision \~0.91:** Very few false alarms → good for not blocking legit users
* **Recall \~0.80:** Baseline catches most fraud but **not perfect** → room for improvement
* **F1 \~0.85:** Balanced performance

This becomes the **benchmark** for evaluating **Candidate v2**.

---

## **4. Expected Drift on Q1 2024 Data**

When we test v1 on **new fraud patterns in Feb–Mar 2024 holdout set**:

* **Precision stays stable (\~0.90)** → it still correctly labels legit transactions
* **Recall drops to \~0.75** → it misses *new fraud categories* and *nighttime fraud patterns*
* **F1 decreases to \~0.82** → performance degradation signals **concept drift**

This drift **justifies retraining a candidate model (v2)** with **Q1 2024 data**.

---

## **5. Deliverables from Phase 2**

✅ **Trained TensorFlow Baseline Model**

* `models/fraud_v1/` (SavedModel format for TF Serving)
* Lightweight (\~5–10 MB), easily deployable on CPU

✅ **Baseline Metrics Report**

* Offline evaluation on Dec 2023 validation set
* Drift detection on Feb–Mar 2024 holdout set
* Confusion matrices, Precision/Recall curves, and AUC-ROC

✅ **Documentation**

* Notes on **training process, hyperparameters, class weights**
* Baseline’s expected recall drop → reason for retraining

---

## **Why Keep Baseline Simple?**

* It represents a **production model that’s been running for months**
* Keeping it **same architecture as Candidate** lets us isolate **data drift** as the only cause of improvement
* Minimizes deployment complexity → v2 can **reuse same TF Serving container**

---

## **Phase 2 Summary**

* **v1** is the **currently deployed fraud model**
* Trained on **stale data (2023)** → misses new Q1 fraud signals
* **Baseline recall \~0.80** on known data but **drops to \~0.75** on drifted Q1 holdout
* **Candidate v2** retraining becomes necessary

This sets the stage for **Phase 3: Candidate Model Training (v2)**.
