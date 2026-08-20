from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..database import connect

router = APIRouter()


@router.get("/inventory", response_class=HTMLResponse)
def inventory(request: Request, q: str = ""):
    con = connect()

    if q:
        rows = con.execute(
            """
            SELECT im.*,
                (SELECT COUNT(*) FROM assets a WHERE a.item_master_id=im.id) tracked
            FROM item_master im
            WHERE description LIKE ? OR category LIKE ?
            ORDER BY category, description
            LIMIT 500
            """,
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = con.execute(
            """
            SELECT im.*,
                (SELECT COUNT(*) FROM assets a WHERE a.item_master_id=im.id) tracked
            FROM item_master im
            ORDER BY category, description
            LIMIT 500
            """
        ).fetchall()

    con.close()
    return request.app.state.templates.TemplateResponse(
        "inventory.html",
        {"request": request, "rows": rows, "q": q},
    )
