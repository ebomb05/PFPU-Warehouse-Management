from urllib.parse import quote

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
            "/assets?message="
            + quote("Inventory item was not found."),
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
            "/assets?message="
            + quote("Please choose an active location."),
            status_code=303,
        )

    create_qty = max(0, min(qty, 500))

    if create_qty < 1:
        con.close()

        return RedirectResponse(
            "/assets?message="
            + quote("Quantity must be at least 1."),
            status_code=303,
        )

    prefix = (item["prefix"] or "").strip()

    if not prefix:
        con.close()

        return RedirectResponse(
            "/assets?message="
            + quote(
                "This inventory item does not have an "
                "Asset ID prefix."
            ),
            status_code=303,
        )

    location_text = location["code"]

    created_count = 0

    try:

        for _ in range(create_qty):

            # -------------------------------------------------
            # GENERATE A UNIQUE ASSET ID
            # -------------------------------------------------

            candidate = next_asset_id(prefix)

            existing = con.execute(
                """
                SELECT id
                FROM assets
                WHERE asset_id = ?
                   OR barcode_value = ?
                LIMIT 1
                """,
                (
                    candidate,
                    candidate,
                ),
            ).fetchone()

            # next_asset_id() may use another DB connection.
            # During a multi-asset batch, our uncommitted inserts
            # may therefore be invisible to it. If the suggested
            # ID is already used in this transaction, advance the
            # numeric suffix until we find a free ID.
            if existing:

                parts = candidate.rsplit("-", 1)

                if (
                    len(parts) == 2
                    and parts[1].isdigit()
                ):
                    id_prefix = parts[0]
                    number = int(parts[1])
                    width = len(parts[1])

                    while existing:
                        number += 1

                        candidate = (
                            f"{id_prefix}-"
                            f"{number:0{width}d}"
                        )

                        existing = con.execute(
                            """
                            SELECT id
                            FROM assets
                            WHERE asset_id = ?
                               OR barcode_value = ?
                            LIMIT 1
                            """,
                            (
                                candidate,
                                candidate,
                            ),
                        ).fetchone()

                else:
                    raise ValueError(
                        "Unable to safely generate the next "
                        "Asset ID."
                    )

            asset_id = candidate

            # -------------------------------------------------
            # CREATE BARCODE FILE
            # -------------------------------------------------

            svg_file = make_barcode_svg(asset_id)

            # -------------------------------------------------
            # CREATE ASSET
            # -------------------------------------------------

            cursor = con.execute(
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

            new_asset_db_id = cursor.lastrowid

            # -------------------------------------------------
            # ADD BARCODE TO PRINT QUEUE
            # -------------------------------------------------

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

            # -------------------------------------------------
            # RECORD INITIAL LOCATION HISTORY
            # -------------------------------------------------

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
                    new_asset_db_id,
                    location_id,
                    "Asset Created",
                    "Initial asset location",
                ),
            )

            created_count += 1

        con.commit()

    except Exception as exc:

        con.rollback()
        con.close()

        return RedirectResponse(
            "/assets?message="
            + quote(
                "Asset generation failed. "
                f"No assets were created. {exc}"
            ),
            status_code=303,
        )

    con.close()

    return RedirectResponse(
        "/assets?message="
        + quote(
            f"Successfully created {created_count} "
            f"asset(s) for {item['description']}."
        ),
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
        "/assets?message="
        + quote(result["message"]),
        status_code=303,
    )