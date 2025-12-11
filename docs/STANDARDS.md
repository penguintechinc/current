# Current Development Standards and Conventions

## Code Quality Standards

### Python Style (PEP 8)

**Formatting**: black (88-char line length)
**Import Organization**: isort
**Linting**: flake8 (E9, F63, F7, F82)

**Pre-commit Check**:
```bash
black shorturl-app/ tests/
isort shorturl-app/ tests/
flake8 shorturl-app/ tests/
```

### Docstrings (PEP 257)

All public functions and classes must have docstrings:

```python
def create_short_url(long_url: str, user_id: int) -> str:
    """Create a shortened URL for the given long URL.

    Args:
        long_url: Full URL to shorten
        user_id: ID of user creating the URL

    Returns:
        Short URL code (e.g., 'abc123')

    Raises:
        ValueError: If long_url is invalid
        PermissionError: If user not authorized
    """
```

### Type Hints (PEP 484)

```python
from typing import Optional, List, Dict

def get_url_stats(short_code: str) -> Optional[Dict[str, int]]:
    """Get statistics for a short URL."""
    pass
```

## Testing Standards

### Unit Tests

**Framework**: pytest
**Coverage**: Minimum 70%
**Scope**: `tests/` directory

**Structure**:
```
tests/
├── test_auth.py
├── test_models.py
├── test_security.py
└── test_urlshortener.py
```

**Run Tests**:
```bash
pytest tests/ -v --cov=shorturl-app
```

### Integration Tests

- Database interactions
- API endpoints
- Authentication workflows

## Security Standards

### Input Validation

**Never Trust User Input**:
```python
# BAD
query = f"SELECT * FROM urls WHERE code = '{user_input}'"

# GOOD
from sqlalchemy import text
query = text("SELECT * FROM urls WHERE code = :code")
result = db.execute(query, {"code": user_input})
```

### Secret Management

**Environment Variables**:
```bash
DATABASE_PASSWORD=secure_password_here
SECRET_KEY=very_secret_key
API_KEY=external_api_key
```

**Never Hardcode**:
```python
# BAD
database_url = "postgresql://user:password@localhost/db"

# GOOD
import os
database_url = os.environ.get('DATABASE_URL')
```

### Password Hashing

```python
# Use strong hashing
from werkzeug.security import generate_password_hash, check_password_hash

# Create hash
hashed = generate_password_hash(password, method='pbkdf2:sha256')

# Verify
if check_password_hash(hashed, user_input):
    # Password correct
    pass
```

### SQL Injection Prevention

Always use parameterized queries:

```python
# Using SQLAlchemy ORM (safe)
user = db.session.query(User).filter_by(username=username).first()

# Using raw SQL (safe with parameters)
query = text("SELECT * FROM users WHERE username = :username")
result = db.execute(query, {"username": username})

# NOT SAFE
query = f"SELECT * FROM users WHERE username = '{username}'"
```

## API Design

### Endpoint Standards

**RESTful Principles**:
- `POST /shorten` - Create resource
- `GET /{short_code}` - Retrieve resource
- `DELETE /{short_code}` - Delete resource

**Response Format**:
```json
{
  "success": true,
  "data": {
    "short_code": "abc123",
    "long_url": "https://example.com/very/long/url",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

**Error Responses**:
```json
{
  "success": false,
  "error": "Invalid URL format",
  "error_code": "INVALID_INPUT"
}
```

### Authentication

JWT-based authentication:

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(credentials = Depends(security)):
    """Verify JWT token and return current user."""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401)
        return user_id
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401)
```

## Database Standards

### Models

```python
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ShortURL(Base):
    """Short URL mapping."""
    __tablename__ = "short_urls"

    id = Column(Integer, primary_key=True)
    short_code = Column(String(10), unique=True, index=True)
    long_url = Column(String(2048), nullable=False)
    user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ShortURL {self.short_code}>"
```

### Queries

Always use parameterized queries:

```python
# Good - ORM
url = session.query(ShortURL).filter_by(short_code=code).first()

# Good - Raw SQL with parameters
stmt = text("SELECT * FROM short_urls WHERE short_code = :code")
result = session.execute(stmt, {"code": code})
```

## Git Workflow

### Branch Naming

```
feature/new-feature-name
bugfix/issue-description
chore/maintenance-task
docs/documentation-update
```

### Commit Messages

**Format**: `type(scope): subject`

```
feat(auth): implement JWT token refresh
fix(shortener): correct duplicate code generation
chore(deps): update dependency versions
docs(api): add endpoint examples
```

### Pull Requests

- Clear description of changes
- Link to related issues
- Request reviews from maintainers
- Ensure all checks pass

## Error Handling

### Custom Exceptions

```python
class InvalidURLError(Exception):
    """Raised when URL format is invalid."""
    pass

class DuplicateShortCodeError(Exception):
    """Raised when short code already exists."""
    pass
```

### Error Responses

```python
@app.exception_handler(InvalidURLError)
async def invalid_url_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": str(exc),
            "error_code": "INVALID_URL"
        }
    )
```

## Logging Standards

```python
import logging

logger = logging.getLogger(__name__)

# Info level
logger.info(f"User {user_id} created short URL {short_code}")

# Warning level
logger.warning(f"High rate of requests from IP {ip_address}")

# Error level
logger.error(f"Database connection failed: {error}", exc_info=True)
```

## Performance Standards

- **API Response Time**: < 200ms
- **Database Queries**: < 100ms
- **Short URL Resolution**: < 50ms

## Documentation

### Module Documentation

```python
"""URL shortening service core module.

Provides functionality for creating, resolving, and managing short URLs.

Classes:
    URLShortener: Main URL shortening handler

Functions:
    create_short_url: Generate short code for URL
    resolve_short_url: Get long URL from short code
"""
```

### Function Documentation

```python
def validate_url(url: str) -> bool:
    """Validate URL format and accessibility.

    Args:
        url: URL to validate

    Returns:
        True if URL is valid, False otherwise

    Raises:
        ValueError: If URL is empty

    Example:
        >>> validate_url("https://example.com")
        True
    """
```

## Code Review Checklist

- [ ] Code follows PEP 8 style guide
- [ ] All functions have docstrings
- [ ] Tests added for new functionality
- [ ] No hardcoded credentials or secrets
- [ ] SQL queries use parameterization
- [ ] Error handling implemented
- [ ] Performance acceptable (no N+1 queries)
- [ ] Logging adequate for debugging
- [ ] Security issues addressed
- [ ] Documentation updated

## Related Documents

- [Workflows Documentation](WORKFLOWS.md)
- [CI/CD Configuration](../CLAUDE.md#cicd-pipeline-workflow-compliance)
