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

# Run prerequisites check
echo "1. Checking Infrastructure Prerequisites"
echo "----------------------------------------"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set namespace
NAMESPACE=${NAMESPACE:-"fraud-detection"}
echo "Using namespace: $NAMESPACE"
echo ""

# Run prerequisites check script
if ! "$SCRIPT_DIR/check-prerequisites.sh" --namespace "$NAMESPACE"; then
    echo ""
    echo -e "${RED}Prerequisites check failed. Cannot proceed with deployment.${NC}"
    exit 1
fi

echo ""
echo "2. Checking Application Namespace"
echo "---------------------------------"
if kubectl get namespace $NAMESPACE &>/dev/null; then
    echo -e "${GREEN}✓ Namespace '$NAMESPACE' exists${NC}"
else
    echo -e "${YELLOW}⚠ Namespace '$NAMESPACE' not found, using default${NC}"
    NAMESPACE="default"
fi

echo ""
echo "3. Deploying Fraud Detection Models"
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
    
    # Clean up any ServerConfig in fraud-detection (from previous incorrect deployments)
    if kubectl get serverconfig mlserver-config -n $NAMESPACE &>/dev/null; then
        echo -e "${YELLOW}⚠ Found ServerConfig in $NAMESPACE, removing (Pattern 3 requires it in seldon-system only)${NC}"
        kubectl delete serverconfig mlserver-config -n $NAMESPACE
        echo "ServerConfig should only exist in seldon-system (managed by infrastructure team)"
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
echo "4. Checking Runtime Components"
echo "------------------------------"

# Check which pattern is being used
echo "Checking Seldon deployment pattern..."
SCHEDULER_IN_SYSTEM=$(kubectl get pods -n seldon-system -l "app.kubernetes.io/name=seldon-scheduler" --no-headers 2>/dev/null | wc -l)
SCHEDULER_IN_NS=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-scheduler" --no-headers 2>/dev/null | wc -l)

# Check for runtime components in application namespace (Pattern 3)
if [ "$SCHEDULER_IN_NS" -gt 0 ]; then
    ENVOY_IN_NS=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-envoy" --no-headers 2>/dev/null | wc -l)
    MODELGW_IN_NS=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-modelgateway" --no-headers 2>/dev/null | wc -l)
    
    echo -e "${GREEN}✓ Found runtime components in $NAMESPACE (Pattern 3 detected)${NC}"
    echo "Runtime components in $NAMESPACE:"
    kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name in (seldon-scheduler,seldon-envoy,seldon-modelgateway,seldon-pipelinegateway)" --no-headers 2>/dev/null | head -5
    
    if [ "$SCHEDULER_IN_SYSTEM" -gt 0 ]; then
        echo -e "${YELLOW}ℹ Infrastructure runtime also exists in seldon-system (normal for this setup)${NC}"
    fi
elif [ "$SCHEDULER_IN_SYSTEM" -gt 0 ]; then
    echo -e "${YELLOW}⚠ Found runtime components only in seldon-system (Pattern 1/4 detected)${NC}"
    kubectl get pods -n seldon-system -l "app.kubernetes.io/name in (seldon-scheduler,seldon-envoy)" --no-headers 2>/dev/null | head -5
