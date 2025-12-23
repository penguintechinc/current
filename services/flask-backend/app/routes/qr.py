"""QR Code API endpoints for URL shortener.

Provides endpoints for:
- Creating/updating QR code configurations
- Downloading QR codes in multiple formats (PNG, SVG, PDF)
- Previewing QR codes
"""

from flask import Blueprint, Response, g, jsonify, request

from ..middleware import token_required
from ..models import get_db
from ..services.qr_generator import (
    QRConfig,
    QRFormat,
    QRStyle,
    ErrorCorrection,
    generate_qr_code,
)
from ..utils.permissions import can_manage_url

qr_bp = Blueprint("qr", __name__)

# MIME types for download
MIME_TYPES = {
    "png": "image/png",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
}


@qr_bp.route("/urls/<int:url_id>", methods=["GET"])
@token_required
def get_qr_config(url_id: int):
    """Get QR code configuration for a URL.

    Args:
        url_id: Short URL ID.

    Returns:
        JSON with QR configuration.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check URL exists and user has access
    url = db(db.short_urls.id == url_id).select(
        db.short_urls.ALL,
        db.domains.domain,
        left=db.domains.on(db.short_urls.domain_id == db.domains.id),
    ).first()

    if not url or not url.short_urls:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url.short_urls):
        return jsonify({"error": "Access denied"}), 403

    # Get QR config if exists
    qr_config = db(db.qr_codes.short_url_id == url_id).select().first()

    if qr_config:
        result = qr_config.as_dict()
    else:
        # Return defaults
        result = {
            "short_url_id": url_id,
            "foreground_color": "#000000",
            "background_color": "#FFFFFF",
            "style": "square",
            "error_correction": "M",
            "logo_url": None,
            "logo_size": 25,
            "frame_style": None,
            "frame_text": None,
        }

    # Add URL info
    result["url"] = {
        "id": url.short_urls.id,
        "slug": url.short_urls.slug,
        "domain": url.domains.domain if url.domains else None,
        "full_url": f"https://{url.domains.domain}/{url.short_urls.slug}"
        if url.domains
        else None,
    }

    return jsonify(result)


@qr_bp.route("/urls/<int:url_id>", methods=["POST", "PUT"])
@token_required
def save_qr_config(url_id: int):
    """Create or update QR code configuration.

    Args:
        url_id: Short URL ID.

    Request body:
        foreground_color: Foreground color (hex)
        background_color: Background color (hex)
        style: Module style (square, rounded, dots, gapped)
        error_correction: Error level (L, M, Q, H)
        logo_url: URL to logo image (optional)
        logo_size: Logo size percentage (10-40)
        frame_style: Frame style (optional)
        frame_text: Frame text (optional)

    Returns:
        JSON with saved configuration.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    # Check URL exists and user has access
    url = db(db.short_urls.id == url_id).select().first()

    if not url:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url):
        return jsonify({"error": "Access denied"}), 403

    # Validate colors
    fg_color = data.get("foreground_color", "#000000")
    bg_color = data.get("background_color", "#FFFFFF")

    if not _is_valid_hex_color(fg_color):
        return jsonify({"error": "Invalid foreground_color format"}), 400
    if not _is_valid_hex_color(bg_color):
        return jsonify({"error": "Invalid background_color format"}), 400

    # Validate style
    style = data.get("style", "square")
    if style not in ["square", "rounded", "dots", "gapped"]:
        style = "square"

    # Validate error correction
    error_correction = data.get("error_correction", "M")
    if error_correction not in ["L", "M", "Q", "H"]:
        error_correction = "M"

    # Validate logo size
    logo_size = data.get("logo_size", 25)
    if not isinstance(logo_size, int) or logo_size < 10 or logo_size > 40:
        logo_size = 25

    # Prepare config data
    config_data = {
        "foreground_color": fg_color,
        "background_color": bg_color,
        "style": style,
        "error_correction": error_correction,
        "logo_url": data.get("logo_url"),
        "logo_size": logo_size,
        "frame_style": data.get("frame_style"),
        "frame_text": data.get("frame_text"),
    }

    # Check if config exists
    existing = db(db.qr_codes.short_url_id == url_id).select().first()

    try:
        if existing:
            db(db.qr_codes.id == existing.id).update(**config_data)
        else:
            config_data["short_url_id"] = url_id
            db.qr_codes.insert(**config_data)

        db.commit()

    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to save configuration: {str(e)}"}), 500

    # Return updated config
    qr_config = db(db.qr_codes.short_url_id == url_id).select().first()
    return jsonify(qr_config.as_dict())


