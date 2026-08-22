from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect

router = APIRouter()


@router.get("/job-packs", response_class=HTMLResponse)
def job_packs_page(
    request: Request,
    message: str = "",
):
    con = connect()

    packs = con.execute(
        """
        SELECT
            jp.*,
            COUNT(jpi.id) AS item_count,
            COALESCE(SUM(jpi.qty_needed), 0) AS total_quantity
        FROM job_packs jp
        LEFT JOIN job_pack_items jpi
            ON jpi.job_pack_id = jp.id
        GROUP BY jp.id
        ORDER BY jp.active DESC, jp.name
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "job_packs.html",
        {
            "request": request,
            "packs": packs,
            "message": message,
        },
    )


@router.post("/job-packs/create")
def create_job_pack(
    name: str = Form(...),
    description: str = Form(""),
):
    name = name.strip()

    if not name:
        return RedirectResponse(
            "/job-packs?message=Job Pack name is required",
            status_code=303,
        )

    con = connect()

    existing = con.execute(
        """
        SELECT id
        FROM job_packs
        WHERE LOWER(name) = LOWER(?)
        """,
        (name,),
    ).fetchone()

    if existing:
        con.close()

        return RedirectResponse(
            "/job-packs?message=A Job Pack with that name already exists",
            status_code=303,
        )

    con.execute(
        """
        INSERT INTO job_packs(
            name,
            description,
            active
        )
        VALUES (?, ?, 1)
        """,
        (
            name,
            description.strip(),
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/job-packs?message=Job Pack {name} created",
        status_code=303,
    )


@router.get("/job-packs/{pack_id}", response_class=HTMLResponse)
def job_pack_detail(
    request: Request,
    pack_id: int,
    message: str = "",
):
    con = connect()

    pack = con.execute(
        """
        SELECT *
        FROM job_packs
        WHERE id = ?
        """,
        (pack_id,),
    ).fetchone()

    if not pack:
        con.close()

        return RedirectResponse(
            "/job-packs?message=Job Pack not found",
            status_code=303,
        )

    pack_items = con.execute(
        """
        SELECT
            jpi.*,
            im.description,
            im.category,
            im.qty_total
        FROM job_pack_items jpi
        JOIN item_master im
            ON im.id = jpi.item_master_id
        WHERE jpi.job_pack_id = ?
        ORDER BY im.category, im.description
        """,
        (pack_id,),
    ).fetchall()

    inventory_items = con.execute(
        """
        SELECT
            id,
            description,
            category,
            qty_total
        FROM item_master
        ORDER BY category, description
        LIMIT 2000
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "job_pack_detail.html",
        {
            "request": request,
            "pack": pack,
            "pack_items": pack_items,
            "inventory_items": inventory_items,
            "message": message,
        },
    )


@router.post("/job-packs/{pack_id}/update")
def update_job_pack(
    pack_id: int,
    name: str = Form(...),
    description: str = Form(""),
):
    con = connect()

    pack = con.execute(
        """
        SELECT id
        FROM job_packs
        WHERE id = ?
        """,
        (pack_id,),
    ).fetchone()

    if not pack:
        con.close()

        return RedirectResponse(
            "/job-packs?message=Job Pack not found",
            status_code=303,
        )

    duplicate = con.execute(
        """
        SELECT id
        FROM job_packs
        WHERE LOWER(name) = LOWER(?)
          AND id != ?
        """,
        (
            name.strip(),
            pack_id,
        ),
    ).fetchone()

    if duplicate:
        con.close()

        return RedirectResponse(
            f"/job-packs/{pack_id}?message=Another Job Pack already uses that name",
            status_code=303,
        )

    con.execute(
        """
        UPDATE job_packs
        SET name = ?,
            description = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            name.strip(),
            description.strip(),
            pack_id,
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/job-packs/{pack_id}?message=Job Pack updated successfully",
        status_code=303,
    )


@router.post("/job-packs/{pack_id}/add-item")
def add_job_pack_item(
    pack_id: int,
    item_master_id: int = Form(...),
    qty_needed: int = Form(...),
    notes: str = Form(""),
):
    con = connect()

    existing = con.execute(
        """
        SELECT *
        FROM job_pack_items
        WHERE job_pack_id = ?
          AND item_master_id = ?
        """,
        (
            pack_id,
            item_master_id,
        ),
    ).fetchone()

    if existing:
        con.execute(
            """
            UPDATE job_pack_items
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
            INSERT INTO job_pack_items(
                job_pack_id,
                item_master_id,
                qty_needed,
                notes
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                pack_id,
                item_master_id,
                qty_needed,
                notes.strip(),
            ),
        )

    con.execute(
        """
        UPDATE job_packs
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (pack_id,),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/job-packs/{pack_id}",
        status_code=303,
    )


@router.post("/job-packs/{pack_id}/items/{item_id}/update")
def update_job_pack_item(
    pack_id: int,
    item_id: int,
    qty_needed: int = Form(...),
    notes: str = Form(""),
):
    con = connect()

    con.execute(
        """
        UPDATE job_pack_items
        SET qty_needed = ?,
            notes = ?
        WHERE id = ?
          AND job_pack_id = ?
        """,
        (
            max(1, qty_needed),
            notes.strip(),
            item_id,
            pack_id,
        ),
    )

    con.execute(
        """
        UPDATE job_packs
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (pack_id,),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/job-packs/{pack_id}?message=Pack item updated",
        status_code=303,
    )


@router.post("/job-packs/{pack_id}/items/{item_id}/remove")
def remove_job_pack_item(
    pack_id: int,
    item_id: int,
):
    con = connect()

    con.execute(
        """
        DELETE FROM job_pack_items
        WHERE id = ?
          AND job_pack_id = ?
        """,
        (
            item_id,
            pack_id,
        ),
    )

    con.execute(
        """
        UPDATE job_packs
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (pack_id,),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/job-packs/{pack_id}?message=Item removed from Job Pack",
        status_code=303,
    )


@router.post("/job-packs/{pack_id}/toggle-active")
def toggle_job_pack_active(pack_id: int):
    con = connect()

    pack = con.execute(
        """
        SELECT *
        FROM job_packs
        WHERE id = ?
        """,
        (pack_id,),
    ).fetchone()

    if not pack:
        con.close()

        return RedirectResponse(
            "/job-packs?message=Job Pack not found",
            status_code=303,
        )

    new_status = 0 if pack["active"] else 1

    con.execute(
        """
        UPDATE job_packs
        SET active = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            new_status,
            pack_id,
        ),
    )

    con.commit()
    con.close()

    message = (
        "Job Pack reactivated successfully"
        if new_status
        else "Job Pack retired successfully"
    )

    return RedirectResponse(
        f"/job-packs/{pack_id}?message={message}",
        status_code=303,
    )