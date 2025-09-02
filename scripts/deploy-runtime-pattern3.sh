#!/bin/bash

# Deploy Seldon Runtime Components for Pattern 3 Architecture
# This script deploys the required runtime components to the fraud-detection namespace
#
# Pattern 3 requires:
# - ServerConfig in seldon-system (managed by infrastructure team)
# - Runtime components in application namespace (deployed by this script)
# - Application resources (Models, Server, Experiment) in application namespace

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE=${NAMESPACE:-"fraud-detection"}

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Seldon Runtime Deployment for Pattern 3${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# 1. Check infrastructure prerequisites
echo "1. Checking Infrastructure Prerequisites"
echo "----------------------------------------"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run prerequisites check with quiet mode for cleaner output
if ! "$SCRIPT_DIR/check-prerequisites.sh" --namespace "$NAMESPACE" --quiet; then
    echo -e "${RED}Infrastructure prerequisites not met.${NC}"
    echo ""
    echo "Run the full check for details:"
    echo "  ./scripts/check-prerequisites.sh --namespace $NAMESPACE"
    exit 1
fi
echo -e "${GREEN}✓ All infrastructure prerequisites met${NC}"

# Check if namespace exists (create if needed)
if ! kubectl get namespace $NAMESPACE &>/dev/null; then
    echo -e "${YELLOW}Creating namespace $NAMESPACE...${NC}"
    kubectl create namespace $NAMESPACE
fi
echo -e "${GREEN}✓ Namespace $NAMESPACE ready${NC}"

# 2. Check current runtime location
echo ""
echo "2. Checking Current Runtime Location"
echo "-----------------------------------"

SCHEDULER_IN_SYSTEM=$(kubectl get pods -n seldon-system -l "app.kubernetes.io/name=seldon-scheduler" --no-headers 2>/dev/null | wc -l)
SCHEDULER_IN_NS=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-scheduler" --no-headers 2>/dev/null | wc -l)

if [ "$SCHEDULER_IN_SYSTEM" -gt 0 ]; then
    echo -e "${YELLOW}⚠ Runtime components found in seldon-system (Pattern 1/4)${NC}"
    echo "Pattern 3 requires runtime components in $NAMESPACE."
    echo ""
fi

if [ "$SCHEDULER_IN_NS" -gt 0 ]; then
    echo -e "${GREEN}✓ Runtime components already exist in $NAMESPACE${NC}"
    echo "Do you want to upgrade/reinstall? (y/N)"
    read -r RESPONSE
    if [[ ! "$RESPONSE" =~ ^[Yy]$ ]]; then
        echo "Skipping runtime deployment."
        exit 0
    fi
fi

# 3. Install Helm if needed
echo ""
echo "3. Checking Helm Installation"
echo "----------------------------"

if ! command -v helm &> /dev/null; then
    echo -e "${RED}✗ Helm is not installed${NC}"
    echo ""
    echo "Please install Helm first:"
    echo "  curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
    exit 1
fi
echo -e "${GREEN}✓ Helm is installed${NC}"

# Add Seldon helm repo
if ! helm repo list | grep -q seldon-charts; then
    echo "Adding Seldon Helm repository..."
    helm repo add seldon-charts https://seldonio.github.io/seldon-core-v2-charts
fi

echo "Updating Helm repositories..."
helm repo update

# 4. Deploy runtime components
echo ""
echo "4. Deploying Runtime Components"
echo "-------------------------------"
echo "Deploying to namespace: $NAMESPACE"
echo ""

# Check what releases already exist
EXISTING_RELEASE=""
if helm list -n $NAMESPACE | grep -q seldon-core-v2-runtime-fraud-detection; then
    EXISTING_RELEASE="seldon-core-v2-runtime-fraud-detection"
    echo "Found existing release: $EXISTING_RELEASE"
elif helm list -n $NAMESPACE | grep -q seldon-runtime-fraud; then
    EXISTING_RELEASE="seldon-runtime-fraud"
    echo "Found existing release: $EXISTING_RELEASE"
fi

if [ -n "$EXISTING_RELEASE" ]; then
    echo "Upgrading existing runtime deployment: $EXISTING_RELEASE..."
    helm upgrade "$EXISTING_RELEASE" seldon-charts/seldon-core-v2-runtime \
      --version 2.9.1 \
      --namespace $NAMESPACE \
      --set seldonRuntime.scheduler.enabled=true \
      --set seldonRuntime.envoy.enabled=true \
      --set seldonRuntime.modelGateway.enabled=true \
      --set seldonRuntime.pipelineGateway.enabled=true \
      --set seldonRuntime.dataflowEngine.enabled=true \
      --wait \
      --timeout 5m
else
    echo "Installing new runtime deployment..."
    helm install seldon-core-v2-runtime-fraud-detection seldon-charts/seldon-core-v2-runtime \
      --version 2.9.1 \
      --namespace $NAMESPACE \
      --create-namespace \
      --set seldonRuntime.scheduler.enabled=true \
      --set seldonRuntime.envoy.enabled=true \
      --set seldonRuntime.modelGateway.enabled=true \
      --set seldonRuntime.pipelineGateway.enabled=true \
      --set seldonRuntime.dataflowEngine.enabled=true \
      --wait \
      --timeout 5m
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Runtime components deployed successfully${NC}"
else
    echo -e "${RED}✗ Runtime deployment failed${NC}"
    echo "Check the error messages above for details."
    exit 1
fi

# 5. Verify deployment
echo ""
echo "5. Verifying Runtime Components"
echo "-------------------------------"

echo "Waiting for pods to be ready..."
sleep 5

# Check scheduler
SCHEDULER_READY=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-scheduler" --no-headers 2>/dev/null | grep -c Running || echo "0")
if [ "$SCHEDULER_READY" -gt 0 ]; then
    echo -e "${GREEN}✓ Scheduler is running${NC}"
else
    echo -e "${YELLOW}⚠ Scheduler not ready yet${NC}"
fi

# Check mesh/envoy
MESH_READY=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-mesh" --no-headers 2>/dev/null | grep -c Running || echo "0")
if [ "$MESH_READY" -gt 0 ]; then
    echo -e "${GREEN}✓ Mesh (Envoy) is running${NC}"
else
    echo -e "${YELLOW}⚠ Mesh not ready yet${NC}"
fi

# Check model gateway
MODELGW_READY=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-modelgateway" --no-headers 2>/dev/null | grep -c Running || echo "0")
if [ "$MODELGW_READY" -gt 0 ]; then
    echo -e "${GREEN}✓ Model Gateway is running${NC}"
else
    echo -e "${YELLOW}⚠ Model Gateway not ready yet${NC}"
fi

# Show all runtime pods
echo ""
echo "Runtime pods in $NAMESPACE:"
kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/part-of=seldon-core-v2"

# 6. Next steps
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Next Steps${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "1. Deploy your application resources:"
echo "   kubectl apply -k k8s/base/"
echo ""
echo "2. Verify deployment:"
echo "   ./scripts/test-k8s-deployment.sh"
echo ""
echo "3. Check model status:"
echo "   kubectl get models -n $NAMESPACE"
echo "   kubectl get server -n $NAMESPACE"
echo ""
echo -e "${GREEN}✓ Runtime components are ready for Pattern 3 deployment${NC}"