#!/bin/bash
# Workaround for Seldon Core v2.9.1 bug: Cross-namespace ServerConfig references don't work
# This script copies ServerConfig from seldon-system to the application namespace
# Bug: The operator can't parse "namespace/name" format in Server.spec.serverConfig

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get namespace from argument or current context
NAMESPACE=${1:-fraud-detection}

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Seldon Core v2.9.1 ServerConfig Workaround${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}Known Bug: Seldon v2.9.1 cannot parse cross-namespace ServerConfig references${NC}"
echo "Copying ServerConfig from seldon-system to $NAMESPACE..."
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check connection to cluster
if ! kubectl cluster-info &>/dev/null; then
    echo -e "${RED}✗ Cannot connect to Kubernetes cluster${NC}"
    exit 1
fi

# Check if seldon-system namespace exists
if ! kubectl get namespace seldon-system &>/dev/null; then
    echo -e "${RED}✗ seldon-system namespace not found${NC}"
    echo "Please ensure Seldon Core is installed"
    exit 1
fi

# Create target namespace if it doesn't exist
if ! kubectl get namespace $NAMESPACE &>/dev/null; then
    echo "Creating namespace $NAMESPACE..."
    kubectl create namespace $NAMESPACE
    echo -e "${GREEN}✓ Namespace created${NC}"
fi

# List of ServerConfigs to copy (common ones used in Seldon)
SERVERCONFIGS="mlserver-config mlserver triton"

COPIED=0
for CONFIG in $SERVERCONFIGS; do
    # Check if ServerConfig exists in seldon-system
    if kubectl get serverconfig $CONFIG -n seldon-system &>/dev/null; then
        echo -n "Copying $CONFIG... "
        
        # Check if it already exists in target namespace
        if kubectl get serverconfig $CONFIG -n $NAMESPACE &>/dev/null; then
            echo -e "${YELLOW}already exists, updating${NC}"
        fi
        
        # Copy the ServerConfig to target namespace
        kubectl get serverconfig $CONFIG -n seldon-system -o yaml | \
            sed "s/namespace: seldon-system/namespace: $NAMESPACE/" | \
            kubectl apply -f - &>/dev/null
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓${NC}"
            COPIED=$((COPIED + 1))
        else
            echo -e "${RED}✗ Failed${NC}"
        fi
    fi
done

echo ""
if [ $COPIED -gt 0 ]; then
    echo -e "${GREEN}✓ Successfully copied $COPIED ServerConfig(s) to $NAMESPACE${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Update your Server resources to use local ServerConfig references:"
    echo "   spec:"
    echo "     serverConfig: mlserver-config  # No 'seldon-system/' prefix"
    echo ""
    echo "2. Apply your Server and Model resources:"
    echo "   kubectl apply -k k8s/base/"
else
    echo -e "${YELLOW}⚠ No ServerConfigs found in seldon-system to copy${NC}"
    echo "Please ensure Seldon Core is properly installed"
fi

echo ""
echo "Verification:"
echo "-------------"
kubectl get serverconfig -n $NAMESPACE