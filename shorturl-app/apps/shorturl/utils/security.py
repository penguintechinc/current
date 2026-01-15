import datetime
import html
import os
import re
import sys
import urllib.parse
from functools import wraps

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
from settings import RATE_LIMIT_ENABLED, RATE_LIMIT_PER_SECOND

from apps.shorturl.models import db


class Security:

    @staticmethod
    def sanitize_input(text):
        """Sanitize user input to prevent XSS"""
        if not text:
            return text
        # HTML escape
        text = html.escape(text)
        # Remove potential script tags
        text = re.sub(
            r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
        )
        # Remove javascript: protocol
        text = re.sub(r"javascript:", "", text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def validate_url(url):
        """Validate URL to prevent SSRF and other attacks"""
        if not url:
            return False

        # Parse URL
        try:
            parsed = urllib.parse.urlparse(url)
        except:
            return False

        # Check protocol
        if parsed.scheme not in ["http", "https"]:
            return False

        # Prevent localhost and internal IPs
        dangerous_hosts = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "169.254.169.254",  # AWS metadata
            "::1",
            "::ffff:127.0.0.1",
        ]

        if parsed.hostname in dangerous_hosts:
            return False

        # Check for internal IP ranges
        if parsed.hostname:
            parts = parsed.hostname.split(".")
            if len(parts) == 4:
                try:
                    # Check for private IP ranges
                    octets = [int(p) for p in parts]
                    if octets[0] == 10:  # 10.0.0.0/8
                        return False
                    if octets[0] == 172 and 16 <= octets[1] <= 31:  # 172.16.0.0/12
                        return False
                    if octets[0] == 192 and octets[1] == 168:  # 192.168.0.0/16
                        return False
                except:
                    pass

        return True

    @staticmethod
    def validate_short_code(code):
        """Validate short code to prevent path traversal"""
        if not code:
            return False

        # Only allow alphanumeric and hyphens
        if not re.match(r"^[a-zA-Z0-9\-_]+$", code):
            return False

        # Prevent path traversal
        if ".." in code or "/" in code or "\\" in code:
            return False

        return True

    @staticmethod
    def check_sql_injection(text):
        """Basic SQL injection prevention check"""
        if not text:
            return True

        # Common SQL injection patterns
        sql_patterns = [
            r"(\bunion\b.*\bselect\b)",
            r"(\bselect\b.*\bfrom\b)",
            r"(\binsert\b.*\binto\b)",
            r"(\bupdate\b.*\bset\b)",
            r"(\bdelete\b.*\bfrom\b)",
            r"(\bdrop\b.*\btable\b)",
            r"(\bcreate\b.*\btable\b)",
            r"(\balter\b.*\btable\b)",
            r"(\bexec\b|\bexecute\b)",
            r"(\bscript\b)",
            r"(--|\#|\/\*)",
            r"(\bor\b.*=.*)",
            r"(\band\b.*=.*)",
        ]

        text_lower = text.lower()
        for pattern in sql_patterns:
            if re.search(pattern, text_lower):
                return False

        return True


class RateLimiter:

    @staticmethod
    def check_rate_limit(ip_address):
        """Check if IP has exceeded rate limit"""
        if not RATE_LIMIT_ENABLED:
            return True

        now = datetime.datetime.utcnow()

        # Get or create rate limit record
        record = db(db.rate_limits.ip_address == ip_address).select().first()

        if not record:
            # Create new record
            db.rate_limits.insert(
                ip_address=ip_address, request_count=1, window_start=now
            )
            db.commit()
            return True

        # Check if blocked
        if record.is_blocked and record.blocked_until and record.blocked_until > now:
            return False

        # Check window
        window_duration = 1  # 1 second window
        if (now - record.window_start).total_seconds() > window_duration:
            # Reset window
            db(db.rate_limits.ip_address == ip_address).update(
                request_count=1, window_start=now, is_blocked=False, blocked_until=None
            )
            db.commit()
            return True

        # Increment counter
        new_count = record.request_count + 1

        if new_count > RATE_LIMIT_PER_SECOND:
            # Block for 1 minute
            db(db.rate_limits.ip_address == ip_address).update(
                request_count=new_count,
                is_blocked=True,
                blocked_until=now + datetime.timedelta(minutes=1),
            )
            db.commit()
            return False

        # Update count
        db(db.rate_limits.ip_address == ip_address).update(request_count=new_count)
        db.commit()
        return True


def rate_limit(func):
    """Decorator for rate limiting"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        from py4web import abort, request

        # Get client IP
        ip = request.environ.get(
            "HTTP_X_FORWARDED_FOR",
            request.environ.get(
                "HTTP_X_REAL_IP", request.environ.get("REMOTE_ADDR", "0.0.0.0")
            ),
        )

        if not RateLimiter.check_rate_limit(ip):
            abort(429, "Rate limit exceeded. Please try again later.")

        return func(*args, **kwargs)

    return wrapper


def sanitize_inputs(func):
    """Decorator to sanitize all string inputs"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        from py4web import request

        # Sanitize GET parameters
        for key in request.query:
            if isinstance(request.query[key], str):
                request.query[key] = Security.sanitize_input(request.query[key])

        # Sanitize POST data
        if request.json:
            for key in request.json:
                if isinstance(request.json[key], str):
                    request.json[key] = Security.sanitize_input(request.json[key])

        return func(*args, **kwargs)

    return wrapper
