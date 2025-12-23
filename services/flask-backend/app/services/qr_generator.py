"""QR code generation service.

Generates customizable QR codes using qrcode + Pillow.
Supports:
- Custom colors (foreground/background)
- Logo embedding
- Multiple styles (square, rounded, dots)
- Multiple formats (PNG, SVG, PDF)
"""

import io
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import (
        GappedSquareModuleDrawer,
        RoundedModuleDrawer,
        SquareModuleDrawer,
        CircleModuleDrawer,
    )
    from PIL import Image, ImageDraw
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

logger = logging.getLogger(__name__)


class QRStyle(str, Enum):
    """QR code module styles."""
    SQUARE = "square"
    ROUNDED = "rounded"
    DOTS = "dots"
    GAPPED = "gapped"


class QRFormat(str, Enum):
    """QR code output formats."""
    PNG = "png"
    SVG = "svg"
    PDF = "pdf"


class ErrorCorrection(str, Enum):
    """QR error correction levels."""
    L = "L"  # 7% recovery
    M = "M"  # 15% recovery (default)
    Q = "Q"  # 25% recovery
    H = "H"  # 30% recovery (best for logos)


# Map error correction strings to qrcode constants
ERROR_CORRECTION_MAP = {
    "L": qrcode.constants.ERROR_CORRECT_L if QR_AVAILABLE else None,
    "M": qrcode.constants.ERROR_CORRECT_M if QR_AVAILABLE else None,
    "Q": qrcode.constants.ERROR_CORRECT_Q if QR_AVAILABLE else None,
    "H": qrcode.constants.ERROR_CORRECT_H if QR_AVAILABLE else None,
}


@dataclass(slots=True)
class QRConfig:
    """QR code configuration."""
    data: str
    foreground_color: str = "#000000"
    background_color: str = "#FFFFFF"
    style: QRStyle = QRStyle.SQUARE
    error_correction: ErrorCorrection = ErrorCorrection.M
    box_size: int = 10
    border: int = 4
    logo_path: Optional[str] = None
    logo_size_percent: int = 25

    def __post_init__(self):
        """Validate configuration."""
        if self.box_size < 1 or self.box_size > 50:
            self.box_size = 10
        if self.border < 0 or self.border > 10:
            self.border = 4
        if self.logo_size_percent < 10 or self.logo_size_percent > 40:
            self.logo_size_percent = 25


class QRGenerator:
    """QR code generator with customization options."""

    def __init__(self):
        """Initialize QR generator."""
        if not QR_AVAILABLE:
            raise RuntimeError("qrcode and Pillow packages are required")

    def generate(
        self,
        config: QRConfig,
        output_format: QRFormat = QRFormat.PNG,
    ) -> bytes:
        """Generate QR code as bytes.

        Args:
            config: QR code configuration.
            output_format: Output format (PNG, SVG, PDF).

        Returns:
            QR code image as bytes.
        """
        if output_format == QRFormat.SVG:
            return self._generate_svg(config)
        elif output_format == QRFormat.PDF:
            return self._generate_pdf(config)
        else:
            return self._generate_png(config)

    def _generate_png(self, config: QRConfig) -> bytes:
        """Generate PNG QR code.

        Args:
            config: QR code configuration.

        Returns:
            PNG image as bytes.
        """
        # Create QR code
        qr = qrcode.QRCode(
            version=None,  # Auto-size
            error_correction=ERROR_CORRECTION_MAP.get(
                config.error_correction.value,
                qrcode.constants.ERROR_CORRECT_M,
            ),
            box_size=config.box_size,
            border=config.border,
        )
        qr.add_data(config.data)
        qr.make(fit=True)

        # Get module drawer based on style
        module_drawer = self._get_module_drawer(config.style)

        # Create styled image
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=module_drawer,
            fill_color=config.foreground_color,
            back_color=config.background_color,
        )

        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Add logo if specified
        if config.logo_path:
            img = self._add_logo(img, config.logo_path, config.logo_size_percent)

        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)

        return buffer.getvalue()

    def _generate_svg(self, config: QRConfig) -> bytes:
        """Generate SVG QR code.

        Args:
            config: QR code configuration.

        Returns:
            SVG as bytes.
        """
        import qrcode.image.svg

        # Create QR code
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECTION_MAP.get(
                config.error_correction.value,
                qrcode.constants.ERROR_CORRECT_M,
            ),
            box_size=config.box_size,
            border=config.border,
        )
        qr.add_data(config.data)
        qr.make(fit=True)

        # Generate SVG
        factory = qrcode.image.svg.SvgPathImage
        img = qr.make_image(image_factory=factory)

        # Get SVG data
        buffer = io.BytesIO()
        img.save(buffer)
        buffer.seek(0)

        # Modify SVG colors
        svg_content = buffer.getvalue().decode("utf-8")
        svg_content = svg_content.replace(
            'fill="#000000"',
            f'fill="{config.foreground_color}"',
        )

        # Add background rect
        svg_content = svg_content.replace(
            "<path",
            f'<rect width="100%" height="100%" fill="{config.background_color}"/><path',
            1,
        )

        return svg_content.encode("utf-8")

    def _generate_pdf(self, config: QRConfig) -> bytes:
        """Generate PDF QR code.

        Args:
            config: QR code configuration.

        Returns:
            PDF as bytes.
        """
        # Generate PNG first
        png_data = self._generate_png(config)

        # Convert PNG to PDF using Pillow
        img = Image.open(io.BytesIO(png_data))

        buffer = io.BytesIO()
        img.save(buffer, format="PDF", resolution=300)
        buffer.seek(0)

        return buffer.getvalue()

    def _get_module_drawer(self, style: QRStyle):
        """Get module drawer for style.

        Args:
            style: QR code style.

        Returns:
            Module drawer instance.
        """
        if style == QRStyle.ROUNDED:
            return RoundedModuleDrawer()
        elif style == QRStyle.DOTS:
            return CircleModuleDrawer()
        elif style == QRStyle.GAPPED:
            return GappedSquareModuleDrawer()
        else:
            return SquareModuleDrawer()

    def _add_logo(
        self,
        qr_img: Image.Image,
        logo_path: str,
        size_percent: int,
    ) -> Image.Image:
        """Add logo to center of QR code.

        Args:
            qr_img: QR code image.
            logo_path: Path to logo file.
            size_percent: Logo size as percentage of QR code.

        Returns:
            QR code image with logo.
        """
        try:
            # Load logo
            logo = Image.open(logo_path)

            # Calculate logo size
            qr_width, qr_height = qr_img.size
            logo_max_size = int(min(qr_width, qr_height) * (size_percent / 100))

            # Resize logo maintaining aspect ratio
            logo.thumbnail((logo_max_size, logo_max_size), Image.Resampling.LANCZOS)

            # Calculate position (center)
            logo_width, logo_height = logo.size
            pos_x = (qr_width - logo_width) // 2
            pos_y = (qr_height - logo_height) // 2

            # Create white background for logo
            logo_bg_size = max(logo_width, logo_height) + 10
            logo_bg = Image.new(
                "RGB",
                (logo_bg_size, logo_bg_size),
                "#FFFFFF",
            )

            # Paste logo on background
            logo_bg_pos = ((logo_bg_size - logo_width) // 2,
                          (logo_bg_size - logo_height) // 2)

            # Handle transparency
            if logo.mode == "RGBA":
                logo_bg.paste(logo, logo_bg_pos, logo)
            else:
                logo_bg.paste(logo, logo_bg_pos)

            # Calculate background position
            bg_pos_x = (qr_width - logo_bg_size) // 2
            bg_pos_y = (qr_height - logo_bg_size) // 2

            # Paste on QR code
            qr_img.paste(logo_bg, (bg_pos_x, bg_pos_y))

            return qr_img

        except Exception as e:
            logger.warning(f"Failed to add logo: {e}")
            return qr_img


# Global generator instance
_qr_generator: Optional[QRGenerator] = None


def get_qr_generator() -> QRGenerator:
    """Get the global QR generator.

    Returns:
        QRGenerator instance.
    """
    global _qr_generator

    if _qr_generator is None:
        _qr_generator = QRGenerator()

    return _qr_generator


def generate_qr_code(
    url: str,
    foreground: str = "#000000",
    background: str = "#FFFFFF",
    style: str = "square",
    error_correction: str = "M",
    output_format: str = "png",
    logo_path: Optional[str] = None,
    box_size: int = 10,
) -> bytes:
    """Convenience function to generate QR code.

    Args:
        url: URL to encode.
        foreground: Foreground color (hex).
        background: Background color (hex).
        style: Module style (square, rounded, dots, gapped).
        error_correction: Error correction level (L, M, Q, H).
        output_format: Output format (png, svg, pdf).
        logo_path: Optional path to logo file.
        box_size: Module size in pixels.

    Returns:
        QR code as bytes.
    """
    config = QRConfig(
        data=url,
        foreground_color=foreground,
        background_color=background,
        style=QRStyle(style) if style in QRStyle.__members__.values() else QRStyle.SQUARE,
        error_correction=ErrorCorrection(error_correction)
        if error_correction in ErrorCorrection.__members__.values()
        else ErrorCorrection.M,
        box_size=box_size,
        logo_path=logo_path,
    )

    fmt = QRFormat(output_format) if output_format in QRFormat.__members__.values() else QRFormat.PNG

    return get_qr_generator().generate(config, fmt)
