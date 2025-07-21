import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
import os
import datetime

# --- Configuration ---
project_dir = '.'
data_splits_dir = os.path.join(project_dir, 'data', 'splits')
models_dir = os.path.join(project_dir, 'models')
os.makedirs(models_dir, exist_ok=True)

# Changed model path to .keras format for saving
baseline_model_path_keras = os.path.join(models_dir, 'fraud_v1.keras')

# --- Step 1: Load Data for Baseline Model (v1) ---
print("Step 1: Loading Data for Baseline Model (v1)...")
train_v1_path = os.path.join(data_splits_dir, 'train_v1.csv')
holdout_test_path = os.path.join(data_splits_dir, 'holdout_test.csv')

if not os.path.exists(train_v1_path) or not os.path.exists(holdout_test_path):
    print(f"Error: Required data files not found. Ensure Phase 1 script has been run and "
          f"files are at {data_splits_dir}")
    exit()

df_train_v1 = pd.read_csv(train_v1_path)
df_holdout_test = pd.read_csv(holdout_test_path)

print(f"Loaded train_v1.csv: {len(df_train_v1)} rows")
print(f"Loaded holdout_test.csv: {len(df_holdout_test)} rows")

# Prepare features (X) and target (y)
# Assuming 'Class' is the target and 'Time', 'Amount', V1-V28 are features
# Drop 'datetime' if it was added in Phase 1 and is not a model feature
features = [col for col in df_train_v1.columns if col.startswith('V') or col in ['Time', 'Amount']]
target = 'Class'

X_train_v1 = df_train_v1[features]
y_train_v1 = df_train_v1[target]

X_holdout_test = df_holdout_test[features]
y_holdout_test = df_holdout_test[target]

print(f"Features used: {features}")

# --- Step 2: Preprocessing (Scaling) ---
print("\nStep 2: Preprocessing Data (Scaling)...")
scaler = StandardScaler()
X_train_v1_scaled = scaler.fit_transform(X_train_v1)
X_holdout_test_scaled = scaler.transform(X_holdout_test) # Use same scaler for holdout

# Convert back to DataFrame for consistency if needed, though TF can take numpy arrays
X_train_v1_scaled_df = pd.DataFrame(X_train_v1_scaled, columns=features)
X_holdout_test_scaled_df = pd.DataFrame(X_holdout_test_scaled, columns=features)

print("Features scaled using StandardScaler.")

# --- Step 3: Define Model Architecture (TensorFlow MLP) ---
print("\nStep 3: Defining Model Architecture (TensorFlow MLP)...")

# Get number of input features dynamically
input_shape = X_train_v1_scaled.shape[1]

model_v1 = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(input_shape,)),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dropout(0.3),
    tf.keras.layers.Dense(64, activation='relu'),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(32, activation='relu'),
    tf.keras.layers.Dense(1, activation='sigmoid') # Sigmoid for binary classification
])

# Use Adam optimizer with a specific learning rate
optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)

# Compile the model
# Use BinaryCrossentropy for binary classification
# Use 'f1_score' as a custom metric, if not directly available from Keras, it can be computed manually
# For simplicity and Keras compatibility, we'll use 'Precision', 'Recall', 'AUC' as built-in metrics
model_v1.compile(optimizer=optimizer,
                  loss='binary_crossentropy',
                  metrics=[
                      tf.keras.metrics.Precision(name='precision'),
                      tf.keras.metrics.Recall(name='recall'),
                      tf.keras.metrics.AUC(name='auc')
                  ])

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
    tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
    tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, min_lr=0.00001)
]

# Train the model
# Use 20% of training data for validation during training
history_v1 = model_v1.fit(X_train_v1_scaled, y_train_v1,
                          epochs=50, # Set a sufficiently high number of epochs, EarlyStopping will manage
                          batch_size=256,
                          class_weight=class_weight,
                          validation_split=0.2, # Use a split of the training data for validation
                          callbacks=callbacks,
                          verbose=1)

print("\nBaseline Model (v1) Training Complete.")

# --- Step 5: Offline Evaluation & Drift Detection ---
print("\nStep 5: Performing Offline Evaluation and Drift Detection...")

# Evaluate on the training set's validation split (if validation_split was used)
# This is usually done to check for overfitting
# train_eval_results = model_v1.evaluate(X_train_v1_scaled, y_train_v1, verbose=0)
# print(f"Training set evaluation (for reference): Loss={train_eval_results[0]:.4f}, Precision={train_eval_results[1]:.4f}, Recall={train_eval_results[2]:.4f}, AUC={train_eval_results[3]:.4f}")


# Evaluate on the holdout test set (Feb–Mar 2024) to detect drift
print("\nEvaluating Baseline Model (v1) on HOLD OUT TEST SET (Feb–Mar 2024 - with drift):")
y_pred_holdout_probs_v1 = model_v1.predict(X_holdout_test_scaled).flatten()
y_pred_holdout_v1 = (y_pred_holdout_probs_v1 > 0.5).astype(int) # Convert probabilities to binary predictions

# Calculate metrics on holdout
precision_holdout_v1 = precision_score(y_holdout_test, y_pred_holdout_v1)
recall_holdout_v1 = recall_score(y_holdout_test, y_pred_holdout_v1)
f1_holdout_v1 = f1_score(y_holdout_test, y_pred_holdout_v1)
roc_auc_holdout_v1 = roc_auc_score(y_holdout_test, y_pred_holdout_probs_v1)
conf_matrix_holdout_v1 = confusion_matrix(y_holdout_test, y_pred_holdout_v1)

print(f"  Holdout Precision (v1): {precision_holdout_v1:.4f}")
print(f"  Holdout Recall (v1):    {recall_holdout_v1:.4f}")
print(f"  Holdout F1-Score (v1):  {f1_holdout_v1:.4f}")
print(f"  Holdout AUC-ROC (v1):   {roc_auc_holdout_v1:.4f}")
print("\n  Holdout Confusion Matrix (v1):\n", conf_matrix_holdout_v1)
print(f"    True Negatives (TN): {conf_matrix_holdout_v1[0,0]}")
print(f"    False Positives (FP): {conf_matrix_holdout_v1[0,1]}")
print(f"    False Negatives (FN): {conf_matrix_holdout_v1[1,0]}")
print(f"    True Positives (TP): {conf_matrix_holdout_v1[1,1]}")


# Expected drift performance (as per Phase 2 doc)
print("\n--- Expected Drift Performance (from Phase 2 Documentation) ---")
print("  Expected Recall on Holdout (v1): ~0.75 (due to new fraud patterns)")
print("  Expected Precision on Holdout (v1): ~0.90 (should remain stable)")
print("  Expected F1 on Holdout (v1): ~0.82")
print("\nCompare the actual holdout recall with the expected value (~0.75). "
      "A drop in recall indicates concept drift, justifying retraining.")


# --- Step 6: Save the Trained Baseline Model ---
print("\nStep 6: Saving the Trained Baseline Model (v1)...")
# Save the model in Keras format (.keras)
model_v1.save(baseline_model_path_keras)
print(f"Baseline model (fraud_v1) saved to: {baseline_model_path_keras}")

print("\n--- Phase 2: Baseline Model Training (v1) - Completed ---")
print("The baseline model has been trained, evaluated, and saved.")
print("Proceed to Phase 3: Candidate Model Training (v2).")