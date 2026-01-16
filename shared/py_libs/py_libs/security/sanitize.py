"""
Input sanitization utilities.

Provides:
- XSS/HTML sanitization
- SQL parameter escaping helpers
- Input normalization
- Dangerous content detection
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional, Set

# Import bleach for HTML sanitization
try:
    import bleach
    from bleach.css_sanitizer import CSSSanitizer

    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False


@dataclass(slots=True)
class SanitizeOptions:
    """Configuration for HTML sanitization."""

    # Allowed HTML tags
    allowed_tags: Set[str] = field(
        default_factory=lambda: {
            "a",
            "abbr",
            "acronym",
            "b",
            "blockquote",
            "code",
            "em",
            "i",
            "li",
            "ol",
            "strong",
            "ul",
            "p",
            "br",
            "span",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "pre",
        }
    )

    # Allowed HTML attributes per tag
    allowed_attributes: dict[str, Set[str]] = field(
        default_factory=lambda: {
            "a": {"href", "title", "rel"},
            "abbr": {"title"},
            "acronym": {"title"},
            "img": {"src", "alt", "title", "width", "height"},
        }
    )

    # Allowed URL schemes for links
    allowed_protocols: Set[str] = field(
        default_factory=lambda: {"http", "https", "mailto"}
    )

    # Strip or escape disallowed tags
    strip_tags: bool = True

    # Strip HTML comments
    strip_comments: bool = True

    @classmethod
    def strict(cls) -> SanitizeOptions:
        """Strict settings - no HTML allowed."""
        return cls(
            allowed_tags=set(),
            allowed_attributes={},
            strip_tags=True,
        )

    @classmethod
    def basic(cls) -> SanitizeOptions:
        """Basic formatting tags only."""
        return cls(
            allowed_tags={"b", "i", "em", "strong", "br", "p"},
            allowed_attributes={},
        )

    @classmethod
    def rich(cls) -> SanitizeOptions:
        """Rich text with links and images."""
        return cls(
            allowed_tags={
                "a",
                "b",
                "blockquote",
                "br",
                "code",
                "em",
                "h1",
                "h2",
                "h3",
                "h4",
                "i",
                "img",
                "li",
                "ol",
                "p",
                "pre",
                "span",
                "strong",
                "ul",
            },
            allowed_attributes={
                "a": {"href", "title", "rel"},
                "img": {"src", "alt", "title", "width", "height"},
            },
        )


def sanitize_html(
    text: str,
    options: Optional[SanitizeOptions] = None,
) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.

    Uses bleach library for robust HTML sanitization.

    Args:
        text: HTML text to sanitize
        options: Sanitization options

    Returns:
        Sanitized HTML string

    Example:
        >>> sanitize_html("<script>alert('xss')</script><b>Hello</b>")
        '<b>Hello</b>'
    """
    if not BLEACH_AVAILABLE:
        # Fallback: escape all HTML
        return html.escape(text)

    opts = options or SanitizeOptions()

    return bleach.clean(
        text,
        tags=opts.allowed_tags,
        attributes=opts.allowed_attributes,
        protocols=opts.allowed_protocols,
        strip=opts.strip_tags,
        strip_comments=opts.strip_comments,
    )


def strip_html(text: str) -> str:
    """
    Remove all HTML tags from text.

    Args:
        text: HTML text

    Returns:
        Plain text with all HTML removed

    Example:
        >>> strip_html("<p>Hello <b>World</b></p>")
        'Hello World'
    """
    if BLEACH_AVAILABLE:
        return bleach.clean(text, tags=set(), strip=True)

    # Fallback: regex-based stripping
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean)


def escape_html(text: str) -> str:
    """
    Escape HTML special characters.

    Args:
        text: Text to escape

    Returns:
        HTML-escaped text

    Example:
        >>> escape_html("<script>alert('xss')</script>")
        '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;'
    """
    return html.escape(text, quote=True)


