"""Flask Backend Application Factory."""

import os
from flask import Flask
from flask_cors import CORS
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from .config import Config
from .models import init_db, get_db


def create_app(config_class: type = Config) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get("CORS_ORIGINS", "*"),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    })

    # Initialize Redis
    _init_redis(app)

    # Initialize database
    with app.app_context():
        init_db(app)

    # Initialize services
    _init_services(app)

    # Register blueprints
    from .auth import auth_bp, sso_bp
    from .users import users_bp
    from .hello import hello_bp
    from .routes import (
        redirect_bp,
        urls_bp,
        teams_bp,
        collections_bp,
        domains_bp,
        analytics_bp,
        qr_bp,
        realtime_bp,
    )

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(sso_bp, url_prefix="/api/v1/sso")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(hello_bp, url_prefix="/api/v1")
    app.register_blueprint(urls_bp, url_prefix="/api/v1/urls")
    app.register_blueprint(teams_bp, url_prefix="/api/v1/teams")
    app.register_blueprint(collections_bp, url_prefix="/api/v1/collections")
    app.register_blueprint(domains_bp, url_prefix="/api/v1/domains")
    app.register_blueprint(analytics_bp, url_prefix="/api/v1/analytics")
    app.register_blueprint(qr_bp, url_prefix="/api/v1/qr")
    app.register_blueprint(realtime_bp, url_prefix="/api/v1/realtime")

    # Register redirect blueprint at root level for short URLs
    app.register_blueprint(redirect_bp, url_prefix="")

    # Health check endpoint
    @app.route("/healthz")
    def health_check():
        """Health check endpoint."""
        try:
            db = get_db()
            db.executesql("SELECT 1")
            return {"status": "healthy", "database": "connected"}, 200
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}, 503

    # Readiness check endpoint
    @app.route("/readyz")
    def readiness_check():
        """Readiness check endpoint."""
        return {"status": "ready"}, 200

    # Add Prometheus metrics endpoint
    app.wsgi_app = DispatcherMiddleware(
        app.wsgi_app,
        {"/metrics": make_wsgi_app()}
    )

    return app


def _init_redis(app: Flask) -> None:
    """Initialize Redis connection.

    Args:
        app: Flask application instance.
    """
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    try:
        import redis
        # Parse Redis URL and create connection pool
        redis_client = redis.from_url(
            redis_url,
            max_connections=50,
            decode_responses=True,
        )
        # Test connection
        redis_client.ping()

        # Store in app extensions
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["redis"] = redis_client

        app.logger.info("Redis connection established")
    except Exception as e:
        app.logger.warning(f"Redis connection failed: {e}. Caching disabled.")
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["redis"] = None


def _init_services(app: Flask) -> None:
    """Initialize application services.

    Args:
        app: Flask application instance.
    """
    # Initialize cache service
    from .services.cache_service import init_cache_service
    redis_client = app.extensions.get("redis") if hasattr(app, "extensions") else None
    init_cache_service(redis_client)

    # Initialize GeoIP service
    from .services.geo_service import init_geo_service
    init_geo_service()
    app.logger.info("GeoIP service initialized")

    # Initialize redirect service with background workers
    # Only start workers if not in testing mode
    if not app.config.get("TESTING"):
        from .services.redirect_service import init_redirect_service
        init_redirect_service()
        app.logger.info("Redirect service initialized")

        # Initialize analytics workers
        from .tasks.aggregation import start_aggregation_scheduler
        from .tasks.cache_warmer import start_cache_warmer

        start_aggregation_scheduler(get_db, redis_client)
        start_cache_warmer(get_db, redis_client)
        app.logger.info("Analytics workers initialized")
