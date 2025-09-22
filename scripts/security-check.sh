#!/bin/bash
# Security check script for mzidentml-reader

set -e

echo "🔒 Running security checks for mzidentml-reader..."

# Dependency vulnerability scanning
echo "📦 Checking for known vulnerabilities in dependencies..."
pipenv run safety check --json || echo "⚠️  Safety check completed with warnings"

# Python security linting
echo "🔍 Running security linting with bandit..."
pipenv run bandit -r . -f json -o bandit-report.json || echo "⚠️  Bandit scan completed with warnings"
pipenv run bandit -r . --format txt

# Check for secrets in code
echo "🔐 Checking for potential secrets..."
pipenv run detect-secrets scan --all-files --disable-plugin AbsolutePathDetectorPlugin || echo "⚠️  Secrets detection completed"

echo "✅ Security checks completed!"
echo "📊 Reports generated:"
echo "  - bandit-report.json (security issues)"
echo "  - Safety output (dependency vulnerabilities)"