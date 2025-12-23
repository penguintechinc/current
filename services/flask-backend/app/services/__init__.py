"""Services module for URL shortener business logic."""

from .cache_service import CacheService, get_cache_service, init_cache_service
from .redirect_service import RedirectService, get_redirect_service, init_redirect_service
from .geo_service import (
    GeoIPService,
    GeoLocation,
    get_geo_service,
    init_geo_service,
    lookup_ip,
    get_country_code,
)
from .qr_generator import (
    QRGenerator,
    QRConfig,
    QRFormat,
    QRStyle,
    ErrorCorrection,
    get_qr_generator,
    generate_qr_code,
)

__all__ = [
    "CacheService",
    "get_cache_service",
    "init_cache_service",
    "RedirectService",
    "get_redirect_service",
    "init_redirect_service",
    "GeoIPService",
    "GeoLocation",
    "get_geo_service",
    "init_geo_service",
    "lookup_ip",
    "get_country_code",
    "QRGenerator",
    "QRConfig",
    "QRFormat",
    "QRStyle",
    "ErrorCorrection",
    "get_qr_generator",
    "generate_qr_code",
]
