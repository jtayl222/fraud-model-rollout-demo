#!/usr/bin/env python3
"""
Update model configuration for GitOps deployments.

This script updates the model configuration with new S3 URIs and traffic splits
for safe deployment of new fraud detection models.
"""

import argparse
import yaml
import sys
from pathlib import Path


def update_model_config(config_file, v1_uri=None, v2_uri=None, 
                       baseline_weight=80, candidate_weight=20):
    """Update model configuration file with new URIs and traffic splits."""
    
    if not config_file.exists():
        print(f"❌ Configuration file not found: {config_file}")
        return False
        
    # Load existing config
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Update model URIs if provided
    if v1_uri:
        config['data']['fraud-v1-storage-uri'] = v1_uri
        print(f"✅ Updated V1 URI: {v1_uri}")
        
    if v2_uri:
        config['data']['fraud-v2-storage-uri'] = v2_uri
        print(f"✅ Updated V2 URI: {v2_uri}")
    
    # Update traffic splits
    config['data']['traffic-split-baseline'] = str(baseline_weight)
    config['data']['traffic-split-candidate'] = str(candidate_weight)
    print(f"✅ Updated traffic split: {baseline_weight}% baseline, {candidate_weight}% candidate")
    
    # Validate traffic split adds to 100
    if baseline_weight + candidate_weight != 100:
        print(f"⚠️  Warning: Traffic splits don't add to 100% ({baseline_weight + candidate_weight}%)")
    
    # Write updated config
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Configuration updated: {config_file}")
    return True


def validate_s3_uri(uri):
    """Basic validation for S3 URI format."""
    if not uri.startswith('s3://'):
        return False, "URI must start with 's3://'"
    
    if len(uri.split('/')) < 4:
        return False, "URI must include bucket and path: s3://bucket/path/"
        
    return True, "Valid S3 URI format"


def main():
    parser = argparse.ArgumentParser(
        description="Update model configuration for GitOps deployments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update both model URIs
  %(prog)s --v1-uri s3://mlflow/exp1/run1/artifacts --v2-uri s3://mlflow/exp2/run2/artifacts
  
  # Update traffic split for canary deployment
  %(prog)s --baseline-weight 90 --candidate-weight 10
  
  # Update specific config file
  %(prog)s --config k8s/overlays/staging/model-config.yaml --v2-uri s3://staging-mlflow/artifacts
        """
    )
    
    parser.add_argument('--config', '-c', 
                       type=Path,
                       default=Path('k8s/base/model-config.yaml'),
                       help='Path to model configuration file (default: k8s/base/model-config.yaml)')
    
    parser.add_argument('--v1-uri',
                       help='S3 URI for baseline model (fraud-v1)')
    
    parser.add_argument('--v2-uri', 
                       help='S3 URI for candidate model (fraud-v2)')
    
    parser.add_argument('--baseline-weight',
                       type=int,
                       default=80,
                       help='Traffic percentage for baseline model (default: 80)')
    
    parser.add_argument('--candidate-weight',
                       type=int, 
                       default=20,
                       help='Traffic percentage for candidate model (default: 20)')
    
    parser.add_argument('--dry-run',
                       action='store_true',
                       help='Show what would be changed without modifying files')
    
    args = parser.parse_args()
    
    # Validate S3 URIs if provided
    for uri_name, uri in [('v1-uri', args.v1_uri), ('v2-uri', args.v2_uri)]:
        if uri:
            valid, msg = validate_s3_uri(uri)
            if not valid:
                print(f"❌ Invalid {uri_name}: {msg}")
                return 1
    
    # Validate traffic splits
    if args.baseline_weight + args.candidate_weight != 100:
        print(f"❌ Traffic weights must sum to 100% (got {args.baseline_weight + args.candidate_weight}%)")
        return 1
    
    if args.baseline_weight < 0 or args.candidate_weight < 0:
        print("❌ Traffic weights must be non-negative")
        return 1
    
    if args.dry_run:
        print("🔍 DRY RUN - Changes that would be made:")
        print(f"  Config file: {args.config}")
        if args.v1_uri:
            print(f"  V1 URI: {args.v1_uri}")
        if args.v2_uri:
            print(f"  V2 URI: {args.v2_uri}")
        print(f"  Traffic split: {args.baseline_weight}%/{args.candidate_weight}%")
        return 0
    
    # Update configuration
    success = update_model_config(
        args.config,
        args.v1_uri,
        args.v2_uri, 
        args.baseline_weight,
        args.candidate_weight
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
