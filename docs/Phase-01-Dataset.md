Here’s a **detailed plan for Phase 1: Dataset Strategy** that explains exactly how we’ll build, enrich, and prepare the fraud dataset for training and A/B testing.

---

# ✅ **Phase 1: Dataset Strategy – Detailed Plan**

We need a **realistic yet manageable fraud dataset** that supports:

* **Baseline vs Candidate training** with a **temporal split**
* **Concept drift simulation** (so v1 underperforms on newer data)
* **Fast CPU-only training** (no GPU required)
* **Ground truth labels** for feedback simulation

We’ll achieve this by **enriching the Kaggle Credit Card Fraud dataset** into \~1M rows with **time-based drift injection**.

---

## **1. Dataset Selection**

### **Base Dataset**

* **[Kaggle Credit Card Fraud Dataset](https://www.kaggle.com/mlg-ulb/creditcardfraud)**

  * \~284,807 transactions
  * \~0.17% fraud rate (492 fraud cases)
  * Already has **real statistical structure** (albeit anonymized PCA features)

### **Why Kaggle (Not Fully Synthetic)?**

✅ It’s **real data** → captures realistic fraud/non-fraud feature correlations
✅ We can **extend & perturb** it to simulate drift without generating unrealistic patterns
✅ Easier for others to **reproduce** the demo

---

## **2. Target Scale & Fraud Rate**

We want a **larger dataset (\~1M rows)** to feel more realistic, but not so big that CPU-only training becomes impractical.

* **Final size:** \~1M rows
* **Fraud rate:** **\~1%** (≈10k fraud cases) → close to reality but still has **enough fraud examples** for training & evaluation

We’ll achieve this by:

* **Oversampling** fraud cases slightly (to increase class signal)
* **Adding Gaussian noise** to non-fraud transactions to expand volume
* **Injecting new fraud patterns for Q1 2024**

---

## **3. Temporal Drift Creation**

To simulate **concept drift**, we’ll partition the dataset into **time windows**:

| Time Window      | Purpose                      | Rows   | Content                             |
| ---------------- | ---------------------------- | ------ | ----------------------------------- |
| **Jan–Dec 2023** | Baseline v1 training data    | \~700k | “Old” fraud patterns                |
| **Jan–Mar 2024** | Candidate v2 additional data | \~200k | Contains **new fraud patterns**     |
| **Feb–Mar 2024** | Holdout for validation/test  | \~100k | Shows **baseline performance drop** |

---

### **How We Inject Drift in Q1 2024**

1. **New fraudulent merchant categories**

   * Introduce **5 new merchant codes** (e.g., new e-commerce vendors) **seen only in Q1 2024**
   * Baseline v1 hasn’t seen them → more false negatives

2. **Different transaction time-of-day patterns**

   * More fraud between **2am–5am** in Q1 2024
   * Baseline v1 learned old patterns (e.g., fraud mostly at noon) → misses these

3. **Slightly higher fraud transaction amounts**

   * Q1 fraud cases have **higher median amount** → baseline underestimates risk

This ensures **baseline recall drops on Feb–Mar 2024 holdout**, triggering a **need for retraining**.

---

## **4. Feature Schema**

We’ll simulate a **realistic tabular fraud dataset** with \~30–50 features.

### **Base Features**

* `txn_amount` → transaction amount
* `merchant_category_encoded` → encoded merchant type
* `txn_time_of_day` → categorical (morning/afternoon/night)
* `geo_risk_score` → based on transaction location (0–1)
* `device_fingerprint_score` → device anomaly score (0–1)
* `account_age_days` → age of account in days
* `customer_txn_frequency` → average # transactions/day
* `customer_avg_txn_amount` → rolling average amount
* `num_chargebacks` → historical fraud count for customer

### **Engineered Features**

* `velocity_score` → # transactions in last 24h
* `merchant_risk_score` → historical fraud rate for merchant
* `geo_distance_from_usual` → distance from customer’s usual transaction location
* `hour_sin`, `hour_cos` → cyclical time encoding

### **Drift-Specific Features**

* New merchant categories in Q1
* Nighttime fraud transactions (2–5am) in Q1
* Higher median fraud amount in Q1

Each transaction will also have:

* `timestamp` → for temporal splitting
* `fraud_label` → 0 (legit) or 1 (fraud)



---

## **5. Sample Schema (columns)**

| Column                          | Description                                    |
| ------------------------------- | ---------------------------------------------- |
| **txn\_id**                     | Unique transaction ID                          |
| **timestamp**                   | Transaction datetime (used for temporal split) |
| **txn\_amount**                 | Transaction amount in USD                      |
| **merchant\_category\_encoded** | Encoded merchant category                      |
| **geo\_risk\_score**            | Risk score for location (0–1)                  |
| **device\_fingerprint\_score**  | Device anomaly score (0–1)                     |
| **account\_age\_days**          | Age of customer account                        |
| **customer\_txn\_frequency**    | Avg # of daily transactions                    |
| **velocity\_score**             | Transactions in last 24h                       |
| **merchant\_risk\_score**       | Merchant historical fraud rate                 |
| **geo\_distance\_from\_usual**  | Distance from usual location (km)              |
| **hour\_sin**, **hour\_cos**    | Cyclical encoding of transaction time          |
| **is\_night\_txn**              | 1 if txn in 2am–5am window                     |
| **fraud\_label**                | 1 = Fraud, 0 = Legit                           |

---

## **6. Sample Rows (10 transactions)**

| txn\_id | timestamp        | txn\_amount | merchant\_category\_encoded | geo\_risk\_score | device\_fingerprint\_score | account\_age\_days | customer\_txn\_frequency | velocity\_score | merchant\_risk\_score | geo\_distance\_from\_usual | hour\_sin | hour\_cos | is\_night\_txn | fraud\_label |
| ------- | ---------------- | ----------- | --------------------------- | ---------------- | -------------------------- | ------------------ | ------------------------ | --------------- | --------------------- | -------------------------- | --------- | --------- | -------------- | ------------ |
| 100001  | 2023-03-15 14:22 | 82.15       | 12                          | 0.12             | 0.08                       | 450                | 3.1                      | 2               | 0.02                  | 1.2                        | 0.72      | 0.69      | 0              | 0            |
| 100002  | 2023-08-09 10:05 | 154.32      | 7                           | 0.33             | 0.15                       | 1120               | 1.4                      | 1               | 0.05                  | 0.8                        | 0.17      | 0.98      | 0              | 0            |
| 100003  | 2023-12-21 16:50 | 430.25      | 19                          | 0.45             | 0.22                       | 760                | 2.7                      | 3               | 0.12                  | 2.4                        | -0.95     | -0.31     | 0              | 1            |
| 100004  | 2024-01-11 03:17 | 995.10      | **27 (new)**                | 0.82             | 0.61                       | 95                 | 4.3                      | 6               | 0.25                  | 8.7                        | -0.06     | -0.99     | **1**          | **1**        |
| 100005  | 2024-01-22 11:45 | 71.80       | 8                           | 0.19             | 0.11                       | 350                | 2.9                      | 2               | 0.03                  | 1.1                        | 0.99      | 0.12      | 0              | 0            |
| 100006  | 2024-02-03 02:40 | 1,220.00    | **29 (new)**                | 0.91             | 0.78                       | 40                 | 5.7                      | 10              | 0.41                  | 15.3                       | -0.13     | -0.99     | **1**          | **1**        |
| 100007  | 2024-02-17 09:10 | 205.33      | 13                          | 0.28             | 0.19                       | 210                | 2.0                      | 1               | 0.07                  | 1.5                        | 0.64      | 0.76      | 0              | 0            |
| 100008  | 2024-02-25 04:55 | 2,310.55    | **28 (new)**                | 0.96             | 0.84                       | 12                 | 8.4                      | 12              | 0.55                  | 22.7                       | -0.27     | -0.96     | **1**          | **1**        |
| 100009  | 2024-03-04 13:33 | 62.99       | 4                           | 0.08             | 0.05                       | 980                | 1.2                      | 0               | 0.01                  | 0.5                        | 0.48      | 0.87      | 0              | 0            |
| 100010  | 2024-03-12 02:15 | 3,405.00    | **30 (new)**                | 0.99             | 0.92                       | 5                  | 12.1                     | 20              | 0.68                  | 35.0                       | -0.50     | -0.86     | **1**          | **1**        |

---

### 🔹 What’s Happening Here?

* **Rows 1–3 (2023)** → Normal historical fraud patterns

  * Merchant categories **7, 12, 19** are *known*
  * Fraud cases have moderate amounts (\~\$400) and happen at normal hours

* **Rows 4, 6, 8, 10 (Q1 2024)** → **New fraud signals**

  * **New merchant\_category codes (27–30)** → unseen by v1
  * **Nighttime fraud (2am–5am)** → baseline hasn’t learned this
  * **Much higher fraud amounts** (\~\$1k–\$3k)

* **Baseline v1 will miss many Q1 frauds** because:

  * It never saw merchant 27–30 during training
  * It didn’t learn new nighttime fraud patterns
  * Its fraud amount thresholds are outdated

* **Candidate v2 retrained on Q1 2024** will catch them → recall improves.

---
---

## **7. Temporal Splitting Process**

1. **Assign synthetic timestamps** to the enriched dataset

   * Map 700k rows to Jan–Dec 2023
   * Map 200k rows to Jan–Mar 2024 (drift period)

2. **Split into train/val/test**:

   ```
   Baseline v1 Train → Jan–Dec 2023 (~700k rows)
   Candidate v2 Train → Jan–Mar 2024 (~900k rows)
   Holdout Test → Feb–Mar 2024 (~100k rows)
   ```

3. Ensure **holdout set contains new fraud patterns unseen by baseline** → v1 recall drops, v2 recall improves.


### 🔹 Temporal Splitting in Context

* **Baseline v1 Train (Jan–Dec 2023)** → Rows like 1–3
* **Candidate v2 Train (Jan–Mar 2024)** → Includes rows like 4–10
* **Holdout Feb–Mar 2024** → Rows 6–10 used to test drift

---

## **8. Deliverable**

At the end of Phase 1 we’ll have **ONE clean dataset** with:

✅ **\~1M rows**
✅ **\~1% fraud rate**
✅ **30–50 features + timestamp + label**
✅ **Temporal splits** to simulate drift
✅ **New fraud patterns introduced only in Q1 2024**

This dataset will be stored as:

```
data/enriched/fraud_dataset.csv
data/splits/train_v1.csv
data/splits/train_v2.csv
data/splits/holdout_test.csv
```

It will be **ready for Phase 2 Baseline training & Phase 3 Candidate retraining**.

---

## **9. Quick Visual Timeline**

```
            Concept Drift Appears
   |--------------------------------------|-----------|
   Jan 2023                           Dec 2023     Mar 2024

   - Baseline v1 training (Jan–Dec 2023)
   - Candidate v2 retrains (Jan–Mar 2024)
   - Holdout test = Feb–Mar 2024 (new fraud patterns)
```

---

## **10. Why This Works Well for the Demo**

* It uses **real Kaggle fraud signals** but **scales up** for a realistic volume (\~1M rows).
* The **temporal drift is controlled**, so baseline v1 predictably underperforms on Q1 2024 → making retraining meaningful.
* It’s still **CPU-friendly** for training (LightGBM/TF MLP \~10–20 min).
* It enables **offline → online consistency** (same data for offline validation + online fast replay).

---



