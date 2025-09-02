import os

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

# --- Configuration for all phases ---
project_dir = "."
data_dir = os.path.join(project_dir, "data")
enriched_dir = os.path.join(data_dir, "enriched")
splits_dir = os.path.join(data_dir, "splits")
models_dir = os.path.join(project_dir, "models")

# Ensure directories exist
os.makedirs(enriched_dir, exist_ok=True)
os.makedirs(splits_dir, exist_ok=True)
os.makedirs(models_dir, exist_ok=True)

# Model paths
baseline_model_path_keras = os.path.join(models_dir, "fraud_v1.keras")
candidate_model_path_keras = os.path.join(models_dir, "fraud_v2.keras")

# --- Phase 1: Dataset Strategy ---
print("--- Phase 1: Dataset Strategy ---")
print("Step 1: Setting up Project Environment (directories created).")

print("\nStep 2: Downloading and Initial Data Exploration...")
# Assuming creditcard.csv is manually downloaded and placed in data/
csv_path = os.path.join(data_dir, "creditcard.csv")

if not os.path.exists(csv_path):
    print(
        f"Error: {csv_path} not found. Please download 'creditcard.csv' from Kaggle "
        "Credit Card Fraud Dataset and place it in the 'data/' folder."
    )
    exit()

df_original = pd.read_csv(csv_path)

print(f"Initial number of rows: {len(df_original)}")
original_fraud_rate = df_original["Class"].value_counts(normalize=True) * 100
print(f"Initial fraud rate: {original_fraud_rate[1]:.2f}%")

print("\nStep 3: Data Replication to Reach Target Scale...")
target_rows = 1_000_000
original_rows = len(df_original)
replication_factor = int(np.ceil(target_rows / original_rows))

df_replicated = pd.concat([df_original] * replication_factor, ignore_index=True)

if len(df_replicated) > target_rows:
    df_replicated = df_replicated.sample(n=target_rows, random_state=42).reset_index(
        drop=True
    )

print(f"Replicated dataset size: {len(df_replicated)} rows")

target_fraud_rate = 0.01  # 1%
required_fraud_cases = int(target_rows * target_fraud_rate)

df_fraud = df_replicated[df_replicated["Class"] == 1].copy()
df_non_fraud = df_replicated[df_replicated["Class"] == 0].copy()

current_fraud_cases = len(df_fraud)
if current_fraud_cases < required_fraud_cases:
    fraud_replication_factor = int(np.ceil(required_fraud_cases / current_fraud_cases))
    df_fraud_oversampled = pd.concat(
        [df_fraud] * fraud_replication_factor, ignore_index=True
    )
    if len(df_fraud_oversampled) > required_fraud_cases:
        df_fraud_oversampled = df_fraud_oversampled.sample(
            n=required_fraud_cases, random_state=42
        ).reset_index(drop=True)
else:
    df_fraud_oversampled = df_fraud.sample(
        n=required_fraud_cases, random_state=42
    ).reset_index(drop=True)

df_enriched = pd.concat([df_non_fraud, df_fraud_oversampled], ignore_index=True)
df_enriched = df_enriched.sample(frac=1, random_state=42).reset_index(drop=True)

final_fraud_rate = df_enriched["Class"].value_counts(normalize=True) * 100
print(f"Final enriched dataset size: {len(df_enriched)} rows")
print(f"Final fraud rate: {final_fraud_rate[1]:.2f}%")

print("\nStep 4: Simulating Temporal Drift in Q1 2024 Data...")
start_date = pd.to_datetime("2023-01-01 00:00:00")
time_scale_factor = (pd.to_timedelta("450 days").total_seconds()) / df_enriched[
    "Time"
].max()
df_enriched["Time_scaled"] = df_enriched["Time"] * time_scale_factor
df_enriched["datetime"] = start_date + pd.to_timedelta(
    df_enriched["Time_scaled"], unit="s"
)

df_enriched = df_enriched.drop(columns=["Time"])
df_enriched = df_enriched.rename(columns={"Time_scaled": "Time"})

q1_2024_start = pd.to_datetime("2024-01-01")
q1_2024_end = pd.to_datetime("2024-03-31")

df_q1_2024 = df_enriched[
    (df_enriched["datetime"] >= q1_2024_start)
    & (df_enriched["datetime"] <= q1_2024_end)
].copy()
df_pre_q1_2024 = df_enriched[
    (df_enriched["datetime"] < q1_2024_start) | (df_enriched["datetime"] > q1_2024_end)
].copy()

