# ShortURL - Enterprise URL Shortener

A high-performance, feature-rich URL shortening service built with Python, py4web, and Docker.

## Features

### Core Functionality
- **URL Shortening**: Create short, memorable URLs with custom or auto-generated codes
- **QR Code Generation**: Automatic QR code generation for all short URLs
- **Category Management**: Organize URLs into categories for better management
- **Search & Filter**: Full-text search across URLs with category filtering

### Security & Access Control
- **Role-Based Access Control (RBAC)**: Four distinct roles:
  - **Admin**: Full system access
  - **Contributor**: Can add/edit URLs but not manage users
  - **Viewer**: Can view current URLs
  - **Reporter**: Analytics access only
- **OWASP Top 10 Compliance**: Built-in protection against common vulnerabilities
- **Rate Limiting**: Configurable per-IP rate limiting (default: 10 req/sec)
- **Input Validation**: Comprehensive validation and sanitization

### Analytics & Monitoring
- **Real-time Analytics**: Track clicks, visitors, geographic data
- **GeoIP Integration**: Location-based analytics using GeoIP2
- **Performance Metrics**: Response time tracking and monitoring
- **Prometheus Integration**: `/metrics` endpoint for monitoring
- **Health Checks**: `/healthz` endpoint for uptime monitoring

### Infrastructure
- **Multi-Port Architecture**:
  - Ports 80/443: URL redirection proxy
  - Port 9443: Admin portal (HTTPS only)
- **TLS/SSL Support**:
  - Auto-generated self-signed certificates
  - ACME/Let's Encrypt integration
  - Automatic certificate renewal
- **Database Flexibility**: Support for any PyDAL-compatible database
- **Docker Containerized**: Easy deployment and scaling

## Quick Start

### Using Docker Compose

1. Clone the repository:
```bash
git clone <repository-url>
cd shorturl
```

2. Copy and configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start the services:
```bash
docker-compose up -d
```

4. Access the services:
- Admin Portal: https://localhost:9443
- Main Site: http://localhost

### Default Credentials

- **Email**: admin@localhost
- **Password**: admin123

⚠️ **Important**: Change the default password immediately after first login!

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_TYPE` | Database type (sqlite, mysql, postgresql) | sqlite |
| `DB_CONNECTION` | Database connection string | /var/data/current/db.sqlite |
| `DOMAIN` | Your domain name | localhost |
| `ADMIN_EMAIL` | Admin email for certificates | admin@localhost |
| `SECRET_KEY` | Application secret key | change-me-in-production |
| `REDIS_URL` | Redis connection URL | redis://redis:6379/0 |
| `RATE_LIMIT_PER_SECOND` | Max requests per second per IP | 10 |
| `ANALYTICS_RETENTION_DAYS` | Days to retain analytics data | 90 |

### Database Configuration

#### SQLite (Default)
```env
DB_TYPE=sqlite
DB_CONNECTION=/var/data/current/db.sqlite
```

#### MySQL
```env
DB_TYPE=mysql
DB_CONNECTION=user:password@host:3306/database
```

#### PostgreSQL
```env
DB_TYPE=postgresql
DB_CONNECTION=user:password@host:5432/database
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `POST /api/auth/register` - User registration

### URL Management
- `GET /api/urls` - List all URLs
- `POST /api/urls` - Create new short URL
- `PUT /api/urls/{id}` - Update URL
- `DELETE /api/urls/{id}` - Delete URL
- `GET /api/urls/search` - Search URLs

### Categories
- `GET /api/categories` - List categories
- `POST /api/categories` - Create category
- `PUT /api/categories/{id}` - Update category
- `DELETE /api/categories/{id}` - Delete category

### Analytics
- `GET /api/analytics/url/{id}` - URL-specific analytics
- `GET /api/analytics/global` - Global analytics
- `GET /api/analytics/visitors` - Top visitors

