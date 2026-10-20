
from ..database import connect


def complete_job(job_id: int, user_id: int):
    """
    Explicitly complete a job after all tracked equipment
    has been resolved through the warehouse workflow.
    """

    con = connect()

    try:
        con.execute("BEGIN IMMEDIATE")

        job = con.execute(
            """
            SELECT id, status, completed_at
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        if not job:
            return {
                "success": False,
                "message": "Job not found.",
            }

        if job["status"] == "Completed":
            return {
                "success": False,
                "message": "This job has already been completed.",
            }

        if job["status"] != "Ready to Complete":
            return {
                "success": False,
                "message": (
                    "This job is not ready to complete. "
                    f"Current status: {job['status']}."
                ),
            }

        if job["completed_at"]:
            return {
                "success": False,
                "message": "This job already has completion information.",
            }

        user = con.execute(
            """
            SELECT id
            FROM users
            WHERE id = ?
              AND active = 1
            """,
            (user_id,),
        ).fetchone()

        if not user:
            return {
                "success": False,
                "message": "A valid active employee is required.",
            }

        outstanding_count = con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE assigned_job_id = ?
              AND status != 'Returned / Inspection'
            """,
            (job_id,),
        ).fetchone()[0]

        if outstanding_count > 0:
            return {
                "success": False,
                "message": (
                    "Cannot complete this job. "
                    f"{outstanding_count} asset(s) have not "
                    "been returned to inspection or resolved."
                ),
            }

        workflow_count = con.execute(
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

        if workflow_count == 0:
            return {
                "success": False,
                "message": (
                    "Cannot complete a job without recorded "
                    "warehouse workflow activity."
                ),
            }

        result = con.execute(
            """
            UPDATE jobs
            SET status = 'Completed',
                completed_at = CURRENT_TIMESTAMP,
                completed_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'Ready to Complete'
              AND completed_at IS NULL
            """,
            (user_id, job_id),
        )

        if result.rowcount != 1:
            return {
                "success": False,
                "message": "Job completion could not be saved.",
            }

        con.commit()

        return {
            "success": True,
            "message": "Job completed successfully.",
            "status": "Completed",
        }

    finally:
        con.close()
