import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
import os
import datetime
import mlflow
import mlflow.tensorflow

# --- Configuration ---
project_dir = "."
data_splits_dir = os.path.join(project_dir, "data", "splits")
models_dir = os.path.join(project_dir, "models")
os.makedirs(models_dir, exist_ok=True)

# MLflow S3 bucket configuration
S3_BUCKET = os.getenv("MLFLOW_S3_BUCKET", "mlflow-artifacts")

candidate_model_path_keras = os.path.join(models_dir, "fraud_v2.keras")

# --- MLflow Configuration ---
# Create or get the fraud detection candidate experiment
experiment_name = "fraud-detection-candidate"
try:
    experiment_id = mlflow.create_experiment(experiment_name)
    print(f"Created new MLflow experiment: {experiment_name} (ID: {experiment_id})")
except Exception:
    experiment = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = experiment.experiment_id
    print(f"Using existing MLflow experiment: {experiment_name} (ID: {experiment_id})")

mlflow.set_experiment(experiment_name)

# --- Step 1: Load Data for Candidate Model (v2) ---
print("Step 1: Loading Data for Candidate Model (v2)...")
train_v2_path = os.path.join(data_splits_dir, "train_v2.csv")
holdout_test_path = os.path.join(
    data_splits_dir, "holdout_test.csv"
)  # Same holdout as Phase 2

if not os.path.exists(train_v2_path) or not os.path.exists(holdout_test_path):
    print(
        f"Error: Required data files not found. Ensure Phase 1 script has been run and "
        f"files are at {data_splits_dir}"
    )
    exit()

df_train_v2 = pd.read_csv(train_v2_path)
df_holdout_test = pd.read_csv(holdout_test_path)

print(f"Loaded train_v2.csv: {len(df_train_v2)} rows")
print(f"Loaded holdout_test.csv: {len(df_holdout_test)} rows")

# Prepare features (X) and target (y)
features = [
    col
    for col in df_train_v2.columns
    if col.startswith("V") or col in ["Time", "Amount"]
]
target = "Class"

X_train_v2 = df_train_v2[features]
y_train_v2 = df_train_v2[target]

X_holdout_test = df_holdout_test[features]
y_holdout_test = df_holdout_test[target]

print(f"Features used: {features}")

# --- Step 2: Preprocessing (Scaling) ---
print("\nStep 2: Preprocessing Data (Scaling)...")
# Important: Use a new scaler instance for v2 training, fitted on v2 training data
# OR if using a global scaler, load the one from Phase 2 and transform.
# For independent training as per "different weights" but "same architecture",
# fitting a new scaler to the new training data (train_v2) is appropriate.
scaler_v2 = StandardScaler()
X_train_v2_scaled = scaler_v2.fit_transform(X_train_v2)
X_holdout_test_scaled = scaler_v2.transform(
    X_holdout_test
)  # Use same scaler for holdout transformation

X_train_v2_scaled_df = pd.DataFrame(X_train_v2_scaled, columns=features)
X_holdout_test_scaled_df = pd.DataFrame(X_holdout_test_scaled, columns=features)

print("Features scaled using StandardScaler (fitted on train_v2 data).")

# --- Step 3: Define Model Architecture (TensorFlow MLP) - Identical to Baseline ---
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

model_v2.summary()

# --- Step 4: Training Setup ---
print("\nStep 4: Training Candidate Model (v2)...")

# Calculate class weights to handle imbalance (based on train_v2 data)
neg_v2, pos_v2 = np.bincount(y_train_v2)
total_v2 = neg_v2 + pos_v2
print(f"Total samples (train_v2): {total_v2}, Non-fraud: {neg_v2}, Fraud: {pos_v2}")

weight_for_0_v2 = (1 / neg_v2) * (total_v2 / 2.0)
weight_for_1_v2 = (1 / pos_v2) * (total_v2 / 2.0)

class_weight_v2 = {0: weight_for_0_v2, 1: weight_for_1_v2}
print(f"Class weights (train_v2): {class_weight_v2}")

callbacks_v2 = [
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=5, restore_best_weights=True
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=3, min_lr=0.00001
    ),
]

