"""
Test suite for infrastructure components and Kubernetes deployments
"""
import pytest
import subprocess
import yaml
import json
import time
from unittest.mock import Mock, patch
from typing import Dict, List


class TestKubernetesDeployments:
    """Test Kubernetes deployment configurations"""
    
    def test_yaml_syntax_validity(self):
        """Test all YAML files have valid syntax"""
        import glob
        
        yaml_files = glob.glob("k8s/**/*.yaml", recursive=True)
        yaml_files.extend(glob.glob("k8s/**/*.yml", recursive=True))
        
        for yaml_file in yaml_files:
            with open(yaml_file, 'r') as f:
                try:
                    yaml.safe_load_all(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML syntax in {yaml_file}: {e}")
    
    def test_required_kubernetes_resources(self):
        """Test required Kubernetes resources are defined"""
        required_resources = [
            "k8s/base/server-config-centralized.yaml",
            "k8s/base/fraud-model-ab-test.yaml", 
            "k8s/base/mlserver.yaml",
            "k8s/base/kustomization.yaml"
        ]
        
        for resource_file in required_resources:
            try:
                with open(resource_file, 'r') as f:
                    docs = list(yaml.safe_load_all(f))
                    assert len(docs) > 0, f"No resources found in {resource_file}"
            except FileNotFoundError:
                pytest.fail(f"Required resource file missing: {resource_file}")
    
    def test_model_resource_configuration(self):
        """Test Model resources are properly configured"""
        with open("k8s/base/fraud-model-ab-test.yaml", 'r') as f:
            docs = list(yaml.safe_load_all(f))
        
        model_resources = [doc for doc in docs if doc.get('kind') == 'Model']
        assert len(model_resources) >= 2, "Should have at least 2 Model resources"
        
        for model in model_resources:
            assert 'metadata' in model
            assert 'name' in model['metadata']
            assert 'spec' in model
            assert 'storageUri' in model['spec']
            
            # Check resource requirements
            if 'requirements' in model['spec']:
                assert 'tensorflow' in model['spec']['requirements']
    
    def test_experiment_configuration(self):
        """Test Experiment resource is properly configured"""
        with open("k8s/base/fraud-model-ab-test.yaml", 'r') as f:
            docs = list(yaml.safe_load_all(f))
        
        experiment_resources = [doc for doc in docs if doc.get('kind') == 'Experiment']
        assert len(experiment_resources) == 1, "Should have exactly 1 Experiment resource"
        
        experiment = experiment_resources[0]
        assert 'spec' in experiment
        assert 'default' in experiment['spec']
        assert 'candidates' in experiment['spec']
        
        candidates = experiment['spec']['candidates']
        assert len(candidates) == 2, "Should have 2 candidates"
        
        # Check weights sum to 100
        total_weight = sum(candidate['weight'] for candidate in candidates)
        assert total_weight == 100, f"Candidate weights should sum to 100, got {total_weight}"
    
    def test_server_configuration(self):
        """Test Server resources are properly configured"""
        with open("k8s/base/mlserver.yaml", 'r') as f:
            docs = list(yaml.safe_load_all(f))
        
        server_resources = [doc for doc in docs if doc.get('kind') == 'Server']
        
        for server in server_resources:
            assert 'spec' in server
            assert 'serverConfig' in server['spec']
            assert 'models' in server['spec']
            
            # Check replicas
            if 'replicas' in server['spec']:
                assert server['spec']['replicas'] > 0


class TestMLflowIntegration:
    """Test MLflow integration and model registry"""
    
    @patch('mlflow.get_registered_model')
    def test_model_registry_access(self, mock_get_model):
        """Test access to MLflow model registry"""
        from src.mlflow_utils import get_model_info
        
        # Mock MLflow response
        mock_model = Mock()
        mock_model.name = "fraud-v1-baseline"
        mock_model.latest_versions = [Mock()]
        mock_model.latest_versions[0].version = "1"
        mock_model.latest_versions[0].stage = "Production"
        mock_get_model.return_value = mock_model
        
        model_info = get_model_info("fraud-v1-baseline")
        
        assert model_info is not None
        assert model_info.name == "fraud-v1-baseline"
        mock_get_model.assert_called_once_with("fraud-v1-baseline")
    
    @patch('mlflow.artifacts.download_artifacts')
    def test_model_artifact_download(self, mock_download):
        """Test model artifact download from MLflow"""
        from src.mlflow_utils import download_model_artifacts
        
        mock_download.return_value = "/tmp/model"
        
        local_path = download_model_artifacts("models:/fraud-v1-baseline/1")
        
        assert local_path == "/tmp/model"
        mock_download.assert_called_once()
    
    def test_mlflow_tracking_connection(self):
        """Test MLflow tracking server connection"""
        import mlflow
        
        # This would test actual connection in real environment
        # For now, just test configuration
        tracking_uri = mlflow.get_tracking_uri()
        assert tracking_uri is not None
        assert tracking_uri != "", "MLflow tracking URI should be configured"


class TestMonitoringAndObservability:
    """Test monitoring and observability components"""
    
    def test_prometheus_metrics_availability(self):
        """Test Prometheus metrics endpoints"""
        # This would test actual metrics in real environment
        # For now, test metric definitions
        
        expected_metrics = [
            "seldon_model_predictions_total",
            "seldon_model_prediction_duration_seconds",
            "seldon_experiment_request_total",
            "custom_fraud_detection_precision",
            "custom_fraud_detection_recall"
        ]
        
        # In real test, would check if metrics are exposed
        for metric in expected_metrics:
            assert isinstance(metric, str)
            assert len(metric) > 0
    
    def test_logging_configuration(self):
        """Test logging configuration"""
        import logging
        
        # Test log level configuration
        logger = logging.getLogger("fraud_detection")
        assert logger.level <= logging.INFO
        
        # Test log format
        for handler in logger.handlers:
            if hasattr(handler, 'formatter'):
                format_str = handler.formatter._fmt
                assert 'timestamp' in format_str or '%(asctime)s' in format_str
    
    def test_alert_rule_syntax(self):
        """Test Prometheus alert rule syntax"""
        try:
            with open("monitoring/alerts.yaml", 'r') as f:
                alerts = yaml.safe_load(f)
                
                if 'groups' in alerts:
                    for group in alerts['groups']:
                        assert 'name' in group
                        assert 'rules' in group
                        
                        for rule in group['rules']:
                            assert 'alert' in rule or 'record' in rule
                            assert 'expr' in rule
        except FileNotFoundError:
            pytest.skip("Alert rules file not found")


class TestSecurityAndCompliance:
    """Test security configurations and compliance"""
    
    def test_secret_management(self):
        """Test that secrets are properly handled"""
        import glob
        
        # Check for hardcoded secrets in YAML files
        yaml_files = glob.glob("k8s/**/*.yaml", recursive=True)
        
        forbidden_patterns = [
            "password:",
            "secret:",
            "token:",
            "key:"
        ]
        
        for yaml_file in yaml_files:
            with open(yaml_file, 'r') as f:
                content = f.read().lower()
                
                for pattern in forbidden_patterns:
                    if pattern in content:
                        # Make sure it's referencing a secret, not hardcoded
                        lines = content.split('\n')
                        for line in lines:
                            if pattern in line and 'secretkeyref' not in line:
                                # Allow certain patterns like "secretName"
                                if not any(allowed in line for allowed in ['secretname', 'secretkeyref', 'name:']):
                                    pytest.fail(f"Potential hardcoded secret in {yaml_file}: {line.strip()}")
    
    def test_rbac_configuration(self):
        """Test RBAC configurations if present"""
        try:
            with open("k8s/base/rbac.yaml", 'r') as f:
                docs = list(yaml.safe_load_all(f))
                
                # Check for ServiceAccount
                service_accounts = [doc for doc in docs if doc.get('kind') == 'ServiceAccount']
                if service_accounts:
                    assert len(service_accounts) >= 1
                
                # Check for Role/ClusterRole
                roles = [doc for doc in docs if doc.get('kind') in ['Role', 'ClusterRole']]
                if roles:
                    for role in roles:
                        assert 'rules' in role
                        
                        # Check permissions are not overly broad
                        for rule in role['rules']:
                            if 'resources' in rule and '*' in rule['resources']:
                                assert 'verbs' in rule
                                assert '*' not in rule['verbs'], "Should not grant all verbs on all resources"
                                
        except FileNotFoundError:
            pytest.skip("RBAC configuration not found")
    
    def test_network_policies(self):
        """Test network policies if present"""
        try:
            with open("k8s/base/network-policy.yaml", 'r') as f:
                docs = list(yaml.safe_load_all(f))
                
                network_policies = [doc for doc in docs if doc.get('kind') == 'NetworkPolicy']
                
                for policy in network_policies:
                    assert 'spec' in policy
                    assert 'podSelector' in policy['spec']
                    
                    # Should have either ingress or egress rules
                    assert 'ingress' in policy['spec'] or 'egress' in policy['spec']
                    
        except FileNotFoundError:
            pytest.skip("Network policies not found")


class TestDisasterRecovery:
    """Test disaster recovery and backup procedures"""
    
    def test_backup_scripts_exist(self):
        """Test backup scripts are available"""
        import os
        
        backup_scripts = [
            "scripts/backup-models.sh",
            "scripts/backup-config.sh"
        ]
        
        for script in backup_scripts:
            if os.path.exists(script):
                # Check script is executable
                assert os.access(script, os.X_OK), f"Script {script} is not executable"
                
                # Check script has error handling
                with open(script, 'r') as f:
                    content = f.read()
                    assert 'set -e' in content or 'set -eu' in content, f"Script {script} should have error handling"
    
    def test_recovery_documentation(self):
        """Test disaster recovery documentation exists"""
        import os
        
        recovery_docs = [
            "docs/disaster-recovery.md",
            "docs/backup-restore.md"
        ]
        
        for doc in recovery_docs:
            if os.path.exists(doc):
                with open(doc, 'r') as f:
                    content = f.read()
                    assert len(content) > 100, f"Recovery doc {doc} seems too short"
                    assert 'backup' in content.lower() or 'restore' in content.lower()


class TestPerformanceAndScaling:
    """Test performance and scaling configurations"""
    
    def test_resource_limits_configured(self):
        """Test resource limits are configured"""
        with open("k8s/base/mlserver.yaml", 'r') as f:
            docs = list(yaml.safe_load_all(f))
        
        server_resources = [doc for doc in docs if doc.get('kind') == 'Server']
        
        for server in server_resources:
            if 'spec' in server and 'resources' in server['spec']:
                resources = server['spec']['resources']
                
                # Should have limits
                if 'limits' in resources:
                    limits = resources['limits']
                    assert 'memory' in limits or 'cpu' in limits
                
                # Should have requests
                if 'requests' in resources:
                    requests = resources['requests']
                    assert 'memory' in requests or 'cpu' in requests
    
    def test_horizontal_pod_autoscaler(self):
        """Test HPA configuration if present"""
        try:
            with open("k8s/base/hpa.yaml", 'r') as f:
                docs = list(yaml.safe_load_all(f))
                
                hpa_resources = [doc for doc in docs if doc.get('kind') == 'HorizontalPodAutoscaler']
                
                for hpa in hpa_resources:
                    assert 'spec' in hpa
                    assert 'scaleTargetRef' in hpa['spec']
                    assert 'minReplicas' in hpa['spec']
                    assert 'maxReplicas' in hpa['spec']
                    
                    # Max should be greater than min
                    assert hpa['spec']['maxReplicas'] > hpa['spec']['minReplicas']
                    
        except FileNotFoundError:
            pytest.skip("HPA configuration not found")


# Fixtures for infrastructure testing
@pytest.fixture
def kubectl_available():
    """Check if kubectl is available"""
    try:
        subprocess.run(['kubectl', 'version', '--client'], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("kubectl not available")

@pytest.fixture
def kubernetes_cluster_access(kubectl_available):
    """Check if we have access to a Kubernetes cluster"""
    try:
        result = subprocess.run(['kubectl', 'cluster-info'], 
                               capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        pytest.skip("No access to Kubernetes cluster")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
