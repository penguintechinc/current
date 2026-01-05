# Flask Backend API Tests

Test suite for the Flask backend service including unit tests, API endpoint tests, and load tests.

## Quick Start

```bash
# Run all tests (build check, unit tests, API tests)
./run-tests.sh

# Run only unit tests
./run-tests.sh --unit

# Run only API endpoint tests
./run-tests.sh --api

# Run load tests (requires running server)
./run-tests.sh --load

# Run everything including load tests
./run-tests.sh --all
```

## Test Files

| File | Description |
|------|-------------|
| `run-tests.sh` | Main test runner script |
| `test_endpoints.py` | API endpoint tests using Quart test client |
| `test_load.py` | Load/performance tests (requires running server) |

## API Endpoint Tests

Tests all REST API endpoints:
- Health checks: `/readyz`, `/livez`, `/api/v1/status`
- Auth: `/api/v1/auth/login`, `/api/v1/auth/register`, `/api/v1/auth/me`, etc.
- Users: `/api/v1/users` CRUD operations
- Error handling: 404, 405 responses

```bash
# Run with test client
python test_endpoints.py

# Run against live server
BASE_URL=http://localhost:5000 python test_endpoints.py
```

## Load Tests

Performance tests with configurable concurrency:

```bash
# Basic load test (100 requests, 10 concurrent)
BASE_URL=http://localhost:5000 python test_load.py

# Heavy load test
BASE_URL=http://localhost:5000 python test_load.py --requests 1000 --concurrency 50
```

### Performance Thresholds

| Endpoint Type | Avg Response Time |
|---------------|-------------------|
| Health checks | < 100ms |
| API endpoints | < 500ms |
| Success rate  | > 95% |

## Running from Project Root

```bash
# From project root
./tests/api/flask-backend/run-tests.sh

# Or using make (if configured)
make test-api-flask
```
