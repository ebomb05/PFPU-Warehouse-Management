from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from ..database import connect

router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/barcodes", response_class=HTMLResponse)
def barcodes(
    request: Request,
):
    permissions = request.state.permissions

    allowed = (
        "assets.create" in permissions
        or "inventory.edit" in permissions
    )

    if not allowed:
        return deny_access()

    con = connect()

    rows = con.execute(
        """
        SELECT *
        FROM barcode_queue
        ORDER BY id DESC
        LIMIT 200
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "barcodes.html",
        {
            "request": request,
            "rows": rows,
        },
    )