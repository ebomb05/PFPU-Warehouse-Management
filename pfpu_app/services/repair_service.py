from ..database import connect
from .asset_service import move_asset


OPEN_REPAIR_STATUSES = (
    "Repair",
    "Waiting for Parts",
    "Dead",
    "Needs Replacement",
    "Out of Commission",
)


def open_repair_record(
    barcode_value: str,
    issue: str,
    *,
    notes: str = "",
    parts_needed: str = "",
    user_id=None,
    job_id=None,
):
    """
    Open a repair record for one tracked asset.

    The asset is:
    - moved to REPAIR if it is not already there
    - removed from any job assignment
    - placed in Repair status
    - given an open repair record

    Prevents duplicate open repair records.
    """

    barcode_value = barcode_value.strip()
    issue = issue.strip()

    if not issue:
        return {
            "success": False,
            "message": "Repair issue is required",
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
            location_id,
            current_location
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

    existing = con.execute(
        """
        SELECT *
        FROM repair_records
        WHERE asset_id = ?
          AND closed_at IS NULL
        ORDER BY id DESC
        LIMIT 1
        """,
        (asset["id"],),
    ).fetchone()

    if existing:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} already has an open repair record"
            ),
            "repair_record_id": existing["id"],
        }

    repair_location = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE code = ?
          AND active = 1
        """,
        ("REPAIR",),
    ).fetchone()

    if not repair_location:
        con.close()

        return {
            "success": False,
            "message": "REPAIR location is missing or inactive",
        }

    asset_db_id = asset["id"]
    asset_code = asset["asset_id"]
    already_in_repair = (
        asset["location_id"] == repair_location["id"]
    )

    con.close()

    if already_in_repair:
        con = connect()

        con.execute(
            """
            UPDATE assets
            SET status = ?,
                assigned_job_id = NULL,
                location_id = ?,
                current_location = ?
            WHERE id = ?
            """,
            (
                "Repair",
                repair_location["id"],
                repair_location["code"],
                asset_db_id,
            ),
        )

        con.commit()
        con.close()

    else:
        move_result = move_asset(
            asset_id=asset_db_id,
            to_location_id=repair_location["id"],
            action="Repair Opened",
            job_id=job_id,
            user_id=user_id,
            notes=issue,
            new_status="Repair",
            set_job_assignment=True,
            assigned_job_id=None,
        )

        if not move_result["success"]:
            return move_result

    con = connect()

    cursor = con.execute(
        """
        INSERT INTO repair_records(
            asset_id,
            status,
            issue,
            notes,
            parts_needed,
            opened_by,
            opened_at,
            updated_by,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
        """,
        (
            asset_db_id,
            "Repair",
            issue,
            notes.strip(),
            parts_needed.strip(),
            user_id,
            user_id,
        ),
    )

    repair_record_id = cursor.lastrowid

    con.commit()
    con.close()

    return {
        "success": True,
        "message": f"Repair record opened for {asset_code}",
        "repair_record_id": repair_record_id,
        "asset_code": asset_code,
        "status": "Repair",
        "location": "REPAIR",
    }

def update_repair_status(
    repair_record_id: int,
    new_status: str,
    *,
    notes: str = "",
    parts_needed: str = "",
    user_id=None,
):
    """
    Update an open repair record and keep the asset status synchronized.
    """

    allowed_statuses = (
        "Repair",
        "Waiting for Parts",
        "Dead",
        "Needs Replacement",
        "Out of Commission",
    )

    new_status = new_status.strip()

    if new_status not in allowed_statuses:
        return {
            "success": False,
            "message": "Invalid repair status",
        }

    con = connect()

    repair = con.execute(
        """
        SELECT
            rr.*,
            a.asset_id AS asset_code
        FROM repair_records rr
        JOIN assets a
            ON a.id = rr.asset_id
        WHERE rr.id = ?
        """,
        (repair_record_id,),
    ).fetchone()

    if not repair:
        con.close()

        return {
            "success": False,
            "message": "Repair record not found",
        }

    if repair["closed_at"] is not None:
        con.close()

        return {
            "success": False,
            "message": "Repair record is already closed",
        }

    con.execute(
        """
        UPDATE repair_records
        SET status = ?,
            notes = CASE
                WHEN ? = ''
                THEN notes
                ELSE ?
            END,
            parts_needed = CASE
                WHEN ? = ''
                THEN parts_needed
                ELSE ?
            END,
            updated_by = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            new_status,
            notes.strip(),
            notes.strip(),
            parts_needed.strip(),
            parts_needed.strip(),
            user_id,
            repair_record_id,
        ),
    )

    con.execute(
        """
        UPDATE assets
        SET status = ?,
            assigned_job_id = NULL
        WHERE id = ?
        """,
        (
            new_status,
            repair["asset_id"],
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"{repair['asset_code']} repair status updated to "
            f"{new_status}"
        ),
        "repair_record_id": repair_record_id,
        "asset_code": repair["asset_code"],
        "status": new_status,
    }

def close_repair_record(
    repair_record_id: int,
    *,
    resolution_notes: str = "",
    user_id=None,
):
    """
    Close an open repair record and return the asset to service.

    The asset is:
    - moved back to its primary assigned storage location
    - marked Available
    - left unassigned from jobs
    - repair record is closed
    """

    con = connect()

    repair = con.execute(
        """
        SELECT
            rr.*,
            a.asset_id AS asset_code,
            a.item_master_id
        FROM repair_records rr
        JOIN assets a
            ON a.id = rr.asset_id
        WHERE rr.id = ?
        """,
        (repair_record_id,),
    ).fetchone()

    if not repair:
        con.close()

        return {
            "success": False,
            "message": "Repair record not found",
        }

    if repair["closed_at"] is not None:
        con.close()

        return {
            "success": False,
            "message": "Repair record is already closed",
        }

    storage = con.execute(
        """
        SELECT
            isl.location_id,
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
        (repair["item_master_id"],),
    ).fetchone()

    if not storage:
        con.close()

        return {
            "success": False,
            "message": (
                f"No storage location is assigned for "
                f"{repair['asset_code']}"
            ),
        }

    asset_db_id = repair["asset_id"]
    destination_id = storage["location_id"]

    con.close()

    move_result = move_asset(
        asset_id=asset_db_id,
        to_location_id=destination_id,
        action="Repair Completed",
        user_id=user_id,
        notes=resolution_notes,
        new_status="Available",
        set_job_assignment=True,
        assigned_job_id=None,
    )

    if not move_result["success"]:
        return move_result

    con = connect()

    con.execute(
        """
        UPDATE repair_records
        SET status = ?,
            notes = CASE
                WHEN ? = ''
                THEN notes
                ELSE ?
            END,
            updated_by = ?,
            updated_at = CURRENT_TIMESTAMP,
            closed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            "Returned to Service",
            resolution_notes.strip(),
            resolution_notes.strip(),
            user_id,
            repair_record_id,
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"{repair['asset_code']} returned to service at "
            f"{storage['location_code']}"
        ),
        "repair_record_id": repair_record_id,
        "asset_code": repair["asset_code"],
        "status": "Returned to Service",
        "asset_status": "Available",
        "storage_location": storage["location_code"],
    }