else
    echo -e "${YELLOW}⚠ No Seldon runtime components found${NC}"
    echo ""
    echo "Runtime components are required for Seldon Core v2 to work."
    echo "Checking if they need to be deployed..."
    
    # Check if the operator expects Pattern 3 (runtime in app namespace)
    OPERATOR_CONFIG=$(kubectl get deployment -n seldon-system seldon-controller-manager -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="CONTROLLER_CLUSTERWIDE")].value}' 2>/dev/null)
    WATCH_NS=$(kubectl get deployment -n seldon-system seldon-controller-manager -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="CONTROLLER_NAMESPACE")].value}' 2>/dev/null)
    
    if [ "$OPERATOR_CONFIG" = "true" ] || [ -n "$WATCH_NS" ]; then
        echo "Operator is configured for Pattern 3 (runtime per namespace)"
        echo ""
        echo -e "${RED}✗ Runtime components MUST be deployed to $NAMESPACE${NC}"
        echo ""
        echo "To deploy runtime components, run:"
        echo ""
        echo "  # Using Ansible (recommended):"
        echo "  ansible-playbook -i inventory/production/hosts infrastructure/cluster/site.yml --tags seldon"
        echo ""
        echo "  # Or using Helm directly:"
        echo "  helm repo add seldon-charts https://seldonio.github.io/seldon-core-v2-charts"
        echo "  helm install seldon-core-v2-runtime seldon-charts/seldon-core-v2-runtime \\"
        echo "    --version 2.9.1 \\"
        echo "    --namespace $NAMESPACE \\"
        echo "    --create-namespace"
        echo ""
        echo -e "${YELLOW}Cannot proceed without runtime components.${NC}"
        # Don't exit, let the test continue to show what's missing
    else
        echo "Operator appears to be using Pattern 1/4 (centralized runtime)"
        echo "Runtime components should be in seldon-system namespace."
        echo ""
        echo -e "${YELLOW}⚠ This may be a configuration issue. Check the operator deployment.${NC}"
    fi
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
    SERVER_REASON=$(kubectl get server mlserver -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Ready")].reason}' 2>/dev/null)
    
    if [ "$SERVER_READY" != "True" ]; then
        echo -e "${YELLOW}⚠ Server not ready${NC}"
        
        # Check specific issue
        if echo "$SERVER_REASON" | grep -q "ServerConfig.*not found"; then
            echo -e "${RED}✗ ServerConfig reference issue detected${NC}"
            echo ""
            # Check where the ServerConfig actually is
            echo "Checking ServerConfig locations:"
            echo -n "  In seldon-system: "
            if kubectl get serverconfig mlserver-config -n seldon-system &>/dev/null; then
                echo -e "${GREEN}✓ Found${NC}"
                echo ""
                echo "The Server is configured for Pattern 3 (ServerConfig in seldon-system)."
                echo "This is correct. The issue may be:"
                echo "  1. The operator cannot access the ServerConfig across namespaces"
                echo "  2. RBAC permissions may need updating"
                echo "  3. The operator may need to be restarted"
            else
                echo -e "${RED}✗ Not found${NC}"
            fi
            
            echo -n "  In $NAMESPACE: "
            if kubectl get serverconfig mlserver-config -n $NAMESPACE &>/dev/null; then
                echo -e "${GREEN}✓ Found${NC}"
                echo ""
                echo "ServerConfig exists in application namespace (Pattern 4)."
                echo "But Server may be looking in seldon-system."
            else
                echo -e "${RED}✗ Not found${NC}"
            fi
        else
            echo "Reason: $SERVER_REASON"
        fi
        
        echo ""
        echo "Server details:"
        kubectl describe server mlserver -n $NAMESPACE | grep -A10 "Status:"
    else
        echo -e "${GREEN}✓ Server is ready${NC}"
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
            echo ""
            echo "Model: $MODEL_NAME"
            echo "----------------"
            
            # Get the model's server reference
            MODEL_SERVER=$(kubectl get model $MODEL_NAME -n $NAMESPACE -o jsonpath='{.spec.server}' 2>/dev/null)
            echo "  Server reference: $MODEL_SERVER"
            
            # Get the model's status
            kubectl get model $MODEL_NAME -n $NAMESPACE -o jsonpath='{.status}' 2>/dev/null | python3 -m json.tool 2>/dev/null || \
                kubectl describe model $MODEL_NAME -n $NAMESPACE | grep -A10 "Status:"
            echo ""
        done
    fi
    
    # Check if this is a runtime component issue
    echo "Checking runtime components:"
    echo "-----------------------------"
    SCHEDULER_COUNT=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-scheduler" --no-headers 2>/dev/null | wc -l)
    ENVOY_COUNT=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-envoy" --no-headers 2>/dev/null | wc -l)
    MODELGW_COUNT=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-modelgateway" --no-headers 2>/dev/null | wc -l)
    
    echo "  Scheduler pods: $SCHEDULER_COUNT"
    echo "  Envoy (mesh) pods: $ENVOY_COUNT"  
    echo "  Model gateway pods: $MODELGW_COUNT"
    
    if [ "$SCHEDULER_COUNT" -eq 0 ] || [ "$ENVOY_COUNT" -eq 0 ] || [ "$MODELGW_COUNT" -eq 0 ]; then
        echo -e "${RED}✗ Missing critical runtime components${NC}"
        echo ""
        echo "Models cannot run without complete runtime components."
        echo "Deploy missing components: ./scripts/deploy-runtime-pattern3.sh"
    else
        echo -e "${GREEN}✓ All runtime components present${NC}"
        
        # Check Server pods
        echo ""
        echo "Server pods:"
        kubectl get pods -n $NAMESPACE | grep -E "(mlserver|server)" || echo "No server pods found"
        
        # Check scheduler logs for errors
        echo ""
        echo "Recent scheduler logs:"
        kubectl logs -n $NAMESPACE --tail=10 -l app.kubernetes.io/name=seldon-scheduler 2>/dev/null || \
            kubectl logs -n seldon-system --tail=10 -l app.kubernetes.io/name=seldon-scheduler 2>/dev/null || \
            echo "No scheduler logs available"
    fi
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
    # Get error count, ensuring it's a single number
    ERROR_COUNT=$(kubectl logs -n $NAMESPACE $POD_NAME --tail=50 2>/dev/null | grep -ciE "(error|exception|failed)" 2>/dev/null || echo "0")
    ERROR_COUNT=$(echo "$ERROR_COUNT" | head -1 | tr -d '\n')
    if [ "$ERROR_COUNT" -gt 0 ] 2>/dev/null; then
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

# Collect detailed status
MODELS_READY=$(kubectl get models -n $NAMESPACE 2>/dev/null | grep fraud | grep -c "True" | head -1 || echo "0")
MODELS_TOTAL=$(kubectl get models -n $NAMESPACE 2>/dev/null | grep -c fraud | head -1 || echo "0")
SERVER_READY=$(kubectl get server mlserver -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
SCHEDULER_PODS=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-scheduler" --no-headers 2>/dev/null | wc -l)
ENVOY_PODS=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/name=seldon-envoy" --no-headers 2>/dev/null | wc -l)
RUNTIME_PODS_TOTAL=$((SCHEDULER_PODS + ENVOY_PODS))
SERVERCONFIG_IN_SYSTEM=$(kubectl get serverconfig mlserver-config -n seldon-system &>/dev/null && echo "YES" || echo "NO")
SERVERCONFIG_IN_NS=$(kubectl get serverconfig mlserver-config -n $NAMESPACE &>/dev/null && echo "YES" || echo "NO")

echo "Component Status:"
echo "-----------------"
echo -e "Models Ready:             $MODELS_READY / $MODELS_TOTAL"
echo -e "Server Ready:             $([ "$SERVER_READY" = "True" ] && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}")"
echo -e "Runtime Components:       $([ $RUNTIME_PODS_TOTAL -gt 1 ] && echo -e "${GREEN}$RUNTIME_PODS_TOTAL pods${NC}" || echo -e "${RED}$RUNTIME_PODS_TOTAL pods${NC}")"
echo -e "  Scheduler:              $([ $SCHEDULER_PODS -gt 0 ] && echo -e "${GREEN}$SCHEDULER_PODS${NC}" || echo -e "${RED}0${NC}")"
echo -e "  Envoy (mesh):           $([ $ENVOY_PODS -gt 0 ] && echo -e "${GREEN}$ENVOY_PODS${NC}" || echo -e "${RED}0${NC}")"
echo -e "ServerConfig (system):    $([ "$SERVERCONFIG_IN_SYSTEM" = "YES" ] && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}")"
echo -e "ServerConfig (namespace): $([ "$SERVERCONFIG_IN_NS" = "YES" ] && echo -e "${GREEN}YES${NC}" || echo -e "${YELLOW}NO${NC}")"

