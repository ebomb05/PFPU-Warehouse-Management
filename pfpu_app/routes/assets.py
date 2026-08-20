from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.barcode_service import make_barcode_svg
from ..services.inventory_service import next_asset_id

router = APIRouter()


@router.get("/assets", response_class=HTMLResponse)
def assets(request: Request, q: str = ""):
    con = connect()

    if q:
        rows = con.execute(
            """
            SELECT * FROM assets
            WHERE asset_id LIKE ?
               OR description LIKE ?
               OR current_location LIKE ?
            ORDER BY asset_id DESC
            LIMIT 500
            """,
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM assets ORDER BY id DESC LIMIT 500"
        ).fetchall()

    items = con.execute(
        "SELECT id, description, qty_total, prefix FROM item_master ORDER BY description LIMIT 1000"
    ).fetchall()
    locations = con.execute(
        "SELECT name FROM locations ORDER BY name"
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
        },
    )


@router.post("/assets/generate")
def generate_assets(
    item_master_id: int = Form(...),
    qty: int = Form(...),
    location: str = Form("Warehouse"),
):
    con = connect()
    item = con.execute(
        "SELECT * FROM item_master WHERE id=?",
        (item_master_id,),
    ).fetchone()

    if not item:
        con.close()
        return RedirectResponse("/assets", status_code=303)

    for _ in range(max(0, min(qty, 500))):
        asset_id = next_asset_id(item["prefix"])
        svg_file = make_barcode_svg(asset_id)

        con.execute(
            """
            INSERT INTO assets(
                asset_id, barcode_value, item_master_id, description,
                category, status, current_location
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                asset_id,
                asset_id,
                item_master_id,
                item["description"],
                item["category"],
                "Available",
                location,
            ),
        )

        con.execute(
            """
            INSERT INTO barcode_queue(
                asset_id, barcode_value, description, svg_file
            )
            VALUES(?,?,?,?)
            """,
            (asset_id, asset_id, item["description"], svg_file),
        )

    con.commit()
    con.close()
    return RedirectResponse("/assets", status_code=303)
