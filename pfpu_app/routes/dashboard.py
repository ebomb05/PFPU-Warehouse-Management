from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from ..database import connect
from ..services.auth_service import request_has_permission
from ..services.inventory_service import availability


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    message: str = "",
):
    if not request_has_permission(
        request,
        "dashboard.view",
    ):
        return PlainTextResponse(
            "Access denied",
            status_code=403,
        )

    con = connect()

    today_date = date.today()
    today = today_date.isoformat()
    soon_date = (
        today_date + timedelta(days=2)
    ).isoformat()

    # =====================================================
    # DASHBOARD STAT CARDS
    # =====================================================

    stats = {
        "jobs_today": con.execute(
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE out_date = ?
              AND status NOT IN (
                  'Cancelled',
                  'Returned',
                  'Completed'
              )
            """,
            (today,),
        ).fetchone()[0],

        "active_jobs": con.execute(
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE status NOT IN (
                'Cancelled',
                'Returned',
                'Completed'
            )
            """
        ).fetchone()[0],

        "prep": con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE status = 'Reserved / Prep'
            """
        ).fetchone()[0],

        "job_site": con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE status = 'Checked Out'
            """
        ).fetchone()[0],

        "inspection": con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE status = 'Returned / Inspection'
            """
        ).fetchone()[0],

        "repair": con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE status IN (
                'Repair',
                'Waiting for Parts',
                'Out of Commission',
                'Needs Replacement',
                'Dead'
            )
            """
        ).fetchone()[0],
    }

    # =====================================================
    # UPCOMING JOBS
    # =====================================================

    jobs = con.execute(
        """
        SELECT
            j.*,
            COALESCE(c.name, j.customer) AS customer_name
        FROM jobs j
        LEFT JOIN customers c
            ON c.id = j.customer_id
        WHERE j.status NOT IN (
            'Cancelled',
            'Returned',
            'Completed'
        )
        ORDER BY
            j.out_date,
            j.out_time,
            j.job_number
        LIMIT 8
        """
    ).fetchall()

    # =====================================================
    # TRACKING PRIORITIES
    # =====================================================

    priorities = con.execute(
        """
        SELECT
            tracking_priority,
            COUNT(*) AS c,
            COALESCE(SUM(qty_total), 0) AS q
        FROM item_master
        GROUP BY tracking_priority
        ORDER BY tracking_priority
        """
    ).fetchall()

    # =====================================================
    # AWAITING INSPECTION
    # =====================================================

    inspection_assets = con.execute(
        """
        SELECT
            a.id,
            a.asset_id,
            a.description,
            a.status,
            a.assigned_job_id,
            j.job_number
        FROM assets a
        LEFT JOIN jobs j
            ON j.id = a.assigned_job_id
        WHERE a.status = 'Returned / Inspection'
        ORDER BY a.description, a.asset_id
        LIMIT 10
        """
    ).fetchall()

    # =====================================================
    # REPAIR / DOWN EQUIPMENT
    # =====================================================

    repair_assets = con.execute(
        """
        SELECT
            a.id,
            a.asset_id,
            a.description,
            a.status
        FROM assets a
        WHERE a.status IN (
            'Repair',
            'Waiting for Parts',
            'Out of Commission',
            'Needs Replacement',
            'Dead'
        )
        ORDER BY
            a.status,
            a.description,
            a.asset_id
        LIMIT 10
        """
    ).fetchall()

    # =====================================================
    # JOBS LEAVING SOON
    # =====================================================

    jobs_leaving_soon = con.execute(
        """
        SELECT
            j.id,
            j.job_number,
            j.event_name,
            j.out_date,
            j.out_time,
            j.status,
            COALESCE(c.name, j.customer) AS customer_name
        FROM jobs j
        LEFT JOIN customers c
            ON c.id = j.customer_id
        WHERE j.out_date >= ?
          AND j.out_date <= ?
          AND j.status NOT IN (
              'Cancelled',
              'Returned',
              'Completed'
          )
        ORDER BY
            j.out_date,
            j.out_time,
            j.job_number
        LIMIT 10
        """,
        (
            today,
            soon_date,
        ),
    ).fetchall()

    # =====================================================
    # INVENTORY CONFLICTS
    # =====================================================

    conflict_jobs = []

    active_jobs = con.execute(
        """
        SELECT
            id,
            job_number,
            out_date,
            return_date
        FROM jobs
        WHERE status NOT IN (
            'Cancelled',
            'Returned',
            'Completed'
        )
        ORDER BY out_date, job_number
        """
    ).fetchall()

    for job in active_jobs:

        job_lines = con.execute(
            """
            SELECT
                jl.item_master_id,
                jl.qty_needed,
                im.description
            FROM job_lines jl
            JOIN item_master im
                ON im.id = jl.item_master_id
            WHERE jl.job_id = ?
            ORDER BY im.description
            """,
            (job["id"],),
        ).fetchall()

        conflict_count = 0

        for line in job_lines:

            available_info = availability(
                line["item_master_id"],
                job["out_date"],
                job["return_date"],
                exclude_job_id=job["id"],
            )

            if (
                line["qty_needed"]
                > available_info["available"]
            ):
                conflict_count += 1

        if conflict_count > 0:
            conflict_jobs.append(
                {
                    "id": job["id"],
                    "job_number": job["job_number"],
                    "conflict_count": conflict_count,
                }
            )

    attention = {
        "conflicts": len(conflict_jobs),
        "inspection": len(inspection_assets),
        "repair": len(repair_assets),
        "leaving_soon": len(jobs_leaving_soon),
    }

    con.close()

    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "jobs": jobs,
            "priorities": priorities,
            "today": today,
            "message": message,

            "attention": attention,
            "conflict_jobs": conflict_jobs,
            "inspection_assets": inspection_assets,
            "repair_assets": repair_assets,
            "jobs_leaving_soon": jobs_leaving_soon,
        },
    )