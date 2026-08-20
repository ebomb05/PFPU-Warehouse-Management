from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.inventory_service import availability

router = APIRouter()


@router.get("/jobs", response_class=HTMLResponse)
def jobs(request: Request):
    con = connect()
    rows = con.execute("SELECT * FROM jobs ORDER BY out_date DESC").fetchall()
    con.close()

    return request.app.state.templates.TemplateResponse(
        "jobs.html",
        {"request": request, "rows": rows},
    )


@router.post("/jobs/create")
def create_job(
    customer: str = Form(...),
    event_name: str = Form(""),
    out_date: str = Form(...),
    return_date: str = Form(...),
    notes: str = Form(""),
):
    # Step 4A preserves the current job number behavior intentionally.
    job_number = f"JOB-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    con = connect()
    con.execute(
        """
        INSERT INTO jobs(
            job_number, customer, event_name, out_date, return_date, notes
        )
        VALUES(?,?,?,?,?,?)
        """,
        (job_number, customer, event_name, out_date, return_date, notes),
    )
    con.commit()
    con.close()

    return RedirectResponse("/jobs", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int):
    con = connect()
    job = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    if not job:
        con.close()
        return RedirectResponse("/jobs", status_code=303)

    lines = con.execute(
        """
        SELECT jl.*, im.description, im.category, im.qty_total
        FROM job_lines jl
        JOIN item_master im ON im.id=jl.item_master_id
        WHERE jl.job_id=?
        """,
        (job_id,),
    ).fetchall()

    line_infos = []
    for line in lines:
        available = availability(
            line["item_master_id"],
            job["out_date"],
            job["return_date"],
            exclude_job_id=job_id,
        )
        line_infos.append(
            {
                "line": line,
                "availability": available,
                "conflict": line["qty_needed"] > available["available"],
            }
        )

    items = con.execute(
        "SELECT id, description, category, qty_total FROM item_master ORDER BY description LIMIT 1000"
    ).fetchall()
    con.close()

    return request.app.state.templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "job": job,
            "line_infos": line_infos,
            "items": items,
        },
    )


@router.post("/jobs/{job_id}/add-line")
def add_job_line(
    job_id: int,
    item_master_id: int = Form(...),
    qty_needed: int = Form(...),
    notes: str = Form(""),
):
    con = connect()
    con.execute(
        """
        INSERT INTO job_lines(job_id, item_master_id, qty_needed, notes)
        VALUES(?,?,?,?)
        """,
        (job_id, item_master_id, qty_needed, notes),
    )
    con.commit()
    con.close()

    return RedirectResponse(f"/jobs/{job_id}", status_code=303)
