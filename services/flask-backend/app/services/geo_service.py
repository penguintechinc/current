"""GeoIP service for geographic analytics.

Supports both MaxMind paid (GeoIP2) and free (GeoLite2) databases.

Database priority:
1. GeoIP2-City.mmdb (paid - more accurate, includes ISP/ASN data)
2. GeoLite2-City.mmdb (free - good accuracy for most use cases)

Download databases from:
- Free: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
- Paid: https://www.maxmind.com/en/geoip2-databases

Environment variables:
- GEOIP_DB_PATH: Path to city database (auto-detects paid vs free)
- GEOIP_ASN_DB_PATH: Path to ASN database (optional, for ISP data)
- GEOIP_DB_DIR: Directory containing databases (alternative to full paths)
"""

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# GeoIP2 is optional - gracefully degrade if not available
try:
    import geoip2.database
    import geoip2.errors

    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False
    logger.warning("geoip2 not installed, geographic features disabled")


@dataclass(slots=True, frozen=True)
class GeoLocation:
    """Geographic location data from IP lookup."""

    country_code: str
    country_name: str
    city: str
    region: str
    latitude: float
    longitude: float
    timezone: str
    # Extended fields (paid database only)
    isp: Optional[str] = None
    organization: Optional[str] = None
    asn: Optional[int] = None
    is_anonymous_proxy: bool = False
    is_satellite_provider: bool = False

    @classmethod
    def unknown(cls) -> "GeoLocation":
        """Return unknown location placeholder."""
        return cls(
            country_code="XX",
            country_name="Unknown",
            city="Unknown",
            region="Unknown",
            latitude=0.0,
            longitude=0.0,
            timezone="UTC",
        )


