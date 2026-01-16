# Testing Guide

## Overview

The ShortURL application includes a comprehensive test suite to ensure code quality and functionality.

## Test Structure

```
tests/
├── __init__.py
├── test_security_isolated.py    # Security function tests
├── test_utils.py               # Utility function tests  
├── test_integration.py         # Integration tests
├── test_startup.py            # Application startup tests
└── (other test files)
```

## Running Tests

### Quick Test Run
```bash
# Run all tests
python3 run_tests.py

# Run specific test module
python3 -m unittest tests.test_security_isolated -v

# Run multiple specific tests
python3 -m unittest tests.test_security_isolated tests.test_utils -v
```

### With pytest (if available)
```bash
# Install dev dependencies first
pip install -r shorturl-app/requirements-dev.txt

# Run with pytest
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=shorturl-app --cov-report=html
```

## Test Categories

### 1. Security Tests (`test_security_isolated.py`)

Tests security-related functions without external dependencies:

- **Input Sanitization**: XSS prevention, HTML escaping
- **URL Validation**: SSRF prevention, protocol validation, internal IP blocking
- **Short Code Validation**: Path traversal prevention, character validation
- **SQL Injection Prevention**: Pattern detection, input validation

Key test methods:
- `test_sanitize_input()` - Tests XSS and HTML escaping
- `test_validate_url()` - Tests URL validation and SSRF prevention
- `test_validate_short_code()` - Tests short code format validation
- `test_check_sql_injection()` - Tests SQL injection pattern detection

### 2. Utility Tests (`test_utils.py`)

Tests core utility functions:

- **Short Code Generation**: Uniqueness, length validation
- **Password Hashing**: SHA256 hashing, verification
- **Reserved Path Validation**: Admin path protection
- **Role Validation**: RBAC permission checking

Key test methods:
- `test_generate_short_code()` - Tests random code generation
- `test_hash_password()` - Tests password hashing and verification
- `test_reserved_paths()` - Tests reserved path detection
- `test_role_validation()` - Tests role-based permissions

### 3. Integration Tests (`test_integration.py`)

Tests application integration and file structure:

- **File Existence**: Verifies required files exist
- **Python Syntax**: Validates all Python files compile
- **Environment Variables**: Tests configuration handling
- **Directory Structure**: Validates project organization

Key test methods:
- `test_docker_build_files_exist()` - Verifies Docker build files
- `test_python_files_syntax()` - Validates Python syntax
- `test_environment_variables()` - Tests env var handling
- `test_directory_structure()` - Validates project structure

### 4. Startup Tests (`test_startup.py`)

Tests application startup and configuration:

- **Main Application Structure**: Validates main.py organization
- **Settings Configuration**: Verifies required settings exist
- **Docker Configuration**: Validates Dockerfile and docker-compose.yml
- **GitHub Workflows**: Verifies CI/CD configuration

Key test methods:
- `test_main_py_structure()` - Validates main application structure
- `test_settings_structure()` - Tests configuration completeness
- `test_dockerfile_structure()` - Validates Docker configuration
- `test_github_workflows_exist()` - Verifies CI/CD setup

## Test Results

Current test coverage:

```
============================================================
TEST SUMMARY
============================================================
Total tests run: 19
Failures: 0
Errors: 0
Success rate: 100.0%
```

### Test Breakdown:
- **Security Tests**: 4 tests ✅
- **Utility Tests**: 4 tests ✅
- **Integration Tests**: 4 tests ✅
- **Startup Tests**: 7 tests ✅

## Continuous Integration

### GitHub Actions Integration

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests
- Release creation

See `.github/workflows/build-and-test.yml` for full CI configuration.

### Local Pre-commit Testing

Run tests locally before committing:

```bash
# Quick syntax check
find shorturl-app -name "*.py" -exec python3 -m py_compile {} \;

# Full test suite
python3 run_tests.py

# Check specific functionality
python3 -m unittest tests.test_security_isolated.test_validate_url -v
```

## Adding New Tests

### Test File Structure

```python
import unittest

class TestNewFeature(unittest.TestCase):
    """Test new feature functionality"""
    
    def test_feature_functionality(self):
        """Test that feature works correctly"""
        # Arrange
        input_data = "test_input"
        
        # Act
        result = your_function(input_data)
        
        # Assert
        self.assertEqual(result, expected_output)
        
if __name__ == '__main__':
    unittest.main()
```

### Best Practices

1. **Isolated Tests**: Tests should not depend on external services
2. **Clear Names**: Test method names should describe what's being tested
3. **AAA Pattern**: Arrange, Act, Assert structure
4. **Mock Dependencies**: Use mocks for external dependencies
5. **Edge Cases**: Test both success and failure scenarios

### Test Categories to Add

When extending the application, consider adding tests for:

- **Database Operations**: Test PyDAL models and queries
- **API Endpoints**: Test HTTP request/response handling  
- **Authentication**: Test login/logout and session management
- **URL Redirection**: Test proxy functionality
- **Analytics**: Test data collection and reporting
- **Certificate Management**: Test SSL/TLS certificate handling

## Performance Testing

For performance testing (not included in unit tests):

```bash
# Load testing with Apache Bench
ab -n 1000 -c 10 http://localhost/test123

# Memory profiling
python3 -m memory_profiler shorturl-app/main.py

# CPU profiling  
python3 -m cProfile shorturl-app/main.py
```

## Troubleshooting Tests

### Common Issues

1. **Import Errors**: 
   ```bash
   # Ensure Python path is correct
   export PYTHONPATH=/path/to/shorturl-app:$PYTHONPATH
   ```

2. **Missing Dependencies**:
   ```bash
   # Install test dependencies
   pip install -r shorturl-app/requirements-dev.txt
   ```

3. **Path Issues**:
   ```bash
   # Run from project root
   cd /path/to/shorturl
   python3 run_tests.py
   ```

### Debugging Failed Tests

```bash
# Run with maximum verbosity
python3 -m unittest tests.test_name -v

# Run single test method
python3 -m unittest tests.test_security_isolated.TestSecurityIsolated.test_validate_url -v

# Add debug prints to test methods
def test_function(self):
    result = function_to_test()
    print(f"Debug: result = {result}")
    self.assertEqual(result, expected)
```