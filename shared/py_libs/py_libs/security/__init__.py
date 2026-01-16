"""
Security module - Security utilities for Flask/Quart applications.

Provides:
- sanitize: XSS/HTML sanitization, SQL parameter escaping
- headers: Secure headers middleware
- ratelimit: Rate limiting (in-memory + Redis)
- csrf: CSRF protection helpers
- audit: Audit logging
"""

from py_libs.security.sanitize import (
    sanitize_html,
    strip_html,
    escape_html,
    unescape_html,
    sanitize_filename,
    sanitize_url,
    sanitize_input,
    normalize_whitespace,
    remove_null_bytes,
    remove_control_chars,
    detect_sql_injection,
    detect_xss,
    SanitizeOptions,
    BLEACH_AVAILABLE,
)

from py_libs.security.headers import (
    SecurityHeadersMiddleware,
    SecurityHeadersConfig,
    CSPDirective,
    build_headers,
    apply_security_headers,
    security_headers_decorator,
)

from py_libs.security.ratelimit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitResult,
    RateLimitStorage,
    InMemoryStorage,
    SlidingWindowRateLimiter,
    rate_limit,
    REDIS_AVAILABLE,
)

from py_libs.security.csrf import (
    CSRFProtection,
    CSRFConfig,
    CSRFMiddleware,
    csrf_protect,
    generate_csrf_token,
    validate_csrf_token,
)

from py_libs.security.audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
    configure_audit_logger,
    audit_log,
    audit_login_success,
    audit_login_failure,
    audit_access_denied,
    audit_data_access,
)

# Conditionally import Redis storage
try:
    from py_libs.security.ratelimit import RedisStorage
except ImportError:
    RedisStorage = None  # type: ignore

__all__ = [
    # Sanitization
    "sanitize_html",
    "strip_html",
    "escape_html",
    "unescape_html",
    "sanitize_filename",
    "sanitize_url",
    "sanitize_input",
    "normalize_whitespace",
    "remove_null_bytes",
    "remove_control_chars",
    "detect_sql_injection",
    "detect_xss",
    "SanitizeOptions",
    "BLEACH_AVAILABLE",
    # Headers
    "SecurityHeadersMiddleware",
    "SecurityHeadersConfig",
    "CSPDirective",
    "build_headers",
    "apply_security_headers",
    "security_headers_decorator",
    # Rate limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitStorage",
    "InMemoryStorage",
    "RedisStorage",
    "SlidingWindowRateLimiter",
    "rate_limit",
    "REDIS_AVAILABLE",
    # CSRF
    "CSRFProtection",
    "CSRFConfig",
    "CSRFMiddleware",
    "csrf_protect",
    "generate_csrf_token",
    "validate_csrf_token",
    # Audit
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
    "get_audit_logger",
    "configure_audit_logger",
    "audit_log",
    "audit_login_success",
    "audit_login_failure",
    "audit_access_denied",
    "audit_data_access",
]
