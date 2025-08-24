#!/bin/bash
# Cleanup script to remove redundant/experimental files from Pattern 3 branch

echo "🧹 Cleaning up redundant files from Pattern 3 branch..."

# Remove AI/Development artifacts
echo "Removing development artifacts..."
git rm -f .claude/settings.local.json
git rm -f fraud-detection-ml-secrets-20250722.tar.gz
git rm -f seldon-system-ml-secrets-20250719.tar.gz

# Remove one-time use scripts
echo "Removing one-time scripts..."
git rm -f scripts/seldon-architecture-diagram.py

# Remove experimental/incomplete files
echo "Removing experimental files..."
git rm -f data.ipynb
git rm -f docs/Phase-12-Hodometer-Analytics-Configuration.md
git rm -rf k8s/multi-namespace/
git rm -rf k8s/manifests/

# Remove superseded documentation
echo "Removing superseded documentation..."
git rm -f docs/seldon-production-architecture-decision.md
git rm -f docs/istio-gateway-config.yaml

echo "✅ Cleanup complete!"
echo ""
echo "Files removed from git:"
echo "- .claude/settings.local.json"
echo "- fraud-detection-ml-secrets-20250722.tar.gz"
echo "- seldon-system-ml-secrets-20250719.tar.gz"
echo "- scripts/seldon-architecture-diagram.py"
echo "- data.ipynb"
echo "- docs/Phase-12-Hodometer-Analytics-Configuration.md"
echo "- k8s/multi-namespace/ (directory)"
echo "- k8s/manifests/ (directory)"
echo "- docs/seldon-production-architecture-decision.md"
echo "- docs/istio-gateway-config.yaml"
echo ""
echo "Next steps:"
echo "1. Review remaining files in git diff main.. --name-only"
echo "2. Commit the cleanup: git commit -m 'Clean up redundant files for Pattern 3'"
echo "3. Files remaining are essential for Pattern 3 migration"
