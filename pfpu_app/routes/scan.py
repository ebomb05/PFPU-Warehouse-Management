from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.asset_service import move_asset
from ..services.auth_service import request_has_permission
from ..services.repair_service import open_repair_record

router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/scan", response_class=HTMLResponse)
def scan_page(
    request: Request,
    message: str = "",
):
    permissions = request.state.permissions

    allowed = any(
        permission in permissions
        for permission in (
            "assets.move",
            "scan.checkout",
            "scan.checkin",
            "repairs.update",
        )
    )

    if not allowed:
        return deny_access()

    con = connect()

    jobs = con.execute(
        """
        SELECT
            id,
            job_number,
            customer,
            event_name,
            status
        FROM jobs
        WHERE status NOT IN (
            'Cancelled',
            'Completed',
            'Returned'
        )
        ORDER BY out_date, job_number
        """
    ).fetchall()

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

    con.close()

    return request.app.state.templates.TemplateResponse(
        "scan.html",
        {
            "request": request,
            "jobs": jobs,
            "locations": locations,
            "message": message,
        },
    )


@router.post("/scan")
def scan(
    request: Request,
    barcode_value: str = Form(...),
    action: str = Form(...),
    to_location_id: str = Form(""),
    job_id: str = Form(""),
    notes: str = Form(""),
):
    barcode_value = barcode_value.strip()
    notes = notes.strip()

    to_location_id = to_location_id.strip()
    job_id = job_id.strip()

    to_location_id_value = (
        int(to_location_id)
        if to_location_id
        else None
    )

    job_id_value = (
        int(job_id)
        if job_id
        else None
    )

    # ---------------------------------------------------------
    # PERMISSION CHECK FOR REQUESTED ACTION
    # ---------------------------------------------------------

    if action == "move":
        if not request_has_permission(
            request,
            "assets.move",
        ):
            return deny_access()

    elif action == "repair":
        if not request_has_permission(
            request,
            "repairs.update",
        ):
            return deny_access()

    elif action in ("prep", "checkout"):
        if not request_has_permission(
            request,
            "scan.checkout",
        ):
            return deny_access()

    elif action == "return":
        if not request_has_permission(
            request,
            "scan.checkin",
        ):
            return deny_access()

    else:
        return RedirectResponse(
            "/scan?message=" + quote(
                "Unknown Scan Station action."
            ),
            status_code=303,
        )

    con = connect()

    asset = con.execute(
        """
        SELECT
            id,
            asset_id,
            status,
            assigned_job_id,
            location_id,
            current_location
        FROM assets
        WHERE barcode_value = ?
           OR asset_id = ?
        """,
        (
            barcode_value,
            barcode_value,
        ),
    ).fetchone()

    con.close()

    if not asset:
        return RedirectResponse(
            "/scan?message="
            + quote(
                "Asset / QR not found. Create the asset first."
            ),
            status_code=303,
        )

    # ---------------------------------------------------------
    # MANUAL LOCATION MOVE
    # ---------------------------------------------------------

    if action == "move":

        if to_location_id_value is None:
            return RedirectResponse(
                "/scan?message="
                + quote("Choose a destination location."),
                status_code=303,
            )

        result = move_asset(
            asset_id=asset["id"],
            to_location_id=to_location_id_value,
            action="Manual Move",
            notes=notes,
        )

        return RedirectResponse(
            "/scan?message=" + quote(result["message"]),
            status_code=303,
        )

    # ---------------------------------------------------------
    # REPAIR
    # ---------------------------------------------------------

    if action == "repair":

        issue = (
            notes
            if notes
            else "Sent to repair from Scan Station"
        )

        result = open_repair_record(
            barcode_value=barcode_value,
            issue=issue,
            notes=notes,
            job_id=job_id_value,
        )

        return RedirectResponse(
            "/scan?message=" + quote(result["message"]),
            status_code=303,
        )

    # ---------------------------------------------------------
    # JOB WORKFLOW ACTIONS
    # Dedicated workflow screens intentionally handle these.
    # ---------------------------------------------------------

    if action == "prep":

        if job_id_value is None:
            message = (
                "Choose a job before pulling equipment to PREP."
            )
        else:
            message = (
                "Use the Job Pull / PREP screen for job equipment. "
                "This prevents bypassing quantity and conflict checks."
            )

        return RedirectResponse(
            "/scan?message=" + quote(message),
            status_code=303,
        )

    if action == "checkout":

        message = (
            "Use the Job Load / Dispatch workflow to check "
            "equipment out to a job."
        )

        return RedirectResponse(
            "/scan?message=" + quote(message),
            status_code=303,
        )

    if action == "return":

        message = (
            "Use the job Return Equipment screen to check "
            "equipment in. This preserves return inspection "
            "and job-status tracking."
        )

        return RedirectResponse(
            "/scan?message=" + quote(message),
            status_code=303,
        )

    return RedirectResponse(
        "/scan?message="
        + quote("Unknown Scan Station action."),
        status_code=303,
    )