class GeoIPService:
    """Service for IP geolocation using MaxMind GeoIP2/GeoLite2.

    Automatically detects and uses paid databases if available,
    falling back to free GeoLite2 databases.
    """

    __slots__ = ("_city_reader", "_asn_reader", "_db_path", "_asn_db_path", "_is_paid")

    # Database search paths (in order of preference)
    PAID_DB_NAMES = ["GeoIP2-City.mmdb", "GeoIP2-City-Africa.mmdb"]
    FREE_DB_NAMES = ["GeoLite2-City.mmdb"]
    ASN_DB_NAMES = ["GeoIP2-ISP.mmdb", "GeoLite2-ASN.mmdb"]

    DEFAULT_DB_DIRS = [
        "/var/lib/GeoIP",
        "/usr/share/GeoIP",
        "/opt/geoip",
        "./data/geoip",
    ]

    ENV_DB_PATH = "GEOIP_DB_PATH"
    ENV_ASN_DB_PATH = "GEOIP_ASN_DB_PATH"
    ENV_DB_DIR = "GEOIP_DB_DIR"

    def __init__(
        self,
        db_path: Optional[str] = None,
        asn_db_path: Optional[str] = None,
    ):
        """Initialize GeoIP service.

        Args:
            db_path: Path to city database file. If not specified, auto-detects
                     from environment variables or standard locations.
            asn_db_path: Path to ASN/ISP database file (optional, for ISP data).
        """
        self._city_reader = None
        self._asn_reader = None
        self._is_paid = False

        # Resolve database paths
        self._db_path = self._resolve_city_db_path(db_path)
        self._asn_db_path = self._resolve_asn_db_path(asn_db_path)

        if GEOIP_AVAILABLE:
            self._init_readers()

    def _resolve_city_db_path(self, db_path: Optional[str]) -> Optional[str]:
        """Resolve city database path.

        Priority:
        1. Explicit db_path parameter
        2. GEOIP_DB_PATH environment variable
        3. Search in GEOIP_DB_DIR or default directories

        Args:
            db_path: Explicit path or None.

        Returns:
            Resolved path or None if not found.
        """
        # Check explicit path
        if db_path:
            if os.path.exists(db_path):
                return db_path
            logger.warning(f"Specified GeoIP database not found: {db_path}")

        # Check environment variable
        env_path = os.environ.get(self.ENV_DB_PATH)
        if env_path and os.path.exists(env_path):
            return env_path

        # Search directories
        search_dirs = []
        env_dir = os.environ.get(self.ENV_DB_DIR)
        if env_dir:
            search_dirs.append(env_dir)
        search_dirs.extend(self.DEFAULT_DB_DIRS)

        # Search for paid databases first, then free
        for db_dir in search_dirs:
            if not os.path.isdir(db_dir):
                continue

            # Try paid databases first
            for db_name in self.PAID_DB_NAMES:
                path = os.path.join(db_dir, db_name)
                if os.path.exists(path):
                    self._is_paid = True
                    logger.info(f"Found paid GeoIP2 database: {path}")
                    return path

            # Fall back to free databases
            for db_name in self.FREE_DB_NAMES:
                path = os.path.join(db_dir, db_name)
                if os.path.exists(path):
                    logger.info(f"Found free GeoLite2 database: {path}")
                    return path

        return None

    def _resolve_asn_db_path(self, asn_db_path: Optional[str]) -> Optional[str]:
        """Resolve ASN/ISP database path.

        Args:
            asn_db_path: Explicit path or None.

        Returns:
            Resolved path or None if not found.
        """
        # Check explicit path
        if asn_db_path:
            if os.path.exists(asn_db_path):
                return asn_db_path

        # Check environment variable
        env_path = os.environ.get(self.ENV_ASN_DB_PATH)
        if env_path and os.path.exists(env_path):
            return env_path

        # Search directories
        search_dirs = []
        env_dir = os.environ.get(self.ENV_DB_DIR)
        if env_dir:
            search_dirs.append(env_dir)
        search_dirs.extend(self.DEFAULT_DB_DIRS)

        for db_dir in search_dirs:
            if not os.path.isdir(db_dir):
                continue

            for db_name in self.ASN_DB_NAMES:
                path = os.path.join(db_dir, db_name)
                if os.path.exists(path):
                    return path

        return None

    def _init_readers(self) -> None:
        """Initialize GeoIP2 database readers."""
        # Initialize city reader
        if self._db_path:
            try:
                self._city_reader = geoip2.database.Reader(self._db_path)
                db_type = "paid GeoIP2" if self._is_paid else "free GeoLite2"
                logger.info(f"Loaded {db_type} city database from {self._db_path}")
            except Exception as e:
                logger.error(f"Failed to load city database: {e}")
        else:
            logger.warning("No GeoIP city database found")

        # Initialize ASN reader (optional)
        if self._asn_db_path:
            try:
                self._asn_reader = geoip2.database.Reader(self._asn_db_path)
                logger.info(f"Loaded ASN database from {self._asn_db_path}")
            except Exception as e:
                logger.warning(f"Failed to load ASN database: {e}")

    def close(self) -> None:
        """Close the database readers."""
        if self._city_reader:
            self._city_reader.close()
            self._city_reader = None
        if self._asn_reader:
            self._asn_reader.close()
            self._asn_reader = None

    @property
    def is_paid_database(self) -> bool:
        """Check if using paid GeoIP2 database."""
        return self._is_paid

    @property
    def has_asn_data(self) -> bool:
        """Check if ASN/ISP data is available."""
        return self._asn_reader is not None

    @lru_cache(maxsize=10000)
    def lookup(self, ip_address: str) -> GeoLocation:
        """Look up geographic location for an IP address.

        Uses LRU cache to avoid repeated lookups for the same IP.

        Args:
            ip_address: IPv4 or IPv6 address string.

        Returns:
            GeoLocation with geographic data or unknown placeholder.
        """
        if not self._city_reader:
            return GeoLocation.unknown()

        # Skip private/local IPs
        if self._is_private_ip(ip_address):
            return GeoLocation.unknown()

        try:
            response = self._city_reader.city(ip_address)

            # Get ASN/ISP data if available
            isp = None
            organization = None
            asn = None

            if self._asn_reader:
                try:
                    asn_response = self._asn_reader.asn(ip_address)
                    asn = asn_response.autonomous_system_number
                    organization = asn_response.autonomous_system_organization
                except Exception:
                    pass  # ASN lookup is optional

            # Check for anonymous/satellite traits (paid database)
            is_anonymous_proxy = False
            is_satellite_provider = False

            if hasattr(response, "traits"):
                traits = response.traits
                is_anonymous_proxy = getattr(traits, "is_anonymous_proxy", False)
                is_satellite_provider = getattr(traits, "is_satellite_provider", False)

                # ISP from traits (paid database)
                if hasattr(traits, "isp"):
                    isp = traits.isp
                if hasattr(traits, "organization"):
                    organization = organization or traits.organization

            return GeoLocation(
                country_code=response.country.iso_code or "XX",
                country_name=response.country.name or "Unknown",
                city=response.city.name or "Unknown",
                region=response.subdivisions.most_specific.name
                if response.subdivisions
                else "Unknown",
                latitude=response.location.latitude or 0.0,
                longitude=response.location.longitude or 0.0,
                timezone=response.location.time_zone or "UTC",
                isp=isp,
                organization=organization,
                asn=asn,
                is_anonymous_proxy=is_anonymous_proxy,
                is_satellite_provider=is_satellite_provider,
            )

        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"IP not found in GeoIP database: {ip_address}")
            return GeoLocation.unknown()

        except Exception as e:
            logger.warning(f"GeoIP lookup failed for {ip_address}: {e}")
            return GeoLocation.unknown()

    def _is_private_ip(self, ip_address: str) -> bool:
        """Check if IP address is private/local.

        Args:
            ip_address: IP address string.

        Returns:
            True if IP is private/local.
        """
        try:
            import ipaddress

            ip = ipaddress.ip_address(ip_address)
            return ip.is_private or ip.is_loopback or ip.is_reserved
        except ValueError:
            return True

    def get_country_code(self, ip_address: str) -> str:
        """Get just the country code for an IP.

        Args:
            ip_address: IP address string.

        Returns:
            Two-letter country code or "XX" for unknown.
        """
        return self.lookup(ip_address).country_code

    def get_city(self, ip_address: str) -> str:
        """Get city name for an IP.

        Args:
            ip_address: IP address string.

        Returns:
            City name or "Unknown".
        """
        return self.lookup(ip_address).city


# Global service instance
_geo_service: Optional[GeoIPService] = None


def init_geo_service(db_path: Optional[str] = None) -> GeoIPService:
    """Initialize the global GeoIP service.

    Args:
        db_path: Optional path to GeoLite2 database.

    Returns:
        GeoIPService instance.
    """
    global _geo_service

    if _geo_service is not None:
        _geo_service.close()

    _geo_service = GeoIPService(db_path)
    return _geo_service


def get_geo_service() -> GeoIPService:
    """Get the global GeoIP service.

    Returns:
        GeoIPService instance (initializes if needed).
    """
    global _geo_service

    if _geo_service is None:
        _geo_service = GeoIPService()

    return _geo_service


def lookup_ip(ip_address: str) -> GeoLocation:
    """Convenience function to lookup IP location.

    Args:
        ip_address: IP address string.

    Returns:
        GeoLocation data.
    """
    return get_geo_service().lookup(ip_address)


def get_country_code(ip_address: str) -> str:
    """Convenience function to get country code.

    Args:
        ip_address: IP address string.

    Returns:
        Two-letter country code.
    """
    return get_geo_service().get_country_code(ip_address)