# Start MLflow run for candidate training
with mlflow.start_run(run_name="fraud_v2_candidate_training"):

    # Log hyperparameters
    mlflow.log_param("model_version", "v2")
    mlflow.log_param("model_type", "candidate")
    mlflow.log_param("epochs", 50)
    mlflow.log_param("batch_size", 256)
    mlflow.log_param("input_features", X_train_v2_scaled.shape[1])
    mlflow.log_param("architecture", "MLP_128_64_32")
    mlflow.log_param("optimizer", "Adam")
    mlflow.log_param("loss", "binary_crossentropy")
    mlflow.log_param(
        "class_weight_ratio", f"{class_weight_v2[0]:.2f}:{class_weight_v2[1]:.2f}"
    )
    mlflow.log_param("training_data", "Jan2023-Mar2024")

    # Train the model
    history_v2 = model_v2.fit(
        X_train_v2_scaled,
        y_train_v2,
        epochs=50,
        batch_size=256,
        class_weight=class_weight_v2,
        validation_split=0.2,  # Use a split of the training data for validation
        callbacks=callbacks_v2,
        verbose=1,
    )

    print("\nCandidate Model (v2) Training Complete.")

    # --- Step 5: Offline Evaluation ---
    print("\nStep 5: Performing Offline Evaluation for Candidate Model (v2)...")

    print("\nEvaluating Candidate Model (v2) on HOLD OUT TEST SET (Feb–Mar 2024):")
    y_pred_holdout_probs_v2 = model_v2.predict(X_holdout_test_scaled).flatten()
    y_pred_holdout_v2 = (y_pred_holdout_probs_v2 > 0.5).astype(int)

    # Calculate metrics on holdout
    precision_holdout_v2 = precision_score(y_holdout_test, y_pred_holdout_v2)
    recall_holdout_v2 = recall_score(y_holdout_test, y_pred_holdout_v2)
    f1_holdout_v2 = f1_score(y_holdout_test, y_pred_holdout_v2)
    roc_auc_holdout_v2 = roc_auc_score(y_holdout_test, y_pred_holdout_probs_v2)
    conf_matrix_holdout_v2 = confusion_matrix(y_holdout_test, y_pred_holdout_v2)

    # Log metrics to MLflow
    mlflow.log_metric("precision", precision_holdout_v2)
    mlflow.log_metric("recall", recall_holdout_v2)
    mlflow.log_metric("f1_score", f1_holdout_v2)
    mlflow.log_metric("roc_auc", roc_auc_holdout_v2)
    mlflow.log_metric("true_negatives", int(conf_matrix_holdout_v2[0, 0]))
    mlflow.log_metric("false_positives", int(conf_matrix_holdout_v2[0, 1]))
    mlflow.log_metric("false_negatives", int(conf_matrix_holdout_v2[1, 0]))
    mlflow.log_metric("true_positives", int(conf_matrix_holdout_v2[1, 1]))

    print(f"  Holdout Precision (v2): {precision_holdout_v2:.4f}")
    print(f"  Holdout Recall (v2):    {recall_holdout_v2:.4f}")
    print(f"  Holdout F1-Score (v2):  {f1_holdout_v2:.4f}")
    print(f"  Holdout AUC-ROC (v2):   {roc_auc_holdout_v2:.4f}")
    print("\n  Holdout Confusion Matrix (v2):\n", conf_matrix_holdout_v2)
    print(f"    True Negatives (TN): {conf_matrix_holdout_v2[0,0]}")
    print(f"    False Positives (FP): {conf_matrix_holdout_v2[0,1]}")
    print(f"    False Negatives (FN): {conf_matrix_holdout_v2[1,0]}")
    print(f"    True Positives (TP): {conf_matrix_holdout_v2[1,1]}")

    # --- Step 6: Save the Trained Candidate Model ---
    print("\nStep 6: Saving the Trained Candidate Model (v2)...")
    # Save the model in Keras format (.keras)
    model_v2.save(candidate_model_path_keras)
    print(f"Candidate model (fraud_v2) saved to: {candidate_model_path_keras}")

    # Use a predictable artifact path for easy Seldon integration
    predictable_path = "fraud-v2-candidate"

    # Log model with predictable path
    mlflow.tensorflow.log_model(model_v2, artifact_path=predictable_path)

    # Get the run info to capture the S3 URI
    run = mlflow.active_run()
    model_uri = f"runs:/{run.info.run_id}/{predictable_path}"
    s3_uri = f"s3://{S3_BUCKET}/{run.info.experiment_id}/{run.info.run_id}/artifacts/{predictable_path}"

    # IMPORTANT: Print the exact Seldon storageUri to copy-paste
    print("\n" + "=" * 60)
    print("📋 COPY THIS FOR SELDON DEPLOYMENT:")
    print(f'storageUri: "{s3_uri}"')
    print("=" * 60 + "\n")

    print(f"Model logged to S3 at: {s3_uri}")
    print(f"Model URI for registry: {model_uri}")

    # Register the model in the Model Registry
    from mlflow import register_model

    result = register_model(model_uri, "fraud-detection-v2")
    print(f"Model registered as 'fraud-detection-v2' version {result.version}")

    # Save the S3 URI to a file for easy access
    with open("models/fraud_v2_s3_uri.txt", "w") as f:
        f.write(s3_uri)

    # Log deployment info as tags
    mlflow.set_tag("s3_uri", s3_uri)
    mlflow.set_tag("seldon_storage_uri", s3_uri)
    mlflow.set_tag("model_version", "v2")
    mlflow.set_tag("deployment_ready", "true")
    mlflow.set_tag("artifact_path", predictable_path)

print("\n--- Phase 3: Candidate Model Training (v2) - Completed ---")
print("The candidate model has been trained, evaluated, and saved.")
print("Proceed to Phase 4: Offline Validation & Deployment Decision Gate.")
