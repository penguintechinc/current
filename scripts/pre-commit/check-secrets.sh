#!/bin/bash
# Secrets Detection Script
# Checks for hardcoded credentials, API keys, tokens, and other secrets

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "=== Secrets Detection Check ==="
echo "Checking for hardcoded secrets, credentials, and tokens..."

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SECRETS_FOUND=0

# Patterns to detect secrets
PATTERNS=(
    # API Keys and tokens
    'api[_-]?key["\s]*[:=]["\s]*[a-zA-Z0-9_\-]{20,}'
    'api[_-]?token["\s]*[:=]["\s]*[a-zA-Z0-9_\-]{20,}'
    'access[_-]?token["\s]*[:=]["\s]*[a-zA-Z0-9_\-]{20,}'
    'secret[_-]?key["\s]*[:=]["\s]*[a-zA-Z0-9_\-]{20,}'

    # AWS credentials
    'AKIA[0-9A-Z]{16}'
    'aws[_-]?access[_-]?key[_-]?id["\s]*[:=]'
    'aws[_-]?secret[_-]?access[_-]?key["\s]*[:=]'

    # Private keys
    '-----BEGIN (RSA |DSA |EC )?PRIVATE KEY-----'
    '-----BEGIN OPENSSH PRIVATE KEY-----'

    # Database connection strings with passwords
    '(mysql|postgresql|postgres)://[^:]+:[^@]{8,}@'
    'mongodb://[^:]+:[^@]{8,}@'

    # Generic passwords (avoid false positives)
    'password["\s]*[:=]["\s]*[^"\s]{8,}'

    # JWT tokens
    'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'

    # GitHub tokens
    'ghp_[a-zA-Z0-9]{36}'
    'gho_[a-zA-Z0-9]{36}'
    'ghu_[a-zA-Z0-9]{36}'

    # Generic secrets
    'client[_-]?secret["\s]*[:=]["\s]*[a-zA-Z0-9_\-]{20,}'
)

# Files to exclude from scanning
EXCLUDE_PATTERNS=(
    "*.md"
    "*.json.example"
    "*.env.example"
    ".git/*"
    "node_modules/*"
    "venv/*"
    ".venv/*"
    "__pycache__/*"
    "*.pyc"
    "dist/*"
    "build/*"
    "*.log"
    ".version"
    "package-lock.json"
    "yarn.lock"
    "go.sum"
)

# Build exclude arguments for grep
EXCLUDE_ARGS=""
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    EXCLUDE_ARGS="${EXCLUDE_ARGS} --exclude=${pattern}"
done

echo "Scanning for secrets in: ${PROJECT_ROOT}"
echo ""

# Check each pattern
for pattern in "${PATTERNS[@]}"; do
    echo "Checking pattern: ${pattern:0:50}..."

    # Use grep to search for patterns
    if grep -rniE ${EXCLUDE_ARGS} --exclude-dir=".git" --exclude-dir="node_modules" \
        --exclude-dir="venv" --exclude-dir=".venv" --exclude-dir="__pycache__" \
        "${pattern}" "${PROJECT_ROOT}" 2>/dev/null; then

        echo -e "${RED}✗ Potential secret found matching pattern: ${pattern}${NC}"
        SECRETS_FOUND=$((SECRETS_FOUND + 1))
    fi
done

# Additional checks for common secret files
echo ""
echo "Checking for secret files..."

SECRET_FILES=(
    ".env"
    "credentials.json"
    "secrets.yaml"
    "secrets.yml"
    "private.key"
    "id_rsa"
    "id_dsa"
    "*.pem"
)

for file_pattern in "${SECRET_FILES[@]}"; do
    if find "${PROJECT_ROOT}" -name "${file_pattern}" -not -path "*/node_modules/*" \
        -not -path "*/.git/*" -not -path "*/venv/*" -not -path "*/.venv/*" \
        -not -name "*.example" 2>/dev/null | grep -q .; then

        echo -e "${YELLOW}⚠ Warning: Found file matching secret pattern: ${file_pattern}${NC}"
        find "${PROJECT_ROOT}" -name "${file_pattern}" -not -path "*/node_modules/*" \
            -not -path "*/.git/*" -not -path "*/venv/*" -not -path "*/.venv/*" \
            -not -name "*.example"

        # Check if file is in .gitignore
        if ! grep -q "${file_pattern}" "${PROJECT_ROOT}/.gitignore" 2>/dev/null; then
            echo -e "${RED}✗ ${file_pattern} is NOT in .gitignore!${NC}"
            SECRETS_FOUND=$((SECRETS_FOUND + 1))
        else
            echo -e "${GREEN}✓ ${file_pattern} is properly ignored in .gitignore${NC}"
        fi
    fi
done

echo ""
echo "=== Secrets Detection Summary ==="

if [ ${SECRETS_FOUND} -eq 0 ]; then
    echo -e "${GREEN}✓ No secrets detected${NC}"
    exit 0
else
    echo -e "${RED}✗ Found ${SECRETS_FOUND} potential secret(s)${NC}"
    echo ""
    echo "Please review the findings above and:"
    echo "1. Remove any hardcoded secrets from source code"
    echo "2. Use environment variables for sensitive data"
    echo "3. Ensure secret files are in .gitignore"
    echo "4. Consider using a secrets management tool (e.g., Vault, AWS Secrets Manager)"
    echo ""
    exit 1
fi
