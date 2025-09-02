"""
MLflow utility functions for model management
"""
import mlflow
import mlflow.tensorflow
import os
from typing import Optional, Dict, Any


def get_model_info(model_name: str) -> Optional[Any]:
    """
    Get model information from MLflow registry
    
    Args:
        model_name: Name of the registered model
        
    Returns:
        Model metadata or None if not found
    """
    try:
        model = mlflow.get_registered_model(model_name)
        return model
    except Exception as e:
        print(f"Error getting model {model_name}: {e}")
        return None


def download_model_artifacts(model_uri: str, dst_path: Optional[str] = None) -> str:
    """
    Download model artifacts from MLflow
    
    Args:
        model_uri: MLflow model URI (e.g., "models:/model_name/version")
        dst_path: Local destination path
        
    Returns:
        Path to downloaded artifacts
    """
    return mlflow.artifacts.download_artifacts(model_uri, dst_path)


def load_model_from_mlflow(model_uri: str):
    """
    Load TensorFlow model from MLflow
    
    Args:
        model_uri: MLflow model URI
        
    Returns:
        Loaded TensorFlow model
    """
    return mlflow.tensorflow.load_model(model_uri)
