from ..database import connect
from .asset_service import move_asset


def load_asset_to_vehicle(
    job_id: int,
    vehicle_id: int,
    barcode_value: str,
    *,
    user_id=None,
    notes: str = "",
):
    """
    Load one tracked asset from PREP onto a vehicle assigned
    to the specified job.
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

    prep = con.execute(
        """
        SELECT id
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

    if asset["location_id"] != prep["id"]:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not currently in PREP"
            ),
        }

    if asset["status"] != "Reserved / Prep":
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not ready for vehicle loading"
            ),
        }

    vehicle_location_id = vehicle["warehouse_location_id"]

    con.close()

    result = move_asset(
        asset_id=asset["id"],
        to_location_id=vehicle_location_id,
        action="Job Load",
        job_id=job_id,
        user_id=user_id,
        notes=notes,
        new_status="Loaded",
        set_job_assignment=True,
        assigned_job_id=job_id,
    )

    if result["success"]:
        result["vehicle_id"] = vehicle_id
        result["vehicle_name"] = vehicle["name"]
        result["vehicle_location"] = vehicle["location_code"]

    return result