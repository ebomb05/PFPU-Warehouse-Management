from ..database import connect
from .asset_service import move_asset
from .job_status_service import refresh_job_status


def dispatch_asset_to_job_site(
    job_id: int,
    vehicle_id: int,
    barcode_value: str,
    *,
    user_id=None,
    notes: str = "",
):
    """
    Dispatch one loaded tracked asset from an assigned vehicle
    to the JOB-SITE location for the specified job.

    Rules:
    - Job must exist and be active.
    - Vehicle must be assigned to the job.
    - Vehicle must have a valid warehouse vehicle location.
    - Asset must exist.
    - Asset must belong to this job.
    - Asset must currently be on the selected vehicle.
    - Asset must be in Loaded status.
    - Successful dispatch moves the asset to JOB-SITE and
      changes status to Checked Out.
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

    vehicle = con.execute(
        """
        SELECT
            v.*,
            wl.code AS location_code,
            wl.name AS location_name,
            wl.location_type,
            wl.active AS location_active
        FROM vehicles v
        JOIN job_vehicles jv
            ON jv.vehicle_id = v.id
        LEFT JOIN warehouse_locations wl
            ON wl.id = v.warehouse_location_id
        WHERE v.id = ?
          AND jv.job_id = ?
        """,
        (
            vehicle_id,
            job_id,
        ),
    ).fetchone()

    if not vehicle:
        con.close()

        return {
            "success": False,
            "message": "Vehicle is not assigned to this job",
        }

    if not vehicle["active"]:
        con.close()

        return {
            "success": False,
            "message": "Vehicle is retired",
        }

    if vehicle["warehouse_location_id"] is None:
        con.close()

        return {
            "success": False,
            "message": "Vehicle has no warehouse location assigned",
        }

    if (
        not vehicle["location_active"]
        or vehicle["location_type"] != "Vehicle"
    ):
        con.close()

        return {
            "success": False,
            "message": "Vehicle warehouse location is invalid",
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

    if asset["location_id"] != vehicle["warehouse_location_id"]:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not currently on "
                f"{vehicle['name']}"
            ),
        }

    if asset["status"] != "Loaded":
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not ready for dispatch"
            ),
        }

    job_site = con.execute(
        """
        SELECT *
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

    con.close()

    result = move_asset(
        asset_id=asset["id"],
        to_location_id=job_site["id"],
        action="Job Dispatch",
        job_id=job_id,
        user_id=user_id,
        notes=notes,
        new_status="Checked Out",
        set_job_assignment=True,
        assigned_job_id=job_id,
    )

    if result["success"]:
        status_result = refresh_job_status(job_id)
        result["job_status"] = status_result["status"]

    return result