"""
Secure HTTP headers middleware.

Provides security headers for Quart/Flask applications:
- Content-Security-Policy (CSP)
- Strict-Transport-Security (HSTS)
- X-Content-Type-Options
- X-Frame-Options
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Union


@dataclass(slots=True)
class CSPDirective:
    """Content-Security-Policy directive configuration."""

    default_src: List[str] = field(default_factory=lambda: ["'self'"])
    script_src: List[str] = field(default_factory=list)
    style_src: List[str] = field(default_factory=list)
    img_src: List[str] = field(default_factory=list)
    font_src: List[str] = field(default_factory=list)
    connect_src: List[str] = field(default_factory=list)
    media_src: List[str] = field(default_factory=list)
    object_src: List[str] = field(default_factory=lambda: ["'none'"])
    frame_src: List[str] = field(default_factory=list)
    frame_ancestors: List[str] = field(default_factory=lambda: ["'self'"])
    base_uri: List[str] = field(default_factory=lambda: ["'self'"])
    form_action: List[str] = field(default_factory=lambda: ["'self'"])
    upgrade_insecure_requests: bool = True
    block_all_mixed_content: bool = True

    def to_header(self) -> str:
        """Convert to CSP header string."""
        directives = []

        if self.default_src:
            directives.append(f"default-src {' '.join(self.default_src)}")
        if self.script_src:
            directives.append(f"script-src {' '.join(self.script_src)}")
        if self.style_src:
            directives.append(f"style-src {' '.join(self.style_src)}")
        if self.img_src:
            directives.append(f"img-src {' '.join(self.img_src)}")
        if self.font_src:
            directives.append(f"font-src {' '.join(self.font_src)}")
        if self.connect_src:
            directives.append(f"connect-src {' '.join(self.connect_src)}")
        if self.media_src:
            directives.append(f"media-src {' '.join(self.media_src)}")
        if self.object_src:
            directives.append(f"object-src {' '.join(self.object_src)}")
        if self.frame_src:
            directives.append(f"frame-src {' '.join(self.frame_src)}")
        if self.frame_ancestors:
            directives.append(f"frame-ancestors {' '.join(self.frame_ancestors)}")
        if self.base_uri:
            directives.append(f"base-uri {' '.join(self.base_uri)}")
        if self.form_action:
            directives.append(f"form-action {' '.join(self.form_action)}")
        if self.upgrade_insecure_requests:
            directives.append("upgrade-insecure-requests")
        if self.block_all_mixed_content:
            directives.append("block-all-mixed-content")

        return "; ".join(directives)

    @classmethod
    def strict(cls) -> CSPDirective:
        """Strict CSP - no inline scripts or styles."""
        return cls(
            default_src=["'self'"],
            script_src=["'self'"],
            style_src=["'self'"],
            img_src=["'self'", "data:"],
            font_src=["'self'"],
            connect_src=["'self'"],
            object_src=["'none'"],
            frame_ancestors=["'none'"],
        )

    @classmethod
    def relaxed(cls) -> CSPDirective:
        """Relaxed CSP - allows inline scripts and styles."""
        return cls(
            default_src=["'self'"],
            script_src=["'self'", "'unsafe-inline'", "'unsafe-eval'"],
            style_src=["'self'", "'unsafe-inline'"],
            img_src=["'self'", "data:", "blob:", "https:"],
            font_src=["'self'", "data:", "https:"],
            connect_src=["'self'", "https:"],
        )


@dataclass(slots=True)
class SecurityHeadersConfig:
    """Configuration for security headers."""

    # Content-Security-Policy
    csp: Optional[CSPDirective] = None
    csp_report_only: bool = False
    csp_report_uri: Optional[str] = None

    # Strict-Transport-Security
    hsts_enabled: bool = True
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False

    # X-Content-Type-Options
    nosniff: bool = True

    # X-Frame-Options
    frame_options: Optional[str] = "SAMEORIGIN"  # DENY, SAMEORIGIN, or None

    # X-XSS-Protection (deprecated but still useful for older browsers)
    xss_protection: bool = True
    xss_protection_block: bool = True

    # Referrer-Policy
    referrer_policy: str = "strict-origin-when-cross-origin"

    # Permissions-Policy (formerly Feature-Policy)
    permissions_policy: Optional[Dict[str, List[str]]] = None

    # Cache-Control for sensitive pages
    cache_control: Optional[str] = None

    # Cross-Origin headers
    cross_origin_opener_policy: Optional[str] = "same-origin"
    cross_origin_embedder_policy: Optional[str] = None
    cross_origin_resource_policy: Optional[str] = "same-origin"

    @classmethod
    def api(cls) -> SecurityHeadersConfig:
        """Configuration optimized for API endpoints."""
        return cls(
            csp=None,  # APIs don't need CSP
            frame_options="DENY",
            cache_control="no-store, no-cache, must-revalidate, private",
        )

    @classmethod
    def web(cls) -> SecurityHeadersConfig:
        """Configuration for web applications."""
        return cls(
            csp=CSPDirective.relaxed(),
            frame_options="SAMEORIGIN",
        )

    @classmethod
    def strict(cls) -> SecurityHeadersConfig:
        """Strict configuration for high-security applications."""
        return cls(
            csp=CSPDirective.strict(),
            frame_options="DENY",
            hsts_preload=True,
            cross_origin_embedder_policy="require-corp",
        )


def build_headers(config: SecurityHeadersConfig) -> Dict[str, str]:
    """
    Build security headers dictionary from configuration.

    Args:
        config: Security headers configuration

    Returns:
        Dictionary of header names to values
    """
    headers: Dict[str, str] = {}

    # Content-Security-Policy
    if config.csp:
        csp_value = config.csp.to_header()
        if config.csp_report_uri:
            csp_value += f"; report-uri {config.csp_report_uri}"

        header_name = (
            "Content-Security-Policy-Report-Only"
            if config.csp_report_only
            else "Content-Security-Policy"
        )
        headers[header_name] = csp_value

    # Strict-Transport-Security
    if config.hsts_enabled:
        hsts_value = f"max-age={config.hsts_max_age}"
        if config.hsts_include_subdomains:
            hsts_value += "; includeSubDomains"
        if config.hsts_preload:
            hsts_value += "; preload"
        headers["Strict-Transport-Security"] = hsts_value

    # X-Content-Type-Options
    if config.nosniff:
        headers["X-Content-Type-Options"] = "nosniff"

    # X-Frame-Options
    if config.frame_options:
        headers["X-Frame-Options"] = config.frame_options

    # X-XSS-Protection
    if config.xss_protection:
        value = "1"
        if config.xss_protection_block:
            value += "; mode=block"
        headers["X-XSS-Protection"] = value

    # Referrer-Policy
    if config.referrer_policy:
        headers["Referrer-Policy"] = config.referrer_policy

    # Permissions-Policy
    if config.permissions_policy:
        directives = []
        for feature, origins in config.permissions_policy.items():
            if origins:
                directives.append(f"{feature}=({' '.join(origins)})")
            else:
                directives.append(f"{feature}=()")
        headers["Permissions-Policy"] = ", ".join(directives)

    # Cache-Control
    if config.cache_control:
        headers["Cache-Control"] = config.cache_control

    # Cross-Origin headers
    if config.cross_origin_opener_policy:
        headers["Cross-Origin-Opener-Policy"] = config.cross_origin_opener_policy

    if config.cross_origin_embedder_policy:
        headers["Cross-Origin-Embedder-Policy"] = config.cross_origin_embedder_policy

    if config.cross_origin_resource_policy:
        headers["Cross-Origin-Resource-Policy"] = config.cross_origin_resource_policy

    return headers


class SecurityHeadersMiddleware:
    """
    ASGI middleware for adding security headers.

    Compatible with Quart and other ASGI applications.

    Example:
        app = Quart(__name__)
        app = SecurityHeadersMiddleware(app, config=SecurityHeadersConfig.web())
    """

    def __init__(
        self,
        app: Any,
        config: Optional[SecurityHeadersConfig] = None,
        exclude_paths: Optional[Set[str]] = None,
    ) -> None:
        """
        Initialize middleware.

        Args:
            app: ASGI application
            config: Security headers configuration
            exclude_paths: Paths to exclude from header injection
        """
        self.app = app
        self.config = config or SecurityHeadersConfig()
        self.exclude_paths = exclude_paths or set()
        self._headers = build_headers(self.config)

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """ASGI interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check if path is excluded
        path = scope.get("path", "")
        if path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                # Add security headers
                for name, value in self._headers.items():
                    headers.append((name.lower().encode(), value.encode()))

                message = {**message, "headers": headers}

            await send(message)

        await self.app(scope, receive, send_wrapper)


