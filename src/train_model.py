#!/usr/bin/env python3
"""
Unified fraud detection model training script.
Can train baseline (v1) or candidate (v2) models based on parameters.

Usage:
    python src/train_model.py --model-type baseline --model-version v1
    python src/train_model.py --model-type candidate --model-version v2
    
Environment variables:
    MODEL_VERSION: v1, v2, v3, etc.
    MODEL_TYPE: baseline, candidate, retrain, etc.  
    EXPERIMENT_NAME: Custom experiment name
    MODEL_REGISTRY_NAME: Custom registry name
    ARTIFACT_PATH: Custom S3 artifact path
"""

import argparse
import os
import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
import mlflow
import mlflow.tensorflow


def parse_args():
    parser = argparse.ArgumentParser(description="Train fraud detection model")
    parser.add_argument(
        "--model-type",
        type=str,
        default="baseline",
        help="Model type: baseline, candidate, retrain, etc.",
    )
    parser.add_argument(
        "--model-version",
        type=str,
        default="v1",
        help="Model version: v1, v2, v3, etc.",
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="MLflow experiment name (auto-generated if not provided)",
    )
    parser.add_argument(
        "--registry-name",
        type=str,
        default=None,
        help="Model registry name (auto-generated if not provided)",
    )
    parser.add_argument(
        "--artifact-path",
        type=str,
        default=None,
        help="S3 artifact path (auto-generated if not provided)",
    )
    return parser.parse_args()


def get_training_data_path(model_type, model_version):
    """Get the appropriate training data file based on model type/version"""
    data_splits_dir = os.path.join(".", "data", "splits")

    if model_type == "baseline" or model_version == "v1":
        return os.path.join(data_splits_dir, "train_v1.csv")
    elif model_type == "candidate" or model_version == "v2":
        return os.path.join(data_splits_dir, "train_v2.csv")
    else:
        # Default fallback
        return os.path.join(data_splits_dir, "train_v2.csv")


