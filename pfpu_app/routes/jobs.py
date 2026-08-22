from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.inventory_service import availability
from ..services.pull_list_service import build_pull_list
from ..services.job_pull_service import pull_asset_to_prep

router = APIRouter()


def next_job_number(con) -> str:
    """
    Generate job numbers in this format:

    JOB-2026-0001
    JOB-2026-0002

    Numbering resets each calendar year.
    """

    year = datetime.now().year
    prefix = f"JOB-{year}-"

    row = con.execute(
        """
        SELECT job_number
        FROM jobs
        WHERE job_number LIKE ?
        ORDER BY job_number DESC
        LIMIT 1
        """,
        (f"{prefix}%",),
    ).fetchone()

    next_number = 1

    if row:
        try:
            next_number = int(row["job_number"].split("-")[-1]) + 1
        except Exception:
            next_number = 1

    return f"{prefix}{next_number:04d}"


@router.get("/jobs", response_class=HTMLResponse)
def jobs(request: Request, message: str = ""):
    con = connect()

    rows = con.execute(
        """
        SELECT
            j.*,
            COALESCE(c.name, j.customer) AS customer_name
        FROM jobs j
        LEFT JOIN customers c
            ON c.id = j.customer_id
        ORDER BY j.out_date DESC, j.out_time DESC
        """
    ).fetchall()

    customers = con.execute(
        """
        SELECT id, name
        FROM customers
        WHERE active = 1
        ORDER BY name
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "rows": rows,
            "customers": customers,
            "message": message,
        },
    )


@router.post("/jobs/create")
def create_job(
    customer_id: int = Form(...),
    event_name: str = Form(""),
    venue: str = Form(""),
    out_date: str = Form(...),
    out_time: str = Form(""),
    return_date: str = Form(...),
    return_time: str = Form(""),
    notes: str = Form(""),
):
    con = connect()

    customer = con.execute(
        """
        SELECT *
        FROM customers
        WHERE id = ?
          AND active = 1
        """,
        (customer_id,),
    ).fetchone()

    if not customer:
        con.close()

        return RedirectResponse(
            "/jobs?message=Please select an active customer",
            status_code=303,
        )

    if return_date < out_date:
        con.close()

        return RedirectResponse(
            "/jobs?message=Return date cannot be before the out date",
            status_code=303,
        )

    job_number = next_job_number(con)

    con.execute(
        """
        INSERT INTO jobs(
            job_number,
            customer,
            customer_id,
            event_name,
            venue,
            out_date,
            out_time,
            return_date,
            return_time,
            status,
            prep_location,
            notes,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            job_number,
            customer["name"],
            customer_id,
            event_name.strip(),
            venue.strip(),
            out_date,
            out_time,
            return_date,
            return_time,
            "Planning",
            "Prep Area",
            notes.strip(),
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/jobs?message={job_number} created successfully",
        status_code=303,
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, message: str = ""):
    con = connect()

    job = con.execute(
        """
        SELECT
            j.*,
            COALESCE(c.name, j.customer) AS customer_name
        FROM jobs j
        LEFT JOIN customers c
            ON c.id = j.customer_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()

    if not job:
        con.close()

        return RedirectResponse(
            "/jobs?message=Job not found",
            status_code=303,
        )

    lines = con.execute(
        """
        SELECT
            jl.*,
            im.description,
            im.category,
            im.qty_total
        FROM job_lines jl
        JOIN item_master im
            ON im.id = jl.item_master_id
        WHERE jl.job_id = ?
        ORDER BY im.category, im.description
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
        """
        SELECT
            id,
            description,
            category,
            qty_total
        FROM item_master
        ORDER BY category, description
        LIMIT 1000
        """
    ).fetchall()

    job_packs = con.execute(
        """
        SELECT
            id,
            name,
            description
        FROM job_packs
        WHERE active = 1
        ORDER BY name
        """
    ).fetchall()

    pull_list = build_pull_list(job_id)

    con.close()

    return request.app.state.templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "job": job,
            "line_infos": line_infos,
            "items": items,
            "job_packs": job_packs,
            "pull_list": pull_list,
            "message": message,
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

    job = con.execute(
        """
        SELECT id
        FROM jobs
        WHERE id = ?
        """,
        (job_id,),
    ).fetchone()

    if not job:
        con.close()

        return RedirectResponse(
            "/jobs?message=Job not found",
            status_code=303,
        )

    existing = con.execute(
        """
        SELECT *
        FROM job_lines
        WHERE job_id = ?
          AND item_master_id = ?
        """,
        (job_id, item_master_id),
    ).fetchone()

    if existing:
        con.execute(
            """
            UPDATE job_lines
            SET qty_needed = qty_needed + ?,
                notes = CASE
                    WHEN ? != '' THEN ?
                    ELSE notes
                END
            WHERE id = ?
            """,
            (
                qty_needed,
                notes.strip(),
                notes.strip(),
                existing["id"],
            ),
        )

    else:
        con.execute(
            """
            INSERT INTO job_lines(
                job_id,
                item_master_id,
                qty_needed,
                notes
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                item_master_id,
                qty_needed,
                notes.strip(),
            ),
        )

    con.execute(
        """
        UPDATE jobs
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (job_id,),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/jobs/{job_id}",
        status_code=303,
    )

@router.post("/jobs/{job_id}/apply-pack")
def apply_job_pack(
    job_id: int,
    job_pack_id: int = Form(...),
):
    con = connect()

    job = con.execute(
        """
        SELECT *
        FROM jobs
        WHERE id = ?
        """,
        (job_id,),
    ).fetchone()

    if not job:
        con.close()

        return RedirectResponse(
            "/jobs?message=Job not found",
            status_code=303,
        )

    pack = con.execute(
        """
        SELECT *
        FROM job_packs
        WHERE id = ?
          AND active = 1
        """,
        (job_pack_id,),
    ).fetchone()

    if not pack:
        con.close()

        return RedirectResponse(
            f"/jobs/{job_id}?message=Job Pack not found or inactive",
            status_code=303,
        )

    pack_items = con.execute(
        """
        SELECT *
        FROM job_pack_items
        WHERE job_pack_id = ?
        """,
        (job_pack_id,),
    ).fetchall()

    if not pack_items:
        con.close()

        return RedirectResponse(
            f"/jobs/{job_id}?message=Selected Job Pack contains no equipment",
            status_code=303,
        )

    for pack_item in pack_items:

        existing = con.execute(
            """
            SELECT *
            FROM job_lines
            WHERE job_id = ?
              AND item_master_id = ?
            """,
            (
                job_id,
                pack_item["item_master_id"],
            ),
        ).fetchone()

        pack_note = f"Job Pack: {pack['name']}"

        if pack_item["notes"]:
            pack_note += f" — {pack_item['notes']}"

        if existing:
            con.execute(
                """
                UPDATE job_lines
                SET qty_needed = qty_needed + ?,
                    notes = CASE
                        WHEN notes IS NULL OR notes = ''
                            THEN ?
                        ELSE notes || ' | ' || ?
                    END
                WHERE id = ?
                """,
                (
                    pack_item["qty_needed"],
                    pack_note,
                    pack_note,
                    existing["id"],
                ),
            )

        else:
            con.execute(
                """
                INSERT INTO job_lines(
                    job_id,
                    item_master_id,
                    qty_needed,
                    notes
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    job_id,
                    pack_item["item_master_id"],
                    pack_item["qty_needed"],
                    pack_note,
                ),
            )

    con.execute(
        """
        UPDATE jobs
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (job_id,),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        (
            f"/jobs/{job_id}"
            f"?message=Job Pack {pack['name']} applied successfully"
        ),
        status_code=303,
    )

@router.get("/jobs/{job_id}/pull", response_class=HTMLResponse)
def job_pull_page(
    request: Request,
    job_id: int,
    message: str = "",
):
    con = connect()

    job = con.execute(
        """
        SELECT
            j.*,
            COALESCE(c.name, j.customer) AS customer_name
        FROM jobs j
        LEFT JOIN customers c
            ON c.id = j.customer_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()

    if not job:
        con.close()
        return RedirectResponse(
            "/jobs?message=Job not found",
            status_code=303,
        )

    con.close()

    pull_list = build_pull_list(job_id)

    pull_list = build_pull_list(job_id)

    total_needed = pull_list["total_required"]

    con = connect()

    total_pulled = con.execute(
        """
        SELECT COUNT(*)
        FROM assets
        WHERE assigned_job_id = ?
          AND status = 'Reserved / Prep'
        """,
        (job_id,),
    ).fetchone()[0]

    con.close()

    return request.app.state.templates.TemplateResponse(
        "job_pull.html",
        {
            "request": request,
            "job": job,
            "pull_list": pull_list,
            "total_needed": total_needed,
            "total_pulled": total_pulled,
            "message": message,
        },
    )


@router.post("/jobs/{job_id}/pull")
def job_pull_scan(
    job_id: int,
    barcode_value: str = Form(...),
):
    barcode_value = barcode_value.strip()

    if not barcode_value:
        return RedirectResponse(
            f"/jobs/{job_id}/pull?message=Scan an asset barcode",
            status_code=303,
        )

    result = pull_asset_to_prep(
        job_id,
        barcode_value,
        notes="Job Pull scan",
    )

    return RedirectResponse(
        f"/jobs/{job_id}/pull?message={quote(result['message'])}",
        status_code=303,
    )