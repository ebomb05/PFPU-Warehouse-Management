from ..database import connect
from .asset_service import move_asset


def pull_asset_to_prep(
    job_id: int,
    barcode_value: str,
    *,
    user_id=None,
    notes: str = "",
):
    """
    Validate and pull one tracked asset into PREP for a job.

    Rules:
    - Job must exist and be active.
    - Asset must exist.
    - Asset's item must be required by the job.
    - Required quantity must not already be fully pulled.
    - Asset cannot belong to a different active job.
    - PREP location must exist and be active.
    - Successful pull assigns the asset to the job and moves it to PREP.
    """

    barcode_value = barcode_value.strip()

    con = connect()

    job = con.execute(
        """
        SELECT *
        FROM jobs
        WHERE id = ?
          AND status NOT IN ('Cancelled', 'Returned')
        """,
        (job_id,),
    ).fetchone()

    if not job:
        con.close()
        return {
            "success": False,
            "message": "Job not found or inactive",
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

    requirement = con.execute(
        """
        SELECT *
        FROM job_lines
        WHERE job_id = ?
          AND item_master_id = ?
        """,
        (
            job_id,
            asset["item_master_id"],
        ),
    ).fetchone()

    if not requirement:
        con.close()
        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not required for this job"
            ),
        }

    if (
        asset["assigned_job_id"] is not None
        and asset["assigned_job_id"] != job_id
    ):
        con.close()
        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is assigned to another job"
            ),
        }

    pulled_count = con.execute(
        """
        SELECT COUNT(*)
        FROM assets
        WHERE assigned_job_id = ?
          AND item_master_id = ?
          AND status = 'Reserved / Prep'
        """,
        (
            job_id,
            asset["item_master_id"],
        ),
    ).fetchone()[0]

    if pulled_count >= requirement["qty_needed"]:
        con.close()
        return {
            "success": False,
            "message": (
                f"Required quantity already pulled for "
                f"{asset['asset_id']}"
            ),
        }

    prep = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE code = 'PREP'
          AND active = 1
        """
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
        action="Job Pull",
        job_id=job_id,
        user_id=user_id,
        notes=notes,
        new_status="Reserved / Prep",
        set_job_assignment=True,
        assigned_job_id=job_id,
    )

    return result