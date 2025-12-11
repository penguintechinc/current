# Current - GitHub Workflows Documentation

This document describes all GitHub Actions workflows for the Current URL shortening service.

## Overview

Current uses GitHub Actions for continuous integration, security scanning, and automated releases. All workflows follow `.WORKFLOW compliance` standards.

## Workflows

### 1. Build and Security Scan (build.yml)

**Trigger**: Push or pull request on changes to:
- `shorturl-app/**`
- `tests/**`
- `.version`
- `.github/workflows/build.yml`
- `requirements.txt`

**Workflow Jobs**:

#### Security Scan (Bandit)
- **Tool**: Python Bandit security scanner
- **Scope**: `shorturl-app/` directory
- **Severity**: Medium and above (`-ll`)
- **Output**: JSON report artifact
- **Impact**: Informational, does not block build

#### Lint Python Code
- **Tools**:
  - `black`: Code formatter (88-char lines)
  - `isort`: Import organization
  - `flake8`: Style and critical errors
- **Scope**: `shorturl-app/` and `tests/`
- **Impact**: Blocks build on critical errors

#### Run Tests
- **Framework**: pytest with coverage tracking
- **Scope**: `tests/` directory
- **Coverage**: Reports uploaded to Codecov
- **Impact**: Blocks build on test failures

#### Build Application
- **Requires**: Successful security scan and tests
- **Output**: Docker image with version tags
- **Tags**: `current:VERSION` and `current:latest`
- **Cache**: GitHub Actions cache for faster builds

### 2. Create Release on Version Change (version-release.yml)

**Trigger**: Push to `main` branch when `.version` file changes

**Workflow Jobs**:

#### Version Detection
- Reads `.version` file
- Validates semantic versioning format
- Skips if version is 0.0.0 (default development version)
- Skips if release already exists

#### Release Creation
- Generates release notes from template
- Creates GitHub pre-release
- Includes commit SHA and branch information
- Tags release with semantic version

## Version Management

### .version File Format

```
MAJOR.MINOR.PATCH.EPOCH64
```

**Components**:
- **MAJOR**: Major version (breaking changes)
- **MINOR**: Minor version (new features)
- **PATCH**: Patch version (bug fixes)
- **EPOCH64**: Unix timestamp in milliseconds

**Examples**:
```
1.0.0.1702742400000
1.0.1.1702742500000
2.1.5.1702742600000
```

### Version Update Process

1. Make code changes in feature branch
2. Update `.version` file with new semantic version
3. Commit: `chore: bump version to X.Y.Z`
4. Push to main branch
5. Workflow automatically creates release

## Security Scanning Details

### Bandit Configuration

**What It Detects**:
- SQL injection vulnerabilities
- Hardcoded credentials and passwords
- Insecure password hashing (MD5, SHA1)
- Use of exec/eval with untrusted input
- Insecure random number generation
- Flask security issues
- Logging configuration problems

**Severity Levels**:
- **HIGH**: Critical security issues
- **MEDIUM**: Important security concerns
- **LOW**: Informational findings

**Running Locally**:
```bash
pip install bandit
bandit -r shorturl-app/ -f json -o bandit-report.json
```

## Build Artifacts

### Generated Artifacts

- **bandit-report.json**: Python security scan results
- **Docker images**: Multi-platform container images

### Artifact Retention

- Artifacts retained for workflow runs
- Available in "Artifacts" section of workflow results
- Useful for debugging and analysis

## Workflow Status

All workflows must pass before merging to main branch:
- ✅ Security scan (Bandit)
- ✅ Code formatting (black, isort)
- ✅ Linting (flake8)
- ✅ Tests (pytest)
- ✅ Docker build

## Troubleshooting

### Bandit Failures

**Common Issues**:
- Hardcoded passwords in code
- SQL query construction without parameterization
- Use of insecure functions

**Resolution**:
1. Review bandit-report.json in workflow artifacts
2. Fix the identified security issue
3. Re-run workflow

**Example Fix**:
```python
# BAD - Hardcoded credential
api_key = "sk-1234567890abcdef"

# GOOD - Use environment variable
api_key = os.environ.get('API_KEY')
```

### Lint Failures

**Black Formatting**:
```bash
black shorturl-app/ tests/
```

**isort Import Sorting**:
```bash
isort shorturl-app/ tests/
```

**flake8 Style Check**:
```bash
flake8 shorturl-app/ tests/
```

### Test Failures

**Run Tests Locally**:
```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=shorturl-app --cov-report=html
```

**Database Issues**:
- Ensure PostgreSQL is running
- Check DATABASE_URL environment variable
- Verify test database exists

### Release Failures

**Version Format Issues**:
- Verify format: `MAJOR.MINOR.PATCH.EPOCH64`
- Check `.version` file has no extra whitespace

**Release Already Exists**:
- Check GitHub releases page
- Increment patch version if needed

## Workflow Compliance Checklist

- [x] `.version` file monitoring
- [x] Epoch64 timestamp in version
- [x] Version detection and validation
- [x] Conditional metadata tags
- [x] Security scanning (Bandit)
- [x] Workflow file self-triggers
- [x] Comprehensive error handling
- [x] Artifact preservation

## Performance Optimization

- **Caching**: GitHub Actions cache for pip packages
- **Parallel Jobs**: Security and tests run simultaneously
- **Container Registry**: Push only on main branch
- **Build Time**: Typical build: 2-3 minutes

## Best Practices

1. **Local Testing**: Run lint and tests before pushing
2. **Security First**: Address Bandit findings promptly
3. **Version Discipline**: Update `.version` only for releases
4. **Artifact Review**: Check security reports for each build
5. **Test Coverage**: Maintain high test coverage

## Related Documentation

- [Standards and Conventions](STANDARDS.md)
- [Project README](../README.md)
- [CI/CD Configuration](../CLAUDE.md#cicd-pipeline-workflow-compliance)

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [pytest Documentation](https://docs.pytest.org/)
