from typing import Optional

from ..database import connect


def move_asset(
    asset_id: int,
    to_location_id: int,
    action: str,
    *,
    job_id: Optional[int] = None,
    user_id: Optional[int] = None,
    notes: str = "",
    new_status: Optional[str] = None,
    set_job_assignment: bool = False,
    assigned_job_id: Optional[int] = None,
):
    """
    Move one asset to a new warehouse location and record the move.

    Optional status and job assignment changes occur in the same
    database transaction as the location movement.

    Shared movement engine used by:
    - Manual moves
    - Job pull -> Prep
    - Prep -> Vehicle
    - Vehicle -> Shelf
    - Vehicle -> Prep
    - Repair
    - Lost / Found
    - Audit corrections
    """

    con = connect()

    asset = con.execute(
        """
        SELECT
            id,
            asset_id,
            item_master_id,
            location_id,
            current_location,
            status,
            assigned_job_id
        FROM assets
        WHERE id = ?
        """,
        (asset_id,),
    ).fetchone()

    if not asset:
        con.close()

        return {
            "success": False,
            "message": "Asset not found",
        }

    destination = con.execute(
        """
        SELECT
            id,
            code,
            name,
            location_type,
            active
        FROM warehouse_locations
        WHERE id = ?
        """,
        (to_location_id,),
    ).fetchone()

    if not destination:
        con.close()

        return {
            "success": False,
            "message": "Destination location not found",
        }

    if not destination["active"]:
        con.close()

        return {
            "success": False,
            "message": "Destination location is retired",
        }

    from_location_id = asset["location_id"]

    same_location = from_location_id == to_location_id

    # Same-location moves are normally blocked.
    # They are allowed only when we are also changing the
    # asset status or job assignment.
    changing_status = (
        new_status is not None
        and new_status != asset["status"]
    )

    changing_job = (
        set_job_assignment
        and assigned_job_id != asset["assigned_job_id"]
    )

    if same_location and not changing_status and not changing_job:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is already at "
                f"{destination['code']}"
            ),
        }

    location_text = destination["code"]

    status_to_save = (
        new_status
        if new_status is not None
        else asset["status"]
    )

    job_to_save = asset["assigned_job_id"]

    if set_job_assignment:
        job_to_save = assigned_job_id

    con.execute(
        """
        UPDATE assets
        SET location_id = ?,
            current_location = ?,
            status = ?,
            assigned_job_id = ?
        WHERE id = ?
        """,
        (
            to_location_id,
            location_text,
            status_to_save,
            job_to_save,
            asset_id,
        ),
    )

    con.execute(
        """
        INSERT INTO asset_location_history(
            asset_id,
            from_location_id,
            to_location_id,
            action,
            user_id,
            job_id,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset_id,
            from_location_id,
            to_location_id,
            action,
            user_id,
            job_id,
            notes.strip(),
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"{asset['asset_id']} moved to "
            f"{destination['code']}"
        ),
        "asset_code": asset["asset_id"],
        "item_master_id": asset["item_master_id"],
        "destination_code": destination["code"],
        "status": status_to_save,
        "assigned_job_id": job_to_save,
    }