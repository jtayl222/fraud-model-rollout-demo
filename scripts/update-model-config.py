#!/usr/bin/env python3
"""
Update model-config.yaml with S3 URIs from training runs.
This eliminates the need to manually copy-paste URIs.

Usage:
    # Read URIs from saved files
    python scripts/update-model-config.py
    
    # Specify URIs directly
    python scripts/update-model-config.py \
        --v1-uri "s3://mlflow-artifacts/40/abc123/artifacts/fraud-v1-baseline" \
        --v2-uri "s3://mlflow-artifacts/41/def456/artifacts/fraud-v2-candidate"
        
    # Update traffic split too
    python scripts/update-model-config.py --baseline-weight 70 --candidate-weight 30
"""

import argparse
import os
import yaml

def parse_args():
    parser = argparse.ArgumentParser(description='Update model configuration with S3 URIs')
    parser.add_argument('--v1-uri', type=str, help='S3 URI for fraud v1 baseline model')
    parser.add_argument('--v2-uri', type=str, help='S3 URI for fraud v2 candidate model')
    parser.add_argument('--baseline-weight', type=int, default=80, help='Traffic weight for baseline model')
    parser.add_argument('--candidate-weight', type=int, default=20, help='Traffic weight for candidate model')
    parser.add_argument('--config-file', type=str, default='k8s/base/model-config.yaml', 
                       help='Path to model config YAML file')
    return parser.parse_args()

def read_s3_uri_from_file(filepath):
    """Read S3 URI from saved file"""
    try:
        with open(filepath, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def update_model_config(config_file, v1_uri, v2_uri, baseline_weight, candidate_weight):
    """Update the model-config.yaml file with new values"""
    
    # Load existing config
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Update data section
    if 'data' not in config:
        config['data'] = {}
    
    if v1_uri:
        config['data']['fraud-v1-storage-uri'] = v1_uri
        print(f"✅ Updated V1 URI: {v1_uri}")
    
    if v2_uri:
        config['data']['fraud-v2-storage-uri'] = v2_uri
        print(f"✅ Updated V2 URI: {v2_uri}")
    
    # Update traffic split
    config['data']['traffic-split-baseline'] = str(baseline_weight)
    config['data']['traffic-split-candidate'] = str(candidate_weight)
    print(f"✅ Updated traffic split: {baseline_weight}/{candidate_weight}")
    
    # Write back to file
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Updated {config_file}")

def main():
    args = parse_args()
    
    # Try to read URIs from files if not provided
    v1_uri = args.v1_uri
    v2_uri = args.v2_uri
    
    if not v1_uri:
        v1_uri = read_s3_uri_from_file("models/baseline_v1_s3_uri.txt")
        if v1_uri:
            print(f"📁 Read V1 URI from file: {v1_uri}")
    
    if not v2_uri:
        v2_uri = read_s3_uri_from_file("models/candidate_v2_s3_uri.txt")
        if v2_uri:
            print(f"📁 Read V2 URI from file: {v2_uri}")
    
    # Check if we have at least one URI to update
    if not v1_uri and not v2_uri:
        print("❌ No S3 URIs found. Either:")
        print("   1. Run model training first: python src/train_model.py ...")
        print("   2. Specify URIs directly: --v1-uri s3://... --v2-uri s3://...")
        return 1
    
    # Validate config file exists
    if not os.path.exists(args.config_file):
        print(f"❌ Config file not found: {args.config_file}")
        return 1
    
    # Update the configuration
    update_model_config(args.config_file, v1_uri, v2_uri, args.baseline_weight, args.candidate_weight)
    
    print(f"\n🚀 Ready to deploy!")
    print(f"   kubectl apply -k k8s/base/")
    
    return 0

if __name__ == "__main__":
    exit(main())