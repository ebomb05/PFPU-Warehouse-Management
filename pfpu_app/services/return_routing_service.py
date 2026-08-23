from datetime import datetime

from ..database import connect


DEFAULT_PREP_WINDOW_DAYS = 3


def find_next_job_for_item(
    current_job_id: int,
    item_master_id: int,
    *,
    prep_window_days: int = DEFAULT_PREP_WINDOW_DAYS,
):
    """
    Find the next active job requiring the same item after the
    current job returns.

    Returns a recommendation only when the next job's out date
    falls within prep_window_days after the current job return date.
    """

    con = connect()

    current_job = con.execute(
        """
        SELECT
            id,
            job_number,
            return_date
        FROM jobs
        WHERE id = ?
        """,
        (current_job_id,),
    ).fetchone()

    if not current_job:
        con.close()

        return {
            "recommended": False,
            "message": "Current job not found",
            "next_job": None,
        }

    next_job = con.execute(
        """
        SELECT
            j.id,
            j.job_number,
            j.customer,
            j.event_name,
            j.out_date,
            j.return_date,
            jl.qty_needed
        FROM job_lines jl
        JOIN jobs j
            ON j.id = jl.job_id
        WHERE jl.item_master_id = ?
          AND j.id != ?
          AND j.status NOT IN ('Cancelled', 'Returned')
          AND j.out_date >= ?
        ORDER BY j.out_date
        LIMIT 1
        """,
        (
            item_master_id,
            current_job_id,
            current_job["return_date"],
        ),
    ).fetchone()

    if not next_job:
        con.close()

        return {
            "recommended": False,
            "message": "No upcoming job requires this item",
            "next_job": None,
        }

    current_return = datetime.strptime(
        current_job["return_date"],
        "%Y-%m-%d",
    ).date()

    next_out = datetime.strptime(
        next_job["out_date"],
        "%Y-%m-%d",
    ).date()

    gap_days = (next_out - current_return).days

    result = {
        "recommended": gap_days <= prep_window_days,
        "gap_days": gap_days,
        "prep_window_days": prep_window_days,
        "next_job": dict(next_job),
    }

    if result["recommended"]:
        result["message"] = (
            f"Keep in PREP for {next_job['job_number']} "
            f"in {gap_days} day(s)"
        )
    else:
        result["message"] = (
            f"Next job is {next_job['job_number']} "
            f"in {gap_days} day(s)"
        )

    con.close()

    return result