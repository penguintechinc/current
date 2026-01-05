"""
Quart Backend Application Factory.

Creates and configures the Quart application with:
- Flask-Security-Too authentication
- PyDAL database integration
- CORS support
- Prometheus metrics
- Security headers
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from quart import Quart, jsonify
from quart_cors import cors

from .config import Config, get_config
from .datastore import PyDALUserDatastore
from .models import get_db, init_db

if TYPE_CHECKING:
    from flask_security import Security


# Global security instance
security: Security | None = None


def create_app(config_class: type | None = None) -> Quart:
    """
    Create and configure the Quart application.

    Args:
        config_class: Configuration class to use (defaults to env-based config)

    Returns:
        Configured Quart application instance
    """
    app = Quart(__name__)

    # Load configuration
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Setup logging
    _setup_logging(app)

    # Initialize CORS
    app = cors(
        app,
        allow_origin=app.config.get("CORS_ORIGINS", "*").split(","),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
        allow_credentials=True,
    )

    # Initialize database
    db = init_db(app)

    # Initialize Flask-Security-Too
    _init_security(app, db)

    # Apply security headers middleware
    _apply_security_headers(app)

    # Register blueprints
    _register_blueprints(app)

    # Register health endpoints
    _register_health_endpoints(app)

    # Setup Prometheus metrics
    if app.config.get("PROMETHEUS_ENABLED", True):
        _setup_prometheus(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register shutdown handler for async db executor
    @app.after_serving
    async def cleanup() -> None:
        """Cleanup resources on shutdown."""
        from .async_db import shutdown_executor

        shutdown_executor()

    return app


def _setup_logging(app: Quart) -> None:
    """Configure application logging."""
    log_level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper())
    log_format = app.config.get(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logging.basicConfig(level=log_level, format=log_format)

    # Set specific loggers
    logging.getLogger("quart").setLevel(log_level)
    logging.getLogger("hypercorn").setLevel(log_level)


def _init_security(app: Quart, db: any) -> None:
    """
    Initialize Flask-Security-Too with PyDAL datastore.

    Note: Flask-Security-Too works with Quart through quart-flask-patch
    or by using its async-compatible features.
    """
    global security

    # Create PyDAL-based user datastore (always needed for user operations)
    user_datastore = PyDALUserDatastore(
        db=db,
        user_table=db.auth_user,
        role_table=db.auth_role,
        user_roles_table=db.auth_user_roles,
    )

    # Store datastore in app config for access in routes
    app.config["user_datastore"] = user_datastore

    # Skip Flask-Security initialization in testing mode
    # Flask-Principal hooks conflict with Quart's async test client
    # The auth module already provides JWT-based authentication
    if app.config.get("TESTING"):
        app.logger.info("Testing mode: Using JWT-only authentication")
        return

    try:
        from flask_security import Security

        # Initialize Flask-Security
        # Note: In Quart, we need to handle this carefully
        # Flask-Security init_app sets up the security context
        security = Security(app, user_datastore, register_blueprint=False)

        app.logger.info("Flask-Security-Too initialized successfully")

    except ImportError as e:
        app.logger.warning(f"Flask-Security-Too not available: {e}")
        app.logger.warning("Running in legacy mode without Flask-Security")


def _apply_security_headers(app: Quart) -> None:
    """Apply security headers to all responses."""
    try:
        from py_libs.security.headers import SecurityHeadersConfig, build_headers

        headers_config = SecurityHeadersConfig(
            hsts_enabled=not app.config.get("DEBUG", False),
            frame_options="DENY",
            nosniff=True,
            xss_protection=True,
            xss_protection_block=True,
        )
        security_headers = build_headers(headers_config)

        @app.after_request
        async def add_security_headers(response):
            """Add security headers to response."""
            for name, value in security_headers.items():
                if name not in response.headers:
                    response.headers[name] = value
            return response

    except ImportError:
        app.logger.warning("py_libs.security.headers not available")


def _register_blueprints(app: Quart) -> None:
    """Register application blueprints."""
    from .auth import auth_bp
    from .hello import hello_bp
    from .users import users_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(hello_bp, url_prefix="/api/v1")


def _register_health_endpoints(app: Quart) -> None:
    """Register health check endpoints."""

    @app.route("/healthz")
    async def health_check():
        """
        Health check endpoint for kubernetes/load balancers.

        Returns 200 if the service is healthy, 503 if unhealthy.
        """
        try:
            db = get_db()
            db.executesql("SELECT 1")
            return jsonify({"status": "healthy", "database": "connected"}), 200
        except Exception as e:
            app.logger.error(f"Health check failed: {e}")
            return jsonify({"status": "unhealthy", "error": str(e)}), 503

    @app.route("/readyz")
    async def readiness_check():
        """
        Readiness check endpoint for kubernetes.

        Returns 200 if the service is ready to accept traffic.
        """
        return jsonify({"status": "ready"}), 200

    @app.route("/livez")
    async def liveness_check():
        """
        Liveness check endpoint for kubernetes.

        Returns 200 if the service is alive.
        """
        return jsonify({"status": "alive"}), 200


def _setup_prometheus(app: Quart) -> None:
    """Setup Prometheus metrics endpoint."""
    try:
        from prometheus_client import (
            CONTENT_TYPE_LATEST,
            CollectorRegistry,
            Counter,
            Histogram,
            generate_latest,
            multiprocess,
        )

        # Create metrics
        REQUEST_COUNT = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        REQUEST_LATENCY = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["method", "endpoint"],
        )

        @app.before_request
        async def before_request():
            """Record request start time."""
            from quart import g
            import time

            g.start_time = time.time()

        @app.after_request
        async def after_request(response):
            """Record request metrics."""
            from quart import g, request

            if hasattr(g, "start_time"):
                import time

                latency = time.time() - g.start_time
                REQUEST_LATENCY.labels(
                    method=request.method,
                    endpoint=request.endpoint or "unknown",
                ).observe(latency)

            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.endpoint or "unknown",
                status=response.status_code,
            ).inc()

            return response

        @app.route("/metrics")
        async def metrics():
            """Prometheus metrics endpoint."""
            from quart import Response

            return Response(
                generate_latest(),
                mimetype=CONTENT_TYPE_LATEST,
            )

    except ImportError:
        app.logger.warning("prometheus_client not available, metrics disabled")


def _register_error_handlers(app: Quart) -> None:
    """Register global error handlers."""

    @app.errorhandler(400)
    async def bad_request(error):
        """Handle 400 Bad Request errors."""
        return jsonify({"error": "Bad request", "message": str(error)}), 400

    @app.errorhandler(401)
    async def unauthorized(error):
        """Handle 401 Unauthorized errors."""
        return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401

    @app.errorhandler(403)
    async def forbidden(error):
        """Handle 403 Forbidden errors."""
        return jsonify({"error": "Forbidden", "message": "Access denied"}), 403

    @app.errorhandler(404)
    async def not_found(error):
        """Handle 404 Not Found errors."""
        return jsonify({"error": "Not found", "message": "Resource not found"}), 404

    @app.errorhandler(405)
    async def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors."""
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(422)
    async def unprocessable_entity(error):
        """Handle 422 Unprocessable Entity errors (validation failures)."""
        return jsonify({"error": "Validation error", "message": str(error)}), 422

    @app.errorhandler(429)
    async def rate_limit_exceeded(error):
        """Handle 429 Too Many Requests errors."""
        return jsonify({"error": "Rate limit exceeded", "message": "Too many requests"}), 429

    @app.errorhandler(500)
    async def internal_error(error):
        """Handle 500 Internal Server errors."""
        app.logger.error(f"Internal server error: {error}")
        return jsonify({"error": "Internal server error"}), 500


def get_user_datastore() -> PyDALUserDatastore | None:
    """Get the user datastore from the current app context."""
    from quart import current_app

    return current_app.config.get("user_datastore")
