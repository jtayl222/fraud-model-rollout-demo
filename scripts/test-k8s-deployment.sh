#!/bin/bash

# Test K8s Deployment in Existing Cluster
# This script validates the fraud detection models are working in the actual K8s environment
# 
# Usage: ./scripts/test-k8s-deployment.sh [--force]
#   --force: Force redeployment even if resources are up to date
#
# This script is IDEMPOTENT - safe to run multiple times

set -e

# Check for --force flag
FORCE_DEPLOY=false
if [ "$1" == "--force" ]; then
    FORCE_DEPLOY=true
    echo "Force deployment mode enabled"
fi

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Fraud Detection K8s Deployment Test${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check kubectl connection
echo "1. Checking Kubernetes Connection"
echo "---------------------------------"
if kubectl cluster-info &>/dev/null; then
    echo -e "${GREEN}✓ Connected to Kubernetes cluster${NC}"
    kubectl cluster-info | head -n 1
else
    echo -e "${RED}✗ Cannot connect to Kubernetes cluster${NC}"
    echo "Please ensure KUBECONFIG is set correctly"
    exit 1
fi

echo ""
echo "2. Checking Namespaces"
echo "----------------------"
NAMESPACE=${NAMESPACE:-"fraud-detection"}
echo "Using namespace: $NAMESPACE"

if kubectl get namespace $NAMESPACE &>/dev/null; then
    echo -e "${GREEN}✓ Namespace '$NAMESPACE' exists${NC}"
else
    echo -e "${YELLOW}⚠ Namespace '$NAMESPACE' not found, using default${NC}"
    NAMESPACE="default"
fi

echo ""
echo "3. Checking Seldon Core Installation"
echo "------------------------------------"
if kubectl get crd models.mlops.seldon.io &>/dev/null; then
    echo -e "${GREEN}✓ Seldon Core v2 CRDs found${NC}"
    
    # Check Seldon controller
    if kubectl get pods -n seldon-system 2>/dev/null | grep -q Running; then
        echo -e "${GREEN}✓ Seldon controller is running${NC}"
    else
        echo -e "${YELLOW}⚠ Seldon controller not found or not running${NC}"
    fi
else
    echo -e "${RED}✗ Seldon Core CRDs not found${NC}"
    echo "Please install Seldon Core v2 first"
    exit 1
fi

echo ""
echo "4. Deploying Fraud Detection Models"
echo "-----------------------------------"

# Check if models already exist
if kubectl get models -n $NAMESPACE 2>/dev/null | grep -q fraud; then
    echo -e "${YELLOW}⚠ Existing fraud models found, will update${NC}"
    kubectl get models -n $NAMESPACE | grep fraud
fi

# Apply K8s configurations
echo "Applying K8s configurations..."
if [ -f "k8s/base/kustomization.yaml" ]; then
    echo "Using Kustomize..."
    # First, check which namespace the kustomization expects
    KUSTOMIZE_NS=$(grep "^namespace:" k8s/base/kustomization.yaml | awk '{print $2}')
    if [ -n "$KUSTOMIZE_NS" ]; then
        echo "Kustomization specifies namespace: $KUSTOMIZE_NS"
        NAMESPACE=$KUSTOMIZE_NS
        
        # Create namespace if it doesn't exist
        if ! kubectl get namespace $NAMESPACE &>/dev/null; then
            echo "Creating namespace $NAMESPACE..."
            kubectl create namespace $NAMESPACE
        fi
    fi
    
    # Pattern 3: Apply ServerConfig to seldon-system first (centralized)
    if [ -f "k8s/base/server-config-centralized.yaml" ]; then
        echo "Checking centralized ServerConfig in seldon-system..."
        
        # Check if ServerConfig already exists
        if kubectl get serverconfig mlserver-config -n seldon-system &>/dev/null; then
            echo -e "${GREEN}✓ ServerConfig 'mlserver-config' already exists in seldon-system${NC}"
            
            # Check if it needs updating by comparing with file
            echo "Verifying ServerConfig is up to date..."
            if [ "$FORCE_DEPLOY" = true ] || ! kubectl diff -f k8s/base/server-config-centralized.yaml &>/dev/null; then
                if [ "$FORCE_DEPLOY" = true ]; then
                    echo "Force mode: Updating ServerConfig..."
                else
                    echo "Updating ServerConfig..."
                fi
                kubectl apply -f k8s/base/server-config-centralized.yaml
                echo -e "${GREEN}✓ ServerConfig updated${NC}"
            else
                echo -e "${GREEN}✓ ServerConfig is up to date${NC}"
            fi
        else
            echo "Applying new centralized ServerConfig to seldon-system..."
            kubectl apply -f k8s/base/server-config-centralized.yaml
            echo -e "${GREEN}✓ ServerConfig deployed to seldon-system${NC}"
        fi
    fi
    
    # Apply the main kustomization (idempotent)
    echo "Applying kustomization to $NAMESPACE..."
    
    # kubectl apply is idempotent, but let's check for major conflicts first
    echo "Checking for configuration changes..."
    if [ "$FORCE_DEPLOY" = true ] || ! kubectl diff -k k8s/base/ &>/dev/null; then
        if [ "$FORCE_DEPLOY" = true ]; then
            echo "Force mode: Applying kustomization..."
        else
            echo "Applying configuration updates..."
        fi
        kubectl apply -k k8s/base/
        
        # Wait a moment for resources to be processed
        sleep 3
        echo -e "${GREEN}✓ Kustomization applied${NC}"
    else
        echo -e "${GREEN}✓ No configuration changes needed${NC}"
    fi
else
    echo "Applying individual files..."
    for file in k8s/base/*.yaml; do
        if [[ ! "$file" == *".example"* ]] && [[ ! "$file" == *"kustomization"* ]]; then
            echo "  Applying $(basename $file)..."
            kubectl apply -f $file -n $NAMESPACE
        fi
    done
fi

echo ""
echo "5. Checking Server Status"
echo "-------------------------"

# First check if Server is ready
echo "Checking mlserver status..."
SERVER_STATUS=$(kubectl get server mlserver -n $NAMESPACE 2>/dev/null || echo "NOT_FOUND")
if [ "$SERVER_STATUS" = "NOT_FOUND" ]; then
    echo -e "${RED}✗ Server 'mlserver' not found in $NAMESPACE${NC}"
    echo "Available servers:"
    kubectl get servers -n $NAMESPACE 2>/dev/null || echo "None"
else
    echo "Server status:"
    kubectl get server mlserver -n $NAMESPACE
    
    # Check if Server has issues
    SERVER_READY=$(kubectl get server mlserver -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    if [ "$SERVER_READY" != "True" ]; then
        echo -e "${YELLOW}⚠ Server not ready, checking details...${NC}"
        kubectl describe server mlserver -n $NAMESPACE | tail -20
    fi
fi

echo ""
echo "6. Waiting for Models to be Ready"
echo "---------------------------------"
echo "Waiting for models to initialize (this may take 1-2 minutes)..."

# Wait for models to be ready
TIMEOUT=120
ELAPSED=0
MODEL_READY=false

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Check if any fraud models exist
    if kubectl get models -n $NAMESPACE 2>/dev/null | grep -q fraud; then
        # Check if any fraud models are ready
        if kubectl get models -n $NAMESPACE 2>/dev/null | grep fraud | grep -q "True"; then
            echo -e "\n${GREEN}✓ Models are ready${NC}"
            kubectl get models -n $NAMESPACE | grep fraud
            MODEL_READY=true
            break
        else
            # Show current model status every 30 seconds
            if [ $((ELAPSED % 30)) -eq 0 ] && [ $ELAPSED -gt 0 ]; then
                echo -e "\n${YELLOW}Current model status:${NC}"
                kubectl get models -n $NAMESPACE | grep fraud
            fi
        fi
    else
        echo -e "\n${YELLOW}⚠ No fraud models found in $NAMESPACE${NC}"
        echo "Available models:"
        kubectl get models -n $NAMESPACE 2>/dev/null || echo "None"
        break
    fi
    
    echo -n "."
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ "$MODEL_READY" = false ]; then
    echo -e "\n${YELLOW}⚠ Models not ready after ${TIMEOUT}s${NC}"
    echo "Final status:"
    kubectl get models -n $NAMESPACE 2>/dev/null || echo "No models found"
    
    echo ""
    echo "Debugging information:"
    echo "----------------------"
    
    # Check for any fraud models and their detailed status
    FRAUD_MODELS=$(kubectl get models -n $NAMESPACE -o name 2>/dev/null | grep fraud || echo "")
    if [ -n "$FRAUD_MODELS" ]; then
        for model in $FRAUD_MODELS; do
            MODEL_NAME=$(echo $model | cut -d'/' -f2)
            echo "Model: $MODEL_NAME"
            kubectl describe model $MODEL_NAME -n $NAMESPACE | grep -A5 -B5 -E "(Status:|Conditions:|Message:|Reason:)"
            echo "---"
        done
    fi
    
    # Check Server pods
    echo "Server pods:"
    kubectl get pods -n $NAMESPACE | grep -E "(mlserver|server)" || echo "No server pods found"
    
    # Check scheduler logs for errors
    echo ""
    echo "Recent scheduler logs:"
    kubectl logs -n $NAMESPACE --tail=10 -l app.kubernetes.io/name=seldon-scheduler 2>/dev/null || echo "No scheduler logs available"
fi

echo ""
echo "7. Checking Model Endpoints"
echo "---------------------------"

# Get service endpoints
echo "Looking for model services..."
kubectl get svc -n $NAMESPACE | grep -E "(fraud|mlserver|seldon)" || echo "No fraud-related services found"

# Check for ingress
echo ""
echo "Checking for ingress..."
kubectl get ingress -n $NAMESPACE 2>/dev/null | grep -E "(fraud|ml-api)" || echo "No ingress configured"

echo ""
echo "8. Testing Model Predictions"
echo "----------------------------"

# Find the service endpoint
SERVICE_NAME=$(kubectl get svc -n $NAMESPACE -o name | grep -E "(fraud|mlserver)" | head -n 1 | cut -d'/' -f2)
if [ -z "$SERVICE_NAME" ]; then
    echo -e "${YELLOW}⚠ No model service found, skipping prediction test${NC}"
else
    echo "Found service: $SERVICE_NAME"
    
    # Port-forward to test locally
    echo "Setting up port-forward..."
    kubectl port-forward -n $NAMESPACE svc/$SERVICE_NAME 8080:8080 &
    PF_PID=$!
    sleep 3
    
    # Create test request
    echo "Sending test prediction..."
    cat > /tmp/test-request.json <<EOF
{
  "inputs": [
    {
      "name": "predict",
      "shape": [1, 30],
      "datatype": "FP32",
      "data": [
        -1.359807, -0.072781, 2.536347, 1.378155, -0.338321,
        0.462388, 0.239599, 0.086939, 0.099742, -0.270826,
        -0.838774, -0.414575, -0.503199, -0.905588, -1.436518,
        0.186068, -0.071213, -0.294862, -0.932860, 0.172245,
        -0.087103, -0.071213, -0.123960, -0.034095, -0.051429,
        0.449912, 0.008873, -0.019914, -0.018308, 149.62
      ]
    }
  ]
}
EOF
    
    # Send request
    RESPONSE=$(curl -s -X POST http://localhost:8080/v2/models/fraud-model/infer \
        -H "Content-Type: application/json" \
        -d @/tmp/test-request.json 2>/dev/null || echo "")
    
    # Kill port-forward
    kill $PF_PID 2>/dev/null || true
    
    if [ -n "$RESPONSE" ]; then
        echo -e "${GREEN}✓ Model responded successfully${NC}"
        echo "Response: $RESPONSE" | head -c 200
        echo "..."
    else
        echo -e "${YELLOW}⚠ Could not get model response${NC}"
    fi
fi

echo ""
echo "9. Checking Logs for Errors"
echo "---------------------------"

# Check for recent errors in model pods
echo "Checking for errors in model pods..."
for pod in $(kubectl get pods -n $NAMESPACE -o name | grep -E "(fraud|mlserver|seldon)"); do
    POD_NAME=$(echo $pod | cut -d'/' -f2)
    echo -n "  $POD_NAME: "
    ERROR_COUNT=$(kubectl logs -n $NAMESPACE $POD_NAME --tail=50 2>/dev/null | grep -ciE "(error|exception|failed)" || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}$ERROR_COUNT errors found${NC}"
    else
        echo -e "${GREEN}✓ No errors${NC}"
    fi
done

echo ""
echo "10. Resource Usage"
echo "------------------"
kubectl top pods -n $NAMESPACE 2>/dev/null | grep -E "(fraud|mlserver|seldon)" || echo "Metrics not available (metrics-server may not be installed)"

echo ""
echo "============================================"
echo "Test Summary"
echo "============================================"

# Collect status
MODELS_READY=$(kubectl get models -n $NAMESPACE 2>/dev/null | grep -c "Ready" || echo "0")
PODS_RUNNING=$(kubectl get pods -n $NAMESPACE 2>/dev/null | grep -E "(fraud|mlserver)" | grep -c "Running" || echo "0")
SERVICES=$(kubectl get svc -n $NAMESPACE 2>/dev/null | grep -cE "(fraud|mlserver)" || echo "0")

echo -e "Models Ready:    ${GREEN}$MODELS_READY${NC}"
echo -e "Pods Running:    ${GREEN}$PODS_RUNNING${NC}"
echo -e "Services:        ${GREEN}$SERVICES${NC}"

if [ $MODELS_READY -gt 0 ] && [ $PODS_RUNNING -gt 0 ]; then
    echo -e "\n${GREEN}✅ Deployment test PASSED!${NC}"
    echo "The fraud detection models are deployed and running in Kubernetes"
else
    echo -e "\n${YELLOW}⚠ Deployment test INCOMPLETE${NC}"
    echo "Some components may not be fully deployed. Check the logs above for details."
fi

echo ""
echo "Next Steps:"
echo "1. Check Grafana dashboards for monitoring"
echo "2. Run production validation: python scripts/validate-production-pipeline.py"
echo "3. Start A/B testing: python scripts/deploy-extended-ab-test.py"