fraud_q1_2024_indices = df_q1_2024[df_q1_2024["Class"] == 1].index

if not fraud_q1_2024_indices.empty:
    num_new_pattern_fraud = int(0.25 * len(fraud_q1_2024_indices))
    if num_new_pattern_fraud > 0:
        new_pattern_indices = np.random.choice(
            fraud_q1_2024_indices, num_new_pattern_fraud, replace=False
        )
        df_q1_2024.loc[new_pattern_indices, "V1"] += np.random.normal(
            loc=1.0, scale=0.2, size=num_new_pattern_fraud
        )
        df_q1_2024.loc[new_pattern_indices, "V2"] -= np.random.normal(
            loc=0.5, scale=0.1, size=num_new_pattern_fraud
        )
        df_q1_2024.loc[new_pattern_indices, "V3"] += np.random.normal(
            loc=0.7, scale=0.15, size=num_new_pattern_fraud
        )
        df_q1_2024.loc[new_pattern_indices, "Amount"] *= np.random.uniform(
            1.2, 1.5, size=num_new_pattern_fraud
        )

    df_q1_2024.loc[df_q1_2024["Class"] == 1, "Amount"] *= 1.1

    nighttime_fraud_indices = np.random.choice(
        fraud_q1_2024_indices, int(0.3 * len(fraud_q1_2024_indices)), replace=False
    )
    for idx in nighttime_fraud_indices:
        current_dt = df_q1_2024.loc[idx, "datetime"]
        if not (current_dt.hour >= 22 or current_dt.hour < 6):
            random_hour = np.random.choice(list(range(22, 24)) + list(range(0, 6)))
            random_minute = np.random.randint(0, 60)
            random_second = np.random.randint(0, 60)
            df_q1_2024.loc[idx, "datetime"] = current_dt.replace(
                hour=random_hour, minute=random_minute, second=random_second
            )

df_final_enriched = pd.concat([df_pre_q1_2024, df_q1_2024], ignore_index=True)
df_final_enriched = df_final_enriched.sample(frac=1, random_state=42).reset_index(
    drop=True
)

print("\nStep 5: Create Temporal Splits for Training and Validation...")
train_v1_end_date = pd.to_datetime("2023-12-31 23:59:59")
train_v2_end_date = pd.to_datetime("2024-03-31 23:59:59")
holdout_start_date = pd.to_datetime("2024-02-01 00:00:00")
holdout_end_date = pd.to_datetime("2024-03-31 23:59:59")

df_train_v1 = df_final_enriched[
    df_final_enriched["datetime"] <= train_v1_end_date
].copy()
df_train_v2 = df_final_enriched[
    df_final_enriched["datetime"] <= train_v2_end_date
].copy()
df_holdout_test = df_final_enriched[
    (df_final_enriched["datetime"] >= holdout_start_date)
    & (df_final_enriched["datetime"] <= holdout_end_date)
].copy()

print(f"train_v1 size (Jan–Dec 2023): {len(df_train_v1)} rows")
print(f"train_v2 size (Jan 2023 – Mar 2024): {len(df_train_v2)} rows")
print(f"holdout_test size (Feb–Mar 2024): {len(df_holdout_test)} rows")

print("\nStep 6: Final Data Storage...")
df_final_enriched.to_csv(os.path.join(enriched_dir, "fraud_dataset.csv"), index=False)
df_train_v1.to_csv(os.path.join(splits_dir, "train_v1.csv"), index=False)
df_train_v2.to_csv(os.path.join(splits_dir, "train_v2.csv"), index=False)
df_holdout_test.to_csv(os.path.join(splits_dir, "holdout_test.csv"), index=False)
print("Phase 1 Completed.")

# --- Phase 2: Baseline Model Training (v1) ---
print("\n--- Phase 2: Baseline Model Training (v1) ---")
print("Step 1: Loading Data for Baseline Model (v1)...")
train_v1_path = os.path.join(splits_dir, "train_v1.csv")
holdout_test_path = os.path.join(splits_dir, "holdout_test.csv")

df_train_v1 = pd.read_csv(train_v1_path)
df_holdout_test_phase2 = pd.read_csv(
    holdout_test_path
)  # Use a distinct name to avoid conflict

features = [
    col
    for col in df_train_v1.columns
    if col.startswith("V") or col in ["Time", "Amount"]
]
target = "Class"

