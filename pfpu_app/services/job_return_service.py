from ..database import connect
from .asset_service import move_asset
from .job_status_service import refresh_job_status


def return_asset_to_prep(
    job_id: int,
    barcode_value: str,
    *,
    user_id=None,
    notes: str = "",
):
    """
    Return one tracked asset from JOB-SITE back to PREP.

    Rules:
    - Job must exist and not be cancelled.
    - Asset must exist.
    - Asset must belong to this job.
    - Asset must currently be at JOB-SITE.
    - Asset must currently be Checked Out.
    - Successful return moves the asset to PREP.
    - Job assignment remains in place until the return is fully processed.
    """

    barcode_value = barcode_value.strip()

    con = connect()

    job = con.execute(
        """
        SELECT *
        FROM jobs
        WHERE id = ?
          AND status != 'Cancelled'
        """,
        (job_id,),
    ).fetchone()

    if not job:
        con.close()

        return {
            "success": False,
            "message": "Job not found or cancelled",
        }

    asset = con.execute(
        """
        SELECT
            id,
            asset_id,
            item_master_id,
            status,
            assigned_job_id,
            location_id
        FROM assets
        WHERE barcode_value = ?
           OR asset_id = ?
        """,
        (
            barcode_value,
            barcode_value,
        ),
    ).fetchone()

    if not asset:
        con.close()

        return {
            "success": False,
            "message": "Asset not found",
        }

    if asset["assigned_job_id"] != job_id:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not assigned to this job"
            ),
        }

    job_site = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("JOB-SITE",),
    ).fetchone()

    if not job_site:
        con.close()

        return {
            "success": False,
            "message": "JOB-SITE location is missing or inactive",
        }

    if asset["location_id"] != job_site["id"]:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not currently at JOB-SITE"
            ),
        }

    if asset["status"] != "Checked Out":
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not ready for return"
            ),
        }

    prep = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("PREP",),
    ).fetchone()

    if not prep:
        con.close()

        return {
            "success": False,
            "message": "PREP location is missing or inactive",
        }

    con.close()

    result = move_asset(
        asset_id=asset["id"],
        to_location_id=prep["id"],
        action="Job Return",
        job_id=job_id,
        user_id=user_id,
        notes=notes,
        new_status="Returned / Inspection",
        set_job_assignment=True,
        assigned_job_id=job_id,
    )

    if result["success"]:
        status_result = refresh_job_status(job_id)
        result["job_status"] = status_result["status"]

    return result