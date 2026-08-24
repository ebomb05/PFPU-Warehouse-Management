from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.auth_service import request_has_permission
from ..services.audit_service import (
    complete_audit,
    get_audit_summary,
    scan_audit_asset,
    start_location_audit,
)

router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/audits", response_class=HTMLResponse)
def audits_page(
    request: Request,
    message: str = "",
):
    if not request_has_permission(
        request,
        "audits.perform",
    ):
        return deny_access()

    con = connect()

    locations = con.execute(
        """
        SELECT
            id,
            code,
            name,
            location_type
        FROM warehouse_locations
        WHERE active = 1
        ORDER BY location_type, code
        """
    ).fetchall()

    sessions = con.execute(
        """
        SELECT
            s.id,
            s.audit_type,
            s.status,
            s.started_at,
            s.completed_at,
            wl.code AS location_code,
            wl.name AS location_name
        FROM audit_sessions s
        LEFT JOIN warehouse_locations wl
            ON wl.id = s.location_id
        ORDER BY s.id DESC
        LIMIT 25
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "audits.html",
        {
            "request": request,
            "locations": locations,
            "sessions": sessions,
            "message": message,
        },
    )


@router.post("/audits/start")
def audit_start(
    request: Request,
    location_id: int = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "audits.perform",
    ):
        return deny_access()

    result = start_location_audit(
        location_id,
        notes=notes,
    )

    if result["success"]:
        return RedirectResponse(
            f"/audits/{result['audit_session_id']}",
            status_code=303,
        )

    return RedirectResponse(
        "/audits?message=" + quote(result["message"]),
        status_code=303,
    )


@router.get("/audits/{audit_session_id}", response_class=HTMLResponse)
def audit_detail(
    request: Request,
    audit_session_id: int,
    message: str = "",
):
    if not request_has_permission(
        request,
        "audits.perform",
    ):
        return deny_access()

    summary = get_audit_summary(audit_session_id)

    if not summary["success"]:
        return RedirectResponse(
            "/audits?message=" + quote(summary["message"]),
            status_code=303,
        )

    return request.app.state.templates.TemplateResponse(
        "audit_detail.html",
        {
            "request": request,
            "summary": summary,
            "message": message,
        },
    )


@router.post("/audits/{audit_session_id}/scan")
def audit_scan(
    request: Request,
    audit_session_id: int,
    barcode_value: str = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "audits.perform",
    ):
        return deny_access()

    result = scan_audit_asset(
        audit_session_id,
        barcode_value,
        notes=notes,
    )

    return RedirectResponse(
        (
            f"/audits/{audit_session_id}"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )


@router.post("/audits/{audit_session_id}/complete")
def audit_complete(
    request: Request,
    audit_session_id: int,
):
    if not request_has_permission(
        request,
        "audits.perform",
    ):
        return deny_access()

    result = complete_audit(audit_session_id)

    return RedirectResponse(
        (
            f"/audits/{audit_session_id}"
            f"?message={quote(result.get('message', 'Audit completed'))}"
        ),
        status_code=303,
    )