X_train_v1 = df_train_v1[features]
y_train_v1 = df_train_v1[target]

X_holdout_test_phase2 = df_holdout_test_phase2[features]
y_holdout_test_phase2 = df_holdout_test_phase2[target]

print("\nStep 2: Preprocessing Data (Scaling)...")
scaler_v1 = StandardScaler()  # Scaler for v1
X_train_v1_scaled = scaler_v1.fit_transform(X_train_v1)
X_holdout_test_phase2_scaled = scaler_v1.transform(X_holdout_test_phase2)

print("\nStep 3: Defining Model Architecture (TensorFlow MLP)...")
input_shape = X_train_v1_scaled.shape[1]
model_v1 = tf.keras.Sequential(
    [
        tf.keras.layers.Input(shape=(input_shape,)),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ]
)

optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)
model_v1.compile(
    optimizer=optimizer,
    loss="binary_crossentropy",
    metrics=[
        tf.keras.metrics.Precision(name="precision"),
        tf.keras.metrics.Recall(name="recall"),
        tf.keras.metrics.AUC(name="auc"),
    ],
)

print("\nStep 4: Training Baseline Model (v1)...")
neg, pos = np.bincount(y_train_v1)
total = neg + pos
weight_for_0 = (1 / neg) * (total / 2.0)
weight_for_1 = (1 / pos) * (total / 2.0)
class_weight = {0: weight_for_0, 1: weight_for_1}

callbacks = [
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=5, restore_best_weights=True
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=3, min_lr=0.00001
    ),
]

history_v1 = model_v1.fit(
    X_train_v1_scaled,
    y_train_v1,
    epochs=50,
    batch_size=256,
    class_weight=class_weight,
    validation_split=0.2,
    callbacks=callbacks,
    verbose=0,
)  # Set to 0 for less verbose output in full script

print("\nStep 5: Performing Offline Evaluation and Drift Detection...")
y_pred_holdout_probs_v1 = model_v1.predict(X_holdout_test_phase2_scaled).flatten()
y_pred_holdout_v1 = (y_pred_holdout_probs_v1 > 0.5).astype(int)

precision_holdout_v1 = precision_score(y_holdout_test_phase2, y_pred_holdout_v1)
recall_holdout_v1 = recall_score(y_holdout_test_phase2, y_pred_holdout_v1)
f1_holdout_v1 = f1_score(y_holdout_test_phase2, y_pred_holdout_v1)
roc_auc_holdout_v1 = roc_auc_score(y_holdout_test_phase2, y_pred_holdout_probs_v1)
conf_matrix_holdout_v1 = confusion_matrix(y_holdout_test_phase2, y_pred_holdout_v1)

print(f"  Holdout Precision (v1): {precision_holdout_v1:.4f}")
print(f"  Holdout Recall (v1):    {recall_holdout_v1:.4f}")
print(f"  Holdout F1-Score (v1):  {f1_holdout_v1:.4f}")
print(f"  Holdout AUC-ROC (v1):   {roc_auc_holdout_v1:.4f}")

print("\nStep 6: Saving the Trained Baseline Model (v1)...")
model_v1.save(baseline_model_path_keras)
print(f"Baseline model (fraud_v1) saved to: {baseline_model_path_keras}")
print("Phase 2 Completed.")

# --- Phase 3: Candidate Model Training (v2) ---
print("\n--- Phase 3: Candidate Model Training (v2) ---")
print("Step 1: Loading Data for Candidate Model (v2)...")
train_v2_path = os.path.join(splits_dir, "train_v2.csv")
holdout_test_path = os.path.join(splits_dir, "holdout_test.csv")

df_train_v2 = pd.read_csv(train_v2_path)
df_holdout_test_phase3 = pd.read_csv(holdout_test_path)  # Distinct name

features = [
    col
    for col in df_train_v2.columns
    if col.startswith("V") or col in ["Time", "Amount"]
]
target = "Class"

X_train_v2 = df_train_v2[features]
y_train_v2 = df_train_v2[target]

X_holdout_test_phase3 = df_holdout_test_phase3[features]
y_holdout_test_phase3 = df_holdout_test_phase3[target]

print("\nStep 2: Preprocessing Data (Scaling)...")
scaler_v2 = StandardScaler()  # New scaler for v2
X_train_v2_scaled = scaler_v2.fit_transform(X_train_v2)
X_holdout_test_phase3_scaled = scaler_v2.transform(X_holdout_test_phase3)

