from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.auth_service import request_has_permission
from ..services.return_inspection_service import route_returned_asset
from ..services.return_routing_service import find_next_job_for_item


router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/inspection", response_class=HTMLResponse)
def inspection_page(
    request: Request,
    message: str = "",
    result: str = "",
    inspect_asset: str = "",
):
    if not request_has_permission(
        request,
        "scan.checkin",
    ):
        return deny_access()

    con = connect()

    inspection = con.execute(
        """
        SELECT
            id,
            code,
            name
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("INSPECTION",),
    ).fetchone()

    if not inspection:
        con.close()

        return request.app.state.templates.TemplateResponse(
            "inspection.html",
            {
                "request": request,
                "inspection": None,
                "waiting_count": 0,
                "waiting_assets": [],
                "selected_info": None,
                "message": (
                    message
                    or "INSPECTION location is missing or inactive."
                ),
                "result": result or "error",
            },
        )

    waiting_assets = con.execute(
        """
        SELECT
            a.id,
            a.asset_id,
            a.description,
            a.status,
            a.assigned_job_id,
            j.job_number,
            j.event_name,
            COALESCE(c.name, j.customer) AS customer_name
        FROM assets a
        LEFT JOIN jobs j
            ON j.id = a.assigned_job_id
        LEFT JOIN customers c
            ON c.id = j.customer_id
        WHERE a.location_id = ?
          AND a.status = 'Returned / Inspection'
        ORDER BY
            j.job_number,
            a.description,
            a.asset_id
        """,
        (inspection["id"],),
    ).fetchall()

    waiting_count = len(waiting_assets)

    selected_asset = None

    inspect_asset = inspect_asset.strip()

    if inspect_asset:
        selected_asset = con.execute(
            """
            SELECT
                a.id,
                a.asset_id,
                a.barcode_value,
                a.item_master_id,
                a.description,
                a.status,
                a.assigned_job_id,
                j.job_number,
                j.event_name,
                COALESCE(c.name, j.customer) AS customer_name
            FROM assets a
            LEFT JOIN jobs j
                ON j.id = a.assigned_job_id
            LEFT JOIN customers c
                ON c.id = j.customer_id
            WHERE a.location_id = ?
              AND a.status = 'Returned / Inspection'
              AND (
                    a.barcode_value = ?
                    OR a.asset_id = ?
                  )
            """,
            (
                inspection["id"],
                inspect_asset,
                inspect_asset,
            ),
        ).fetchone()

    con.close()

    selected_info = None

    if selected_asset:
        recommendation = None

        if selected_asset["assigned_job_id"] is not None:
            recommendation = find_next_job_for_item(
                current_job_id=selected_asset["assigned_job_id"],
                item_master_id=selected_asset["item_master_id"],
            )

        selected_info = {
            "asset": selected_asset,
            "recommendation": recommendation,
        }

    return request.app.state.templates.TemplateResponse(
        "inspection.html",
        {
            "request": request,
            "inspection": inspection,
            "waiting_count": waiting_count,
            "waiting_assets": waiting_assets,
            "selected_info": selected_info,
            "message": message,
            "result": result,
        },
    )


@router.post("/inspection/select")
def inspection_select_asset(
    request: Request,
    barcode_value: str = Form(...),
):
    if not request_has_permission(
        request,
        "scan.checkin",
    ):
        return deny_access()

    barcode_value = barcode_value.strip()

    if not barcode_value:
        return RedirectResponse(
            (
                "/inspection"
                "?result=error"
                "&message="
                + quote("Scan an asset QR / Asset ID.")
            ),
            status_code=303,
        )

    con = connect()

    inspection = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("INSPECTION",),
    ).fetchone()

    if not inspection:
        con.close()

        return RedirectResponse(
            (
                "/inspection"
                "?result=error"
                "&message="
                + quote(
                    "INSPECTION location is missing or inactive."
                )
            ),
            status_code=303,
        )

    asset = con.execute(
        """
        SELECT
            asset_id,
            assigned_job_id
        FROM assets
        WHERE location_id = ?
          AND status = 'Returned / Inspection'
          AND (
                barcode_value = ?
                OR asset_id = ?
              )
        """,
        (
            inspection["id"],
            barcode_value,
            barcode_value,
        ),
    ).fetchone()

    con.close()

    if not asset:
        return RedirectResponse(
            (
                "/inspection"
                "?result=error"
                "&message="
                + quote(
                    "That asset is not waiting for inspection."
                )
            ),
            status_code=303,
        )

    if asset["assigned_job_id"] is None:
        return RedirectResponse(
            (
                "/inspection"
                "?result=error"
                "&message="
                + quote(
                    f"{asset['asset_id']} has no originating job assigned."
                )
            ),
            status_code=303,
        )

    return RedirectResponse(
        (
            "/inspection"
            f"?inspect_asset={quote(asset['asset_id'])}"
        ),
        status_code=303,
    )


@router.post("/inspection/inspect")
def inspection_route_asset(
    request: Request,
    barcode_value: str = Form(...),
    action: str = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "scan.checkin",
    ):
        return deny_access()

    barcode_value = barcode_value.strip()

    con = connect()

    inspection = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("INSPECTION",),
    ).fetchone()

    if not inspection:
        con.close()

        return RedirectResponse(
            (
                "/inspection"
                "?result=error"
                "&message="
                + quote(
                    "INSPECTION location is missing or inactive."
                )
            ),
            status_code=303,
        )

    asset = con.execute(
        """
        SELECT
            asset_id,
            assigned_job_id
        FROM assets
        WHERE location_id = ?
          AND status = 'Returned / Inspection'
          AND (
                barcode_value = ?
                OR asset_id = ?
              )
        """,
        (
            inspection["id"],
            barcode_value,
            barcode_value,
        ),
    ).fetchone()

    con.close()

    if not asset:
        return RedirectResponse(
            (
                "/inspection"
                "?result=error"
                "&message="
                + quote(
                    "That asset is no longer waiting for inspection."
                )
            ),
            status_code=303,
        )

    if asset["assigned_job_id"] is None:
        return RedirectResponse(
            (
                "/inspection"
                "?result=error"
                "&message="
                + quote(
                    f"{asset['asset_id']} has no originating job assigned."
                )
            ),
            status_code=303,
        )

    inspection_result = route_returned_asset(
        job_id=asset["assigned_job_id"],
        barcode_value=asset["asset_id"],
        action=action,
        user_id=request.state.user_id,
        notes=notes,
    )

    result_type = (
        "success"
        if inspection_result["success"]
        else "error"
    )

    return RedirectResponse(
        (
            "/inspection"
            f"?result={result_type}"
            f"&message={quote(inspection_result['message'])}"
        ),
        status_code=303,
    )