### Monitoring
- `GET /healthz` - Health check
- `GET /metrics` - Prometheus metrics

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Docker Container                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────┐    ┌──────────────────┐      │
│  │  Proxy Server   │    │   Admin Portal    │      │
│  │  (Ports 80/443) │    │   (Port 9443)     │      │
│  └────────┬────────┘    └─────────┬────────┘      │
│           │                        │                │
│           └────────────┬───────────┘                │
│                       │                            │
│            ┌──────────▼──────────┐                 │
│            │      PyDAL ORM      │                 │
│            └──────────┬──────────┘                 │
│                       │                            │
│     ┌─────────────────▼─────────────────┐          │
│     │           Database                │          │
│     │  (SQLite/MySQL/PostgreSQL/etc)    │          │
│     └───────────────────────────────────┘          │
│                                                     │
│     ┌───────────────────────────────────┐          │
│     │           Redis Cache             │          │
│     │       (Rate Limiting/Sessions)     │          │
│     └───────────────────────────────────┘          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Security Considerations

1. **Change Default Credentials**: Always change the default admin password
2. **Use HTTPS**: Configure proper SSL certificates for production
3. **Set Strong Secret Key**: Use a cryptographically secure secret key
4. **Database Security**: Use strong database passwords and limit network access
5. **Rate Limiting**: Adjust rate limits based on your traffic patterns
6. **Regular Updates**: Keep the application and dependencies updated

## Troubleshooting

### Certificate Issues
If you encounter certificate problems:
```bash
# Regenerate self-signed certificate
docker-compose exec shorturl rm -rf /etc/letsencrypt/live/${DOMAIN}
docker-compose restart shorturl
```

### Database Connection Issues
Check your database configuration and ensure the database server is accessible:
```bash
docker-compose logs shorturl
```

### Port Conflicts
If ports are already in use, modify the port mappings in `docker-compose.yml`:
```yaml
ports:
  - "8080:80"    # Change 8080 to your preferred port
  - "8443:443"   # Change 8443 to your preferred port
  - "9443:9443"  # Change first 9443 to your preferred port
```

## Development

### Local Development Setup

1. Install Python 3.12+
2. Install dependencies:
```bash
pip install -r shorturl-app/requirements.txt
pip install -r shorturl-app/requirements-dev.txt  # For development/testing
```

3. Set environment variables:
```bash
export DB_TYPE=sqlite
export DB_CONNECTION=./dev.db
export DOMAIN=localhost
```

4. Run the application:
```bash
python shorturl-app/main.py
```

### Testing

The application includes comprehensive unit and integration tests:

```bash
# Run all tests
python3 run_tests.py

# Run specific test categories
python3 -m unittest tests.test_security_isolated -v    # Security tests
python3 -m unittest tests.test_utils -v               # Utility tests
python3 -m unittest tests.test_integration -v         # Integration tests
python3 -m unittest tests.test_startup -v            # Startup tests

# With pytest (if available)
pytest tests/ -v --tb=short
```

**Test Coverage**: 19 tests with 100% success rate covering:
- Security functions (XSS, SSRF, SQL injection prevention)
- Utility functions (password hashing, code generation)
- Application integration and file structure
- Docker and deployment configuration

See [docs/TESTING.md](docs/TESTING.md) for detailed testing information.

## License

ShortURL is licensed under the Limited AGPL v3 with Fair Use Preamble. See [LICENSE.md](docs/LICENSE.md) for details.

**License Highlights:**
- **Personal & Internal Use**: Free under AGPL-3.0
- **Commercial Use**: Requires commercial license
- **SaaS Deployment**: Requires commercial license if providing as a service

### Contributor Employer Exception (GPL-2.0 Grant)

Companies employing official contributors receive GPL-2.0 access to community features:

- **Perpetual for Contributed Versions**: GPL-2.0 rights to versions where the employee contributed remain valid permanently, even after the employee leaves the company
- **Attribution Required**: Employee must be credited in CONTRIBUTORS, AUTHORS, commit history, or release notes
- **Future Versions**: New versions released after employment ends require standard licensing
- **Community Only**: Enterprise features still require a commercial license

This exception rewards contributors by providing lasting fair use rights to their employers.

## Support

For issues and feature requests, please use the GitHub issue tracker.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.