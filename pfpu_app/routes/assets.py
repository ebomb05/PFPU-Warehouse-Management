from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.asset_service import move_asset
from ..services.auth_service import request_has_permission
from ..services.barcode_service import make_barcode_svg
from ..services.inventory_service import next_asset_id

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
        SELECT id, description, qty_total, prefix
        FROM item_master
        ORDER BY description
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

    con = connect()

    item = con.execute(
        """
        SELECT *
        FROM item_master
        WHERE id = ?
        """,
        (item_master_id,),
    ).fetchone()

    if not item:
        con.close()

        return RedirectResponse(
            "/assets",
            status_code=303,
        )

    location = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE id = ?
          AND active = 1
        """,
        (location_id,),
    ).fetchone()

    if not location:
        con.close()

        return RedirectResponse(
            "/assets",
            status_code=303,
        )

    location_text = location["code"]

    for _ in range(max(0, min(qty, 500))):
        asset_id = next_asset_id(item["prefix"])
        svg_file = make_barcode_svg(asset_id)

        con.execute(
            """
            INSERT INTO assets(
                asset_id,
                barcode_value,
                item_master_id,
                description,
                category,
                status,
                current_location,
                location_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                asset_id,
                item_master_id,
                item["description"],
                item["category"],
                "Available",
                location_text,
                location_id,
            ),
        )

        con.execute(
            """
            INSERT INTO barcode_queue(
                asset_id,
                barcode_value,
                description,
                svg_file
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                asset_id,
                asset_id,
                item["description"],
                svg_file,
            ),
        )

        new_asset = con.execute(
            """
            SELECT id
            FROM assets
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()

        if new_asset:
            con.execute(
                """
                INSERT INTO asset_location_history(
                    asset_id,
                    from_location_id,
                    to_location_id,
                    action,
                    notes
                )
                VALUES (?, NULL, ?, ?, ?)
                """,
                (
                    new_asset["id"],
                    location_id,
                    "Asset Created",
                    "Initial asset location",
                ),
            )

    con.commit()
    con.close()

    return RedirectResponse(
        "/assets",
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
    )

    return RedirectResponse(
        f"/assets?message={result['message']}",
        status_code=303,
    )