from ..database import connect


def refresh_job_status(job_id: int):
    """
    Recalculate a job's workflow status from its tracked assets
    and recorded movement history.

    Status priority:
    - Cancelled stays Cancelled
    - Checked Out assets -> Dispatched
    - Returned / Inspection assets -> Returning
    - Loaded assets -> Ready / Loaded
    - Reserved / Prep assets -> Pulling
    - No assets assigned + prior workflow activity -> Ready to Complete
    - Otherwise -> Planning
    """

    con = connect()

    job = con.execute(
        """
        SELECT
            id,
            status
        FROM jobs
        WHERE id = ?
        """,
        (job_id,),
    ).fetchone()

    if not job:
        con.close()

        return {
            "success": False,
            "message": "Job not found",
        }

    if job["status"] in ("Cancelled", "Completed"):
        con.close()

        return {
            "success": True,
            "status": job["status"],
            "previous_status": job["status"],
        }

    counts = con.execute(
        """
        SELECT
            SUM(
                CASE
                    WHEN status = 'Reserved / Prep'
                    THEN 1
                    ELSE 0
                END
            ) AS prep_count,

            SUM(
                CASE
                    WHEN status = 'Loaded'
                    THEN 1
                    ELSE 0
                END
            ) AS loaded_count,

            SUM(
                CASE
                    WHEN status = 'Checked Out'
                    THEN 1
                    ELSE 0
                END
            ) AS checked_out_count,

            SUM(
                CASE
                    WHEN status = 'Returned / Inspection'
                    THEN 1
                    ELSE 0
                END
            ) AS returning_count,

            COUNT(*) AS assigned_count

        FROM assets
        WHERE assigned_job_id = ?
        """,
        (job_id,),
    ).fetchone()

    prep_count = counts["prep_count"] or 0
    loaded_count = counts["loaded_count"] or 0
    checked_out_count = counts["checked_out_count"] or 0
    returning_count = counts["returning_count"] or 0
    assigned_count = counts["assigned_count"] or 0

    workflow_history_count = con.execute(
        """
        SELECT COUNT(*)
        FROM asset_location_history
        WHERE job_id = ?
          AND action IN (
              'Job Pull',
              'Job Load',
              'Job Dispatch',
              'Job Return',
              'Return Put Away',
              'Return Hold for Next Job',
              'Return Repair'
          )
        """,
        (job_id,),
    ).fetchone()[0]

    current_status = job["status"]

    if checked_out_count > 0:
        new_status = "Dispatched"

    elif returning_count > 0:
        new_status = "Returning"

    elif loaded_count > 0:
        new_status = "Ready / Loaded"

    elif prep_count > 0:
        new_status = "Pulling"

    elif assigned_count == 0 and workflow_history_count > 0:
        new_status = "Ready to Complete"

    else:
        new_status = "Planning"

    con.execute(
        """
        UPDATE jobs
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            new_status,
            job_id,
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "status": new_status,
        "previous_status": current_status,
        "assigned_count": assigned_count,
        "workflow_history_count": workflow_history_count,
    }