"""Routes module for URL shortener API endpoints."""

from .redirect import redirect_bp
from .urls import urls_bp
from .teams import teams_bp
from .collections import collections_bp
from .domains import domains_bp
from .analytics import analytics_bp
from .qr import qr_bp
from .realtime import realtime_bp

__all__ = [
    "redirect_bp",
    "urls_bp",
    "teams_bp",
    "collections_bp",
    "domains_bp",
    "analytics_bp",
    "qr_bp",
    "realtime_bp",
]
