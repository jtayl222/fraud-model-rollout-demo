#!/usr/bin/env python3
"""
Integration tests for GitOps + MLOps platform
Tests the complete workflow from Git to Production
"""

import os
import sys
import json
import yaml
import subprocess
import requests
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import unittest
from unittest.mock import Mock, patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

class GitOpsIntegrationTest(unittest.TestCase):
    """Integration tests for GitOps platform"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.project_root = PROJECT_ROOT
        cls.kubectl_available = cls.check_kubectl()
        cls.argo_cli_available = cls.check_argo_cli()
        
    @classmethod
    def check_kubectl(cls) -> bool:
        """Check if kubectl is available"""
        try:
            subprocess.run(['kubectl', 'version', '--client'], 
                          capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @classmethod  
    def check_argo_cli(cls) -> bool:
        """Check if argo CLI is available"""
        try:
            subprocess.run(['argo', 'version'], 
                          capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def test_yaml_syntax_validation(self):
        """Test that all YAML files have valid syntax"""
        yaml_files = [
            'argocd/mlops-project.yaml',
            'argocd/fraud-detection-app.yaml',
            'argocd/rollback-automation.yaml',
            'argo-workflows/ml-training-pipeline.yaml',
            'k8s/base/flagger-canary.yaml',
            'monitoring/gitops-alerts.yaml',
            '.github/workflows/build-push.yml',
            '.github/workflows/deploy-staging.yml',
            '.github/workflows/production-deploy.yml'
        ]
        
        for yaml_file in yaml_files:
            file_path = self.project_root / yaml_file
            if file_path.exists():
                with open(file_path, 'r') as f:
                    try:
                        # Load all documents in the file
                        list(yaml.safe_load_all(f))
                    except yaml.YAMLError as e:
                        self.fail(f"Invalid YAML syntax in {yaml_file}: {e}")
            else:
                self.fail(f"Missing YAML file: {yaml_file}")

    def test_kubernetes_resource_validation(self):
        """Test Kubernetes resource definitions using kubectl dry-run"""
        if not self.kubectl_available:
            self.skipTest("kubectl not available")
        
        k8s_files = [
            'argocd/mlops-project.yaml',
            'argocd/fraud-detection-app.yaml', 
            'argocd/rollback-automation.yaml',
            'argo-workflows/ml-training-pipeline.yaml',
            'k8s/base/flagger-canary.yaml',
            'monitoring/gitops-alerts.yaml'
        ]
        
        for k8s_file in k8s_files:
            file_path = self.project_root / k8s_file
            if file_path.exists():
                try:
                    result = subprocess.run(
                        ['kubectl', 'apply', '--dry-run=client', '-f', str(file_path)],
                        capture_output=True, text=True, check=True
                    )
                    # Check for dry-run success indicators
                    output = result.stdout.lower() + result.stderr.lower()
                    self.assertTrue('configured' in output or 'created' in output,
                                    f"Expected dry-run success indicators in: {output}")
                except subprocess.CalledProcessError as e:
                    # Skip CRD-dependent resources if CRDs aren't installed
                    if "no matches for kind" in e.stderr and "ensure CRDs are installed first" in e.stderr:
                        self.skipTest(f"Skipping {k8s_file} - requires CRDs to be installed: {e.stderr}")
                    else:
                        self.fail(f"Invalid K8s resources in {k8s_file}: {e.stderr}")

    def test_argocd_project_configuration(self):
        """Test ArgoCD project configuration completeness"""
        project_file = self.project_root / 'argocd/mlops-project.yaml'
        self.assertTrue(project_file.exists(), "ArgoCD project file missing")
        
        with open(project_file, 'r') as f:
            project_config = yaml.safe_load(f)
        
        # Validate project structure
        self.assertEqual(project_config['kind'], 'AppProject')
        self.assertIn('spec', project_config)
        
        spec = project_config['spec']
        required_fields = ['sourceRepos', 'destinations', 'roles']
        for field in required_fields:
            self.assertIn(field, spec, f"Missing {field} in ArgoCD project")
        
        # Validate RBAC roles
        roles = spec['roles']
        self.assertGreater(len(roles), 0, "No RBAC roles defined")
        
        required_roles = ['ml-engineer', 'ml-reviewer', 'readonly']
        role_names = [role['name'] for role in roles]
        for required_role in required_roles:
            self.assertIn(required_role, role_names, f"Missing role: {required_role}")

    def test_argo_workflows_pipeline(self):
        """Test Argo Workflows pipeline configuration"""
        pipeline_file = self.project_root / 'argo-workflows/ml-training-pipeline.yaml'
        self.assertTrue(pipeline_file.exists(), "Argo Workflows pipeline file missing")
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = yaml.safe_load(f)
        
        # Validate workflow structure
        self.assertEqual(pipeline_config['kind'], 'WorkflowTemplate')
        self.assertIn('spec', pipeline_config)
        
        spec = pipeline_config['spec']
        self.assertIn('templates', spec, "No templates defined in workflow")
        
        # Check for required workflow steps
        templates = spec['templates']
        template_names = [t['name'] for t in templates]
        
        required_steps = [
            'ml-pipeline', 'git-clone', 'data-preparation', 'data-validation',
            'train-model', 'model-evaluation', 'container-build', 
            'update-k8s-manifest', 'argocd-sync'
        ]
        
        for step in required_steps:
            self.assertIn(step, template_names, f"Missing workflow step: {step}")
        
        # Validate DAG structure
        ml_pipeline = next(t for t in templates if t['name'] == 'ml-pipeline')
        self.assertIn('dag', ml_pipeline, "ML pipeline should use DAG")
        
        dag_tasks = ml_pipeline['dag']['tasks']
        task_names = [task['name'] for task in dag_tasks]
        
        expected_tasks = [
            'clone-repo', 'prepare-data', 'validate-data', 
            'train-baseline', 'train-candidate', 'evaluate-models'
        ]
        
        for task in expected_tasks:
            self.assertIn(task, task_names, f"Missing DAG task: {task}")

    def test_flagger_canary_configuration(self):
        """Test Flagger canary deployment configuration"""
        canary_file = self.project_root / 'k8s/base/flagger-canary.yaml'
        self.assertTrue(canary_file.exists(), "Flagger canary file missing")
        
        with open(canary_file, 'r') as f:
            canary_docs = list(yaml.safe_load_all(f))
        
        # Find canary resource
        canary_config = None
        for doc in canary_docs:
            if doc and doc.get('kind') == 'Canary':
                canary_config = doc
                break
        
        self.assertIsNotNone(canary_config, "Canary resource not found")
        
        # Validate canary structure
        spec = canary_config['spec']
        required_fields = ['targetRef', 'analysis', 'service']
        for field in required_fields:
            self.assertIn(field, spec, f"Missing {field} in canary spec")
        
        # Validate analysis configuration
        analysis = spec['analysis']
        self.assertIn('interval', analysis, "Missing analysis interval")
        self.assertIn('metrics', analysis, "Missing analysis metrics")
        
        # Check for ML-specific metrics
        metrics = analysis['metrics']
        metric_names = [m['name'] for m in metrics]
        
        expected_metrics = ['model-precision', 'model-recall', 'model-f1-score']
        for metric in expected_metrics:
            self.assertIn(metric, metric_names, f"Missing metric: {metric}")

    def test_monitoring_configuration(self):
        """Test monitoring and alerting configuration"""
        alerts_file = self.project_root / 'monitoring/gitops-alerts.yaml'
        self.assertTrue(alerts_file.exists(), "GitOps alerts file missing")
        
        with open(alerts_file, 'r') as f:
            alerts_config = yaml.safe_load(f)
        
        # Validate Prometheus rule structure
        self.assertEqual(alerts_config['kind'], 'PrometheusRule')
        self.assertIn('spec', alerts_config)
        
        spec = alerts_config['spec']
        self.assertIn('groups', spec, "No alert groups defined")
        
        # Check for required alert groups
        groups = spec['groups']
        group_names = [g['name'] for g in groups]
        
        expected_groups = [
            'gitops.deployment', 'argo.workflows', 'flagger.canary', 
            'mlops.model.performance', 'gitops.infrastructure'
        ]
        
        for group in expected_groups:
            self.assertIn(group, group_names, f"Missing alert group: {group}")
        
        # Validate alert rules
        total_rules = sum(len(g.get('rules', [])) for g in groups)
        self.assertGreater(total_rules, 10, "Too few alert rules defined")

    def test_github_actions_workflows(self):
        """Test GitHub Actions workflow configurations"""
        workflow_files = [
            '.github/workflows/build-push.yml',
            '.github/workflows/deploy-staging.yml', 
            '.github/workflows/production-deploy.yml'
        ]
        
        for workflow_file in workflow_files:
            file_path = self.project_root / workflow_file
            self.assertTrue(file_path.exists(), f"Missing workflow: {workflow_file}")
            
            with open(file_path, 'r') as f:
                workflow_config = yaml.safe_load(f)
            
            # Validate workflow structure
            self.assertIn('name', workflow_config, f"Missing name in {workflow_file}")
            self.assertIn('on', workflow_config, f"Missing triggers in {workflow_file}")
            self.assertIn('jobs', workflow_config, f"Missing jobs in {workflow_file}")
            
            # Check for environment variables
            jobs = workflow_config['jobs']
            for job_name, job_config in jobs.items():
                if 'env' in job_config:
                    env_vars = job_config['env']
                    # Should reference secrets, not hardcode values
                    for var, value in env_vars.items():
                        if isinstance(value, str) and 'secret' not in value.lower():
                            # Allow some hardcoded values like URLs
                            allowed_hardcoded = ['http', 'https', 'localhost', 'fraud-detection']
                            if not any(allowed in value.lower() for allowed in allowed_hardcoded):
                                self.fail(f"Potential hardcoded secret in {workflow_file}: {var}")

    def test_script_executability(self):
        """Test that scripts are executable and have valid syntax"""
        scripts = [
            'scripts/setup-gitops.sh',
            'scripts/trigger-ml-pipeline.sh',
            'scripts/validate-gitops-platform.sh'
        ]
        
        for script in scripts:
            script_path = self.project_root / script
            self.assertTrue(script_path.exists(), f"Missing script: {script}")
            
            # Check executable permission
            self.assertTrue(os.access(script_path, os.X_OK), 
                          f"Script not executable: {script}")
            
            # Check bash syntax
            try:
                result = subprocess.run(
                    ['bash', '-n', str(script_path)],
                    capture_output=True, text=True, check=True
                )
            except subprocess.CalledProcessError as e:
                self.fail(f"Bash syntax error in {script}: {e.stderr}")

    def test_security_configurations(self):
        """Test security-related configurations"""
        # Check for hardcoded secrets
        sensitive_files = [
            'argocd/mlops-project.yaml',
            'argocd/fraud-detection-app.yaml',
            'argo-workflows/ml-training-pipeline.yaml'
        ]
        
        secret_patterns = [
            'password:', 'secret:', 'token:', 'key:',
            'aws_secret'
        ]
        
        for file_path in sensitive_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                with open(full_path, 'r') as f:
                    content = f.read().lower()
                
                for pattern in secret_patterns:
                    if pattern in content:
                        # Check if it's a proper secret reference
                        lines_with_pattern = [
                            line for line in content.split('\n') 
                            if pattern in line
                        ]
                        
                        # Split content into lines for context checking
                        lines = content.split('\n')
                        for i, full_line in enumerate(lines):
                            line = full_line.lower()
                            if pattern in line:
                                # Allow secretKeyRef, secretName patterns, and Kubernetes secret volumes
                                if ('secretkeyref' in line or 'secretname' in line or 
                                    line.strip() == 'secret:'):
                                    continue
                                    
                                # Check if this line is part of a secretKeyRef block
                                in_secret_ref_context = False
                                # Look at preceding lines for secretKeyRef context
                                for j in range(max(0, i-5), i):
                                    prev_line = lines[j].lower().strip()
                                    if 'secretkeyref:' in prev_line:
                                        in_secret_ref_context = True
                                        break
                                    # Also check if we're under valueFrom
                                    if 'valuefrom:' in prev_line:
                                        # Look ahead to see if secretKeyRef follows
                                        for k in range(j+1, min(len(lines), j+5)):
                                            if 'secretkeyref:' in lines[k].lower():
                                                in_secret_ref_context = True
                                                break
                                        break
                                
                                if in_secret_ref_context:
                                    continue
                                    
                                # Allow comments and documentation
                                if not line.strip().startswith('#'):
                                    self.fail(f"Potential hardcoded secret in {file_path}: {line.strip()}")

    def test_integration_endpoints(self):
        """Test integration endpoint configurations"""
        # Test MLflow integration
        pipeline_file = self.project_root / 'argo-workflows/ml-training-pipeline.yaml'
        with open(pipeline_file, 'r') as f:
            content = f.read()
        
        self.assertIn('MLFLOW_TRACKING_URI', content, 
                     "MLflow tracking URI not configured")
        
        # Test Harbor registry integration
        self.assertIn('harbor', content.lower(), 
                     "Harbor registry not configured")
        
        # Test ArgoCD integration
        self.assertIn('argocd-sync', content, 
                     "ArgoCD sync not configured")

    @unittest.skipUnless(os.environ.get('RUN_LIVE_TESTS'), 
                        "Live tests disabled, set RUN_LIVE_TESTS=1 to enable")
    def test_kubectl_connectivity(self):
        """Test kubectl connectivity to cluster"""
        if not self.kubectl_available:
            self.skipTest("kubectl not available")
        
        try:
            result = subprocess.run(
                ['kubectl', 'cluster-info'],
                capture_output=True, text=True, check=True, timeout=10
            )
            self.assertIn('running', result.stdout.lower())
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            self.fail(f"Cannot connect to Kubernetes cluster: {e}")

    @unittest.skipUnless(os.environ.get('RUN_LIVE_TESTS'),
                        "Live tests disabled, set RUN_LIVE_TESTS=1 to enable")
    def test_argocd_connectivity(self):
        """Test ArgoCD server connectivity"""
        if not self.kubectl_available:
            self.skipTest("kubectl not available")
        
        try:
            # Check if ArgoCD namespace exists
            result = subprocess.run(
                ['kubectl', 'get', 'namespace', 'argocd'],
                capture_output=True, text=True, check=True
            )
            self.assertIn('argocd', result.stdout)
            
            # Check if ArgoCD server is running
            result = subprocess.run(
                ['kubectl', 'get', 'pods', '-n', 'argocd', '-l', 'app.kubernetes.io/name=argocd-server'],
                capture_output=True, text=True, check=True
            )
            self.assertIn('Running', result.stdout)
            
        except subprocess.CalledProcessError as e:
            self.fail(f"ArgoCD server not accessible: {e}")

    @unittest.skipUnless(os.environ.get('RUN_LIVE_TESTS'),
                        "Live tests disabled, set RUN_LIVE_TESTS=1 to enable")
    def test_argo_workflows_connectivity(self):
        """Test Argo Workflows server connectivity"""
        if not self.kubectl_available:
            self.skipTest("kubectl not available")
        
        try:
            # Check if Argo Workflows namespace exists
            result = subprocess.run(
                ['kubectl', 'get', 'namespace', 'argowf'],
                capture_output=True, text=True, check=True
            )
            self.assertIn('argowf', result.stdout)
            
        except subprocess.CalledProcessError as e:
            self.fail(f"Argo Workflows not accessible: {e}")

    def test_end_to_end_dry_run(self):
        """Test end-to-end workflow simulation"""
        # Test setup script dry run
        setup_script = self.project_root / 'scripts/setup-gitops.sh'
        if setup_script.exists():
            try:
                result = subprocess.run(
                    [str(setup_script), '--dry-run'],
                    capture_output=True, text=True, timeout=30
                )
                # Script should handle dry-run gracefully
                self.assertIn('DRY RUN', result.stdout + result.stderr)
            except subprocess.TimeoutExpired:
                self.fail("Setup script dry run timed out")
            except Exception as e:
                self.fail(f"Setup script dry run failed: {e}")
        
        # Test pipeline trigger dry run  
        trigger_script = self.project_root / 'scripts/trigger-ml-pipeline.sh'
        if trigger_script.exists():
            try:
                result = subprocess.run(
                    [str(trigger_script), '--dry-run'],
                    capture_output=True, text=True, timeout=30
                )
                # Should show workflow without submitting
                self.assertEqual(result.returncode, 0)
            except subprocess.TimeoutExpired:
                self.fail("Pipeline trigger dry run timed out")
            except Exception as e:
                self.fail(f"Pipeline trigger dry run failed: {e}")


class TestUtilities:
    """Utility functions for testing"""
    
    @staticmethod
    def run_comprehensive_validation():
        """Run the comprehensive validation script"""
        validation_script = PROJECT_ROOT / 'scripts/validate-gitops-platform.sh'
        if validation_script.exists():
            try:
                result = subprocess.run(
                    [str(validation_script)],
                    capture_output=True, text=True, timeout=120
                )
                return result.returncode == 0, result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                return False, "Validation script timed out"
            except Exception as e:
                return False, f"Validation script failed: {e}"
        else:
            return False, "Validation script not found"


def run_quick_validation():
    """Quick validation function that can be called directly"""
    print("🧪 Running GitOps + MLOps Integration Tests...")
    
    # Run unittest suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(GitOpsIntegrationTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("✅ All integration tests passed!")
        
        # Run comprehensive validation
        print("\n🔍 Running comprehensive validation...")
        success, output = TestUtilities.run_comprehensive_validation()
        
        if success:
            print("✅ Comprehensive validation passed!")
            print("\n🚀 GitOps + MLOps platform is ready for deployment!")
            return True
        else:
            print("❌ Comprehensive validation failed:")
            print(output)
            return False
    else:
        print(f"❌ {len(result.failures + result.errors)} integration tests failed")
        return False


if __name__ == '__main__':
    # Can be run directly for quick validation
    if len(sys.argv) > 1 and sys.argv[1] == 'quick':
        success = run_quick_validation()
        sys.exit(0 if success else 1)
    else:
        unittest.main()
