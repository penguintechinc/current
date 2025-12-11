# Claude Context & Project Information - Current

## Project Overview

- **Project Name**: Current
- **Type**: URL Shortening Service with Advanced Features
- **License**: Limited AGPL3 with preamble
- **Status**: Production-ready

## Technical Stack

- **Language**: Python 3.13
- **Framework**: FastAPI (async web framework)
- **Database**: PostgreSQL
- **Containerization**: Docker
- **Web Server**: Uvicorn

## Architecture

Current is a modern URL shortening service with:
- RESTful API for URL management
- Authentication and authorization
- Admin portal for management
- Security isolation between components
- Comprehensive testing suite

## Project Structure

```
Current/
├── shorturl-app/          # Main application
│   ├── main.py            # FastAPI entry point
│   ├── models.py          # Database models
│   ├── auth.py            # Authentication
│   ├── proxy_server.py     # Proxy/forwarding logic
│   ├── admin_portal.py     # Admin interface
│   ├── settings.py        # Configuration
│   └── apps/              # Feature modules
├── tests/                 # Test suite
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container definition
└── .version              # Version file
```

## CI/CD Pipeline (.WORKFLOW Compliance)

### Workflow Automation

Current uses GitHub Actions for continuous integration, testing, and security scanning. All workflows follow `.WORKFLOW compliance` standards.

**Workflows**:

1. **build.yml** - Continuous Integration Pipeline
   - Triggers: Push/PR to main/develop on code changes or .version updates
   - Jobs:
     - Security Scan (Bandit): Python security analysis
     - Lint: Code formatting (black), imports (isort), style (flake8)
     - Test: Unit tests with pytest
     - Build: Docker image creation with version tagging

2. **version-release.yml** - Automated Release Management
   - Triggers: Push to main when .version file changes
   - Validates semantic versioning
   - Creates pre-release with commit information
   - Skips release if version is 0.0.0 (default)

### Security Scanning

**Bandit Integration**:
- Scans `shorturl-app/` directory
- Medium severity level (`-ll`)
- Common issues: SQL injection, hardcoded credentials, insecure hashing
- Reports: JSON artifacts in workflow results
- Failure: Informational only, does not block builds

### Code Quality Standards

**Linting Requirements**:
- `black`: Code formatting (88-char lines)
- `isort`: Import organization
- `flake8`: Style and critical errors
- All must pass before build proceeds

**Test Coverage**:
- Framework: pytest with coverage tracking
- Scope: Unit tests and integration tests
- Reports: Uploaded to Codecov per PR

### Version Management (.version File)

**Format**: `MAJOR.MINOR.PATCH.EPOCH64`

**Release Process**:
- Update `.version` file with new semantic version
- Commit and push to main branch
- GitHub workflow automatically creates release

### Build Artifacts

**Security Reports**:
- `bandit-report.json`: Python security findings

**Docker Images**:
- Tags: `current:VERSION` and `current:latest`
- Registry: GHCR (GitHub Container Registry)
- Metadata: Version and build timestamp injected

## Database

**PostgreSQL**:
- Primary database for all application data
- URL mappings, user accounts, audit logs
- Migrations managed via SQLAlchemy ORM

**Connection**:
- Environment-based configuration
- Connection pooling for performance
- Support for local development and production

## Authentication & Authorization

- JWT-based authentication
- Role-based access control
- Admin vs. user roles
- Secure password hashing

## API Endpoints

**Core Endpoints**:
- `POST /shorten` - Create short URL
- `GET /{short_code}` - Resolve short URL
- `DELETE /{short_code}` - Remove short URL
- `GET /analytics/{short_code}` - URL statistics

**Admin Endpoints**:
- User management
- System configuration
- Audit log access

## Development Commands

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python shorturl-app/main.py

# Run tests
pytest tests/ -v

# Run linting
black shorturl-app/ tests/
isort shorturl-app/ tests/
flake8 shorturl-app/ tests/

# Run security scan
bandit -r shorturl-app/
```

### Docker Development

```bash
# Build image
docker build -t current:dev .

# Run container
docker run -p 8000:8000 current:dev

# Run with PostgreSQL
docker-compose up
```

## Deployment

**Development**:
- Docker Compose for local environment
- SQLite for local testing (optional)
- Live reloading for development

**Production**:
- Docker container on cloud platform
- PostgreSQL database on managed service
- Environment variables for configuration
- Reverse proxy (nginx) for routing

## Version Management

**Format**: `MAJOR.MINOR.PATCH.EPOCH64`

Example:
```
1.0.0.1702742400000  → Release v1.0.0
1.0.1.1702742500000  → Patch release
```

**Version Update Script**:
```bash
./scripts/version/update-version.sh patch  # Increment patch
```

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/current_db
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=current_db
DATABASE_USER=postgres
DATABASE_PASSWORD=secure_password

# Application
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here

# License Server
LICENSE_KEY=PENG-XXXX-XXXX-XXXX-XXXX-ABCD
LICENSE_SERVER_URL=https://license.penguintech.io
RELEASE_MODE=false
```

## Security Standards

- OWASP Top 10 compliance
- Input validation on all endpoints
- SQL injection prevention (parameterized queries)
- CSRF protection
- Secure headers (HSTS, CSP, X-Frame-Options)
- Rate limiting on sensitive endpoints
- Comprehensive audit logging

## Testing

**Unit Tests**: Core business logic
**Integration Tests**: Database interactions, API endpoints
**Security Tests**: Authentication, authorization, input validation

Run all tests:
```bash
pytest tests/ -v --cov=shorturl-app
```

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL running
docker ps | grep postgres

# Verify connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Application Startup Issues

```bash
# Check logs
docker logs container-name

# Verify dependencies
pip install -r requirements.txt

# Run migrations (if applicable)
alembic upgrade head
```

### Test Failures

```bash
# Run with verbose output
pytest tests/ -vv -s

# Run specific test
pytest tests/test_auth.py -v

# Check coverage
pytest --cov=shorturl-app
```

## Related Documentation

- [CI/CD Workflows](docs/WORKFLOWS.md) - Workflow descriptions
- [Development Standards](docs/STANDARDS.md) - Code quality requirements
- [Company Website](https://www.penguintech.io)
- [License Server](https://license.penguintech.io)

## Support

- **Issues**: GitHub Issues tracker
- **Code Review**: Pull request reviews required for main branch
- **Documentation**: See docs/ folder

## License

Limited AGPL3 with preamble. See LICENSE file for details.
