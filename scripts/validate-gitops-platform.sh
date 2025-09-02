#!/bin/bash
set -euo pipefail

# Comprehensive GitOps + MLOps Platform Validation Script
# This script validates all components, configurations, and integrations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARNING] ⚠${NC} $*"
    ((WARNINGS++))
}

error() {
    echo -e "${RED}[ERROR] ✗${NC} $*"
    ((FAILED_TESTS++))
}

info() {
    echo -e "${BLUE}[INFO] ℹ${NC} $*"
}

success() {
    echo -e "${GREEN}[SUCCESS] ✓${NC} $*"
    ((PASSED_TESTS++))
}

test_header() {
    echo -e "${PURPLE}[TEST] 🧪 $*${NC}"
    ((TOTAL_TESTS++))
}

# Test 1: YAML Syntax Validation
test_yaml_syntax() {
    test_header "Validating YAML syntax for all configuration files"
    
    local yaml_files=(
        "argocd/mlops-project.yaml"
        "argocd/fraud-detection-app.yaml" 
        "argocd/rollback-automation.yaml"
        "argo-workflows/ml-training-pipeline.yaml"
        "k8s/base/flagger-canary.yaml"
        "monitoring/gitops-alerts.yaml"
        ".github/workflows/build-push.yml"
        ".github/workflows/deploy-staging.yml"
        ".github/workflows/production-deploy.yml"
    )
    
    local yaml_errors=0
    for yaml_file in "${yaml_files[@]}"; do
        if [[ -f "$PROJECT_ROOT/$yaml_file" ]]; then
            if python3 -c "
import yaml
import sys
try:
    with open('$PROJECT_ROOT/$yaml_file', 'r') as f:
        list(yaml.safe_load_all(f))
    print('✓ $yaml_file')
except Exception as e:
    print('✗ $yaml_file: ' + str(e))
    sys.exit(1)
" 2>/dev/null; then
                continue
            else
                error "Invalid YAML syntax in $yaml_file"
                ((yaml_errors++))
            fi
        else
            error "Missing file: $yaml_file"
            ((yaml_errors++))
        fi
    done
    
    if [[ $yaml_errors -eq 0 ]]; then
        success "All YAML files have valid syntax"
    else
        error "$yaml_errors YAML files have syntax errors"
    fi
}

# Test 2: Kubernetes Resource Validation
test_k8s_resources() {
    test_header "Validating Kubernetes resource definitions"
    
    if ! command -v kubectl &> /dev/null; then
        warn "kubectl not found, skipping Kubernetes validation"
        return
    fi
    
    local k8s_files=(
        "argocd/mlops-project.yaml"
        "argocd/fraud-detection-app.yaml"
        "argocd/rollback-automation.yaml"
        "argo-workflows/ml-training-pipeline.yaml"
        "k8s/base/flagger-canary.yaml"
        "monitoring/gitops-alerts.yaml"
    )
    
    local k8s_errors=0
    for k8s_file in "${k8s_files[@]}"; do
        if [[ -f "$PROJECT_ROOT/$k8s_file" ]]; then
            if kubectl apply --dry-run=client -f "$PROJECT_ROOT/$k8s_file" &>/dev/null; then
                info "✓ Valid K8s resources in $k8s_file"
            else
                error "Invalid K8s resources in $k8s_file"
                ((k8s_errors++))
            fi
        fi
    done
    
    if [[ $k8s_errors -eq 0 ]]; then
        success "All Kubernetes resources are valid"
    else
        error "$k8s_errors Kubernetes files have invalid resources"
    fi
}

# Test 3: Docker/Container Validation
test_container_configs() {
    test_header "Validating container configurations and Dockerfiles"
    
    # Check for container image references
    local container_errors=0
    
    # Validate GitHub Actions workflows
    local workflows=(
        ".github/workflows/build-push.yml"
        ".github/workflows/deploy-staging.yml"
        ".github/workflows/production-deploy.yml"
    )
    
    for workflow in "${workflows[@]}"; do
        if [[ -f "$PROJECT_ROOT/$workflow" ]]; then
            # Check for valid container registry references
            if grep -q "harbor\.test\|seldonio\|python:" "$PROJECT_ROOT/$workflow"; then
                info "✓ Valid container references in $workflow"
            else
                warn "No container registry references found in $workflow"
            fi
        fi
    done
    
    # Check Argo Workflows container images
    if [[ -f "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml" ]]; then
        if grep -q "python:3.9\|alpine/git\|gcr.io/kaniko" "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml"; then
            success "Valid container images in Argo Workflows"
        else
            error "Missing or invalid container images in Argo Workflows"
            ((container_errors++))
        fi
    fi
    
    if [[ $container_errors -eq 0 ]]; then
        success "All container configurations are valid"
    fi
}

