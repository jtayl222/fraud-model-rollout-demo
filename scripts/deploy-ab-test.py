#!/usr/bin/env python3
"""
Helper script to extract S3 URIs from MLflow Model Registry 
and generate deployment-ready Seldon YAML files.

This simulates what CI/CD would do automatically.
"""

import os
import mlflow
from mlflow.tracking import MlflowClient
import yaml
import subprocess

def get_latest_model_s3_uri(model_name):
    """Get the S3 URI for the latest version of a registered model"""
    client = MlflowClient()
    try:
        # Get latest version
        latest_versions = client.get_latest_versions(model_name)
        if not latest_versions:
            print(f"No versions found for model '{model_name}'")
            return None
            
        latest_version = latest_versions[0]
        s3_uri = latest_version.source  # This should be the S3 path
        print(f"Model '{model_name}' version {latest_version.version}: {s3_uri}")
        return s3_uri
        
    except Exception as e:
        print(f"Error fetching model '{model_name}': {e}")
        return None

def substitute_yaml_template(template_path, output_path, s3_uri_v1, s3_uri_v2):
    """Replace placeholders in YAML template with actual S3 URIs"""
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Replace placeholders
    content = content.replace('"{{ S3_URI_V1 }}"', f'"{s3_uri_v1}"')
    content = content.replace('"{{ S3_URI_V2 }}"', f'"{s3_uri_v2}"')
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    print(f"Generated deployment YAML: {output_path}")

def main():
    print("=== MLflow to Seldon Deployment Generator ===")
    print("This script extracts S3 URIs from MLflow Model Registry")
    print("and generates deployment-ready Seldon YAML files.\n")
    
    # Get S3 URIs for both models
    s3_uri_v1 = get_latest_model_s3_uri("fraud-detection-v1")
    s3_uri_v2 = get_latest_model_s3_uri("fraud-detection-v2")
    
    if not s3_uri_v1 or not s3_uri_v2:
        print("Error: Could not retrieve S3 URIs for both models.")
        print("Make sure you've run baseline.py and candidate.py first.")
        return 1
    
    # Generate the deployment YAML
    template_path = "k8s/base/fraud-model-ab-test.yaml"
    output_path = "k8s/base/fraud-model-ab-test-deploy.yaml"
    
    substitute_yaml_template(template_path, output_path, s3_uri_v1, s3_uri_v2)
    
    print(f"\n=== Ready to Deploy ===")
    print(f"Run: kubectl apply -f {output_path}")
    print(f"To deploy the A/B test to your cluster.")
    
    return 0

if __name__ == "__main__":
    exit(main())