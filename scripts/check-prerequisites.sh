#!/bin/bash

# Check Infrastructure Prerequisites for Fraud Detection Application
# This script verifies that the required infrastructure components are properly configured
#
# Usage: ./scripts/check-prerequisites.sh [--namespace NAMESPACE] [--quiet]
#   --namespace: Specify application namespace (default: fraud-detection)
#   --quiet: Only output errors and final result (for use in other scripts)
#
# Exit codes:
#   0: All prerequisites met
#   1: Prerequisites failed

set -e

# Default values
NAMESPACE="fraud-detection"
QUIET=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --quiet)
            QUIET=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--namespace NAMESPACE] [--quiet]"
            echo ""
            echo "Check infrastructure prerequisites for fraud detection application"
            echo ""
            echo "Options:"
            echo "  --namespace NAMESPACE  Application namespace (default: fraud-detection)"
            echo "  --quiet               Only output errors and final result"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Color codes for output (disabled in quiet mode)
if [ "$QUIET" = false ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Output functions
log_info() {
    if [ "$QUIET" = false ]; then
        echo -e "$1"
    fi
}

log_error() {
    echo -e "${RED}✗ $1${NC}" >&2
}

log_success() {
    if [ "$QUIET" = false ]; then
        echo -e "${GREEN}✓ $1${NC}"
    fi
}

log_warning() {
    if [ "$QUIET" = false ]; then
        echo -e "${YELLOW}⚠ $1${NC}"
    fi
}

# Track overall status
PREREQUISITES_FAILED=false

# Header
log_info "${BLUE}============================================${NC}"
log_info "${BLUE}Infrastructure Prerequisites Check${NC}"
log_info "${BLUE}============================================${NC}"
log_info "Checking prerequisites for namespace: $NAMESPACE"
log_info ""

# 1. Check Kubernetes connection
log_info "1. Checking Kubernetes Connection"
log_info "--------------------------------"
if kubectl cluster-info &>/dev/null; then
    log_success "Connected to Kubernetes cluster"
    if [ "$QUIET" = false ]; then
        kubectl cluster-info | head -n 1
    fi
else
    log_error "PREREQUISITE FAILED: Cannot connect to Kubernetes cluster"
    log_error "Please ensure KUBECONFIG is set correctly"
    PREREQUISITES_FAILED=true
fi

# 2. Check seldon-system namespace
log_info ""
log_info "2. Checking seldon-system Namespace"
log_info "-----------------------------------"
if kubectl get namespace seldon-system &>/dev/null; then
    log_success "seldon-system namespace exists"
else
    log_error "PREREQUISITE FAILED: seldon-system namespace not found"
    log_error ""
    log_error "The infrastructure team must create and configure the seldon-system namespace."
    log_error "Contact your infrastructure team to set up Seldon Core v2."
    PREREQUISITES_FAILED=true
fi

# 3. Check Seldon Core v2 CRDs
log_info ""
log_info "3. Checking Seldon Core v2 CRDs"
log_info "-------------------------------"
REQUIRED_CRDS=("models.mlops.seldon.io" "servers.mlops.seldon.io" "experiments.mlops.seldon.io" "serverconfigs.mlops.seldon.io")
CRD_FAILURES=0

for crd in "${REQUIRED_CRDS[@]}"; do
    if kubectl get crd "$crd" &>/dev/null; then
        log_success "CRD $crd found"
    else
        log_error "CRD $crd not found"
        CRD_FAILURES=$((CRD_FAILURES + 1))
    fi
done

if [ $CRD_FAILURES -gt 0 ]; then
    log_error "PREREQUISITE FAILED: $CRD_FAILURES Seldon Core v2 CRDs missing"
    log_error ""
    log_error "The infrastructure team must install Seldon Core v2."
    log_error "Required CRDs: ${REQUIRED_CRDS[*]}"
    PREREQUISITES_FAILED=true
else
    log_success "All required Seldon Core v2 CRDs found"
fi

# 4. Check Seldon controller
log_info ""
log_info "4. Checking Seldon Controller"
log_info "-----------------------------"
CONTROLLER_RUNNING=$(kubectl get pods -n seldon-system -l control-plane=seldon-controller-manager --no-headers 2>/dev/null | grep -c Running || echo "0")
if [ "$CONTROLLER_RUNNING" -eq 0 ]; then
    # Try alternative label - ensure we get a single number
    CONTROLLER_RUNNING=$(kubectl get pods -n seldon-system --no-headers 2>/dev/null | grep -E "(seldon.*controller|controller.*manager)" | grep -c Running 2>/dev/null || echo "0")
    CONTROLLER_RUNNING=$(echo "$CONTROLLER_RUNNING" | head -1 | tr -d '\n')
fi

if [ "${CONTROLLER_RUNNING:-0}" -eq 0 ] 2>/dev/null; then
    log_error "PREREQUISITE FAILED: Seldon controller not running in seldon-system"
    log_error ""
    log_error "The infrastructure team must ensure the Seldon controller is running."
    log_error "Check with: kubectl get pods -n seldon-system"
    PREREQUISITES_FAILED=true
else
    log_success "Seldon controller is running ($CONTROLLER_RUNNING pods)"
fi

# 5. Check required ServerConfig
log_info ""
log_info "5. Checking Required ServerConfig"
log_info "---------------------------------"
if kubectl get serverconfig mlserver -n seldon-system &>/dev/null; then
    log_success "Required ServerConfig 'mlserver' found in seldon-system"
else
    log_error "PREREQUISITE FAILED: ServerConfig 'mlserver' not found in seldon-system"
    log_error ""
    log_error "The infrastructure team must create the ServerConfig in seldon-system namespace."
    log_error "Required: ServerConfig named 'mlserver' with MLServer runtime configuration"
    log_error ""
    log_error "Infrastructure team should apply the ServerConfig from:"
    log_error "  k8s/base/server-config-centralized.yaml"
    log_error ""
    log_error "This project cannot proceed without the infrastructure prerequisites."
    PREREQUISITES_FAILED=true
fi

# 6. Check operator configuration
log_info ""
log_info "6. Checking Operator Configuration"
log_info "----------------------------------"
OPERATOR_POD=$(kubectl get pods -n seldon-system -l control-plane=seldon-controller-manager -o name 2>/dev/null | head -1)
if [ -z "$OPERATOR_POD" ]; then
    OPERATOR_POD=$(kubectl get pods -n seldon-system -o name 2>/dev/null | grep -E "(seldon.*controller|controller.*manager)" | head -1)
fi

if [ -n "$OPERATOR_POD" ]; then
    # Try to get watch namespace configuration
    WATCH_NS=$(kubectl get deployment -n seldon-system -o jsonpath='{.items[*].spec.template.spec.containers[*].env[?(@.name=="WATCH_NAMESPACES")].value}' 2>/dev/null | tr ' ' '\n' | grep -v '^$' | head -1)
    
    if [ -n "$WATCH_NS" ]; then
        if echo "$WATCH_NS" | grep -q "$NAMESPACE"; then
            log_success "Operator is configured to watch $NAMESPACE namespace"
        else
            log_error "PREREQUISITE FAILED: Operator not configured to watch $NAMESPACE namespace"
            log_error ""
            log_error "Current watched namespaces: $WATCH_NS"
            log_error ""
            log_error "The infrastructure team must configure the operator to watch '$NAMESPACE' namespace."
            log_error "Update the WATCH_NAMESPACES environment variable in the operator deployment."
            PREREQUISITES_FAILED=true
        fi
    else
        log_warning "Could not verify operator namespace configuration"
        log_info "Assuming cluster-wide mode or proper configuration..."
    fi
else
    log_warning "Could not find operator pod for configuration check"
fi

# 7. Check application namespace
log_info ""
log_info "7. Checking Application Namespace"
log_info "---------------------------------"
if kubectl get namespace "$NAMESPACE" &>/dev/null; then
    log_success "Application namespace '$NAMESPACE' exists"
else
    log_warning "Application namespace '$NAMESPACE' not found"
    log_info "This will be created during deployment if needed"
fi

# 8. Final result
log_info ""
log_info "============================================"
if [ "$PREREQUISITES_FAILED" = false ]; then
    log_info "${GREEN}✅ All infrastructure prerequisites met${NC}"
    log_info "The fraud detection application can be deployed."
    exit 0
else
    log_info "${RED}❌ Infrastructure prerequisites failed${NC}"
    log_info ""
    log_error "Contact your infrastructure team to resolve the failed prerequisites above."
    log_error "See k8s/base/INFRASTRUCTURE-REQUIREMENTS.md for detailed requirements."
    exit 1
fi