print(
    "\nStep 3: Defining Model Architecture (TensorFlow MLP) - Identical to Baseline..."
)
input_shape = X_train_v2_scaled.shape[1]
model_v2 = tf.keras.Sequential(
    [
        tf.keras.layers.Input(shape=(input_shape,)),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ]
)

optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)
model_v2.compile(
    optimizer=optimizer,
    loss="binary_crossentropy",
    metrics=[
        tf.keras.metrics.Precision(name="precision"),
        tf.keras.metrics.Recall(name="recall"),
        tf.keras.metrics.AUC(name="auc"),
    ],
)

print("\nStep 4: Training Candidate Model (v2)...")
neg_v2, pos_v2 = np.bincount(y_train_v2)
total_v2 = neg_v2 + pos_v2
weight_for_0_v2 = (1 / neg_v2) * (total_v2 / 2.0)
weight_for_1_v2 = (1 / pos_v2) * (total_v2 / 2.0)
class_weight_v2 = {0: weight_for_0_v2, 1: weight_for_1_v2}

callbacks_v2 = [
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=5, restore_best_weights=True
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=3, min_lr=0.00001
    ),
]

history_v2 = model_v2.fit(
    X_train_v2_scaled,
    y_train_v2,
    epochs=50,
    batch_size=256,
    class_weight=class_weight_v2,
    validation_split=0.2,
    callbacks=callbacks_v2,
    verbose=0,
)  # Set to 0 for less verbose output

print("\nStep 5: Performing Offline Evaluation for Candidate Model (v2)...")
y_pred_holdout_probs_v2 = model_v2.predict(X_holdout_test_phase3_scaled).flatten()
y_pred_holdout_v2 = (y_pred_holdout_probs_v2 > 0.5).astype(int)

precision_holdout_v2 = precision_score(y_holdout_test_phase3, y_pred_holdout_v2)
recall_holdout_v2 = recall_score(y_holdout_test_phase3, y_pred_holdout_v2)
f1_holdout_v2 = f1_score(y_holdout_test_phase3, y_pred_holdout_v2)
roc_auc_holdout_v2 = roc_auc_score(y_holdout_test_phase3, y_pred_holdout_probs_v2)
conf_matrix_holdout_v2 = confusion_matrix(y_holdout_test_phase3, y_pred_holdout_v2)

print(f"  Holdout Precision (v2): {precision_holdout_v2:.4f}")
print(f"  Holdout Recall (v2):    {recall_holdout_v2:.4f}")
print(f"  Holdout F1-Score (v2):  {f1_holdout_v2:.4f}")
print(f"  Holdout AUC-ROC (v2):   {roc_auc_holdout_v2:.4f}")

print("\nStep 6: Saving the Trained Candidate Model (v2)...")
model_v2.save(candidate_model_path_keras)
print(f"Candidate model (fraud_v2) saved to: {candidate_model_path_keras}")
print("Phase 3 Completed.")

# --- Phase 4: Offline Validation & Deployment Decision Gate ---
print("\n--- Phase 4: Offline Validation & Deployment Decision Gate ---")
print(
    "Step 1: Set up Environment (directories and libraries assumed from previous phases)."
)

print("\nStep 2: Load Models and Holdout Data...")
df_holdout_test_phase4 = pd.read_csv(holdout_test_path)  # Reload holdout for clarity
X_holdout_phase4 = df_holdout_test_phase4[features]
y_holdout_phase4 = df_holdout_test_phase4[target]

# Load models
model_v1_loaded = tf.keras.models.load_model(baseline_model_path_keras)
model_v2_loaded = tf.keras.models.load_model(candidate_model_path_keras)
print("Models loaded.")

# Apply scaling to holdout data using the scaler fitted on train_v2 data (from Phase 3)
# To correctly scale for evaluation, we reload train_v2 to fit the scaler as it was done in Phase 3
df_train_v2_for_scaler_eval = pd.read_csv(os.path.join(splits_dir, "train_v2.csv"))
X_train_v2_for_scaler_eval = df_train_v2_for_scaler_eval[features]
scaler_eval = StandardScaler()
scaler_eval.fit(
    X_train_v2_for_scaler_eval
)  # Fit scaler on the same data as model_v2 was trained
X_holdout_scaled_phase4 = scaler_eval.transform(X_holdout_phase4)
print("Holdout data scaled for evaluation.")


