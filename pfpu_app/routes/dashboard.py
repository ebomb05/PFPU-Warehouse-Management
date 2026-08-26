from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from ..database import connect
from ..services.auth_service import request_has_permission


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

    today = date.today().isoformat()

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
        },
    )