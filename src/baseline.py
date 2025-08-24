import datetime
import os

import mlflow
import mlflow.tensorflow
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
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# --- Configuration ---
project_dir = "."
data_splits_dir = os.path.join(project_dir, "data", "splits")
models_dir = os.path.join(project_dir, "models")
os.makedirs(models_dir, exist_ok=True)

# Changed model path to .keras format for saving
baseline_model_path_keras = os.path.join(models_dir, "fraud_v1.keras")

# --- Model Configuration Parameters ---
MODEL_VERSION = os.getenv("MODEL_VERSION", "v1")
MODEL_TYPE = os.getenv("MODEL_TYPE", "baseline")
EXPERIMENT_NAME = os.getenv("EXPERIMENT_NAME", f"fraud-detection-{MODEL_TYPE}")
MODEL_REGISTRY_NAME = os.getenv(
    "MODEL_REGISTRY_NAME", f"fraud-detection-{MODEL_VERSION}"
)
ARTIFACT_PATH = os.getenv("ARTIFACT_PATH", f"fraud-{MODEL_VERSION}-{MODEL_TYPE}")
S3_BUCKET = os.getenv("MLFLOW_S3_BUCKET", "mlflow-artifacts")

print(f"Training {MODEL_TYPE} model {MODEL_VERSION}")
print(f"Experiment: {EXPERIMENT_NAME}")
print(f"Registry: {MODEL_REGISTRY_NAME}")
print(f"Artifact path: {ARTIFACT_PATH}")

# --- MLflow Configuration ---
# Create or get the fraud detection experiment
try:
    experiment_id = mlflow.create_experiment(EXPERIMENT_NAME)
    print(f"Created new MLflow experiment: {EXPERIMENT_NAME} (ID: {experiment_id})")
except Exception:
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    experiment_id = experiment.experiment_id
    print(f"Using existing MLflow experiment: {EXPERIMENT_NAME} (ID: {experiment_id})")

mlflow.set_experiment(EXPERIMENT_NAME)

# --- Step 1: Load Data for Baseline Model (v1) ---
print("Step 1: Loading Data for Baseline Model (v1)...")
train_v1_path = os.path.join(data_splits_dir, "train_v1.csv")
holdout_test_path = os.path.join(data_splits_dir, "holdout_test.csv")

if not os.path.exists(train_v1_path) or not os.path.exists(holdout_test_path):
    print(
        f"Error: Required data files not found. Ensure Phase 1 script has been run and "
        f"files are at {data_splits_dir}"
    )
    exit()

df_train_v1 = pd.read_csv(train_v1_path)
df_holdout_test = pd.read_csv(holdout_test_path)

print(f"Loaded train_v1.csv: {len(df_train_v1)} rows")
print(f"Loaded holdout_test.csv: {len(df_holdout_test)} rows")

# Prepare features (X) and target (y)
# Assuming 'Class' is the target and 'Time', 'Amount', V1-V28 are features
# Drop 'datetime' if it was added in Phase 1 and is not a model feature
features = [
    col
    for col in df_train_v1.columns
    if col.startswith("V") or col in ["Time", "Amount"]
]
target = "Class"

X_train_v1 = df_train_v1[features]
y_train_v1 = df_train_v1[target]

X_holdout_test = df_holdout_test[features]
y_holdout_test = df_holdout_test[target]

print(f"Features used: {features}")

# --- Step 2: Preprocessing (Scaling) ---
print("\nStep 2: Preprocessing Data (Scaling)...")
scaler = StandardScaler()
X_train_v1_scaled = scaler.fit_transform(X_train_v1)
X_holdout_test_scaled = scaler.transform(X_holdout_test)  # Use same scaler for holdout

# Convert back to DataFrame for consistency if needed, though TF can take numpy arrays
X_train_v1_scaled_df = pd.DataFrame(X_train_v1_scaled, columns=features)
X_holdout_test_scaled_df = pd.DataFrame(X_holdout_test_scaled, columns=features)

print("Features scaled using StandardScaler.")

# --- Step 3: Define Model Architecture (TensorFlow MLP) ---
print("\nStep 3: Defining Model Architecture (TensorFlow MLP)...")

# Get number of input features dynamically
input_shape = X_train_v1_scaled.shape[1]

