from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.repair_service import (
    close_repair_record,
    open_repair_record,
    update_repair_status,
)

router = APIRouter()


@router.get("/repairs", response_class=HTMLResponse)
def repairs_page(
    request: Request,
    message: str = "",
):
    con = connect()

    open_repairs = con.execute(
        """
        SELECT
            rr.id,
            rr.asset_id,
            rr.status,
            rr.issue,
            rr.notes,
            rr.parts_needed,
            rr.opened_at,
            rr.updated_at,
            a.asset_id AS asset_code,
            a.description,
            a.category,
            a.current_location
        FROM repair_records rr
        JOIN assets a
            ON a.id = rr.asset_id
        WHERE rr.closed_at IS NULL
        ORDER BY rr.updated_at DESC, rr.id DESC
        """
    ).fetchall()

    recent_closed = con.execute(
        """
        SELECT
            rr.id,
            rr.asset_id,
            rr.status,
            rr.issue,
            rr.notes,
            rr.parts_needed,
            rr.opened_at,
            rr.updated_at,
            rr.closed_at,
            a.asset_id AS asset_code,
            a.description,
            a.category,
            a.current_location
        FROM repair_records rr
        JOIN assets a
            ON a.id = rr.asset_id
        WHERE rr.closed_at IS NOT NULL
        ORDER BY rr.closed_at DESC, rr.id DESC
        LIMIT 25
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "repairs.html",
        {
            "request": request,
            "open_repairs": open_repairs,
            "recent_closed": recent_closed,
            "message": message,
        },
    )


@router.post("/repairs/open")
def repair_open(
    barcode_value: str = Form(...),
    issue: str = Form(...),
    notes: str = Form(""),
    parts_needed: str = Form(""),
):
    result = open_repair_record(
        barcode_value=barcode_value,
        issue=issue,
        notes=notes,
        parts_needed=parts_needed,
    )

    return RedirectResponse(
        "/repairs?message=" + quote(result["message"]),
        status_code=303,
    )


@router.post("/repairs/{repair_record_id}/update")
def repair_update(
    repair_record_id: int,
    new_status: str = Form(...),
    notes: str = Form(""),
    parts_needed: str = Form(""),
):
    result = update_repair_status(
        repair_record_id=repair_record_id,
        new_status=new_status,
        notes=notes,
        parts_needed=parts_needed,
    )

    return RedirectResponse(
        "/repairs?message=" + quote(result["message"]),
        status_code=303,
    )


@router.post("/repairs/{repair_record_id}/close")
def repair_close(
    repair_record_id: int,
    resolution_notes: str = Form(""),
):
    result = close_repair_record(
        repair_record_id=repair_record_id,
        resolution_notes=resolution_notes,
    )

    return RedirectResponse(
        "/repairs?message=" + quote(result["message"]),
        status_code=303,
    )