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
):
    """
    Move one asset to a new warehouse location and record the move.

    This will become the shared movement engine used by:
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

    if from_location_id == to_location_id:
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} is already at "
                f"{destination['code']}"
            ),
        }

    # Keep old text location populated for compatibility
    # while location_id remains the permanent source of truth.
    location_text = destination["code"]

    con.execute(
        """
        UPDATE assets
        SET location_id = ?,
            current_location = ?
        WHERE id = ?
        """,
        (
            to_location_id,
            location_text,
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
        "destination_code": destination["code"],
    }