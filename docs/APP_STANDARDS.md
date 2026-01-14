# Application-Specific Standards

**Project**: Current (URL Shortener & Management Platform)
**Version**: 1.0.0
**Last Updated**: 2026-01-13

> ⚠️ **Note**: This file contains application-specific standards, architecture decisions, and context. For company-wide development standards, see [STANDARDS.md](STANDARDS.md) and the [docs/standards/](standards/) directory.

## Project Overview

Current is a comprehensive URL shortener and management platform with enterprise features including:
- URL shortening with custom aliases
- Analytics and tracking
- QR code generation
- User authentication and authorization
- Role-based access control (Admin, Maintainer, Viewer)
- License-gated enterprise features

## Application Architecture

### Three-Container Microservices Architecture

1. **Flask Backend** (`services/flask-backend/`)
   - **Technology**: Quart (async Flask) with Python 3.13
   - **Purpose**: Primary API server, authentication, user management
   - **Port**: 5000 (internal), exposed as 5008 (external)
   - **Database**: PyDAL with PostgreSQL/MySQL/SQLite support
   - **Authentication**: Flask-Security-Too with JWT tokens
   - **Features**:
     - User registration and authentication
     - Role-based access control (RBAC)
     - URL management API (`/api/v1/urls/`)
     - Analytics API (`/api/v1/analytics/`)
     - Health monitoring (`/api/v1/health`)

2. **WebUI** (`services/webui/`)
   - **Technology**: Node.js 22 + React + TypeScript
   - **Purpose**: Frontend application shell
   - **Port**: 3000 (internal), exposed as 3008 (external)
   - **Build Tool**: Vite
   - **Styling**: Tailwind CSS
   - **Features**:
     - Role-based UI components
     - Dashboard for URL management
     - Analytics visualization
     - User profile management
     - Settings and configuration

3. **Go Backend** (Optional, not currently implemented)
   - **Purpose**: High-performance URL resolution and redirection
   - **Technology**: Go 1.24+ with XDP/AF_XDP support
   - **When to add**: When traffic exceeds 10K requests/second

### Service Communication

- **External to WebUI**: HTTPS (REST API)
- **WebUI to Flask Backend**: HTTP REST API calls
- **Backend to Database**: PyDAL connection pool
- **Monitoring**: Prometheus metrics exposed on all services

## Database Architecture

### Schema Design

**Users Table** (`users`):
- `id` (Integer, Primary Key)
- `email` (String, Unique, Required)
- `username` (String, Unique, Optional)
- `password` (String, Hashed with bcrypt)
- `active` (Boolean, Default: True)
- `fs_uniquifier` (String, Flask-Security-Too requirement)
- `confirmed_at` (DateTime)
- `last_login_at` (DateTime)
- `current_login_at` (DateTime)
- `last_login_ip` (String)
- `current_login_ip` (String)
- `login_count` (Integer)

**Roles Table** (`roles`):
- `id` (Integer, Primary Key)
- `name` (String, Unique)
- `description` (String)

**User-Roles Junction Table** (`user_roles`):
- `user_id` (Integer, Foreign Key to users)
- `role_id` (Integer, Foreign Key to roles)

**URLs Table** (`urls`):
- `id` (Integer, Primary Key)
- `short_code` (String, Unique, Indexed)
- `long_url` (Text, Required)
- `user_id` (Integer, Foreign Key to users)
- `created_at` (DateTime)
- `expires_at` (DateTime, Optional)
- `click_count` (Integer, Default: 0)
- `active` (Boolean, Default: True)

**Analytics Table** (`analytics`):
- `id` (Integer, Primary Key)
- `url_id` (Integer, Foreign Key to urls)
- `clicked_at` (DateTime)
- `ip_address` (String)
- `user_agent` (String)
- `referrer` (String, Optional)
- `country` (String, Optional)

### Database Configuration

**Supported Databases**:
- PostgreSQL (production default)
- MySQL 8.0+ (production)
- MariaDB Galera (clustered production)
- SQLite (development only)

**Connection String Format**:
```
DB_URI=postgresql://user:pass@host:port/dbname
DB_URI=mysql://user:pass@host:port/dbname
DB_URI=sqlite://storage.db
```

**Migration Strategy**: PyDAL with `migrate=True` for automatic schema updates

## Authentication & Authorization

### Role Hierarchy

1. **Admin** (`admin`)
   - Full system access
   - User management (create, update, delete users)
   - Role assignment
   - System configuration
   - All URL operations (create, read, update, delete all URLs)
   - Access to all analytics