@qr_bp.route("/urls/<int:url_id>/download/<fmt>", methods=["GET"])
@token_required
def download_qr_code(url_id: int, fmt: str):
    """Download QR code in specified format.

    Args:
        url_id: Short URL ID.
        fmt: Output format (png, svg, pdf).

    Query params:
        size: Image size in pixels (100-2000, default 300)

    Returns:
        QR code image file.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Validate format
    fmt = fmt.lower()
    if fmt not in MIME_TYPES:
        return jsonify({"error": f"Invalid format. Use: {', '.join(MIME_TYPES.keys())}"}), 400

    # Check URL exists and user has access
    url = db(db.short_urls.id == url_id).select(
        db.short_urls.ALL,
        db.domains.domain,
        left=db.domains.on(db.short_urls.domain_id == db.domains.id),
    ).first()

    if not url or not url.short_urls:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url.short_urls):
        return jsonify({"error": "Access denied"}), 403

    # Build URL to encode
    if url.domains:
        qr_url = f"https://{url.domains.domain}/{url.short_urls.slug}"
    else:
        qr_url = url.short_urls.original_url

    # Get QR config
    qr_config = db(db.qr_codes.short_url_id == url_id).select().first()

    # Get size from query params
    size = request.args.get("size", 300, type=int)
    size = max(100, min(2000, size))
    box_size = size // 30  # Approximate box size for desired image size

    # Generate QR code
    try:
        qr_data = generate_qr_code(
            url=qr_url,
            foreground=qr_config.foreground_color if qr_config else "#000000",
            background=qr_config.background_color if qr_config else "#FFFFFF",
            style=qr_config.style if qr_config else "square",
            error_correction=qr_config.error_correction if qr_config else "M",
            output_format=fmt,
            logo_path=None,  # Logo URLs need to be downloaded first
            box_size=box_size,
        )

    except Exception as e:
        return jsonify({"error": f"Failed to generate QR code: {str(e)}"}), 500

    # Return file
    filename = f"qr-{url.short_urls.slug}.{fmt}"

    return Response(
        qr_data,
        mimetype=MIME_TYPES[fmt],
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(qr_data)),
        },
    )


@qr_bp.route("/urls/<int:url_id>/preview", methods=["GET"])
@token_required
def preview_qr_code(url_id: int):
    """Preview QR code as inline image.

    Args:
        url_id: Short URL ID.

    Query params:
        fg: Foreground color (hex, optional)
        bg: Background color (hex, optional)
        style: Module style (optional)
        size: Image size (optional)

    Returns:
        PNG image for preview.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check URL exists and user has access
    url = db(db.short_urls.id == url_id).select(
        db.short_urls.ALL,
        db.domains.domain,
        left=db.domains.on(db.short_urls.domain_id == db.domains.id),
    ).first()

    if not url or not url.short_urls:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url.short_urls):
        return jsonify({"error": "Access denied"}), 403

    # Build URL to encode
    if url.domains:
        qr_url = f"https://{url.domains.domain}/{url.short_urls.slug}"
    else:
        qr_url = url.short_urls.original_url

    # Get preview params (override saved config)
    fg_color = request.args.get("fg", "#000000")
    bg_color = request.args.get("bg", "#FFFFFF")
    style = request.args.get("style", "square")
    size = request.args.get("size", 200, type=int)
    size = max(50, min(500, size))
    box_size = size // 25

    # Validate colors
    if not _is_valid_hex_color(fg_color):
        fg_color = "#000000"
    if not _is_valid_hex_color(bg_color):
        bg_color = "#FFFFFF"

    # Generate preview
    try:
        qr_data = generate_qr_code(
            url=qr_url,
            foreground=fg_color,
            background=bg_color,
            style=style if style in ["square", "rounded", "dots", "gapped"] else "square",
            error_correction="M",
            output_format="png",
            box_size=box_size,
        )

    except Exception as e:
        return jsonify({"error": f"Failed to generate preview: {str(e)}"}), 500

    return Response(
        qr_data,
        mimetype="image/png",
        headers={"Cache-Control": "no-cache"},
    )


def _is_valid_hex_color(color: str) -> bool:
    """Validate hex color format.

    Args:
        color: Color string.

    Returns:
        True if valid hex color.
    """
    if not color:
        return False
    if not color.startswith("#"):
        return False
    if len(color) not in (4, 7):  # #RGB or #RRGGBB
        return False
    try:
        int(color[1:], 16)
        return True
    except ValueError:
        return False
