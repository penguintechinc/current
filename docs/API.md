# API Documentation

## Authentication

All admin API endpoints require authentication. Use the login endpoint to establish a session.

### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "admin@localhost",
  "password": "admin123"
}
```

**Response:**
```json
{
  "success": true,
  "user": {
    "id": 1,
    "email": "admin@localhost",
    "first_name": "Admin",
    "last_name": "User",
    "role": "admin"
  }
}
```

### Logout
```http
POST /api/auth/logout
```

## URL Management

### List URLs
```http
GET /api/urls?category_id=1
```

**Response:**
```json
[
  {
    "id": 1,
    "short_code": "abc123",
    "long_url": "https://example.com/very-long-url",
    "title": "Example Site",
    "description": "A sample website",
    "category_id": 1,
    "click_count": 42,
    "show_on_frontpage": true,
    "created_on": "2024-01-01T12:00:00Z"
  }
]
```

### Create Short URL
```http
POST /api/urls
Content-Type: application/json

{
  "long_url": "https://example.com/very-long-url",
  "custom_code": "my-link",
  "title": "My Custom Link",
  "description": "Description of the link",
  "category_id": 1,
  "show_on_frontpage": false
}
```

**Response:**
```json
{
  "success": true,
  "url": {
    "id": 2,
    "short_code": "my-link",
    "long_url": "https://example.com/very-long-url"
  }
}
```

### Update URL
```http
PUT /api/urls/1
Content-Type: application/json

{
  "title": "Updated Title",
  "description": "Updated description",
  "show_on_frontpage": true
}
```

### Delete URL
```http
DELETE /api/urls/1
```

### Search URLs
```http
GET /api/urls/search?q=example&category_id=1
```

## Category Management

### List Categories
```http
GET /api/categories
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "default",
    "description": "Default category"
  },
  {
    "id": 2,
    "name": "frontpage",
    "description": "Links shown on frontpage"
  }
]
```

### Create Category
```http
POST /api/categories
Content-Type: application/json

{
  "name": "marketing",
  "description": "Marketing campaign links"
}
```

### Update Category
```http
PUT /api/categories/1
Content-Type: application/json

{
  "name": "updated-name",
  "description": "Updated description"
}
```

### Delete Category
```http
DELETE /api/categories/1
```

## Analytics

### URL Analytics
```http
GET /api/analytics/url/1?days=30
```

**Response:**
```json
{
  "total_clicks": 150,
  "unique_visitors": 87,
  "countries": {
    "United States": 45,
    "Canada": 23,
    "United Kingdom": 18
  },
  "cities": {
    "New York": 12,
    "Toronto": 8,
    "London": 6
  },
  "devices": {
    "desktop": 89,
    "mobile": 61
  },
  "browsers": {
    "Chrome": 78,
    "Safari": 34,
    "Firefox": 23
  },
  "operating_systems": {
    "Windows": 67,
    "macOS": 45,
    "Linux": 23
  },
  "daily_clicks": {
    "2024-01-01": 5,
    "2024-01-02": 8,
    "2024-01-03": 12
  },
  "top_referers": {
    "https://google.com": 34,
    "https://twitter.com": 12
  },
  "average_response_time": 145.5
}
```

### Global Analytics
```http
GET /api/analytics/global?days=30
```

**Response:**
```json
{
  "total_clicks": 1250,
  "unique_visitors": 567,
  "top_urls": [
    {
      "short_code": "abc123",
      "title": "Popular Link",
      "clicks": 89
    }
  ],
  "top_countries": {
    "United States": 234,
    "Canada": 123
  },
  "total_urls": 45,
  "total_users": 3
}
```

### Top Visitors
```http
GET /api/analytics/visitors?days=30&limit=10
```

**Response:**
```json
[
  {
    "ip_address": "192.168.1.100",
    "click_count": 15,
    "country": "United States",
    "city": "New York",
    "last_seen": "2024-01-15T10:30:00Z"
  }
]
```

## Certificate Management

### Get Certificate Info
```http
GET /api/certificates
```

**Response:**
```json
{
  "domain": "shorturl.example.com",
  "type": "acme",
  "expires_on": "2024-04-01T00:00:00Z",
  "days_until_expiry": 75,
  "auto_renew": true
}
```

### Request ACME Certificate
```http
POST /api/certificates/acme
```

**Response:**
```json
{
  "success": true,
  "message": "Certificate obtained successfully"
}
```

### Renew Certificate
```http
POST /api/certificates/renew
```

## Settings Management

### Get Settings
```http
GET /api/settings
```

**Response:**
```json
{
  "rate_limit_per_second": "10",
  "analytics_retention_days": "90",
  "auto_renew_certs": "true"
}
```

### Update Settings
```http
PUT /api/settings
Content-Type: application/json

{
  "rate_limit_per_second": "20",
  "analytics_retention_days": "120"
}
```

## Monitoring Endpoints

### Health Check
```http
GET /healthz
```

**Response:**
```json
{
  "status": "healthy"
}
```

### Prometheus Metrics
```http
GET /metrics
Authorization: Basic <base64-encoded-credentials>
```

**Response:**
```
# HELP shorturl_total_urls Total number of active URLs
# TYPE shorturl_total_urls gauge
shorturl_total_urls 45

# HELP shorturl_total_clicks Total number of clicks
# TYPE shorturl_total_clicks counter
shorturl_total_clicks 1250

# HELP shorturl_total_users Total number of active users
# TYPE shorturl_total_users gauge
shorturl_total_users 3

# HELP shorturl_total_categories Total number of active categories  
# TYPE shorturl_total_categories gauge
shorturl_total_categories 5
```

## Role-Based Access

Different user roles have different API access:

### Admin
- Full access to all endpoints
- Can manage users, URLs, categories, certificates, settings

### Contributor  
- Can create, update, delete URLs
- Can view analytics
- Cannot manage users or system settings

### Viewer
- Can view URLs and search
- Can view basic analytics
- Cannot create/modify data

### Reporter
- Can only access analytics endpoints
- Cannot view or modify URLs

## Error Responses

All API endpoints return standard HTTP status codes:

- `200` - Success
- `400` - Bad Request (validation error)
- `401` - Unauthorized (login required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `429` - Rate Limited
- `500` - Internal Server Error

**Error Response Format:**
```json
{
  "success": false,
  "error": "Description of the error"
}
```

## Rate Limiting

API endpoints are subject to rate limiting:
- Default: 10 requests per second per IP
- Configurable via `RATE_LIMIT_PER_SECOND` environment variable
- Rate limit exceeded returns HTTP 429

## QR Codes

QR codes are automatically generated for all URLs and can be accessed via:
```
GET /{short_code}.qr
```

This returns a PNG image of the QR code for the short URL.