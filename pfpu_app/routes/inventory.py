from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect

router = APIRouter()


@router.get("/inventory", response_class=HTMLResponse)
def inventory(request: Request, q: str = "", message: str = ""):
    con = connect()

    base_query = """
        SELECT
            im.*,

            (
                SELECT COUNT(*)
                FROM assets a
                WHERE a.item_master_id = im.id
            ) AS tracked,

            (
                SELECT COALESCE(SUM(isl.qty_assigned), 0)
                FROM item_storage_locations isl
                WHERE isl.item_master_id = im.id
                  AND isl.active = 1
            ) AS storage_assigned

        FROM item_master im
    """

    if q:
        rows = con.execute(
            base_query
            + """
            WHERE im.description LIKE ?
               OR im.category LIKE ?
               OR im.prefix LIKE ?
            ORDER BY im.category, im.description
            LIMIT 500
            """,
            (
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
            ),
        ).fetchall()

    else:
        rows = con.execute(
            base_query
            + """
            ORDER BY im.category, im.description
            LIMIT 500
            """
        ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "inventory.html",
        {
            "request": request,
            "rows": rows,
            "q": q,
            "message": message,
        },
    )


@router.get("/inventory/{item_id}", response_class=HTMLResponse)
def inventory_detail(
    request: Request,
    item_id: int,
    message: str = "",
):
    con = connect()

    item = con.execute(
        """
        SELECT *
        FROM item_master
        WHERE id = ?
        """,
        (item_id,),
    ).fetchone()

    if not item:
        con.close()

        return RedirectResponse(
            "/inventory?message=Inventory item not found",
            status_code=303,
        )

    storage_locations = con.execute(
        """
        SELECT
            isl.*,
            wl.code AS location_code,
            wl.name AS location_name,
            wl.location_type
        FROM item_storage_locations isl
        JOIN warehouse_locations wl
            ON wl.id = isl.location_id
        WHERE isl.item_master_id = ?
          AND isl.active = 1
        ORDER BY isl.priority, wl.code
        """,
        (item_id,),
    ).fetchall()

    available_locations = con.execute(
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

    tracked_count = con.execute(
        """
        SELECT COUNT(*)
        FROM assets
        WHERE item_master_id = ?
        """,
        (item_id,),
    ).fetchone()[0]

    assigned_quantity = sum(
        row["qty_assigned"]
        for row in storage_locations
    )

    unassigned_quantity = max(
        0,
        (item["qty_total"] or 0) - assigned_quantity,
    )

    con.close()

    return request.app.state.templates.TemplateResponse(
        "inventory_detail.html",
        {
            "request": request,
            "item": item,
            "storage_locations": storage_locations,
            "available_locations": available_locations,
            "tracked_count": tracked_count,
            "assigned_quantity": assigned_quantity,
            "unassigned_quantity": unassigned_quantity,
            "message": message,
        },
    )


@router.post("/inventory/{item_id}/storage/add")
def add_storage_location(
    item_id: int,
    location_id: int = Form(...),
    qty_assigned: int = Form(...),
    priority: int = Form(100),
    notes: str = Form(""),
):
    con = connect()

    item = con.execute(
        """
        SELECT *
        FROM item_master
        WHERE id = ?
        """,
        (item_id,),
    ).fetchone()

    if not item:
        con.close()

        return RedirectResponse(
            "/inventory?message=Inventory item not found",
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
            f"/inventory/{item_id}?message=Location not found or inactive",
            status_code=303,
        )

    if qty_assigned < 0:
        con.close()

        return RedirectResponse(
            f"/inventory/{item_id}?message=Assigned quantity cannot be negative",
            status_code=303,
        )

    existing = con.execute(
        """
        SELECT *
        FROM item_storage_locations
        WHERE item_master_id = ?
          AND location_id = ?
        """,
        (
            item_id,
            location_id,
        ),
    ).fetchone()

    other_assigned = con.execute(
        """
        SELECT COALESCE(SUM(qty_assigned), 0)
        FROM item_storage_locations
        WHERE item_master_id = ?
          AND active = 1
          AND location_id != ?
        """,
        (
            item_id,
            location_id,
        ),
    ).fetchone()[0]

    new_total = other_assigned + qty_assigned

    if new_total > (item["qty_total"] or 0):
        con.close()

        return RedirectResponse(
            (
                f"/inventory/{item_id}"
                f"?message=Cannot assign {new_total} units. "
                f"Only {item['qty_total']} are owned."
            ),
            status_code=303,
        )

    if existing:
        con.execute(
            """
            UPDATE item_storage_locations
            SET qty_assigned = ?,
                priority = ?,
                notes = ?,
                active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                qty_assigned,
                priority,
                notes.strip(),
                existing["id"],
            ),
        )

    else:
        con.execute(
            """
            INSERT INTO item_storage_locations(
                item_master_id,
                location_id,
                qty_assigned,
                priority,
                notes,
                active
            )
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                item_id,
                location_id,
                qty_assigned,
                priority,
                notes.strip(),
            ),
        )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/inventory/{item_id}?message=Storage location saved",
        status_code=303,
    )


@router.post("/inventory/{item_id}/storage/{storage_id}/remove")
def remove_storage_location(
    item_id: int,
    storage_id: int,
):
    con = connect()

    con.execute(
        """
        UPDATE item_storage_locations
        SET active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
          AND item_master_id = ?
        """,
        (
            storage_id,
            item_id,
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/inventory/{item_id}?message=Storage location removed",
        status_code=303,
    )