def unescape_html(text: str) -> str:
    """
    Unescape HTML entities.

    Args:
        text: HTML-escaped text

    Returns:
        Unescaped text
    """
    return html.unescape(text)


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to prevent path traversal and other attacks.

    Args:
        filename: Original filename
        max_length: Maximum allowed length

    Returns:
        Sanitized filename

    Example:
        >>> sanitize_filename("../../../etc/passwd")
        'etc_passwd'
        >>> sanitize_filename("file<script>.txt")
        'filescript.txt'
    """
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*]', "", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Remove parent directory references
    filename = filename.replace("..", "")

    # Normalize unicode
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    # Truncate to max length
    if len(filename) > max_length:
        # Preserve extension if possible
        parts = filename.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) < 10:
            ext = "." + parts[1]
            filename = parts[0][: max_length - len(ext)] + ext
        else:
            filename = filename[:max_length]

    # Default filename if empty
    if not filename:
        filename = "unnamed"

    return filename


def sanitize_url(url: str, allowed_schemes: Optional[Set[str]] = None) -> Optional[str]:
    """
    Sanitize a URL to prevent javascript: and data: attacks.

    Args:
        url: URL to sanitize
        allowed_schemes: Allowed URL schemes (default: http, https)

    Returns:
        Sanitized URL or None if invalid

    Example:
        >>> sanitize_url("javascript:alert('xss')")
        None
        >>> sanitize_url("https://example.com")
        'https://example.com'
    """
    if allowed_schemes is None:
        allowed_schemes = {"http", "https"}

    url = url.strip()

    # Parse scheme
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):.*$", url)
    if scheme_match:
        scheme = scheme_match.group(1).lower()
        if scheme not in allowed_schemes:
            return None
    else:
        # Relative URL - allow it
        pass

    # Check for encoded javascript
    decoded = html.unescape(url.lower())
    if "javascript:" in decoded or "data:" in decoded:
        return None

    return url


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    - Collapse multiple spaces to single space
    - Normalize line endings
    - Strip leading/trailing whitespace

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse multiple spaces (but preserve newlines)
    lines = text.split("\n")
    lines = [" ".join(line.split()) for line in lines]
    text = "\n".join(lines)

    return text.strip()


def remove_null_bytes(text: str) -> str:
    """
    Remove null bytes from text.

    Null bytes can be used to bypass security filters.

    Args:
        text: Text to clean

    Returns:
        Text without null bytes
    """
    return text.replace("\x00", "")


def remove_control_chars(text: str, preserve_newlines: bool = True) -> str:
    """
    Remove control characters from text.

    Args:
        text: Text to clean
        preserve_newlines: Keep newlines and tabs

    Returns:
        Text without control characters
    """
    if preserve_newlines:
        # Keep newline, tab, carriage return
        pattern = r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
    else:
        # Remove all control characters
        pattern = r"[\x00-\x1f\x7f]"

    return re.sub(pattern, "", text)


def detect_sql_injection(text: str) -> bool:
    """
    Detect potential SQL injection patterns.

    This is a basic detection - always use parameterized queries.

    Args:
        text: Text to check

    Returns:
        True if suspicious patterns detected

    Example:
        >>> detect_sql_injection("1; DROP TABLE users;--")
        True
        >>> detect_sql_injection("normal text")
        False
    """
    # Common SQL injection patterns
    patterns = [
        r"(\s|^)(OR|AND)\s+\d+\s*=\s*\d+",  # OR 1=1
        r"(\s|^)(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?",  # OR 'a'='a'
        r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE)",  # Stacked queries
        r"--\s*$",  # SQL comment at end
        r"/\*.*\*/",  # SQL block comment
        r"UNION\s+(ALL\s+)?SELECT",  # UNION injection
        r"(EXEC|EXECUTE)\s*\(",  # Stored procedure execution
        r"xp_cmdshell",  # SQL Server command shell
        r"INTO\s+(OUT|DUMP)FILE",  # MySQL file write
    ]

    text_upper = text.upper()
    for pattern in patterns:
        if re.search(pattern, text_upper, re.IGNORECASE):
            return True

    return False


def detect_xss(text: str) -> bool:
    """
    Detect potential XSS attack patterns.

    Args:
        text: Text to check

    Returns:
        True if suspicious patterns detected
    """
    # Common XSS patterns
    patterns = [
        r"<script[\s>]",
        r"javascript:",
        r"on\w+\s*=",  # Event handlers
        r"<iframe[\s>]",
        r"<object[\s>]",
        r"<embed[\s>]",
        r"<svg[\s>].*on\w+",
        r"expression\s*\(",  # CSS expression
        r"url\s*\(\s*['\"]?javascript:",
        r"&#x?[0-9a-f]+;",  # Encoded characters (suspicious in large quantities)
    ]

    text_lower = text.lower()
    decoded = html.unescape(text_lower)

    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
        if re.search(pattern, decoded, re.IGNORECASE):
            return True

    return False


def sanitize_input(
    text: str,
    strip_html: bool = True,
    normalize_space: bool = True,
    remove_control: bool = True,
    max_length: Optional[int] = None,
) -> str:
    """
    General-purpose input sanitization.

    Combines multiple sanitization steps for safe user input handling.

    Args:
        text: Input text
        strip_html: Remove all HTML tags
        normalize_space: Normalize whitespace
        remove_control: Remove control characters
        max_length: Maximum allowed length

    Returns:
        Sanitized text
    """
    # Remove null bytes first
    text = remove_null_bytes(text)

    # Remove control characters
    if remove_control:
        text = remove_control_chars(text)

    # Strip HTML
    if strip_html:
        if BLEACH_AVAILABLE:
            text = bleach.clean(text, tags=set(), strip=True)
        else:
            text = html.escape(text)

    # Normalize whitespace
    if normalize_space:
        text = normalize_whitespace(text)

    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length]

    return text