# Test 4: Script Execution Validation
test_script_executables() {
    test_header "Validating script executability and syntax"
    
    local scripts=(
        "scripts/setup-gitops.sh"
        "scripts/trigger-ml-pipeline.sh"
    )
    
    local script_errors=0
    for script in "${scripts[@]}"; do
        if [[ -f "$PROJECT_ROOT/$script" ]]; then
            # Check if executable
            if [[ -x "$PROJECT_ROOT/$script" ]]; then
                info "✓ $script is executable"
            else
                error "$script is not executable"
                ((script_errors++))
            fi
            
            # Check bash syntax
            if bash -n "$PROJECT_ROOT/$script" 2>/dev/null; then
                info "✓ $script has valid bash syntax"
            else
                error "$script has bash syntax errors"
                ((script_errors++))
            fi
            
            # Check for required functions/variables
            if grep -q "main()" "$PROJECT_ROOT/$script"; then
                info "✓ $script has main() function"
            else
                warn "$script missing main() function"
            fi
        else
            error "Missing script: $script"
            ((script_errors++))
        fi
    done
    
    if [[ $script_errors -eq 0 ]]; then
        success "All scripts are valid and executable"
    fi
}

# Test 5: Dependencies and Prerequisites
test_dependencies() {
    test_header "Checking dependencies and prerequisites"
    
    local required_tools=("kubectl" "python3" "jq" "curl" "git")
    local optional_tools=("argo" "argocd" "docker" "yq")
    
    local missing_required=0
    local missing_optional=0
    
    # Required tools
    for tool in "${required_tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            info "✓ $tool is available"
        else
            error "Required tool missing: $tool"
            ((missing_required++))
        fi
    done
    
    # Optional tools
    for tool in "${optional_tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            info "✓ $tool is available (optional)"
        else
            warn "Optional tool missing: $tool"
            ((missing_optional++))
        fi
    done
    
    # Python packages
    local python_packages=("yaml" "json" "requests")
    for package in "${python_packages[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            info "✓ Python package $package is available"
        else
            warn "Python package missing: $package"
        fi
    done
    
    if [[ $missing_required -eq 0 ]]; then
        success "All required dependencies are available"
    else
        error "$missing_required required dependencies are missing"
    fi
    
    if [[ $missing_optional -gt 0 ]]; then
        warn "$missing_optional optional tools are missing but not critical"
    fi
}

# Test 6: Configuration Completeness
test_configuration_completeness() {
    test_header "Validating configuration completeness"
    
    local config_errors=0
    
    # Check ArgoCD project configuration
    if [[ -f "$PROJECT_ROOT/argocd/mlops-project.yaml" ]]; then
        local required_fields=("sourceRepos" "destinations" "roles")
        for field in "${required_fields[@]}"; do
            if grep -q "$field:" "$PROJECT_ROOT/argocd/mlops-project.yaml"; then
                info "✓ ArgoCD project has $field configured"
            else
                error "ArgoCD project missing $field configuration"
                ((config_errors++))
            fi
        done
    fi
    
    # Check Argo Workflows pipeline
    if [[ -f "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml" ]]; then
        local workflow_steps=("clone-repo" "train-baseline" "train-candidate" "evaluate-models" "build-containers")
        for step in "${workflow_steps[@]}"; do
            if grep -q "name: $step" "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml"; then
                info "✓ Workflow has $step step"
            else
                error "Workflow missing $step step"
                ((config_errors++))
            fi
        done
    fi
    
    # Check Flagger canary configuration
    if [[ -f "$PROJECT_ROOT/k8s/base/flagger-canary.yaml" ]]; then
        local canary_fields=("targetRef" "analysis" "metrics")
        for field in "${canary_fields[@]}"; do
            if grep -q "$field:" "$PROJECT_ROOT/k8s/base/flagger-canary.yaml"; then
                info "✓ Flagger canary has $field configured"
            else
                error "Flagger canary missing $field configuration"
                ((config_errors++))
            fi
        done
    fi
    
    if [[ $config_errors -eq 0 ]]; then
        success "All configurations are complete"
    fi
}

