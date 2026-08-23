from ..database import connect
from .asset_service import move_asset


def locate_asset(barcode_value: str):
    """
    Look up a tracked asset and determine where it normally belongs.

    Returns:
    - asset identity
    - current system location
    - current status
    - assigned job, if any
    - primary expected storage location
    - all configured storage locations
    """

    barcode_value = barcode_value.strip()

    if not barcode_value:
        return {
            "success": False,
            "message": "Asset ID / QR value is required",
        }

    con = connect()

    asset = con.execute(
        """
        SELECT
            a.id,
            a.asset_id,
            a.barcode_value,
            a.item_master_id,
            a.description,
            a.category,
            a.serial_number,
            a.status,
            a.assigned_job_id,
            a.location_id,
            a.current_location,
            wl.code AS current_location_code,
            wl.name AS current_location_name,
            wl.location_type AS current_location_type,
            j.job_number AS assigned_job_number
        FROM assets a
        LEFT JOIN warehouse_locations wl
            ON wl.id = a.location_id
        LEFT JOIN jobs j
            ON j.id = a.assigned_job_id
        WHERE a.barcode_value = ?
           OR a.asset_id = ?
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

    storage_locations = con.execute(
        """
        SELECT
            isl.location_id,
            isl.qty_assigned,
            isl.priority,
            isl.notes,
            wl.code,
            wl.name,
            wl.location_type
        FROM item_storage_locations isl
        JOIN warehouse_locations wl
            ON wl.id = isl.location_id
        WHERE isl.item_master_id = ?
          AND isl.active = 1
          AND wl.active = 1
          AND isl.qty_assigned > 0
        ORDER BY
            isl.priority,
            wl.code
        """,
        (asset["item_master_id"],),
    ).fetchall()

    history = con.execute(
        """
        SELECT
            h.action,
            h.from_location_id,
            h.to_location_id,
            h.job_id,
            h.notes,
            h.moved_at,
            from_loc.code AS from_code,
            to_loc.code AS to_code
        FROM asset_location_history h
        LEFT JOIN warehouse_locations from_loc
            ON from_loc.id = h.from_location_id
        LEFT JOIN warehouse_locations to_loc
            ON to_loc.id = h.to_location_id
        WHERE h.asset_id = ?
        ORDER BY h.id DESC
        LIMIT 5
        """,
        (asset["id"],),
    ).fetchall()

    con.close()

    primary_storage = (
        dict(storage_locations[0])
        if storage_locations
        else None
    )

    current_code = (
        asset["current_location_code"]
        or asset["current_location"]
        or "Unknown"
    )

    if primary_storage:
        expected_code = primary_storage["code"]

        if asset["assigned_job_id"] is not None:
            location_message = (
                f"{asset['asset_id']} is assigned to "
                f"{asset['assigned_job_number'] or 'a job'} "
                f"and is currently recorded at {current_code}"
            )

        elif current_code == expected_code:
            location_message = (
                f"{asset['asset_id']} is already at its "
                f"expected storage location {expected_code}"
            )

        else:
            location_message = (
                f"{asset['asset_id']} normally belongs at "
                f"{expected_code}"
            )

    else:
        location_message = (
            f"{asset['asset_id']} does not have a storage "
            f"location assigned"
        )

    return {
        "success": True,
        "message": location_message,
        "asset": dict(asset),
        "primary_storage": primary_storage,
        "storage_locations": [
            dict(row)
            for row in storage_locations
        ],
        "history": [
            dict(row)
            for row in history
        ],
    }

def mark_asset_missing(
    barcode_value: str,
    *,
    notes: str = "",
    user_id=None,
):
    """
    Mark a tracked asset as Lost / Missing.

    Important:
    - The asset's location is NOT changed.
    - Its current location remains the last-known location.
    - Existing job assignment is preserved.
    - An exception record is opened.
    - Duplicate open Missing Asset exceptions are prevented.
    """

    barcode_value = barcode_value.strip()

    if not barcode_value:
        return {
            "success": False,
            "message": "Asset ID / QR value is required",
        }

    con = connect()

    asset = con.execute(
        """
        SELECT
            id,
            asset_id,
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

    existing_exception = con.execute(
        """
        SELECT id
        FROM exceptions
        WHERE asset_id = ?
          AND exception_type = ?
          AND status = 'Open'
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            asset["id"],
            "Missing Asset",
        ),
    ).fetchone()

    if existing_exception:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is already marked Lost / Missing"
            ),
            "exception_id": existing_exception["id"],
        }

    last_known_location = (
        asset["current_location"]
        or "Unknown"
    )

    exception_message = (
        f"{asset['asset_id']} reported missing. "
        f"Last known location: {last_known_location}"
    )

    if notes.strip():
        exception_message += f". Notes: {notes.strip()}"

    cursor = con.execute(
        """
        INSERT INTO exceptions(
            job_id,
            asset_id,
            exception_type,
            severity,
            message,
            created_by,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'Open')
        """,
        (
            asset["assigned_job_id"],
            asset["id"],
            "Missing Asset",
            "Warning",
            exception_message,
            user_id,
        ),
    )

    exception_id = cursor.lastrowid

    con.execute(
        """
        UPDATE assets
        SET status = ?
        WHERE id = ?
        """,
        (
            "Lost / Missing",
            asset["id"],
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"{asset['asset_id']} marked Lost / Missing. "
            f"Last known location: {last_known_location}"
        ),
        "asset_code": asset["asset_id"],
        "exception_id": exception_id,
        "status": "Lost / Missing",
        "last_known_location": last_known_location,
        "assigned_job_id": asset["assigned_job_id"],
    }

from .asset_service import move_asset


def resolve_found_asset(
    barcode_value: str,
    *,
    notes: str = "",
    user_id=None,
):
    """
    Resolve a Lost / Missing asset and return it to its
    primary assigned storage location.

    Rules:
    - Asset must exist.
    - Asset must currently be Lost / Missing.
    - An open Missing Asset exception must exist.
    - A primary storage location must be assigned.
    - Missing exception is resolved.
    - Asset is returned to storage and marked Available.
    """

    barcode_value = barcode_value.strip()

    if not barcode_value:
        return {
            "success": False,
            "message": "Asset ID / QR value is required",
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

    if asset["status"] != "Lost / Missing":
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is not currently marked Lost / Missing"
            ),
        }

    missing_exception = con.execute(
        """
        SELECT *
        FROM exceptions
        WHERE asset_id = ?
          AND exception_type = ?
          AND status = 'Open'
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            asset["id"],
            "Missing Asset",
        ),
    ).fetchone()

    if not missing_exception:
        con.close()

        return {
            "success": False,
            "message": "No open Missing Asset exception was found",
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

    asset_db_id = asset["id"]
    exception_id = missing_exception["id"]
    destination_id = storage["location_id"]

    con.close()

    move_result = move_asset(
        asset_id=asset_db_id,
        to_location_id=destination_id,
        action="Lost Asset Found",
        user_id=user_id,
        notes=notes,
        new_status="Available",
        set_job_assignment=True,
        assigned_job_id=None,
    )

    if not move_result["success"]:
        return move_result

    con = connect()

    con.execute(
        """
        UPDATE exceptions
        SET status = 'Resolved',
            resolved_by = ?,
            resolved_at = CURRENT_TIMESTAMP,
            resolution_notes = ?
        WHERE id = ?
        """,
        (
            user_id,
            notes.strip() or "Asset found and returned to storage",
            exception_id,
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"{asset['asset_id']} found and returned to "
            f"{storage['location_code']}"
        ),
        "asset_code": asset["asset_id"],
        "exception_id": exception_id,
        "status": "Available",
        "storage_location": storage["location_code"],
    }