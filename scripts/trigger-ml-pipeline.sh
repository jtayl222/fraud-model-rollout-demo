#!/bin/bash
set -euo pipefail

# ML Pipeline Trigger Script for GitOps Integration
# This script triggers the ML training pipeline through Argo Workflows

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration
WORKFLOW_NAMESPACE="argowf"
WORKFLOW_TEMPLATE="fraud-model-training"
GIT_REPO="https://github.com/jtayl222/fraud-model-rollout-demo"
GIT_BRANCH="main"
MODEL_VERSION="v3"
MLFLOW_URI="http://mlflow.test:5000"
HARBOR_REGISTRY="harbor.test/mlops"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*"
    exit 1
}

info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

# Show usage
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Trigger ML training pipeline through Argo Workflows with GitOps integration.

OPTIONS:
    -v, --model-version VERSION    Model version to train (default: $MODEL_VERSION)
    -r, --git-repo URL            Git repository URL (default: $GIT_REPO)
    -b, --git-branch BRANCH       Git branch (default: $GIT_BRANCH)
    -n, --namespace NAMESPACE     Workflow namespace (default: $WORKFLOW_NAMESPACE)
    -w, --workflow TEMPLATE       Workflow template name (default: $WORKFLOW_TEMPLATE)
    --mlflow-uri URI             MLflow tracking URI (default: $MLFLOW_URI)
    --harbor-registry REGISTRY    Harbor registry (default: $HARBOR_REGISTRY)
    --wait                       Wait for workflow completion
    --follow                     Follow workflow logs
    --dry-run                    Show workflow without submitting
    -h, --help                   Show this help message

EXAMPLES:
    # Trigger with default parameters
    $0

    # Trigger specific model version
    $0 --model-version v4

    # Trigger and wait for completion
    $0 --model-version v3 --wait --follow

    # Dry run to see the workflow
    $0 --dry-run
EOF
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check argo CLI
    if ! command -v argo &> /dev/null; then
        error "argo CLI not found. Please install: https://github.com/argoproj/argo-workflows/releases"
    fi
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl not found. Please install kubectl."
    fi
    
    # Skip live cluster checks in dry run mode
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log "Dry run mode - skipping cluster connectivity checks"
        log "Prerequisites check completed ✓"
        return 0
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster."
    fi
    
    # Check workflow namespace
    if ! kubectl get namespace "$WORKFLOW_NAMESPACE" &> /dev/null; then
        error "Workflow namespace '$WORKFLOW_NAMESPACE' not found."
    fi
    
    # Check workflow template
    if ! kubectl get workflowtemplate "$WORKFLOW_TEMPLATE" -n "$WORKFLOW_NAMESPACE" &> /dev/null; then
        error "Workflow template '$WORKFLOW_TEMPLATE' not found in namespace '$WORKFLOW_NAMESPACE'."
    fi
    
    log "Prerequisites check completed ✓"
}

# Generate workflow from template
generate_workflow() {
    local workflow_name="fraud-training-$(date +%Y%m%d-%H%M%S)"
    
    cat <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: $workflow_name-
  namespace: $WORKFLOW_NAMESPACE
  labels:
    workflows.argoproj.io/workflow-template: $WORKFLOW_TEMPLATE
    project: fraud-detection
    triggered-by: script
    model-version: $MODEL_VERSION
  annotations:
    git-repo: $GIT_REPO
    git-branch: $GIT_BRANCH
    triggered-at: "$(date -Iseconds)"
spec:
  workflowTemplateRef:
    name: $WORKFLOW_TEMPLATE
  arguments:
    parameters:
    - name: model-version
      value: "$MODEL_VERSION"
    - name: git-repo
      value: "$GIT_REPO"
    - name: git-branch
      value: "$GIT_BRANCH"
    - name: mlflow-tracking-uri
      value: "$MLFLOW_URI"
    - name: harbor-registry
      value: "$HARBOR_REGISTRY"
  # TTL strategy to clean up completed workflows
  ttlStrategy:
    secondsAfterCompletion: 86400  # 24 hours
    secondsAfterSuccess: 43200     # 12 hours
    secondsAfterFailure: 172800    # 48 hours
EOF
}

