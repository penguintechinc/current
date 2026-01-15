import os
from dotenv import load_dotenv

load_dotenv()

# Application settings
APP_NAME = "ShortURL"
APP_VERSION = "1.0.0"

# Database configuration
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DB_CONNECTION = os.getenv("DB_CONNECTION", "/var/data/current/db.sqlite")
DB_URI = (
    f"{DB_TYPE}://{DB_CONNECTION}"
    if DB_TYPE != "sqlite"
    else f"sqlite://{DB_CONNECTION}"
)

# Security settings
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")
SESSION_TYPE = "database"
CSRF_ENABLED = True

# Domain and certificate settings
DOMAIN = os.getenv("DOMAIN", "localhost")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@localhost")
CERT_PATH = f"/etc/letsencrypt/live/{DOMAIN}"

# Redis configuration for rate limiting
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Rate limiting settings
RATE_LIMIT_PER_SECOND = int(os.getenv("RATE_LIMIT_PER_SECOND", "10"))
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"

# Server ports
PROXY_HTTP_PORT = int(os.getenv("PROXY_HTTP_PORT", "80"))
PROXY_HTTPS_PORT = int(os.getenv("PROXY_HTTPS_PORT", "443"))
ADMIN_HTTPS_PORT = int(os.getenv("ADMIN_HTTPS_PORT", "9443"))

# Analytics settings
GEOIP_DB_PATH = "/app/geoip/GeoLite2-City.mmdb"
ANALYTICS_RETENTION_DAYS = int(os.getenv("ANALYTICS_RETENTION_DAYS", "90"))

# URL shortening settings
DEFAULT_SHORT_LENGTH = 6
MAX_CUSTOM_LENGTH = 14
RESERVED_PATHS = ["admin", "api", "healthz", "metrics", "static", "auth"]

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "/var/log/shorturl/app.log"
