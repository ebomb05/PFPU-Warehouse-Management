from ..config import BARCODE_DIR


def make_barcode_svg(value: str) -> str:
    """
    Step 4A intentionally preserves the existing Code 128 output.
    QR conversion is a later milestone so this refactor does not change behavior.
    """
    try:
        import barcode

        code128 = barcode.get_barcode_class("code128")
        writer = barcode.writer.SVGWriter()
        filename = BARCODE_DIR / value
        code128(value, writer=writer).save(
            str(filename),
            options={
                "write_text": True,
                "module_height": 12,
                "font_size": 10,
            },
        )
        return f"{value}.svg"
    except Exception:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80">'
            '<rect width="100%" height="100%" fill="white"/>'
            f'<text x="20" y="45" font-size="20" font-family="Arial">{value}</text>'
            "</svg>"
        )
        path = BARCODE_DIR / f"{value}.svg"
        path.write_text(svg, encoding="utf-8")
        return path.name
