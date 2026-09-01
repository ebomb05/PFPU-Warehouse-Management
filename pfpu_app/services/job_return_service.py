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

def return_job_to_inspection(
    job_id: int,
    *,
    user_id=None,
    notes: str = "",
):
    """
    Return all checked-out tracked assets for a job from
    JOB-SITE to the INSPECTION location.

    This represents the truck/job physically returning to the
    warehouse. Individual assets are inspected afterward.

    Assets remain assigned to the current job until inspection
    routes them to storage, PREP for another job, or repair.
    """

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
            "returned_count": 0,
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
            "returned_count": 0,
        }

    inspection = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("INSPECTION",),
    ).fetchone()

    if not inspection:
        con.close()

        return {
            "success": False,
            "message": "INSPECTION location is missing or inactive",
            "returned_count": 0,
        }

    assets = con.execute(
        """
        SELECT
            id,
            asset_id,
            barcode_value
        FROM assets
        WHERE assigned_job_id = ?
          AND location_id = ?
          AND status = 'Checked Out'
        ORDER BY asset_id
        """,
        (
            job_id,
            job_site["id"],
        ),
    ).fetchall()

    con.close()

    if not assets:
        return {
            "success": False,
            "message": (
                "No checked-out equipment is currently at "
                "JOB-SITE for this job."
            ),
            "returned_count": 0,
        }

    returned_count = 0
    errors = []

    for asset in assets:

        result = move_asset(
            asset_id=asset["id"],
            to_location_id=inspection["id"],
            action="Job Return",
            job_id=job_id,
            user_id=user_id,
            notes=notes,
            new_status="Returned / Inspection",
            set_job_assignment=True,
            assigned_job_id=job_id,
        )

        if result["success"]:
            returned_count += 1
        else:
            errors.append(
                f"{asset['asset_id']}: {result['message']}"
            )

    status_result = refresh_job_status(job_id)

    if errors:
        return {
            "success": False,
            "message": (
                f"Returned {returned_count} asset(s) to INSPECTION, "
                f"but {len(errors)} asset(s) could not be returned. "
                + " | ".join(errors)
            ),
            "returned_count": returned_count,
            "job_status": status_result["status"],
        }

    return {
        "success": True,
        "message": (
            f"Job returned to warehouse. "
            f"{returned_count} tracked asset(s) moved to INSPECTION."
        ),
        "returned_count": returned_count,
        "job_status": status_result["status"],
    }