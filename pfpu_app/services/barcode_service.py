from html import escape

import qrcode
from qrcode.constants import ERROR_CORRECT_H

from ..config import BARCODE_DIR


def make_barcode_svg(
    value: str,
    *,
    display_value: str | None = None,
    filename_value: str | None = None,
    subtitle: str = "Power Factory Productions",
) -> str:
    """
    Generate a durable PFPU QR label as an SVG file.

    value is the actual QR payload.

    Optional display_value, filename_value, and subtitle parameters
    allow other PFPU QR types to reuse the same QR engine.

    Existing asset QR calls remain backward compatible.
    """

    value = value.strip()

    if not value:
        raise ValueError("QR value cannot be empty.")

    if display_value is None:
        display_value = value

    if filename_value is None:
        filename_value = value

    display_value = display_value.strip()
    filename_value = filename_value.strip()
    subtitle = subtitle.strip()

    if not display_value:
        display_value = value

    if not filename_value:
        raise ValueError("QR filename value cannot be empty.")

    BARCODE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    qr.add_data(value)
    qr.make(fit=True)

    matrix = qr.get_matrix()

    module_size = 8
    qr_width = len(matrix) * module_size

    label_width = qr_width + 260
    label_height = max(
        qr_width + 20,
        150,
    )

    safe_display_value = escape(display_value)
    safe_subtitle = escape(subtitle)

    svg_parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{label_width}" '
            f'height="{label_height}" '
            f'viewBox="0 0 {label_width} {label_height}">'
        ),
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    offset_x = 10
    offset_y = 10

    for row_index, row in enumerate(matrix):
        for column_index, enabled in enumerate(row):
            if not enabled:
                continue

            x = offset_x + (
                column_index * module_size
            )

            y = offset_y + (
                row_index * module_size
            )

            svg_parts.append(
                (
                    f'<rect '
                    f'x="{x}" '
                    f'y="{y}" '
                    f'width="{module_size}" '
                    f'height="{module_size}" '
                    f'fill="black"/>'
                )
            )

    text_x = qr_width + 30

    svg_parts.extend(
        [
            (
                f'<text '
                f'x="{text_x}" '
                f'y="62" '
                f'font-size="22" '
                f'font-family="Arial, sans-serif" '
                f'font-weight="bold">'
                f'{safe_display_value}'
                f'</text>'
            ),
            (
                f'<text '
                f'x="{text_x}" '
                f'y="92" '
                f'font-size="15" '
                f'font-family="Arial, sans-serif">'
                f'{safe_subtitle}'
                f'</text>'
            ),
            "</svg>",
        ]
    )

    filename = f"{filename_value}.svg"

    path = BARCODE_DIR / filename

    path.write_text(
        "".join(svg_parts),
        encoding="utf-8",
    )

    return filename


def make_location_qr_svg(
    location_code: str,
    location_name: str = "",
) -> str:
    """
    Generate a PFPU warehouse location QR label.

    Location QR payloads use the PFPU:LOCATION namespace so scanner
    workflows can distinguish locations from normal asset identifiers.
    """

    location_code = location_code.strip().upper()
    location_name = location_name.strip()

    if not location_code:
        raise ValueError("Location code cannot be empty.")

    payload = f"PFPU:LOCATION:{location_code}"

    if location_name:
        subtitle = location_name
    else:
        subtitle = "Power Factory Productions"

    return make_barcode_svg(
        payload,
        display_value=location_code,
        filename_value=f"LOCATION-{location_code}",
        subtitle=subtitle,
    )
