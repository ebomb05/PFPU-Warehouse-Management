from html import escape
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_H

from ..config import BARCODE_DIR


def make_barcode_svg(value: str) -> str:
    """
    Generate a durable PFPU QR label as an SVG file.

    The QR payload is the stable asset identifier itself.
    Existing PFPU scanning/database behavior remains unchanged.
    """

    value = value.strip()

    if not value:
        raise ValueError("QR value cannot be empty.")

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

    label_width = qr_width + 220
    label_height = max(
        qr_width + 20,
        150,
    )

    safe_value = escape(value)

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
                f'{safe_value}'
                f'</text>'
            ),
            (
                f'<text '
                f'x="{text_x}" '
                f'y="92" '
                f'font-size="15" '
                f'font-family="Arial, sans-serif">'
                f'Power Factory Productions'
                f'</text>'
            ),
            "</svg>",
        ]
    )

    filename = f"{value}.svg"

    path = BARCODE_DIR / filename

    path.write_text(
        "".join(svg_parts),
        encoding="utf-8",
    )

    return filename