print("\nStep 3: Evaluate Both Models on the Holdout Set...")
print("\n--- Evaluating Baseline Model (v1) ---")
y_pred_probs_v1_eval = model_v1_loaded.predict(X_holdout_scaled_phase4).flatten()
y_pred_v1_eval = (y_pred_probs_v1_eval > 0.5).astype(int)

precision_v1_eval = precision_score(y_holdout_phase4, y_pred_v1_eval)
recall_v1_eval = recall_score(y_holdout_phase4, y_pred_v1_eval)
f1_v1_eval = f1_score(y_holdout_phase4, y_pred_v1_eval)
auc_v1_eval = roc_auc_score(y_holdout_phase4, y_pred_probs_v1_eval)
conf_matrix_v1_eval = confusion_matrix(y_holdout_phase4, y_pred_v1_eval)

print(f"  Precision (v1): {precision_v1_eval:.4f}")
print(f"  Recall (v1):    {recall_v1_eval:.4f}")
print(f"  F1-Score (v1):  {f1_v1_eval:.4f}")
print(f"  AUC-ROC (v1):   {auc_v1_eval:.4f}")

print("\n--- Evaluating Candidate Model (v2) ---")
y_pred_probs_v2_eval = model_v2_loaded.predict(X_holdout_scaled_phase4).flatten()
y_pred_v2_eval = (y_pred_probs_v2_eval > 0.5).astype(int)

precision_v2_eval = precision_score(y_holdout_phase4, y_pred_v2_eval)
recall_v2_eval = recall_score(y_holdout_phase4, y_pred_v2_eval)
f1_v2_eval = f1_score(y_holdout_phase4, y_pred_v2_eval)
auc_v2_eval = roc_auc_score(y_holdout_phase4, y_pred_probs_v2_eval)
conf_matrix_v2_eval = confusion_matrix(y_holdout_phase4, y_pred_v2_eval)

print(f"  Precision (v2): {precision_v2_eval:.4f}")
print(f"  Recall (v2):    {recall_v2_eval:.4f}")
print(f"  F1-Score (v2):  {f1_v2_eval:.4f}")
print(f"  AUC-ROC (v2):   {auc_v2_eval:.4f}")

print("\nStep 4: Compare Models and Make a Deployment Decision...")
print("\n--- Model Comparison on Holdout Set ---")
print("Metric       | Baseline (v1) | Candidate (v2) | Improvement")
print("-----------------------------------------------------------------")
print(
    f"Precision    | {precision_v1_eval:.4f}        | {precision_v2_eval:.4f}        | {precision_v2_eval - precision_v1_eval:+.4f}"
)
print(
    f"Recall       | {recall_v1_eval:.4f}        | {recall_v2_eval:.4f}        | {recall_v2_eval - recall_v1_eval:+.4f}"
)
print(
    f"F1-Score     | {f1_v1_eval:.4f}        | {f1_v2_eval:.4f}        | {f1_v2_eval - f1_v1_eval:+.4f}"
)
print(
    f"AUC-ROC      | {auc_v1_eval:.4f}        | {auc_v2_eval:.4f}        | {auc_v2_eval - auc_v1_eval:+.4f}"
)

recall_improvement_percent = (
    ((recall_v2_eval - recall_v1_eval) / recall_v1_eval) * 100
    if recall_v1_eval != 0
    else 0
)
print(f"\nRecall Improvement (v2 over v1): {recall_improvement_percent:.2f}%")

print("\n--- Deployment Decision Gate ---")
# Decision criteria: Recall improvement >= 5% AND Precision stability within +/- 1%
if (
    recall_improvement_percent >= 5
    and abs(precision_v2_eval - precision_v1_eval) <= 0.01
):
    print("Recommendation: **PROMOTE CANDIDATE MODEL (v2)**")
    print(
        "Reason: Candidate model shows significant recall improvement while maintaining stable precision. This justifies proceeding to Phase 5 for A/B testing in production."
    )
else:
    print("Recommendation: **DO NOT PROMOTE CANDIDATE MODEL (v2) YET**")
    print(
        "Reason: Candidate model did not meet the required performance criteria (e.g., <5% recall improvement or significant precision drop). Further investigation or retraining is needed before deployment."
    )

print("\nPhase 4 Completed.")
print("\n--- All Phases (1-4) Completed ---")
