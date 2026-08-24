from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.inventory_service import availability
from ..services.pull_list_service import build_pull_list
from ..services.job_pull_service import pull_asset_to_prep
from ..services.job_load_service import load_asset_to_vehicle
from ..services.job_dispatch_service import dispatch_asset_to_job_site
from ..services.job_return_service import return_asset_to_prep
from ..services.return_inspection_service import route_returned_asset
from ..services.return_routing_service import find_next_job_for_item
from ..services.auth_service import request_has_permission

router = APIRouter()

def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )

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
def jobs(
    request: Request,
    message: str = "",
):
    if not request_has_permission(
        request,
        "jobs.view",
    ):
        return deny_access()

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
    request: Request,
    customer_id: int = Form(...),
    event_name: str = Form(""),
    venue: str = Form(""),
    out_date: str = Form(...),
    out_time: str = Form(""),
    return_date: str = Form(...),
    return_time: str = Form(""),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "jobs.create",
    ):
        return deny_access()

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
def job_detail(
    request: Request,
    job_id: int,
    message: str = "",
):
    if not request_has_permission(
        request,
        "jobs.view",
    ):
        return deny_access()

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

    assigned_vehicles = con.execute(
        """
        SELECT
            v.id,
            v.name,
            v.vehicle_number,
            v.license_plate,
            v.warehouse_location_id,
            wl.code AS location_code,
            wl.name AS location_name
        FROM job_vehicles jv
        JOIN vehicles v
            ON v.id = jv.vehicle_id
        LEFT JOIN warehouse_locations wl
            ON wl.id = v.warehouse_location_id
        WHERE jv.job_id = ?
        ORDER BY v.name
        """,
        (job_id,),
    ).fetchall()

    available_vehicles = con.execute(
        """
        SELECT
            v.id,
            v.name,
            v.vehicle_number,
            v.license_plate,
            v.warehouse_location_id,
            wl.code AS location_code,
            wl.name AS location_name
        FROM vehicles v
        JOIN warehouse_locations wl
            ON wl.id = v.warehouse_location_id
        WHERE v.active = 1
          AND wl.active = 1
          AND wl.location_type = 'Vehicle'
          AND NOT EXISTS (
              SELECT 1
              FROM job_vehicles jv
              WHERE jv.job_id = ?
                AND jv.vehicle_id = v.id
          )
        ORDER BY v.name
        """,
        (job_id,),
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
            "assigned_vehicles": assigned_vehicles,
            "available_vehicles": available_vehicles,
            "pull_list": pull_list,
            "message": message,
        },
    )


@router.post("/jobs/{job_id}/add-line")
def add_job_line(
    request: Request,
    job_id: int,
    item_master_id: int = Form(...),
    qty_needed: int = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "jobs.edit",
    ):
        return deny_access()

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
    request: Request,
    job_id: int,
    pack_id: int = Form(...),
):
    if not request_has_permission(
        request,
        "jobs.edit",
    ):
        return deny_access()

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