2. **Maintainer** (`maintainer`)
   - Read and write access to URLs
   - Create and manage own URLs
   - View analytics for own URLs
   - Cannot manage users or roles
   - Cannot access system configuration

3. **Viewer** (`viewer`)
   - Read-only access
   - View own URLs
   - View analytics for own URLs
   - Cannot create or modify URLs

### Authentication Flow

1. **Registration**: POST `/api/v1/auth/register`
   - Email validation required
   - Password strength requirements (min 8 chars, complexity)
   - Default role: `viewer`

2. **Login**: POST `/api/v1/auth/login`
   - Returns JWT access token and refresh token
   - Token expiry: 1 hour (access), 7 days (refresh)

3. **Token Refresh**: POST `/api/v1/auth/refresh`
   - Requires valid refresh token
   - Returns new access token

4. **Logout**: POST `/api/v1/auth/logout`
   - Invalidates refresh token

### API Authentication

All authenticated endpoints require:
```
Authorization: Bearer <jwt_token>
```

## API Versioning

**Current Version**: v1

All API endpoints use versioned paths:
```
/api/v1/urls/
/api/v1/analytics/
/api/v1/auth/
/api/v1/users/
/api/v1/health
```

**Version Support Policy**: N-2 (current + 2 previous versions)

## License-Gated Features

### Community Features (Free)
- URL shortening (up to 1000 URLs)
- Basic analytics
- QR code generation
- Standard roles

### Professional Features (License Required)
- Unlimited URLs
- Advanced analytics and reporting
- Custom domains
- Bulk operations
- API rate limit increase

### Enterprise Features (License Required)
- SSO integration (SAML/OAuth2)
- Multi-tenancy
- Audit logging
- Advanced security features
- Priority support
- Custom branding

### License Integration

**License Server**: `https://license.penguintech.io`

**Environment Variables**:
```bash
LICENSE_KEY=PENG-XXXX-XXXX-XXXX-XXXX-ABCD
LICENSE_SERVER_URL=https://license.penguintech.io
PRODUCT_NAME=current-url-shortener
RELEASE_MODE=false  # Development mode (no license checks)
```

**Release Mode Behavior**:
- `RELEASE_MODE=false` (development): All features available
- `RELEASE_MODE=true` (production): License validation enforced

## Environment Configuration

### Required Environment Variables

**Flask Backend**:
```bash
# Flask configuration
SECRET_KEY=<random-secret-key>
SECURITY_PASSWORD_SALT=<random-salt>

# Database
DB_TYPE=postgresql
DB_URI=postgresql://user:pass@postgres:5432/current

# Redis/Valkey cache
REDIS_URL=redis://redis:6379/0

# License (production only)
LICENSE_KEY=PENG-XXXX-XXXX-XXXX-XXXX-ABCD
LICENSE_SERVER_URL=https://license.penguintech.io
PRODUCT_NAME=current-url-shortener
RELEASE_MODE=false

# Email (for user registration)
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=noreply@example.com
MAIL_PASSWORD=<email-password>
```

**WebUI**:
```bash
NODE_ENV=production
PORT=3000
FLASK_API_URL=http://flask-backend:5000
```

## Performance Requirements

### Target Metrics

- **API Response Time**: < 100ms (p95)
- **URL Resolution**: < 50ms (p95)
- **Database Queries**: < 20ms (p95)
- **Frontend Load Time**: < 2s (first contentful paint)

### Scalability

- **Horizontal Scaling**: Flask backend via Kubernetes HPA
- **Database**: Connection pooling (20 connections per backend instance)
- **Cache**: Redis for frequently accessed URLs
- **CDN**: Static assets served via CDN

## Security Standards

### Application-Specific Security

1. **URL Validation**: All submitted URLs validated and sanitized
2. **Rate Limiting**:
   - 100 requests/minute per IP (unauthenticated)
   - 1000 requests/minute per user (authenticated)
3. **SQL Injection Prevention**: PyDAL parameterized queries
4. **XSS Prevention**: Content Security Policy headers
5. **CSRF Protection**: Disabled for API-only backend (JWT-based)

### Secrets Management

All secrets stored in environment variables, never committed to repository.

**Production Secrets** (managed via Kubernetes secrets):
- `SECRET_KEY`
- `SECURITY_PASSWORD_SALT`
- `DB_URI`
- `LICENSE_KEY`
- `MAIL_PASSWORD`

## Testing Strategy

### Application-Specific Tests

1. **Unit Tests** (`services/flask-backend/tests/`)
   - Authentication flows
   - URL shortening logic
   - Analytics calculations
   - Role-based access control

2. **Integration Tests** (`tests/`)
   - Database operations
   - API endpoint integration
   - License server communication