def apply_security_headers(
    response: Any,
    config: Optional[SecurityHeadersConfig] = None,
) -> Any:
    """
    Apply security headers to a Flask/Quart response object.

    Args:
        response: Response object
        config: Security headers configuration

    Returns:
        Response with security headers applied
    """
    cfg = config or SecurityHeadersConfig()
    headers = build_headers(cfg)

    for name, value in headers.items():
        response.headers[name] = value

    return response


def security_headers_decorator(
    config: Optional[SecurityHeadersConfig] = None,
) -> Callable:
    """
    Decorator to apply security headers to a route.

    Example:
        @app.route("/api/data")
        @security_headers_decorator(config=SecurityHeadersConfig.api())
        async def get_data():
            return {"data": "value"}
    """
    cfg = config or SecurityHeadersConfig()
    headers = build_headers(cfg)

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            response = await func(*args, **kwargs)

            # Handle different response types
            if hasattr(response, "headers"):
                for name, value in headers.items():
                    response.headers[name] = value
            elif isinstance(response, tuple):
                # (body, status, headers) tuple
                if len(response) >= 3:
                    resp_headers = dict(response[2])
                    resp_headers.update(headers)
                    response = (response[0], response[1], resp_headers)
                else:
                    response = (*response, headers)

            return response

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
