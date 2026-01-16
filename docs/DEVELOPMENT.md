# Local Development Guide

Complete guide to setting up a local development environment for the Current shorturl application, running the application locally, and following the development workflow.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Starting Development Environment](#starting-development-environment)
4. [Development Workflow](#development-workflow)
5. [Common Tasks](#common-tasks)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **macOS 12+**, **Linux (Ubuntu 20.04+)**, or **Windows 10+ with WSL2**
- **Docker Desktop** 4.0+ (or Docker Engine 20.10+)
- **Docker Compose** 2.0+
- **Git** 2.30+
- **Python** 3.13+ (for local development without Docker)
- **PostgreSQL** 14+ (if running database locally)
- **Redis** 6.0+ (optional, for caching)

### Optional Tools

- **Docker Buildx** (for multi-architecture builds)
- **Helm** (for Kubernetes deployments)
- **kubectl** (for Kubernetes clusters)

### Installation

**macOS (Homebrew)**:
```bash
brew install docker docker-compose git python
brew install --cask docker
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git python3.13
sudo usermod -aG docker $USER  # Allow docker without sudo
newgrp docker                   # Activate group change
```

**Verify Installation**:
```bash
docker --version      # Docker 20.10+
docker-compose --version  # Docker Compose 2.0+
git --version
python3 --version     # Python 3.13+
```

---

## Initial Setup

### Clone Repository

```bash
git clone <repository-url>
cd Current
```

### Install Dependencies

```bash
# Install Python dependencies
pip install -r shorturl-app/requirements.txt
pip install -r shorturl-app/requirements-dev.txt
```

### Environment Configuration

Copy and customize environment files:

```bash
# Copy example environment files
cp .env.example .env 2>/dev/null || cat > .env << 'EOF'
# Database
DB_TYPE=sqlite
DB_HOST=localhost
DB_PORT=5432
DB_NAME=current_dev.db
DB_USER=postgres
DB_PASSWORD=postgres

# Flask/Py4Web Backend
FLASK_ENV=development
SECRET_KEY=your-secret-key-for-dev

# License (Development - all features available)
RELEASE_MODE=false
LICENSE_KEY=not-required-in-dev

# Port Configuration
SHORTURL_PORT=5000
REDIS_PORT=6379

# Admin Portal
ADMIN_PORT=8001

# Proxy Server
PROXY_PORT=8002
EOF
```

**Key Environment Variables**:
```bash
# Database
DB_TYPE=sqlite              # sqlite, postgresql, mysql, mariadb
DB_HOST=localhost
DB_PORT=5432
DB_NAME=current_dev.db
DB_USER=postgres
DB_PASSWORD=postgres

# Application
FLASK_ENV=development
SECRET_KEY=your-secret-key-for-dev

# License (Development)
RELEASE_MODE=false
LICENSE_KEY=not-required-in-dev

# Port Configuration
SHORTURL_PORT=5000
ADMIN_PORT=8001
PROXY_PORT=8002
REDIS_PORT=6379
```

### Database Initialization

```bash
# Create database and run migrations (automatic on startup with PyDAL)
# SQLite database will be created automatically in current_dev.db

# For PostgreSQL (optional):
# createdb current_dev
# psql current_dev < schema.sql  # If schema file exists
```

---

## Starting Development Environment

### Quick Start (Docker Compose)

```bash
# Start all services in one command
docker-compose up -d

# This runs:
# - PostgreSQL database (if configured)
# - Redis cache (optional)
# - Py4Web shorturl application (port 5000)
# - Admin portal (port 8001)
# - Proxy server (port 8002)

# Access the application:
# Main App:      http://localhost:5000
# Admin Portal:  http://localhost:8001
# Proxy Server:  http://localhost:8002
```

### Local Development (Without Docker)

```bash
# Start from the shorturl-app directory
cd shorturl-app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run the main application
python main.py

# In another terminal, run admin portal
python admin_portal.py

# In another terminal, run proxy server
python proxy_server.py
```

### Service Management

**View service logs**:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f shorturl-app

# Last 100 lines, follow new entries
docker-compose logs -f --tail=100 shorturl-app
```

**Stop services**:
```bash
# Stop all services (keep data)
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Restart services
docker-compose restart

# Rebuild and restart (apply code changes)
docker-compose down && docker-compose up -d --build
```

### Development Docker Compose Files

- **`docker-compose.dev.yml`**: Local development (hot-reload, debug ports)
- **`docker-compose.yml`**: Production-like (health checks, resource limits)

Use dev version locally:
```bash
docker-compose -f docker-compose.dev.yml up
```

---

## Development Workflow

### 1. Start Development Environment

```bash
docker-compose up -d  # Start all services
```

### 2. Make Code Changes

Edit files in your favorite editor. Services may need restart:

- **Python (Py4Web)**: Hot-reload enabled (auto-refresh on file save)
- **Changes to dependencies**: Requires container rebuild (`docker-compose up -d --build`)

### 3. Verify Changes

```bash
# Run linters
cd shorturl-app
flake8 .
black --check .
isort --check-only .

# Run unit tests
pytest tests/

# Run security check
bandit -r apps/ -ll
```

### 4. Test Endpoints

```bash
# Health check
curl http://localhost:5000/health

# API endpoints
curl -X POST http://localhost:5000/api/v1/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "custom_code": "ex"}'

# Check admin portal
curl http://localhost:8001/

# Proxy server health
curl http://localhost:8002/health
```

### 5. Run Pre-Commit Checklist

Before committing, run comprehensive checks:

```bash
# All linting, security, and tests
cd shorturl-app

# Linting
flake8 .
black .
isort .

# Security scanning
bandit -r apps/ -ll
safety check

# Run tests
pytest tests/ -v --cov=apps

# Build Docker image
docker build -t shorturl-app:test .
```

### 6. Testing & Validation

Comprehensive testing:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_urlshortener.py -v

# Run with coverage
pytest tests/ --cov=apps

# Unit tests only
pytest tests/ -v -m "not integration"
```

See [Testing Documentation](TESTING.md) for complete testing guide.

### 7. Create Pull Request

Once tests pass:

```bash
# Push branch
git push origin feature-branch-name

# Create PR via GitHub CLI
gh pr create --title "Brief feature description" \
  --body "Detailed description of changes"
```

---

## Common Tasks

### Adding a New Python Dependency

```bash
# Add to shorturl-app/requirements.txt
echo "new-package==1.0.0" >> shorturl-app/requirements.txt

# Rebuild application container
docker-compose up -d --build shorturl-app

# Verify import works
docker-compose exec shorturl-app python -c "import new_package"
```

### Adding a New Environment Variable

```bash
# Add to .env
echo "NEW_VAR=value" >> .env

# Restart services to pick up new variable
docker-compose restart

# Verify it's set
docker-compose exec shorturl-app printenv | grep NEW_VAR
```

### Debugging a Service

**View logs in real-time**:
```bash
docker-compose logs -f shorturl-app
```

**Access container shell**:
```bash
docker-compose exec shorturl-app bash
```

**Execute commands in container**:
```bash
# Run Python script
docker-compose exec shorturl-app python -c "print('hello')"

# Check service health
docker-compose exec shorturl-app curl http://localhost:5000/health
```

### Database Operations

**Connect to database**:
```bash
# PostgreSQL
docker-compose exec postgres psql -U postgres -d current_dev

# SQLite
sqlite3 current_dev.db
```

**Reset database**:
```bash
# Full reset (deletes all data)
docker-compose down -v
docker-compose up -d
# Database recreated automatically by PyDAL on startup
```

### Working with Git Branches

```bash
# Create feature branch
git checkout -b feature/new-feature-name

# Keep branch updated with main
git fetch origin
git rebase origin/main

# Clean commit history before PR
git rebase -i origin/main

# Push branch
git push origin feature/new-feature-name
```

### Database Backups

```bash
# Backup SQLite
cp current_dev.db current_dev.db.backup

# Backup PostgreSQL
docker-compose exec postgres pg_dump -U postgres current_dev > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U postgres current_dev < backup.sql
```

---

## Troubleshooting

### Services Won't Start

**Check if ports are already in use**:
```bash
# Find what's using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or use different ports in .env
SHORTURL_PORT=5001
```

**Docker daemon not running**:
```bash
# macOS
open /Applications/Docker.app

# Linux
sudo systemctl start docker

# Windows (Docker Desktop)
# Start Docker Desktop from Applications
```

### Database Connection Error

```bash
# Verify database container is running (if using PostgreSQL)
docker-compose ps postgres

# Check database credentials in .env
cat .env | grep DB_

# For SQLite, verify file exists
ls -la current_dev.db

# View logs
docker-compose logs shorturl-app
```

### Py4Web Application Won't Start

```bash
# Check logs
docker-compose logs shorturl-app

# Verify database migration
docker-compose exec shorturl-app python -c "from apps.shorturl.models import *"

# Reset and rebuild
docker-compose down
docker-compose up -d --build shorturl-app
```

### Tests Failing

```bash
# Check which test failed
pytest tests/ -v

# Run individual test file
pytest tests/test_urlshortener.py -v

# Run with verbose output for debugging
pytest tests/ -vv -s
```

### Git Merge Conflicts

```bash
# View conflicts
git status

# Edit conflicted files (marked with <<<<, ====, >>>>)
# Remove conflict markers and keep desired code

# Mark as resolved
git add <resolved-file>

# Complete merge
git commit -m "Resolve merge conflicts"
```

### Slow Docker Builds

```bash
# Check Docker disk usage
docker system df

# Clean up unused images/containers
docker system prune

# Rebuild without cache (slow, but fresh)
docker-compose build --no-cache shorturl-app
```

---

## Tips & Best Practices

### Hot Reload Development

For fastest iteration:
```bash
# Start services once
docker-compose up -d

# Edit Python files → auto-reload (hot-reload enabled)
# Edit configuration → restart service
```

### Environment-Specific Configuration

```bash
# Development settings (auto-loaded)
.env              # Default development config
.env.local        # Local machine overrides (gitignored)

# Production settings (via secret management)
Environment variables
Docker secrets
Kubernetes secrets
```

### Code Organization

Keep project clean:
```bash
# Remove old branches
git branch -D old-branch

# Clean local Docker images
docker image prune -a

# Clean unused containers
docker container prune
```

### Performance Tips

```bash
# Use lightweight testing
pytest tests/test_urlshortener.py  # Test specific module while developing

# Cache Docker layers by building in order of frequency of change
# Dockerfile: base → dependencies → code → entrypoint
```

---

## Related Documentation

- **Testing**: [Testing Documentation](TESTING.md)
  - Unit, integration, and E2E tests
  - Mock data scripts
  - Performance tests

- **Pre-Commit**: [Pre-Commit Checklist](PRE_COMMIT.md)
  - Linting requirements
  - Security scanning
  - Build verification
  - Test requirements

- **Deployment**: [Deployment Guide](DEPLOYMENT.md)
  - Containerization
  - Kubernetes deployment
  - Docker Compose production
  - Health checks

- **Standards**: [Development Standards](STANDARDS.md)
  - Architecture decisions
  - Code style
  - API conventions
  - Database patterns

- **Workflows**: [CI/CD Workflows](WORKFLOWS.md)
  - GitHub Actions pipelines
  - Build automation
  - Test automation
  - Release processes

---

**Last Updated**: 2026-01-06
**Application**: Current Shorturl Service
**Maintained by**: Penguin Tech Inc