def main():
    args = parse_args()

    # Override with environment variables if set
    MODEL_VERSION = os.getenv("MODEL_VERSION", args.model_version)
    MODEL_TYPE = os.getenv("MODEL_TYPE", args.model_type)
    EXPERIMENT_NAME = os.getenv(
        "EXPERIMENT_NAME", args.experiment_name or f"fraud-detection-{MODEL_TYPE}"
    )
    MODEL_REGISTRY_NAME = os.getenv(
        "MODEL_REGISTRY_NAME", args.registry_name or f"fraud-detection-{MODEL_VERSION}"
    )
    ARTIFACT_PATH = os.getenv(
        "ARTIFACT_PATH", args.artifact_path or f"fraud-{MODEL_VERSION}-{MODEL_TYPE}"
    )
    S3_BUCKET = os.getenv("MLFLOW_S3_BUCKET", "mlflow-artifacts")

    print(f"Training {MODEL_TYPE} model {MODEL_VERSION}")
    print(f"Experiment: {EXPERIMENT_NAME}")
    print(f"Registry: {MODEL_REGISTRY_NAME}")
    print(f"Artifact path: {ARTIFACT_PATH}")

    # Setup directories
    models_dir = os.path.join(".", "models")
    os.makedirs(models_dir, exist_ok=True)

    # Model save path
    model_save_path = os.path.join(models_dir, f"fraud_{MODEL_VERSION}.keras")

    # MLflow experiment setup
    try:
        experiment_id = mlflow.create_experiment(EXPERIMENT_NAME)
        print(f"Created new MLflow experiment: {EXPERIMENT_NAME} (ID: {experiment_id})")
    except Exception:
        experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
        experiment_id = experiment.experiment_id
        print(
            f"Using existing MLflow experiment: {EXPERIMENT_NAME} (ID: {experiment_id})"
        )

    mlflow.set_experiment(EXPERIMENT_NAME)

    # Load training data
    train_data_path = get_training_data_path(MODEL_TYPE, MODEL_VERSION)
    holdout_test_path = os.path.join(".", "data", "splits", "holdout_test.csv")

    if not os.path.exists(train_data_path) or not os.path.exists(holdout_test_path):
        print(f"Error: Required data files not found.")
        print(f"Training data: {train_data_path}")
        print(f"Holdout test: {holdout_test_path}")
        return 1

    df_train = pd.read_csv(train_data_path)
    df_holdout_test = pd.read_csv(holdout_test_path)

    print(f"Loaded training data: {len(df_train)} rows")
    print(f"Loaded holdout test: {len(df_holdout_test)} rows")

    # Prepare features and target
    features = [
        col
        for col in df_train.columns
        if col.startswith("V") or col in ["Time", "Amount"]
    ]
    target = "Class"

    X_train = df_train[features]
    y_train = df_train[target]
    X_holdout_test = df_holdout_test[features]
    y_holdout_test = df_holdout_test[target]

    # Preprocessing
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_holdout_test_scaled = scaler.transform(X_holdout_test)

    # Model architecture
    input_shape = X_train_scaled.shape[1]
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Dense(128, activation="relu", input_shape=(input_shape,)),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(64, activation="relu"),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dropout(0.1),
            tf.keras.layers.Dense(1, activation="sigmoid"),
        ]
    )

    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["precision", "recall", "AUC"],
    )

    # Class weights for imbalance
    neg, pos = np.bincount(y_train)
    total = neg + pos
    weight_for_0 = (1 / neg) * (total / 2.0)
    weight_for_1 = (1 / pos) * (total / 2.0)
    class_weight = {0: weight_for_0, 1: weight_for_1}

    # Callbacks
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, min_lr=0.00001
        ),
    ]

    # Start MLflow run
    with mlflow.start_run(run_name=f"fraud_{MODEL_VERSION}_{MODEL_TYPE}_training"):

        # Log hyperparameters
        mlflow.log_param("model_version", MODEL_VERSION)
        mlflow.log_param("model_type", MODEL_TYPE)
        mlflow.log_param("epochs", 50)
        mlflow.log_param("batch_size", 256)
        mlflow.log_param("input_features", input_shape)
        mlflow.log_param("architecture", "MLP_128_64_32")
        mlflow.log_param("optimizer", "Adam")
        mlflow.log_param("loss", "binary_crossentropy")
        mlflow.log_param("class_weight_ratio", f"{weight_for_0:.2f}:{weight_for_1:.2f}")
        mlflow.log_param("training_data", train_data_path)

        # Train the model
        print(f"\nTraining {MODEL_TYPE} model ({MODEL_VERSION})...")
        history = model.fit(
            X_train_scaled,
            y_train,
            epochs=50,
            batch_size=256,
            class_weight=class_weight,
            validation_split=0.2,
            callbacks=callbacks,
            verbose=1,
        )

        print(f"\n{MODEL_TYPE} Model ({MODEL_VERSION}) Training Complete.")

        # Evaluation
        print(
            f"\nEvaluating {MODEL_TYPE} Model ({MODEL_VERSION}) on holdout test set..."
        )
        y_pred_probs = model.predict(X_holdout_test_scaled).flatten()
        y_pred = (y_pred_probs > 0.5).astype(int)

        # Calculate metrics
        precision = precision_score(y_holdout_test, y_pred)
        recall = recall_score(y_holdout_test, y_pred)
        f1 = f1_score(y_holdout_test, y_pred)
        roc_auc = roc_auc_score(y_holdout_test, y_pred_probs)
        conf_matrix = confusion_matrix(y_holdout_test, y_pred)

        # Log metrics to MLflow
        mlflow.log_metric("precision", precision)
        mlflow.log_metric("recall", recall)
        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("roc_auc", roc_auc)
        mlflow.log_metric("true_negatives", int(conf_matrix[0, 0]))
        mlflow.log_metric("false_positives", int(conf_matrix[0, 1]))
        mlflow.log_metric("false_negatives", int(conf_matrix[1, 0]))
        mlflow.log_metric("true_positives", int(conf_matrix[1, 1]))

        print(f"  Holdout Precision ({MODEL_VERSION}): {precision:.4f}")
        print(f"  Holdout Recall ({MODEL_VERSION}):    {recall:.4f}")
        print(f"  Holdout F1-Score ({MODEL_VERSION}):  {f1:.4f}")
        print(f"  Holdout AUC-ROC ({MODEL_VERSION}):   {roc_auc:.4f}")

        # Save model locally
        model.save(model_save_path)
        print(f"Model saved locally to: {model_save_path}")

        # Log model to S3 via MLflow
        mlflow.tensorflow.log_model(model, artifact_path=ARTIFACT_PATH)

        # Get S3 URI for Seldon deployment
        run = mlflow.active_run()
        model_uri = f"runs:/{run.info.run_id}/{ARTIFACT_PATH}"
        s3_uri = f"s3://{S3_BUCKET}/{run.info.experiment_id}/{run.info.run_id}/artifacts/{ARTIFACT_PATH}"

        # IMPORTANT: Print deployment info
        print("\n" + "=" * 60)
        print("📋 COPY THIS FOR SELDON DEPLOYMENT:")
        print(f'storageUri: "{s3_uri}"')
        print("=" * 60 + "\n")

        # Register the model
        from mlflow import register_model

        result = register_model(model_uri, MODEL_REGISTRY_NAME)
        print(f"Model registered as '{MODEL_REGISTRY_NAME}' version {result.version}")

        # Save S3 URI to file for easy access
        output_file = f"models/{MODEL_TYPE}_{MODEL_VERSION}_s3_uri.txt"
        with open(output_file, "w") as f:
            f.write(s3_uri)
        print(f"S3 URI saved to: {output_file}")

        # Log deployment tags
        mlflow.set_tag("s3_uri", s3_uri)
        mlflow.set_tag("seldon_storage_uri", s3_uri)
        mlflow.set_tag("model_version", MODEL_VERSION)
        mlflow.set_tag("model_type", MODEL_TYPE)
        mlflow.set_tag("deployment_ready", "true")
        mlflow.set_tag("artifact_path", ARTIFACT_PATH)

    print(
        f"\n--- {MODEL_TYPE.capitalize()} Model ({MODEL_VERSION}) Training Complete ---"
    )
    return 0


if __name__ == "__main__":
    exit(main())