@router.post("/jobs/{job_id}/vehicles/assign")
def assign_vehicle_to_job(
    request: Request,
    job_id: int,
    vehicle_id: int = Form(...),
):
    if not request_has_permission(
        request,
        "jobs.edit",
    ):
        return deny_access()

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

    vehicle = con.execute(
        """
        SELECT
            v.*,
            wl.active AS location_active,
            wl.location_type
        FROM vehicles v
        LEFT JOIN warehouse_locations wl
            ON wl.id = v.warehouse_location_id
        WHERE v.id = ?
        """,
        (vehicle_id,),
    ).fetchone()

    if not vehicle:
        con.close()

        return RedirectResponse(
            f"/jobs/{job_id}?message=Vehicle not found",
            status_code=303,
        )

    if not vehicle["active"]:
        con.close()

        return RedirectResponse(
            f"/jobs/{job_id}?message=Vehicle is retired",
            status_code=303,
        )

    if vehicle["warehouse_location_id"] is None:
        con.close()

        return RedirectResponse(
            f"/jobs/{job_id}?message=Vehicle is not linked to a warehouse vehicle location",
            status_code=303,
        )

    if (
        not vehicle["location_active"]
        or vehicle["location_type"] != "Vehicle"
    ):
        con.close()

        return RedirectResponse(
            f"/jobs/{job_id}?message=Vehicle warehouse location is invalid",
            status_code=303,
        )

    con.execute(
        """
        INSERT OR IGNORE INTO job_vehicles(
            job_id,
            vehicle_id
        )
        VALUES (?, ?)
        """,
        (
            job_id,
            vehicle_id,
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
        f"/jobs/{job_id}?message=Vehicle assigned to job",
        status_code=303,
    )


@router.post("/jobs/{job_id}/vehicles/{vehicle_id}/remove")
def remove_vehicle_from_job(
    request: Request,
    job_id: int,
    vehicle_id: int,
):
    if not request_has_permission(
        request,
        "jobs.edit",
    ):
        return deny_access()

    con = connect()

    loaded_assets = con.execute(
        """
        SELECT COUNT(*)
        FROM assets
        WHERE assigned_job_id = ?
          AND location_id = (
              SELECT warehouse_location_id
              FROM vehicles
              WHERE id = ?
          )
        """,
        (
            job_id,
            vehicle_id,
        ),
    ).fetchone()[0]

    if loaded_assets > 0:
        con.close()

        return RedirectResponse(
            (
                f"/jobs/{job_id}"
                f"?message=Cannot remove vehicle while job equipment is loaded on it"
            ),
            status_code=303,
        )

    con.execute(
        """
        DELETE FROM job_vehicles
        WHERE job_id = ?
          AND vehicle_id = ?
        """,
        (
            job_id,
            vehicle_id,
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/jobs/{job_id}?message=Vehicle removed from job",
        status_code=303,
    )

@router.get("/jobs/{job_id}/pull", response_class=HTMLResponse)
def job_pull_page(
    request: Request,
    job_id: int,
    message: str = "",
):

    if not request_has_permission(
        request,
        "jobs.view",
    ):
        return deny_access()

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
    request: Request,
    job_id: int,
    barcode_value: str = Form(...),
):
    if not request_has_permission(
        request,
        "scan.checkout",
    ):
        return deny_access()

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

@router.get("/jobs/{job_id}/load", response_class=HTMLResponse)
def job_load_page(
    request: Request,
    job_id: int,
    vehicle_id: int | None = None,
    message: str = "",
):

    if not request_has_permission(
        request,
        "jobs.view",
    ):
        return deny_access()

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

    vehicles = con.execute(
        """
        SELECT
            v.id,
            v.name,
            v.vehicle_number,
            v.warehouse_location_id,
            wl.code AS location_code,
            wl.name AS location_name
        FROM job_vehicles jv
        JOIN vehicles v
            ON v.id = jv.vehicle_id
        JOIN warehouse_locations wl
            ON wl.id = v.warehouse_location_id
        WHERE jv.job_id = ?
          AND v.active = 1
          AND wl.active = 1
        ORDER BY v.name
        """,
        (job_id,),
    ).fetchall()

    if not vehicles:
        con.close()

        return RedirectResponse(
            f"/jobs/{job_id}?message=Assign a vehicle before loading equipment",
            status_code=303,
        )

    selected_vehicle = None

    if vehicle_id is not None:
        for vehicle in vehicles:
            if vehicle["id"] == vehicle_id:
                selected_vehicle = vehicle
                break

    if selected_vehicle is None:
        selected_vehicle = vehicles[0]

    prep = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = 'PREP'
          AND active = 1
        """
    ).fetchone()

    prep_assets = []

    if prep:
        prep_assets = con.execute(
            """
            SELECT
                a.id,
                a.asset_id,
                a.description,
                a.status
            FROM assets a
            WHERE a.assigned_job_id = ?
              AND a.location_id = ?
              AND a.status = 'Reserved / Prep'
            ORDER BY a.description, a.asset_id
            """,
            (
                job_id,
                prep["id"],
            ),
        ).fetchall()

    loaded_assets = con.execute(
        """
        SELECT
            a.id,
            a.asset_id,
            a.description,
            a.status
        FROM assets a
        WHERE a.assigned_job_id = ?
          AND a.location_id = ?
        ORDER BY a.description, a.asset_id
        """,
        (
            job_id,
            selected_vehicle["warehouse_location_id"],
        ),
    ).fetchall()

    total_pulled = len(prep_assets) + len(loaded_assets)
    total_loaded = len(loaded_assets)

    con.close()

    return request.app.state.templates.TemplateResponse(
        "job_load.html",
        {
            "request": request,
            "job": job,
            "vehicles": vehicles,
            "selected_vehicle": selected_vehicle,
            "prep_assets": prep_assets,
            "loaded_assets": loaded_assets,
            "total_pulled": total_pulled,
            "total_loaded": total_loaded,
            "message": message,
        },
    )


@router.post("/jobs/{job_id}/load")
def job_load_scan(
    request: Request,
    job_id: int,
    vehicle_id: int = Form(...),
    barcode_value: str = Form(...),
):
    if not request_has_permission(
        request,
        "scan.checkout",
    ):
        return deny_access()

    result = load_asset_to_vehicle(
        job_id,
        vehicle_id,
        barcode_value,
        notes="Vehicle Load scan",
    )

    return RedirectResponse(
        (
            f"/jobs/{job_id}/load"
            f"?vehicle_id={vehicle_id}"
            f"&message={quote(result['message'])}"
        ),
        status_code=303,
    )

@router.get("/jobs/{job_id}/dispatch", response_class=HTMLResponse)
def job_dispatch_page(
    request: Request,
    job_id: int,
    vehicle_id: int | None = None,
    message: str = "",
):

    if not request_has_permission(
        request,
        "jobs.view",
    ):
        return deny_access()

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

    vehicles = con.execute(
        """
        SELECT
            v.id,
            v.name,
            v.vehicle_number,
            v.warehouse_location_id,
            wl.code AS location_code,
            wl.name AS location_name
        FROM job_vehicles jv
        JOIN vehicles v
            ON v.id = jv.vehicle_id
        JOIN warehouse_locations wl
            ON wl.id = v.warehouse_location_id
        WHERE jv.job_id = ?
          AND v.active = 1
          AND wl.active = 1
        ORDER BY v.name
        """,
        (job_id,),
    ).fetchall()

    if not vehicles:
        con.close()

        return RedirectResponse(
            f"/jobs/{job_id}?message=Assign a vehicle before dispatch",
            status_code=303,
        )

    selected_vehicle = None

    if vehicle_id is not None:
        for vehicle in vehicles:
            if vehicle["id"] == vehicle_id:
                selected_vehicle = vehicle
                break

    if selected_vehicle is None:
        selected_vehicle = vehicles[0]

    job_site = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("JOB-SITE",),
    ).fetchone()

    loaded_assets = con.execute(
        """
        SELECT
            a.id,
            a.asset_id,
            a.description,
            a.status
        FROM assets a
        WHERE a.assigned_job_id = ?
          AND a.location_id = ?
          AND a.status = 'Loaded'
        ORDER BY a.description, a.asset_id
        """,
        (
            job_id,
            selected_vehicle["warehouse_location_id"],
        ),
    ).fetchall()

    dispatched_assets = []

    if job_site:
        dispatched_assets = con.execute(
            """
            SELECT
                a.id,
                a.asset_id,
                a.description,
                a.status
            FROM assets a
            WHERE a.assigned_job_id = ?
              AND a.location_id = ?
              AND a.status = 'Checked Out'
            ORDER BY a.description, a.asset_id
            """,
            (
                job_id,
                job_site["id"],
            ),
        ).fetchall()

    total_dispatchable = len(loaded_assets) + len(dispatched_assets)
    total_dispatched = len(dispatched_assets)

    con.close()

    return request.app.state.templates.TemplateResponse(
        "job_dispatch.html",
        {
            "request": request,
            "job": job,
            "vehicles": vehicles,
            "selected_vehicle": selected_vehicle,
            "loaded_assets": loaded_assets,
            "dispatched_assets": dispatched_assets,
            "total_dispatchable": total_dispatchable,
            "total_dispatched": total_dispatched,
            "message": message,
        },
    )


@router.post("/jobs/{job_id}/dispatch")
def job_dispatch_scan(
    request: Request,
    job_id: int,
    vehicle_id: int = Form(...),
    barcode_value: str = Form(...),
):
    if not request_has_permission(
        request,
        "scan.checkout",
    ):
        return deny_access()

    result = dispatch_asset_to_job_site(
        job_id,
        vehicle_id,
        barcode_value,
        notes="Job Dispatch scan",
    )

    return RedirectResponse(
        (
            f"/jobs/{job_id}/dispatch"
            f"?vehicle_id={vehicle_id}"
            f"&message={quote(result['message'])}"
        ),
        status_code=303,
    )

@router.get("/jobs/{job_id}/return", response_class=HTMLResponse)
def job_return_page(
    request: Request,
    job_id: int,
    message: str = "",
):

    if not request_has_permission(
        request,
        "jobs.view",
    ):
        return deny_access()

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

    job_site = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("JOB-SITE",),
    ).fetchone()

    prep = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("PREP",),
    ).fetchone()

    site_assets = []

    if job_site:
        site_assets = con.execute(
            """
            SELECT
                a.id,
                a.asset_id,
                a.item_master_id,
                a.description,
                a.status
            FROM assets a
            WHERE a.assigned_job_id = ?
              AND a.location_id = ?
              AND a.status = 'Checked Out'
            ORDER BY a.description, a.asset_id
            """,
            (
                job_id,
                job_site["id"],
            ),
        ).fetchall()

    returned_assets = []

    if prep:
        returned_assets = con.execute(
            """
            SELECT
                a.id,
                a.asset_id,
                a.item_master_id,
                a.description,
                a.status
            FROM assets a
            WHERE a.assigned_job_id = ?
              AND a.location_id = ?
              AND a.status = 'Returned / Inspection'
            ORDER BY a.description, a.asset_id
            """,
            (
                job_id,
                prep["id"],
            ),
        ).fetchall()

    total_expected = len(site_assets) + len(returned_assets)
    total_returned = len(returned_assets)

    con.close()

    returned_infos = []

    for asset in returned_assets:
        recommendation = find_next_job_for_item(
            current_job_id=job_id,
            item_master_id=asset["item_master_id"],
        )

        returned_infos.append(
            {
                "asset": asset,
                "recommendation": recommendation,
            }
        )

    return request.app.state.templates.TemplateResponse(
        "job_return.html",
        {
            "request": request,
            "job": job,
            "site_assets": site_assets,
            "returned_infos": returned_infos,
            "total_expected": total_expected,
            "total_returned": total_returned,
            "message": message,
        },
    )

@router.post("/jobs/{job_id}/return")
def job_return_scan(
    request: Request,
    job_id: int,
    barcode_value: str = Form(...),
):
    if not request_has_permission(
        request,
        "scan.checkin",
    ):
        return deny_access()

    result = return_asset_to_prep(
        job_id,
        barcode_value,
        notes="Job Return scan",
    )

    return RedirectResponse(
        (
            f"/jobs/{job_id}/return"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )

@router.post("/jobs/{job_id}/return/inspect")
def job_return_inspect(
    request: Request,
    job_id: int,
    barcode_value: str = Form(...),
    action: str = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "scan.checkin",
    ):
        return deny_access()

    result = route_returned_asset(
        job_id=job_id,
        barcode_value=barcode_value,
        action=action,
        notes=notes,
    )

    return RedirectResponse(
        (
            f"/jobs/{job_id}/return"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )