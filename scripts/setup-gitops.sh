#!/bin/bash
set -euo pipefail

# GitOps Setup Script for Fraud Detection MLOps Platform
# This script sets up ArgoCD, Argo Workflows, and Flagger integration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
ARGOCD_NAMESPACE="argocd"
ARGOWF_NAMESPACE="argowf" 
FRAUD_NAMESPACE="fraud-detection"
MONITORING_NAMESPACE="monitoring"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl not found. Please install kubectl."
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
    fi
    
    # Check if ArgoCD is installed
    if ! kubectl get namespace $ARGOCD_NAMESPACE &> /dev/null; then
        warn "ArgoCD namespace not found. ArgoCD may not be installed."
        info "Please install ArgoCD first: https://argo-cd.readthedocs.io/en/stable/getting_started/"
        read -p "Do you want to continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check if Argo Workflows is installed
    if ! kubectl get namespace $ARGOWF_NAMESPACE &> /dev/null; then
        warn "Argo Workflows namespace not found. Argo Workflows may not be installed."
        info "Please install Argo Workflows first: https://argoproj.github.io/argo-workflows/installation/"
        read -p "Do you want to continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    log "Prerequisites check completed ✓"
}

# Setup namespaces
setup_namespaces() {
    log "Setting up namespaces..."
    
    local namespaces=("$FRAUD_NAMESPACE" "$MONITORING_NAMESPACE")
    
    for ns in "${namespaces[@]}"; do
        if kubectl get namespace "$ns" &> /dev/null; then
            info "Namespace $ns already exists"
        else
            kubectl create namespace "$ns"
            log "Created namespace: $ns"
        fi
        
        # Add labels
        kubectl label namespace "$ns" managed-by=argocd --overwrite
        kubectl label namespace "$ns" project=fraud-detection --overwrite
    done
}

# Setup RBAC for GitOps
setup_rbac() {
    log "Setting up RBAC for GitOps..."
    
    # Service account for Argo Workflows
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: argo-workflow
  namespace: $ARGOWF_NAMESPACE
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argo-workflow-gitops
rules:
# Git operations
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list"]
# MLflow and model management
- apiGroups: ["mlserver.seldon.io"]
  resources: ["*"]
  verbs: ["*"]
# ArgoCD application sync
- apiGroups: ["argoproj.io"]
  resources: ["applications"]
  verbs: ["get", "list", "patch", "update"]
# Container building (Kaniko)
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "create", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argo-workflow-gitops
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: argo-workflow-gitops
subjects:
- kind: ServiceAccount
  name: argo-workflow
  namespace: $ARGOWF_NAMESPACE
EOF
    
    log "RBAC setup completed ✓"
}

# Setup secrets
setup_secrets() {
    log "Setting up secrets..."
    
    # Check if secrets exist or need to be created
    local secrets=(
        "mlflow-s3-secret"
        "harbor-docker-config" 
        "git-credentials"
        "argocd-token"
        "slack-webhook-secret"
    )
    
    for secret in "${secrets[@]}"; do
        if kubectl get secret "$secret" -n "$ARGOWF_NAMESPACE" &> /dev/null; then
            info "Secret $secret already exists in $ARGOWF_NAMESPACE"
        else
            warn "Secret $secret does not exist in $ARGOWF_NAMESPACE"
            info "Please create this secret manually or using the provided templates"
        fi
    done
    
    # Create secret templates if they don't exist
    mkdir -p "$PROJECT_ROOT/secrets"
    
    if [[ ! -f "$PROJECT_ROOT/secrets/secret-templates.yaml" ]]; then
        cat > "$PROJECT_ROOT/secrets/secret-templates.yaml" <<EOF
# Secret templates - Replace with actual values before applying

# MLflow S3 credentials
apiVersion: v1
kind: Secret
metadata:
  name: mlflow-s3-secret
  namespace: $ARGOWF_NAMESPACE
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: "REPLACE_WITH_ACTUAL_ACCESS_KEY"
  AWS_SECRET_ACCESS_KEY: "REPLACE_WITH_ACTUAL_SECRET_KEY"

---
# Harbor Docker config
apiVersion: v1
kind: Secret
metadata:
  name: harbor-docker-config
  namespace: $ARGOWF_NAMESPACE
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: "REPLACE_WITH_BASE64_ENCODED_DOCKER_CONFIG"

---
# Git credentials for pushing updates
apiVersion: v1
kind: Secret
metadata:
  name: git-credentials
  namespace: $ARGOWF_NAMESPACE
type: Opaque
stringData:
  username: "REPLACE_WITH_GIT_USERNAME"
  password: "REPLACE_WITH_GIT_TOKEN"

---
# ArgoCD token for syncing applications
apiVersion: v1
kind: Secret
metadata:
  name: argocd-token
  namespace: $ARGOWF_NAMESPACE
type: Opaque
stringData:
  token: "REPLACE_WITH_ARGOCD_AUTH_TOKEN"

---
# Slack webhook for notifications
apiVersion: v1
kind: Secret
metadata:
  name: slack-webhook-secret
  namespace: $ARGOWF_NAMESPACE
type: Opaque
stringData:
  webhook-url: "REPLACE_WITH_SLACK_WEBHOOK_URL"
EOF
        info "Created secret templates at: $PROJECT_ROOT/secrets/secret-templates.yaml"
        info "Please edit this file with actual values and apply: kubectl apply -f secrets/secret-templates.yaml"
    fi
}

# Deploy ArgoCD applications
deploy_argocd_apps() {
    log "Deploying ArgoCD applications..."
    
    # Apply MLOps project
    kubectl apply -f "$PROJECT_ROOT/argocd/mlops-project.yaml"
    log "Applied MLOps project configuration"
    
    # Wait a bit for project to be created
    sleep 5
    
    # Apply fraud detection applications
    kubectl apply -f "$PROJECT_ROOT/argocd/fraud-detection-app.yaml"
    log "Applied fraud detection applications"
    
    # Apply rollback automation
    kubectl apply -f "$PROJECT_ROOT/argocd/rollback-automation.yaml"
    log "Applied rollback automation"
}

# Deploy Argo Workflows templates
deploy_argo_workflows() {
    log "Deploying Argo Workflows templates..."
    
    # Apply workflow templates
    kubectl apply -f "$PROJECT_ROOT/argo-workflows/"
    log "Applied Argo Workflows templates"
}

# Setup Flagger for progressive delivery
setup_flagger() {
    log "Setting up Flagger for progressive delivery..."
    
    # Check if Flagger is installed
    if ! kubectl get crd canaries.flagger.app &> /dev/null; then
        warn "Flagger CRDs not found. Installing Flagger..."
        
        # Install Flagger
        kubectl apply -k github.com/fluxcd/flagger//kustomize/kubernetes
        
        # Wait for Flagger to be ready
        kubectl -n flagger-system rollout status deployment/flagger
        log "Flagger installed successfully"
    else
        info "Flagger is already installed"
    fi
    
    # Apply Flagger canary configuration
    kubectl apply -f "$PROJECT_ROOT/k8s/base/flagger-canary.yaml"
    log "Applied Flagger canary configuration"
}

# Verify installation
verify_installation() {
    log "Verifying GitOps installation..."
    
    # Check ArgoCD applications
    info "Checking ArgoCD applications..."
    if kubectl get applications -n "$ARGOCD_NAMESPACE" | grep -q "fraud-detection"; then
        log "ArgoCD applications are deployed ✓"
    else
        warn "ArgoCD applications not found"
    fi
    
    # Check Argo Workflows templates
    info "Checking Argo Workflows templates..."
    if kubectl get workflowtemplates -n "$ARGOWF_NAMESPACE" | grep -q "fraud-model-training"; then
        log "Argo Workflows templates are deployed ✓"
    else
        warn "Argo Workflows templates not found"
    fi
    
    # Check Flagger canaries
    info "Checking Flagger canaries..."
    if kubectl get canaries -n "$FRAUD_NAMESPACE" &> /dev/null; then
        log "Flagger canaries are configured ✓"
    else
        warn "Flagger canaries not found"
    fi
    
    # Check rollback automation
    info "Checking rollback automation..."
    if kubectl get deployment argocd-rollback-automation -n "$ARGOCD_NAMESPACE" &> /dev/null; then
        log "Rollback automation is deployed ✓"
    else
        warn "Rollback automation not found"
    fi
}

# Print next steps
print_next_steps() {
    log "GitOps setup completed! 🎉"
    echo
    info "Next steps:"
    echo "1. Review and create the required secrets:"
    echo "   - Edit: $PROJECT_ROOT/secrets/secret-templates.yaml"
    echo "   - Apply: kubectl apply -f secrets/secret-templates.yaml"
    echo
    echo "2. Access ArgoCD UI:"
    echo "   - Port forward: kubectl port-forward svc/argocd-server -n argocd 8080:443"
    echo "   - Open: https://localhost:8080"
    echo
    echo "3. Access Argo Workflows UI:"
    echo "   - Port forward: kubectl port-forward svc/argo-server -n argowf 2746:2746"
    echo "   - Open: https://localhost:2746"
    echo
    echo "4. Trigger a workflow:"
    echo "   - argo submit argo-workflows/ml-training-pipeline.yaml -n argowf"
    echo
    echo "5. Monitor deployments:"
    echo "   - ArgoCD: kubectl get applications -n argocd"
    echo "   - Workflows: argo list -n argowf"
    echo "   - Canaries: kubectl get canaries -n fraud-detection"
    echo
    info "GitOps platform is ready for automated ML deployments! 🚀"
}

# Main execution
main() {
    log "Starting GitOps setup for Fraud Detection MLOps..."
    
    check_prerequisites
    setup_namespaces
    setup_rbac
    setup_secrets
    deploy_argocd_apps
    deploy_argo_workflows
    setup_flagger
    verify_installation
    print_next_steps
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-prerequisites)
            SKIP_PREREQUISITES=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --skip-prerequisites  Skip prerequisite checks"
            echo "  --dry-run            Show what would be done without executing"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Execute main function
if [[ "${DRY_RUN:-false}" == "true" ]]; then
    info "DRY RUN MODE - No changes will be made"
    exit 0
else
    main "$@"
fi
