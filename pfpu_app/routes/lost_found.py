from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.auth_service import request_has_permission
from ..services.lost_found_service import (
    locate_asset,
    mark_asset_missing,
    resolve_found_asset,
)

router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/lost-found", response_class=HTMLResponse)
def lost_found_page(
    request: Request,
    q: str = "",
    message: str = "",
):
    if not request_has_permission(
        request,
        "inventory.view",
    ):
        return deny_access()

    asset_info = None

    if q.strip():
        asset_info = locate_asset(q.strip())

    con = connect()

    open_missing = con.execute(
        """
        SELECT
            e.id,
            e.job_id,
            e.asset_id,
            e.severity,
            e.message,
            e.created_at,
            a.asset_id AS asset_code,
            a.description,
            a.status,
            a.current_location,
            j.job_number
        FROM exceptions e
        LEFT JOIN assets a
            ON a.id = e.asset_id
        LEFT JOIN jobs j
            ON j.id = e.job_id
        WHERE e.exception_type = 'Missing Asset'
          AND e.status = 'Open'
        ORDER BY e.created_at DESC, e.id DESC
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "lost_found.html",
        {
            "request": request,
            "q": q,
            "asset_info": asset_info,
            "open_missing": open_missing,
            "message": message,
        },
    )


@router.post("/lost-found/missing")
def lost_found_mark_missing(
    request: Request,
    barcode_value: str = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "exceptions.resolve",
    ):
        return deny_access()

    result = mark_asset_missing(
        barcode_value,
        notes=notes,
    )

    return RedirectResponse(
        (
            "/lost-found"
            f"?q={quote(barcode_value)}"
            f"&message={quote(result['message'])}"
        ),
        status_code=303,
    )


@router.post("/lost-found/found")
def lost_found_resolve(
    request: Request,
    barcode_value: str = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "assets.move",
    ):
        return deny_access()

    result = resolve_found_asset(
        barcode_value,
        notes=notes,
    )

    return RedirectResponse(
        (
            "/lost-found"
            f"?q={quote(barcode_value)}"
            f"&message={quote(result['message'])}"
        ),
        status_code=303,
    )