#!/bin/bash

# Quick Health Check for Fraud Detection Application
# This script provides a fast overview of the deployment status
#
# Usage: ./scripts/health-check.sh [--namespace NAMESPACE]

set -e

# Default values
NAMESPACE=${NAMESPACE:-"fraud-detection"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--namespace NAMESPACE]"
            echo ""
            echo "Quick health check for fraud detection application"
            echo ""
            echo "Options:"
            echo "  --namespace NAMESPACE  Application namespace (default: fraud-detection)"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Fraud Detection Application Health Check${NC}"
echo -e "${BLUE}============================================${NC}"
echo "Namespace: $NAMESPACE"
echo ""

# 1. Infrastructure Prerequisites (quiet check)
echo -n "Infrastructure Prerequisites: "
if "$SCRIPT_DIR/check-prerequisites.sh" --namespace "$NAMESPACE" --quiet >/dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    INFRA_OK=true
else
    echo -e "${RED}✗ FAIL${NC}"
    INFRA_OK=false
fi

# 2. Runtime Components
echo -n "Runtime Components:           "
SCHEDULER_PODS=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-scheduler" --no-headers 2>/dev/null | wc -l)
ENVOY_PODS=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-envoy" --no-headers 2>/dev/null | wc -l)
RUNTIME_TOTAL=$((SCHEDULER_PODS + ENVOY_PODS))
if [ "$SCHEDULER_PODS" -gt 0 ] && [ "$ENVOY_PODS" -gt 0 ]; then
    echo -e "${GREEN}✓ READY ($RUNTIME_TOTAL pods: $SCHEDULER_PODS scheduler, $ENVOY_PODS envoy)${NC}"
    RUNTIME_OK=true
elif [ "$RUNTIME_TOTAL" -gt 0 ]; then
    echo -e "${YELLOW}⚠ PARTIAL ($RUNTIME_TOTAL pods: scheduler: $SCHEDULER_PODS, envoy: $ENVOY_PODS)${NC}"
    RUNTIME_OK=false
else
    echo -e "${RED}✗ MISSING${NC}"
    RUNTIME_OK=false
fi

# 3. Server Status
echo -n "MLServer Status:              "
SERVER_READY=$(kubectl get server mlserver -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
if [ "$SERVER_READY" = "True" ]; then
    echo -e "${GREEN}✓ READY${NC}"
    SERVER_OK=true
elif kubectl get server mlserver -n $NAMESPACE --no-headers 2>/dev/null | grep -q mlserver; then
    echo -e "${YELLOW}⚠ NOT READY${NC}"
    SERVER_OK=false
else
    echo -e "${RED}✗ NOT FOUND${NC}"
    SERVER_OK=false
fi

# 4. Models Status
echo -n "Models Status:                "
MODELS_READY=$(kubectl get models -n $NAMESPACE 2>/dev/null | grep fraud | grep -c "True" | head -1 || echo "0")
MODELS_TOTAL=$(kubectl get models -n $NAMESPACE 2>/dev/null | grep -c fraud | head -1 || echo "0")
if [ "$MODELS_READY" -gt 0 ] && [ "$MODELS_READY" -eq "$MODELS_TOTAL" ]; then
    echo -e "${GREEN}✓ ALL READY ($MODELS_READY/$MODELS_TOTAL)${NC}"
    MODELS_OK=true
elif [ "$MODELS_READY" -gt 0 ]; then
    echo -e "${YELLOW}⚠ PARTIAL ($MODELS_READY/$MODELS_TOTAL ready)${NC}"
    MODELS_OK=false
elif [ "$MODELS_TOTAL" -gt 0 ]; then
    echo -e "${RED}✗ NONE READY ($MODELS_TOTAL total)${NC}"
    MODELS_OK=false
else
    echo -e "${RED}✗ NOT FOUND${NC}"
    MODELS_OK=false
fi

# 5. A/B Test Status
echo -n "A/B Test Experiment:          "
if kubectl get experiment fraud-ab-test-experiment -n $NAMESPACE --no-headers 2>/dev/null | grep -q fraud-ab-test-experiment; then
    EXP_STATUS=$(kubectl get experiment fraud-ab-test-experiment -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
    if [ "$EXP_STATUS" = "True" ]; then
        echo -e "${GREEN}✓ READY${NC}"
        EXPERIMENT_OK=true
    else
        echo -e "${YELLOW}⚠ NOT READY${NC}"
        EXPERIMENT_OK=false
    fi
else
    echo -e "${RED}✗ NOT FOUND${NC}"
    EXPERIMENT_OK=false
fi

# Overall Status
echo ""
echo "============================================"
echo "Overall Status:"
if [ "$INFRA_OK" = true ] && [ "$RUNTIME_OK" = true ] && [ "$SERVER_OK" = true ] && [ "$MODELS_OK" = true ]; then
    echo -e "${GREEN}✅ HEALTHY - All components ready${NC}"
    OVERALL_STATUS=0
elif [ "$INFRA_OK" = false ]; then
    echo -e "${RED}❌ INFRASTRUCTURE ISSUE - Contact infrastructure team${NC}"
    echo ""
    echo "Run for details: ./scripts/check-prerequisites.sh --namespace $NAMESPACE"
    OVERALL_STATUS=1
elif [ "$RUNTIME_OK" = false ]; then
    echo -e "${YELLOW}⚠ RUNTIME ISSUE - Deploy runtime components${NC}"
    echo ""
    echo "Run: ./scripts/deploy-runtime-pattern3.sh"
    OVERALL_STATUS=1
else
    echo -e "${YELLOW}⚠ APPLICATION ISSUE - Check deployment${NC}"
    echo ""
    echo "Run for details: ./scripts/test-k8s-deployment.sh"
    OVERALL_STATUS=1
fi

echo ""
echo "For detailed diagnostics, run:"
echo "  ./scripts/test-k8s-deployment.sh"

exit $OVERALL_STATUS