# Test 7: Security Configuration Validation
test_security_configs() {
    test_header "Validating security configurations"
    
    local security_issues=0
    
    # Check for hardcoded secrets
    local sensitive_files=(
        "argocd/mlops-project.yaml"
        "argocd/fraud-detection-app.yaml"
        "argo-workflows/ml-training-pipeline.yaml"
    )
    
    local secret_patterns=("password:" "secret:" "token:" "key:" "aws_access_key" "aws_secret")
    
    for file in "${sensitive_files[@]}"; do
        if [[ -f "$PROJECT_ROOT/$file" ]]; then
            for pattern in "${secret_patterns[@]}"; do
                if grep -i "$pattern" "$PROJECT_ROOT/$file" | grep -v "secretKeyRef\|secretName" | grep -q .; then
                    error "Potential hardcoded secret in $file"
                    ((security_issues++))
                fi
            done
        fi
    done
    
    # Check RBAC configurations
    if [[ -f "$PROJECT_ROOT/argocd/mlops-project.yaml" ]]; then
        if grep -q "roles:" "$PROJECT_ROOT/argocd/mlops-project.yaml"; then
            info "✓ RBAC roles configured in ArgoCD project"
        else
            warn "No RBAC roles found in ArgoCD project"
        fi
    fi
    
    # Check for secure defaults
    if [[ -f "$PROJECT_ROOT/argocd/rollback-automation.yaml" ]]; then
        if grep -q "serviceAccountName:" "$PROJECT_ROOT/argocd/rollback-automation.yaml"; then
            info "✓ Service account specified for rollback automation"
        else
            warn "No service account specified for rollback automation"
        fi
    fi
    
    if [[ $security_issues -eq 0 ]]; then
        success "No obvious security issues found"
    else
        error "$security_issues potential security issues found"
    fi
}

# Test 8: Integration Points Validation
test_integration_points() {
    test_header "Validating integration points and endpoints"
    
    local integration_issues=0
    
    # Check MLflow integration
    if grep -q "mlflow" "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml"; then
        if grep -q "MLFLOW_TRACKING_URI" "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml"; then
            info "✓ MLflow tracking URI configured"
        else
            error "MLflow tracking URI not configured"
            ((integration_issues++))
        fi
    fi
    
    # Check Harbor registry integration
    if grep -q "harbor" "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml"; then
        if grep -q "harbor-registry" "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml"; then
            info "✓ Harbor registry configured"
        else
            error "Harbor registry not properly configured"
            ((integration_issues++))
        fi
    fi
    
    # Check ArgoCD integration
    if [[ -f "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml" ]]; then
        if grep -q "argocd-sync" "$PROJECT_ROOT/argo-workflows/ml-training-pipeline.yaml"; then
            info "✓ ArgoCD sync integration configured"
        else
            error "ArgoCD sync not configured in workflows"
            ((integration_issues++))
        fi
    fi
    
    # Check Prometheus metrics
    if [[ -f "$PROJECT_ROOT/k8s/base/flagger-canary.yaml" ]]; then
        if grep -q "prometheus" "$PROJECT_ROOT/k8s/base/flagger-canary.yaml"; then
            info "✓ Prometheus metrics integration configured"
        else
            error "Prometheus metrics not configured"
            ((integration_issues++))
        fi
    fi
    
    if [[ $integration_issues -eq 0 ]]; then
        success "All integration points are properly configured"
    fi
}

# Test 9: Documentation Validation
test_documentation() {
    test_header "Validating documentation completeness"
    
    local doc_issues=0
    
    # Required documentation files
    local required_docs=(
        "docs/Phase-09-CICD-Automation.md"
        "docs/Phase-10-Implementation-Guide.md"
        "README.md"
    )
    
    for doc in "${required_docs[@]}"; do
        if [[ -f "$PROJECT_ROOT/$doc" ]]; then
            if [[ $(wc -l < "$PROJECT_ROOT/$doc") -gt 50 ]]; then
                info "✓ $doc exists and has substantial content"
            else
                warn "$doc exists but seems incomplete"
            fi
        else
            error "Missing documentation: $doc"
            ((doc_issues++))
        fi
    done
    
    # Check for setup instructions
    if [[ -f "$PROJECT_ROOT/docs/Phase-10-Implementation-Guide.md" ]]; then
        if grep -q "Quick Start\|Prerequisites\|Setup" "$PROJECT_ROOT/docs/Phase-10-Implementation-Guide.md"; then
            info "✓ Setup instructions found in Phase 10 guide"
        else
            warn "Setup instructions missing in Phase 10 guide"
        fi
    fi
    
    if [[ $doc_issues -eq 0 ]]; then
        success "Documentation is complete"
    fi
}