# Submit workflow
submit_workflow() {
    local workflow_file="/tmp/fraud-training-workflow.yaml"
    
    log "Generating workflow specification..."
    generate_workflow > "$workflow_file"
    
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        info "DRY RUN - Workflow specification:"
        cat "$workflow_file"
        return 0
    fi
    
    log "Submitting workflow to Argo Workflows..."
    local workflow_name
    workflow_name=$(argo submit "$workflow_file" -n "$WORKFLOW_NAMESPACE" --output name)
    
    if [[ -z "$workflow_name" ]]; then
        error "Failed to submit workflow"
    fi
    
    # Clean up temporary file
    rm -f "$workflow_file"
    
    log "Workflow submitted: $workflow_name"
    echo "WORKFLOW_NAME=$workflow_name"
    
    # Show workflow info
    info "Workflow details:"
    argo get "$workflow_name" -n "$WORKFLOW_NAMESPACE"
    
    # Show access URLs
    echo
    info "Monitor workflow progress:"
    echo "  CLI: argo get $workflow_name -n $WORKFLOW_NAMESPACE"
    echo "  Logs: argo logs $workflow_name -n $WORKFLOW_NAMESPACE"
    echo "  UI: http://localhost:2746 (with port-forward)"
    
    return 0
}

# Wait for workflow completion
wait_for_completion() {
    local workflow_name="$1"
    
    log "Waiting for workflow completion..."
    argo wait "$workflow_name" -n "$WORKFLOW_NAMESPACE" --timeout 3600s
    
    local status
    status=$(argo get "$workflow_name" -n "$WORKFLOW_NAMESPACE" -o json | jq -r '.status.phase')
    
    if [[ "$status" == "Succeeded" ]]; then
        log "Workflow completed successfully ✓"
        
        # Show results
        info "Workflow results:"
        argo get "$workflow_name" -n "$WORKFLOW_NAMESPACE"
        
        # Show ArgoCD sync status
        info "Checking ArgoCD sync status..."
        if command -v argocd &> /dev/null; then
            argocd app list | grep fraud-detection || true
        fi
        
    elif [[ "$status" == "Failed" ]]; then
        error "Workflow failed ✗"
    else
        warn "Workflow ended with status: $status"
    fi
}

# Follow workflow logs
follow_logs() {
    local workflow_name="$1"
    
    log "Following workflow logs..."
    argo logs "$workflow_name" -n "$WORKFLOW_NAMESPACE" --follow
}

# Main execution
main() {
    log "Starting ML pipeline trigger..."
    
    check_prerequisites
    
    local workflow_name
    workflow_name=$(submit_workflow)
    
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        return 0
    fi
    
    # Extract workflow name from output
    workflow_name=$(echo "$workflow_name" | grep "WORKFLOW_NAME=" | cut -d'=' -f2)
    
    if [[ "${FOLLOW_LOGS:-false}" == "true" ]]; then
        follow_logs "$workflow_name" &
        LOG_PID=$!
    fi
    
    if [[ "${WAIT_COMPLETION:-false}" == "true" ]]; then
        wait_for_completion "$workflow_name"
        
        if [[ -n "${LOG_PID:-}" ]]; then
            kill $LOG_PID 2>/dev/null || true
        fi
    else
        info "Workflow submitted successfully!"
        info "Use --wait to wait for completion or --follow to stream logs"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--model-version)
            MODEL_VERSION="$2"
            shift 2
            ;;
        -r|--git-repo)
            GIT_REPO="$2"
            shift 2
            ;;
        -b|--git-branch)
            GIT_BRANCH="$2"
            shift 2
            ;;
        -n|--namespace)
            WORKFLOW_NAMESPACE="$2"
            shift 2
            ;;
        -w|--workflow)
            WORKFLOW_TEMPLATE="$2"
            shift 2
            ;;
        --mlflow-uri)
            MLFLOW_URI="$2"
            shift 2
            ;;
        --harbor-registry)
            HARBOR_REGISTRY="$2"
            shift 2
            ;;
        --wait)
            WAIT_COMPLETION=true
            shift
            ;;
        --follow)
            FOLLOW_LOGS=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Execute main function
main "$@"
