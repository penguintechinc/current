#!/bin/bash
# Secret Detection Pre-Commit Checks
# Scans for accidentally committed secrets

set -e

PROJECT_ROOT="${1:-.}"

echo "Secret Detection Pre-Commit Checks"
echo "==================================="
echo "Project: ${PROJECT_ROOT}"
echo ""

FAILED=0

# Patterns to search for
declare -a SECRET_PATTERNS=(
    # API Keys
    'api[_-]?key\s*[:=]\s*["\047][a-zA-Z0-9]{20,}["\047]'
    'apikey\s*[:=]\s*["\047][a-zA-Z0-9]{20,}["\047]'

    # AWS
    'AKIA[0-9A-Z]{16}'
    'aws[_-]?secret[_-]?access[_-]?key'

    # Generic secrets
    'secret[_-]?key\s*[:=]\s*["\047][^\047"]{8,}["\047]'
    'password\s*[:=]\s*["\047][^\047"]{8,}["\047]'
    'passwd\s*[:=]\s*["\047][^\047"]{8,}["\047]'

    # Private keys
    '-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'
    '-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----'

    # Tokens
    'bearer\s+[a-zA-Z0-9_\-\.]{20,}'
    'token\s*[:=]\s*["\047][a-zA-Z0-9_\-\.]{20,}["\047]'

    # Database URLs with credentials
    '(mysql|postgresql|postgres|mongodb)://[^:]+:[^@]+@'

    # JWT
    'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*'
)

# Files to exclude
EXCLUDE_PATTERNS="*.log|*.lock|node_modules|.git|venv|.venv|__pycache__|*.pyc|dist|build"

echo "Scanning for secrets..."
echo ""

# Check for common secret files that shouldn't be committed
echo "--- Checking for sensitive files ---"
SENSITIVE_FILES=(
    ".env"
    ".env.local"
    ".env.production"
    "credentials.json"
    "secrets.json"
    "*.pem"
    "*.key"
    "id_rsa"
    "id_ed25519"
    ".htpasswd"
    "*.pfx"
    "*.p12"
)

for pattern in "${SENSITIVE_FILES[@]}"; do
    if find "$PROJECT_ROOT" -name "$pattern" -type f -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/venv/*" 2>/dev/null | grep -q .; then
        echo "WARNING: Found potentially sensitive file matching: $pattern"
        find "$PROJECT_ROOT" -name "$pattern" -type f -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/venv/*" 2>/dev/null
        ((FAILED++))
    fi
done

echo ""
echo "--- Scanning code for secrets ---"

# Use git-secrets if available
if command -v git-secrets &> /dev/null; then
    echo "Running git-secrets..."
    cd "$PROJECT_ROOT"
    if ! git secrets --scan 2>&1; then
        echo "git-secrets found potential secrets"
        ((FAILED++))
    fi
    cd - > /dev/null
# Use gitleaks if available
elif command -v gitleaks &> /dev/null; then
    echo "Running gitleaks..."
    if ! gitleaks detect --source "$PROJECT_ROOT" --no-git 2>&1; then
        echo "gitleaks found potential secrets"
        ((FAILED++))
    fi
# Fallback to grep
else
    echo "Using grep pattern matching (install git-secrets or gitleaks for better detection)..."

    for pattern in "${SECRET_PATTERNS[@]}"; do
        matches=$(grep -rniE "$pattern" "$PROJECT_ROOT" \
            --include="*.py" \
            --include="*.js" \
            --include="*.ts" \
            --include="*.jsx" \
            --include="*.tsx" \
            --include="*.go" \
            --include="*.yml" \
            --include="*.yaml" \
            --include="*.json" \
            --include="*.env*" \
            --include="*.conf" \
            --include="*.config" \
            --exclude-dir=node_modules \
            --exclude-dir=.git \
            --exclude-dir=venv \
            --exclude-dir=.venv \
            --exclude-dir=dist \
            --exclude-dir=build \
            2>/dev/null || true)

        if [ -n "$matches" ]; then
            echo "Potential secret found matching pattern:"
            echo "$matches" | head -5
            echo "..."
            ((FAILED++))
        fi
    done
fi

echo ""
echo "========================================"
if [ "$FAILED" -eq 0 ]; then
    echo "No secrets detected!"
    exit 0
else
    echo "Secret detection found $FAILED potential issues"
    echo "Please review and remove any secrets before committing"
    exit 1
fi
