from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect

router = APIRouter()


@router.get("/scan", response_class=HTMLResponse)
def scan_page(request: Request, message: str = ""):
    con = connect()
    jobs = con.execute(
        """
        SELECT id, job_number, customer, event_name
        FROM jobs
        WHERE status NOT IN ('Cancelled','Returned')
        ORDER BY out_date
        """
    ).fetchall()
    locations = con.execute(
        "SELECT name FROM locations ORDER BY name"
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
    barcode_value: str = Form(...),
    action: str = Form(...),
    to_location: str = Form(""),
    job_id: Optional[int] = Form(None),
    notes: str = Form(""),
):
    barcode_value = barcode_value.strip()
    con = connect()

    asset = con.execute(
        "SELECT * FROM assets WHERE barcode_value=? OR asset_id=?",
        (barcode_value, barcode_value),
    ).fetchone()

    if not asset:
        con.close()
        return RedirectResponse(
            "/scan?message=" + quote("Barcode not found. Create the asset first."),
            status_code=303,
        )

    old_location = asset["current_location"]
    status = asset["status"]
    new_location = to_location or old_location
    assigned_job = asset["assigned_job_id"]

    if action == "return":
        status = "Available"
        assigned_job = None
        if not to_location:
            new_location = "Warehouse"
    elif action == "prep":
        status = "Reserved / Prep"
        new_location = "Prep Area"
    elif action == "checkout":
        status = "Checked Out"
        new_location = "Customer / Job Site"
        assigned_job = job_id
    elif action == "repair":
        status = "Repair"
        new_location = "Repair"

    con.execute(
        """
        UPDATE assets
        SET status=?, current_location=?, assigned_job_id=?
        WHERE id=?
        """,
        (status, new_location, assigned_job, asset["id"]),
    )

    con.execute(
        """
        INSERT INTO scan_log(
            barcode_value, asset_id, action, from_location,
            to_location, job_id, notes
        )
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            barcode_value,
            asset["asset_id"],
            action,
            old_location,
            new_location,
            job_id,
            notes,
        ),
    )

    con.commit()
    con.close()

    message = f"{asset['asset_id']} updated: {action} → {new_location}"
    return RedirectResponse(
        "/scan?message=" + quote(message),
        status_code=303,
    )