3. **E2E Tests** (`tests/e2e/`)
   - User registration and login flow
   - URL creation and resolution
   - Analytics dashboard
   - Role-based UI visibility

4. **API Tests** (`tests/api/flask-backend/`)
   - All REST endpoints
   - Authentication scenarios
   - Error handling
   - Rate limiting

5. **Load Tests** (`tests/api/flask-backend/test_load.py`)
   - 1000 concurrent users
   - URL resolution performance
   - Database connection pool limits

## Deployment Strategy

### Beta Deployment

**Host**: `https://current.penguintech.io`
**Registry**: `registry-dal2.penguintech.io/current`
**Cluster**: Beta Kubernetes cluster

**Image Tags**:
- `beta-<epoch64>` - Automatic builds from main branch
- `v1.0.0-beta` - Version-tagged beta releases

### Production Deployment

**Host**: TBD (custom domain or `https://current.penguincloud.io`)
**Image Tags**: `v1.0.0` (semantic version tags)

### Deployment Process

1. Build multi-arch images (amd64/arm64)
2. Push to `registry-dal2.penguintech.io`
3. Deploy via Helm chart or kubectl
4. Run smoke tests
5. Verify health checks
6. Monitor Prometheus metrics

## Monitoring & Observability

### Application Metrics

**Flask Backend Metrics**:
- `current_urls_created_total` - Counter of URLs created
- `current_urls_resolved_total` - Counter of URL resolutions
- `current_auth_attempts_total` - Counter of login attempts
- `current_api_request_duration_seconds` - Histogram of API latency

**WebUI Metrics**:
- `webui_page_loads_total` - Counter of page loads
- `webui_api_errors_total` - Counter of API errors

### Logging

**Log Format**: JSON structured logging

**Log Levels**:
- `DEBUG`: Development only
- `INFO`: Normal operations (default)
- `WARNING`: Recoverable errors
- `ERROR`: Unrecoverable errors
- `CRITICAL`: System failures

**Log Aggregation**: All logs sent to stdout/stderr for Kubernetes collection

## Future Enhancements

### Planned Features

1. **Custom Domains**: Allow users to use custom domains for short URLs
2. **Bulk Import**: CSV/Excel import for multiple URLs
3. **Advanced Analytics**: Geographic tracking, device detection, conversion tracking
4. **Webhooks**: Notification webhooks for URL events
5. **API Keys**: Programmatic API access with API keys
6. **URL Expiration**: Automatic URL expiration and cleanup
7. **Link Preview**: Social media preview customization

### Performance Optimization Roadmap

1. **Add Go Backend**: When traffic > 10K req/sec
2. **Implement Redis Cache**: For frequently accessed URLs
3. **Add CDN**: For static asset delivery
4. **Database Read Replicas**: For analytics queries

## Development Workflow

### Local Development

```bash
# Start all services
make dev

# Seed mock data (3-4 items per feature)
make seed-mock-data

# Run tests
make test

# Run smoke tests
make smoke-test
```

### Pre-Commit Requirements

1. Run linters (Python, Node.js, YAML)
2. Run security scans (bandit, npm audit)
3. Check for secrets (check-secrets.sh)
4. Build Docker images
5. Run smoke tests
6. Run unit and integration tests
7. Update version if needed

### Git Workflow

- Feature branches: `feature/<feature-name>`
- Bug fixes: `bugfix/<issue-number>`
- Main branch: `main` (protected, requires PR review)
- Beta branch: Auto-deploy to beta cluster

## Application-Specific Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check `DB_URI` environment variable
   - Verify database credentials
   - Ensure database container is running

2. **License Validation Failures**
   - Set `RELEASE_MODE=false` for development
   - Verify `LICENSE_KEY` format
   - Check license server connectivity

3. **Authentication Errors**
   - Verify `SECRET_KEY` and `SECURITY_PASSWORD_SALT`
   - Check JWT token expiration
   - Ensure Flask-Security-Too initialization

4. **URL Resolution Slow**
   - Check database connection pool
   - Enable Redis caching
   - Review database query performance

## References

- **Company-Wide Standards**: [STANDARDS.md](STANDARDS.md)
- **License Server Integration**: [docs/licensing/license-server-integration.md](licensing/license-server-integration.md)
- **Development Setup**: [DEVELOPMENT.md](DEVELOPMENT.md)
- **Testing Guide**: [TESTING.md](TESTING.md)
- **Pre-Commit Checklist**: [PRE_COMMIT.md](PRE_COMMIT.md)

---

**Maintained by**: Current Development Team
**Contact**: creatorsemailhere@penguintech.group
**Last Review**: 2026-01-13