echo ""
# Ensure variables have numeric values
MODELS_READY=${MODELS_READY:-0}
SCHEDULER_PODS=${SCHEDULER_PODS:-0}
MESH_PODS=${MESH_PODS:-0}

if [ "$MODELS_READY" -gt 0 ] && [ "$SERVER_READY" = "True" ]; then
    echo -e "${GREEN}✅ Deployment test PASSED!${NC}"
    echo "The fraud detection models are deployed and running in Kubernetes"
elif [ "$RUNTIME_PODS_TOTAL" -lt 2 ]; then
    echo -e "${RED}✗ Deployment test FAILED${NC}"
    echo ""
    echo "Missing runtime components in $NAMESPACE namespace."
    echo "This is required for Pattern 3 architecture."
    echo ""
    echo "Action required:"
    echo "1. Deploy runtime components to $NAMESPACE using Helm:"
    echo "   helm repo add seldon-charts https://seldonio.github.io/seldon-core-v2-charts"
    echo "   helm install seldon-runtime-fraud seldon-charts/seldon-core-v2-runtime \\"
    echo "     --version 2.9.1 --namespace $NAMESPACE --wait"
    echo ""
    echo "2. Or verify if Pattern 1/4 is intended (runtime in seldon-system)"
elif [ "$SERVER_READY" != "True" ] && [ "$SERVERCONFIG_IN_SYSTEM" = "YES" ]; then
    echo -e "${YELLOW}⚠ Deployment test INCOMPLETE${NC}"
    echo ""
    echo "ServerConfig exists in seldon-system but Server cannot access it."
    echo "This is an infrastructure configuration issue."
    echo ""
    echo "Contact your infrastructure team to:"
    echo "1. Verify the Seldon operator can access cross-namespace resources"
    echo "2. Check RBAC permissions allow ServerConfig access from fraud-detection"
    echo "3. Ensure the operator is properly configured for Pattern 3"
    echo ""
    echo "Infrastructure team may need to:"
    echo "- Restart the operator: kubectl rollout restart deployment -n seldon-system seldon-v2-controller-manager"
    echo "- Update RBAC policies for cross-namespace access"
else
    echo -e "${YELLOW}⚠ Deployment test INCOMPLETE${NC}"
    echo "Some components may not be fully deployed. Check the logs above for details."
fi

echo ""
echo "Next Steps:"
echo "1. Check Grafana dashboards for monitoring"
echo "2. Run production validation: python scripts/validate-production-pipeline.py"
echo "3. Start A/B testing: python scripts/deploy-extended-ab-test.py"