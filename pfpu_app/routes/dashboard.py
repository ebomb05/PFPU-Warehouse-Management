from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from ..services.auth_service import request_has_permission

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

    stats = {
        "items": con.execute(
            "SELECT COUNT(*) FROM item_master"
        ).fetchone()[0],

        "qty": con.execute(
            "SELECT COALESCE(SUM(qty_total),0) FROM item_master"
        ).fetchone()[0],

        "assets": con.execute(
            "SELECT COUNT(*) FROM assets"
        ).fetchone()[0],

        "jobs": con.execute(
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE status NOT IN ('Cancelled','Returned')
            """
        ).fetchone()[0],

        "out": con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE status='Checked Out'
            """
        ).fetchone()[0],

        "prep": con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE current_location='Prep Area'
            """
        ).fetchone()[0],
    }

    jobs = con.execute(
        """
        SELECT *
        FROM jobs
        ORDER BY out_date
        LIMIT 8
        """
    ).fetchall()

    priorities = con.execute(
        """
        SELECT
            tracking_priority,
            COUNT(*) c,
            COALESCE(SUM(qty_total),0) q
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
            "message": message,
        },
    )