model_v1 = tf.keras.Sequential(
    [
        tf.keras.layers.Input(shape=(input_shape,)),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(
            1, activation="sigmoid"
        ),  # Sigmoid for binary classification
    ]
)

# Use Adam optimizer with a specific learning rate
optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)

# Compile the model
# Use BinaryCrossentropy for binary classification
# Use 'f1_score' as a custom metric, if not directly available from Keras, it can be computed manually
# For simplicity and Keras compatibility, we'll use 'Precision', 'Recall', 'AUC' as built-in metrics
model_v1.compile(
    optimizer=optimizer,
    loss="binary_crossentropy",
    metrics=[
        tf.keras.metrics.Precision(name="precision"),
        tf.keras.metrics.Recall(name="recall"),
        tf.keras.metrics.AUC(name="auc"),
    ],
)

model_v1.summary()

# --- Step 4: Training Setup ---
print("\nStep 4: Training Baseline Model (v1)...")

# Calculate class weights to handle imbalance
neg, pos = np.bincount(y_train_v1)
total = neg + pos
print(f"Total samples: {total}, Non-fraud: {neg}, Fraud: {pos}")

# Scaling by total/2 helps keep the magnitude of the loss comparable to the case when weights are all one.
# The smaller the number of samples in the minority class, the larger the weight will be.
weight_for_0 = (1 / neg) * (total / 2.0)
weight_for_1 = (1 / pos) * (total / 2.0)

class_weight = {0: weight_for_0, 1: weight_for_1}
print(f"Class weights: {class_weight}")

# Callbacks for early stopping and learning rate reduction
callbacks = [
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=5, restore_best_weights=True
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=3, min_lr=0.00001
    ),
]

# Start MLflow run for baseline training
with mlflow.start_run(run_name="fraud_v1_baseline_training"):

    # Log hyperparameters
    mlflow.log_param("model_version", MODEL_VERSION)
    mlflow.log_param("model_type", MODEL_TYPE)
    mlflow.log_param("epochs", 50)
    mlflow.log_param("batch_size", 256)
    mlflow.log_param("input_features", input_shape)
    mlflow.log_param("architecture", "MLP_128_64_32")
    mlflow.log_param("optimizer", "Adam")
    mlflow.log_param("loss", "binary_crossentropy")
    mlflow.log_param(
        "class_weight_ratio", f"{class_weight[0]:.2f}:{class_weight[1]:.2f}"
    )

    # Train the model
    # Use 20% of training data for validation during training
    history_v1 = model_v1.fit(
        X_train_v1_scaled,
        y_train_v1,
        epochs=50,  # Set a sufficiently high number of epochs, EarlyStopping will manage
        batch_size=256,
        class_weight=class_weight,
        validation_split=0.2,  # Use a split of the training data for validation
        callbacks=callbacks,
        verbose=1,
    )

    print("\nBaseline Model (v1) Training Complete.")

    # --- Step 5: Offline Evaluation & Drift Detection ---
    print("\nStep 5: Performing Offline Evaluation and Drift Detection...")

    # Evaluate on the holdout test set (Feb–Mar 2024) to detect drift
    print(
        "\nEvaluating Baseline Model (v1) on HOLD OUT TEST SET (Feb–Mar 2024 - with drift):"
    )
    y_pred_holdout_probs_v1 = model_v1.predict(X_holdout_test_scaled).flatten()
    y_pred_holdout_v1 = (y_pred_holdout_probs_v1 > 0.5).astype(
        int
    )  # Convert probabilities to binary predictions

    # Calculate metrics on holdout
    precision_holdout_v1 = precision_score(y_holdout_test, y_pred_holdout_v1)
    recall_holdout_v1 = recall_score(y_holdout_test, y_pred_holdout_v1)
    f1_holdout_v1 = f1_score(y_holdout_test, y_pred_holdout_v1)
    roc_auc_holdout_v1 = roc_auc_score(y_holdout_test, y_pred_holdout_probs_v1)
    conf_matrix_holdout_v1 = confusion_matrix(y_holdout_test, y_pred_holdout_v1)

    # Log metrics to MLflow
    mlflow.log_metric("precision", precision_holdout_v1)
    mlflow.log_metric("recall", recall_holdout_v1)
    mlflow.log_metric("f1_score", f1_holdout_v1)
    mlflow.log_metric("roc_auc", roc_auc_holdout_v1)
    mlflow.log_metric("true_negatives", int(conf_matrix_holdout_v1[0, 0]))
    mlflow.log_metric("false_positives", int(conf_matrix_holdout_v1[0, 1]))
    mlflow.log_metric("false_negatives", int(conf_matrix_holdout_v1[1, 0]))
    mlflow.log_metric("true_positives", int(conf_matrix_holdout_v1[1, 1]))

    print(f"  Holdout Precision (v1): {precision_holdout_v1:.4f}")
    print(f"  Holdout Recall (v1):    {recall_holdout_v1:.4f}")
    print(f"  Holdout F1-Score (v1):  {f1_holdout_v1:.4f}")
    print(f"  Holdout AUC-ROC (v1):   {roc_auc_holdout_v1:.4f}")
    print("\n  Holdout Confusion Matrix (v1):\n", conf_matrix_holdout_v1)
    print(f"    True Negatives (TN): {conf_matrix_holdout_v1[0,0]}")
    print(f"    False Positives (FP): {conf_matrix_holdout_v1[0,1]}")
    print(f"    False Negatives (FN): {conf_matrix_holdout_v1[1,0]}")
    print(f"    True Positives (TP): {conf_matrix_holdout_v1[1,1]}")

    # --- Step 6: Save the Trained Baseline Model ---
    print("\nStep 6: Saving the Trained Baseline Model (v1)...")
    # Save the model in Keras format (.keras)
    model_v1.save(baseline_model_path_keras)
    print(f"Baseline model (fraud_v1) saved to: {baseline_model_path_keras}")

    # Log model with predictable path
    mlflow.tensorflow.log_model(model_v1, artifact_path=ARTIFACT_PATH)

    # Get the run info to capture the S3 URI
    run = mlflow.active_run()
    model_uri = f"runs:/{run.info.run_id}/{ARTIFACT_PATH}"
    s3_uri = f"s3://{S3_BUCKET}/{run.info.experiment_id}/{run.info.run_id}/artifacts/{ARTIFACT_PATH}"

    # IMPORTANT: Print the exact Seldon storageUri to copy-paste
    print("\n" + "=" * 60)
    print("📋 COPY THIS FOR SELDON DEPLOYMENT:")
    print(f'storageUri: "{s3_uri}"')
    print("=" * 60 + "\n")

    print(f"Model logged to S3 at: {s3_uri}")
    print(f"Model URI for registry: {model_uri}")

    # Register the model in the Model Registry
    from mlflow import register_model

    result = register_model(model_uri, MODEL_REGISTRY_NAME)
    print(f"Model registered as '{MODEL_REGISTRY_NAME}' version {result.version}")

    # Save the S3 URI to a file for easy access
    output_file = f"models/{MODEL_TYPE}_{MODEL_VERSION}_s3_uri.txt"
    with open(output_file, "w") as f:
        f.write(s3_uri)

    # Log deployment info as tags
    mlflow.set_tag("s3_uri", s3_uri)
    mlflow.set_tag("seldon_storage_uri", s3_uri)
    mlflow.set_tag("model_version", MODEL_VERSION)
    mlflow.set_tag("model_type", MODEL_TYPE)
    mlflow.set_tag("deployment_ready", "true")
    mlflow.set_tag("artifact_path", ARTIFACT_PATH)

# Expected drift performance (as per Phase 2 doc)
print("\n--- Expected Drift Performance (from Phase 2 Documentation) ---")
print("  Expected Recall on Holdout (v1): ~0.75 (due to new fraud patterns)")
print("  Expected Precision on Holdout (v1): ~0.90 (should remain stable)")
print("  Expected F1 on Holdout (v1): ~0.82")
print(
    "\nCompare the actual holdout recall with the expected value (~0.75). "
    "A drop in recall indicates concept drift, justifying retraining."
)

print("\n--- Phase 2: Baseline Model Training (v1) - Completed ---")
print("The baseline model has been trained, evaluated, and saved.")
print("Proceed to Phase 3: Candidate Model Training (v2).")
