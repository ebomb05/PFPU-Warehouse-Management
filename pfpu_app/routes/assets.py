from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.asset_service import move_asset
from ..services.asset_generation_service import generate_assets_for_item
from ..services.auth_service import request_has_permission

router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/assets", response_class=HTMLResponse)
def assets(
    request: Request,
    q: str = "",
    message: str = "",
):
    if not request_has_permission(
        request,
        "inventory.view",
    ):
        return deny_access()

    con = connect()

    if q:
        rows = con.execute(
            """
            SELECT
                a.*,
                wl.code AS location_code,
                wl.name AS location_name
            FROM assets a
            LEFT JOIN warehouse_locations wl
                ON wl.id = a.location_id
            WHERE a.asset_id LIKE ?
               OR a.description LIKE ?
               OR a.current_location LIKE ?
               OR wl.code LIKE ?
               OR wl.name LIKE ?
            ORDER BY a.asset_id DESC
            LIMIT 500
            """,
            (
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
            ),
        ).fetchall()

    else:
        rows = con.execute(
            """
            SELECT
                a.*,
                wl.code AS location_code,
                wl.name AS location_name
            FROM assets a
            LEFT JOIN warehouse_locations wl
                ON wl.id = a.location_id
            ORDER BY a.id DESC
            LIMIT 500
            """
        ).fetchall()

    items = con.execute(
        """
        SELECT
            im.id,
            im.description,
            im.qty_total,
            im.prefix,
            (
                SELECT COUNT(*)
                FROM assets a
                WHERE a.item_master_id = im.id
            ) AS tracked_count
        FROM item_master im
        ORDER BY im.description
        LIMIT 1000
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
        ORDER BY
            CASE
                WHEN location_type = 'Shelf' THEN 0
                ELSE 1
            END,
            code
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "assets.html",
        {
            "request": request,
            "rows": rows,
            "items": items,
            "locations": locations,
            "q": q,
            "message": message,
        },
    )


@router.post("/assets/generate")
def generate_assets(
    request: Request,
    item_master_id: int = Form(...),
    qty: int = Form(...),
    location_id: int = Form(...),
):
    if not request_has_permission(
        request,
        "assets.create",
    ):
        return deny_access()

    result = generate_assets_for_item(
        item_master_id=item_master_id,
        qty=qty,
        location_id=location_id,
    )

    return RedirectResponse(
        "/assets?message="
        + quote(result["message"]),
        status_code=303,
    )


@router.post("/assets/{asset_db_id}/move")
def move_asset_route(
    request: Request,
    asset_db_id: int,
    location_id: int = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "assets.move",
    ):
        return deny_access()

    result = move_asset(
        asset_id=asset_db_id,
        to_location_id=location_id,
        action="Manual Move",
        notes=notes,
        user_id=request.state.user_id,
    )

    return RedirectResponse(
        "/assets?message="
        + quote(result["message"]),
        status_code=303,
    )

@router.get("/assets/{asset_db_id}", response_class=HTMLResponse)
def asset_detail(
    request: Request,
    asset_db_id: int,
):
    if not request_has_permission(
        request,
        "inventory.view",
    ):
        return deny_access()

    con = connect()

    asset = con.execute(
        """
        SELECT
            a.*,
            wl.code AS location_code,
            wl.name AS location_name,
            wl.location_type,
            j.job_number,
            j.customer AS job_customer,
            j.event_name AS job_event_name,
            j.status AS job_status
        FROM assets a
        LEFT JOIN warehouse_locations wl
            ON wl.id = a.location_id
        LEFT JOIN jobs j
            ON j.id = a.assigned_job_id
        WHERE a.id = ?
        """,
        (asset_db_id,),
    ).fetchone()

    if not asset:
        con.close()

        return RedirectResponse(
            "/assets?message="
            + quote("Asset not found."),
            status_code=303,
        )

    open_repair = con.execute(
        """
        SELECT
            rr.*,
            opened_user.display_name AS opened_by_name,
            updated_user.display_name AS updated_by_name
        FROM repair_records rr
        LEFT JOIN users opened_user
            ON opened_user.id = rr.opened_by
        LEFT JOIN users updated_user
            ON updated_user.id = rr.updated_by
        WHERE rr.asset_id = ?
          AND rr.closed_at IS NULL
        ORDER BY rr.id DESC
        LIMIT 1
        """,
        (asset_db_id,),
    ).fetchone()

    movement_history = con.execute(
        """
        SELECT
            h.*,
            old_location.code AS from_location_code,
            old_location.name AS from_location_name,
            new_location.code AS to_location_code,
            new_location.name AS to_location_name,
            u.display_name AS moved_by_name,
            j.job_number AS history_job_number
        FROM asset_location_history h
        LEFT JOIN warehouse_locations old_location
            ON old_location.id = h.from_location_id
        LEFT JOIN warehouse_locations new_location
            ON new_location.id = h.to_location_id
        LEFT JOIN users u
            ON u.id = h.user_id
        LEFT JOIN jobs j
            ON j.id = h.job_id
        WHERE h.asset_id = ?
        ORDER BY h.id DESC
        LIMIT 20
        """,
        (asset_db_id,),
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
        ORDER BY
            CASE
                WHEN location_type = 'Shelf' THEN 0
                ELSE 1
            END,
            code
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "asset_detail.html",
        {
            "request": request,
            "asset": asset,
            "open_repair": open_repair,
            "movement_history": movement_history,
            "locations": locations,
        },
    )