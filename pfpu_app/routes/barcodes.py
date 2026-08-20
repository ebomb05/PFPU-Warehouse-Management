from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..database import connect

router = APIRouter()


@router.get("/barcodes", response_class=HTMLResponse)
def barcodes(request: Request):
    con = connect()
    rows = con.execute(
        "SELECT * FROM barcode_queue ORDER BY id DESC LIMIT 200"
    ).fetchall()
    con.close()

    return request.app.state.templates.TemplateResponse(
        "barcodes.html",
        {"request": request, "rows": rows},
    )
