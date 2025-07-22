#!/usr/bin/env python3
"""
Upload existing trained models to MLflow/S3 without retraining.
This avoids ARM/Intel compatibility issues while testing Phase 5 deployment.
"""

import os
import mlflow
import mlflow.tensorflow
import tensorflow as tf

def upload_model_to_mlflow(model_path, model_version, model_type):
    """Upload existing Keras model to MLflow with proper experiment tracking"""
    
    # Configuration
    EXPERIMENT_NAME = f"fraud-detection-{model_type}"
    MODEL_REGISTRY_NAME = f"fraud-detection-{model_version}"  
    ARTIFACT_PATH = f"fraud-{model_version}-{model_type}"
    S3_BUCKET = os.getenv("MLFLOW_S3_BUCKET", "mlflow-artifacts")
    
    print(f"Uploading {model_type} model {model_version}")
    print(f"Model file: {model_path}")
    print(f"Experiment: {EXPERIMENT_NAME}")
    print(f"Registry: {MODEL_REGISTRY_NAME}")
    print(f"Artifact path: {ARTIFACT_PATH}")
    
    # Create or get experiment
    try:
        experiment_id = mlflow.create_experiment(EXPERIMENT_NAME)
        print(f"Created new MLflow experiment: {EXPERIMENT_NAME} (ID: {experiment_id})")
    except Exception:
        experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
        experiment_id = experiment.experiment_id
        print(f"Using existing MLflow experiment: {EXPERIMENT_NAME} (ID: {experiment_id})")

    mlflow.set_experiment(EXPERIMENT_NAME)
    
    # Load the existing model
    if not os.path.exists(model_path):
        print(f"❌ Model file not found: {model_path}")
        return None
        
    model = tf.keras.models.load_model(model_path)
    print(f"✅ Loaded model from {model_path}")
    
    # Start MLflow run to upload model
    with mlflow.start_run(run_name=f"fraud_{model_version}_{model_type}_upload"):
        
        # Log metadata from status.md results
        mlflow.log_param("model_version", model_version)
        mlflow.log_param("model_type", model_type)
        mlflow.log_param("architecture", "MLP_128_64_32")
        mlflow.log_param("source", "existing_trained_model")
        mlflow.log_param("training_environment", "compatible_system")
        
        # Add metrics from status.md for reference
        if model_version == "v1":
            mlflow.log_metric("precision", 0.9845)
            mlflow.log_metric("recall", 0.7313) 
            mlflow.log_metric("f1_score", 0.8392)
            mlflow.log_metric("roc_auc", 0.9579)
        elif model_version == "v2":
            mlflow.log_metric("precision", 0.9729)
            mlflow.log_metric("recall", 1.0000)
            mlflow.log_metric("f1_score", 0.9863)
            mlflow.log_metric("roc_auc", 1.0000)
        
        # Upload model to S3
        mlflow.tensorflow.log_model(
            model,
            artifact_path=ARTIFACT_PATH
        )
        
        # Get S3 URI
        run = mlflow.active_run()
        model_uri = f"runs:/{run.info.run_id}/{ARTIFACT_PATH}"
        s3_uri = f"s3://{S3_BUCKET}/{run.info.experiment_id}/{run.info.run_id}/artifacts/{ARTIFACT_PATH}"
        
        print("\n" + "="*60)
        print("📋 COPY THIS FOR SELDON DEPLOYMENT:")
        print(f"storageUri: \"{s3_uri}\"")
        print("="*60 + "\n")
        
        # Register model
        from mlflow import register_model
        result = register_model(model_uri, MODEL_REGISTRY_NAME)
        print(f"Model registered as '{MODEL_REGISTRY_NAME}' version {result.version}")
        
        # Save S3 URI to file
        output_file = f"models/{model_type}_{model_version}_s3_uri.txt"
        with open(output_file, "w") as f:
            f.write(s3_uri)
        print(f"S3 URI saved to: {output_file}")
        
        # Add deployment tags
        mlflow.set_tag("s3_uri", s3_uri)
        mlflow.set_tag("seldon_storage_uri", s3_uri)
        mlflow.set_tag("model_version", model_version)
        mlflow.set_tag("model_type", model_type) 
        mlflow.set_tag("deployment_ready", "true")
        mlflow.set_tag("artifact_path", ARTIFACT_PATH)
        
        return s3_uri

def main():
    print("=== Uploading Existing Models to MLflow/S3 ===")
    print("This uploads pre-trained models without retraining to avoid ARM/Intel issues.\n")
    
    # Upload baseline model
    s3_uri_v1 = upload_model_to_mlflow("models/fraud_v1.keras", "v1", "baseline")
    
    print("\n" + "-"*60 + "\n")
    
    # Upload candidate model  
    s3_uri_v2 = upload_model_to_mlflow("models/fraud_v2.keras", "v2", "candidate")
    
    if s3_uri_v1 and s3_uri_v2:
        print(f"\n🎉 Both models uploaded successfully!")
        print(f"✅ V1 Baseline: {s3_uri_v1}")
        print(f"✅ V2 Candidate: {s3_uri_v2}")
        print(f"\n🚀 Next step: python scripts/update-model-config.py")
    else:
        print(f"\n❌ Model upload failed. Check MLflow connection.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())