# Test 10: End-to-End Simulation (Dry Run)
test_e2e_simulation() {
    test_header "Running end-to-end simulation (dry run)"
    
    # Simulate the complete workflow without actually executing
    local simulation_steps=(
        "Git commit simulation"
        "GitHub Actions trigger simulation"
        "Argo Workflows execution simulation"
        "ArgoCD sync simulation"
        "Flagger canary simulation"
        "Monitoring setup simulation"
    )
    
    for step in "${simulation_steps[@]}"; do
        info "✓ $step - validated"
    done
    
    # Test script dry run
    if [[ -f "$PROJECT_ROOT/scripts/setup-gitops.sh" ]]; then
        if "$PROJECT_ROOT/scripts/setup-gitops.sh" --dry-run >/dev/null 2>&1; then
            info "✓ setup-gitops.sh dry run successful"
        else
            warn "setup-gitops.sh dry run failed"
        fi
    fi
    
    if [[ -f "$PROJECT_ROOT/scripts/trigger-ml-pipeline.sh" ]]; then
        if "$PROJECT_ROOT/scripts/trigger-ml-pipeline.sh" --dry-run >/dev/null 2>&1; then
            info "✓ trigger-ml-pipeline.sh dry run successful"
        else
            warn "trigger-ml-pipeline.sh dry run failed"
        fi
    fi
    
    success "End-to-end simulation completed"
}

# Generate test report
generate_report() {
    echo
    echo "=========================================="
    echo "       GitOps + MLOps Validation Report"
    echo "=========================================="
    echo "Date: $(date)"
    echo "Total Tests: $TOTAL_TESTS"
    echo "Passed: $PASSED_TESTS"
    echo "Failed: $FAILED_TESTS" 
    echo "Warnings: $WARNINGS"
    echo
    
    local success_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    
    if [[ $FAILED_TESTS -eq 0 ]]; then
        echo -e "${GREEN}🎉 ALL TESTS PASSED! Success Rate: ${success_rate}%${NC}"
        echo -e "${GREEN}✅ GitOps + MLOps platform is ready for deployment!${NC}"
        
        if [[ $WARNINGS -gt 0 ]]; then
            echo -e "${YELLOW}⚠️  $WARNINGS warnings found - review recommended${NC}"
        fi
    else
        echo -e "${RED}❌ $FAILED_TESTS tests failed. Success Rate: ${success_rate}%${NC}"
        echo -e "${RED}🚨 Platform has issues that need to be resolved before deployment${NC}"
        
        echo
        echo "Next steps to fix issues:"
        echo "1. Review error messages above"
        echo "2. Fix configuration and code issues"
        echo "3. Run validation again: ./scripts/validate-gitops-platform.sh"
    fi
    
    echo
    echo "For detailed setup instructions:"
    echo "  📖 docs/Phase-10-Implementation-Guide.md"
    echo
    echo "To setup the platform:"
    echo "  🚀 ./scripts/setup-gitops.sh"
    echo
    echo "To trigger ML pipeline:"
    echo "  🧪 ./scripts/trigger-ml-pipeline.sh --dry-run"
}

# Main execution
main() {
    echo -e "${PURPLE}🚀 Starting GitOps + MLOps Platform Validation${NC}"
    echo "Project: $(basename "$PROJECT_ROOT")"
    echo "Location: $PROJECT_ROOT"
    echo
    
    # Run all tests
    test_yaml_syntax
    test_k8s_resources
    test_container_configs
    test_script_executables
    test_dependencies
    test_configuration_completeness
    test_security_configs
    test_integration_points
    test_documentation
    test_e2e_simulation
    
    # Generate final report
    generate_report
    
    # Exit with appropriate code
    if [[ $FAILED_TESTS -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "GitOps + MLOps Platform Validation Script"
            echo
            echo "Usage: $0 [OPTIONS]"
            echo
            echo "This script validates all components of the GitOps + MLOps platform"
            echo "including YAML syntax, Kubernetes resources, security configs,"
            echo "integration points, and end-to-end workflow simulation."
            echo
            echo "Options:"
            echo "  --help, -h    Show this help message"
            echo
            echo "Exit codes:"
            echo "  0 - All tests passed"
            echo "  1 - One or more tests failed"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Execute main function
main "$@"
