from ..database import connect
from .asset_service import move_asset
from .return_routing_service import find_next_job_for_item
from .job_status_service import refresh_job_status
from .repair_service import open_repair_record

def route_returned_asset(
    job_id: int,
    barcode_value: str,
    action: str,
    *,
    user_id=None,
    notes: str = "",
    prep_window_days: int = 3,
):
    """
    Route an asset after return inspection.

    Supported actions:
    - shelf
    - prep
    - repair
    """

    barcode_value = barcode_value.strip()
    action = action.strip().lower()

    if action not in ("shelf", "prep", "repair"):
        return {
            "success": False,
            "message": "Invalid return inspection action",
        }

    con = connect()

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
                f"{asset['asset_id']} is not assigned to this return job"
            ),
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
        }

    if asset["location_id"] != inspection["id"]:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not currently in INSPECTION"
            ),
        }

    # ---------------------------------------------------------
    # RETURN TO NORMAL STORAGE
    # ---------------------------------------------------------
    if action == "shelf":

        storage = con.execute(
            """
            SELECT
                isl.location_id,
                isl.priority,
                wl.code AS location_code,
                wl.name AS location_name
            FROM item_storage_locations isl
            JOIN warehouse_locations wl
                ON wl.id = isl.location_id
            WHERE isl.item_master_id = ?
              AND isl.active = 1
              AND isl.qty_assigned > 0
              AND wl.active = 1
            ORDER BY isl.priority, wl.code
            LIMIT 1
            """,
            (asset["item_master_id"],),
        ).fetchone()

        if not storage:
            con.close()

            return {
                "success": False,
                "message": (
                    f"No storage location is assigned for "
                    f"{asset['asset_id']}"
                ),
            }

        destination_id = storage["location_id"]
        destination_code = storage["location_code"]

        con.close()

        result = move_asset(
            asset_id=asset["id"],
            to_location_id=destination_id,
            action="Return Put Away",
            job_id=job_id,
            user_id=user_id,
            notes=notes,
            new_status="Available",
            set_job_assignment=True,
            assigned_job_id=None,
        )

        if result["success"]:
            result["routing_action"] = "shelf"
            result["storage_location"] = destination_code

        status_result = refresh_job_status(job_id)
        result["job_status"] = status_result["status"]

        return result

    # ---------------------------------------------------------
    # SEND TO REPAIR
    # ---------------------------------------------------------
    if action == "repair":

        con.close()

        issue = notes.strip() or "Failed return inspection"

        result = open_repair_record(
            barcode_value=asset["asset_id"],
            issue=issue,
            notes=notes,
            user_id=user_id,
            job_id=job_id,
        )

        if result["success"]:
            result["routing_action"] = "repair"

        status_result = refresh_job_status(job_id)
        result["job_status"] = status_result["status"]

        return result

    prep = con.execute(
        """
        SELECT id
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

    # ---------------------------------------------------------
    # KEEP IN PREP FOR NEXT JOB
    # ---------------------------------------------------------
    recommendation = find_next_job_for_item(
        current_job_id=job_id,
        item_master_id=asset["item_master_id"],
        prep_window_days=prep_window_days,
    )

    if not recommendation["recommended"]:
        con.close()

        return {
            "success": False,
            "message": recommendation["message"],
            "recommendation": recommendation,
        }

    next_job = recommendation["next_job"]

    already_assigned = con.execute(
        """
        SELECT COUNT(*)
        FROM assets
        WHERE assigned_job_id = ?
          AND item_master_id = ?
          AND status IN (
              'Reserved / Prep',
              'Loaded',
              'Checked Out'
          )
        """,
        (
            next_job["id"],
            asset["item_master_id"],
        ),
    ).fetchone()[0]

    if already_assigned >= next_job["qty_needed"]:
        con.close()

        return {
            "success": False,
            "message": (
                f"{next_job['job_number']} already has its required "
                f"quantity assigned"
            ),
        }

    con.close()

    result = move_asset(
        asset_id=asset["id"],
        to_location_id=prep["id"],
        action="Return Hold for Next Job",
        job_id=next_job["id"],
        user_id=user_id,
        notes=notes,
        new_status="Reserved / Prep",
        set_job_assignment=True,
        assigned_job_id=next_job["id"],
    )

    if result["success"]:
        result["routing_action"] = "prep"
        result["next_job_id"] = next_job["id"]
        result["next_job_number"] = next_job["job_number"]
        result["gap_days"] = recommendation["gap_days"]

    old_status_result = refresh_job_status(job_id)
    next_status_result = refresh_job_status(next_job["id"])

    result["old_job_status"] = old_status_result["status"]
    result["next_job_status"] = next_status_result["status"]

    return result