from ..database import connect
from .barcode_service import make_barcode_svg
from .inventory_service import next_asset_id


def generate_assets_for_item(
    item_master_id: int,
    qty: int,
    location_id: int,
):
    """
    Generate individually tracked assets for an inventory item.

    This is the shared asset-generation engine used by routes
    and, later, inventory onboarding/import workflows.
    """

    con = connect()

    try:
        item = con.execute(
            """
            SELECT *
            FROM item_master
            WHERE id = ?
            """,
            (item_master_id,),
        ).fetchone()

        if not item:
            return {
                "success": False,
                "message": "Inventory item was not found.",
                "created_count": 0,
            }

        location = con.execute(
            """
            SELECT *
            FROM warehouse_locations
            WHERE id = ?
              AND active = 1
            """,
            (location_id,),
        ).fetchone()

        if not location:
            return {
                "success": False,
                "message": "Please choose an active location.",
                "created_count": 0,
            }

        requested_qty = max(0, min(qty, 500))

        if requested_qty < 1:
            return {
                "success": False,
                "message": "Quantity must be at least 1.",
                "created_count": 0,
            }

        total_quantity = item["qty_total"] or 0

        tracked_count = con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE item_master_id = ?
            """,
            (item_master_id,),
        ).fetchone()[0]

        available_to_generate = max(
            0,
            total_quantity - tracked_count,
        )

        if available_to_generate < 1:
            return {
                "success": False,
                "message": (
                    "All available inventory has already been "
                    "converted to tracked assets."
                ),
                "created_count": 0,
            }

        if requested_qty > available_to_generate:
            return {
                "success": False,
                "message": (
                    f"Cannot generate {requested_qty} assets. "
                    f"This item has {total_quantity} unit(s) in inventory, "
                    f"{tracked_count} tracked asset(s), and only "
                    f"{available_to_generate} available to generate."
                ),
                "created_count": 0,
            }

        create_qty = requested_qty

        prefix = (item["prefix"] or "").strip()

        if not prefix:
            return {
                "success": False,
                "message": (
                    "This inventory item does not have an "
                    "Asset ID prefix."
                ),
                "created_count": 0,
            }

        location_text = location["code"]
        created_count = 0

        for _ in range(create_qty):

            candidate = next_asset_id(prefix)

            existing = con.execute(
                """
                SELECT id
                FROM assets
                WHERE asset_id = ?
                   OR barcode_value = ?
                LIMIT 1
                """,
                (
                    candidate,
                    candidate,
                ),
            ).fetchone()

            if existing:
                parts = candidate.rsplit("-", 1)

                if (
                    len(parts) == 2
                    and parts[1].isdigit()
                ):
                    id_prefix = parts[0]
                    number = int(parts[1])
                    width = len(parts[1])

                    while existing:
                        number += 1

                        candidate = (
                            f"{id_prefix}-"
                            f"{number:0{width}d}"
                        )

                        existing = con.execute(
                            """
                            SELECT id
                            FROM assets
                            WHERE asset_id = ?
                               OR barcode_value = ?
                            LIMIT 1
                            """,
                            (
                                candidate,
                                candidate,
                            ),
                        ).fetchone()

                else:
                    raise ValueError(
                        "Unable to safely generate the next "
                        "Asset ID."
                    )

            asset_id = candidate

            svg_file = make_barcode_svg(asset_id)

            cursor = con.execute(
                """
                INSERT INTO assets(
                    asset_id,
                    barcode_value,
                    item_master_id,
                    description,
                    category,
                    status,
                    current_location,
                    location_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    asset_id,
                    item_master_id,
                    item["description"],
                    item["category"],
                    "Available",
                    location_text,
                    location_id,
                ),
            )

            new_asset_db_id = cursor.lastrowid

            con.execute(
                """
                INSERT INTO barcode_queue(
                    asset_id,
                    barcode_value,
                    description,
                    svg_file
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    asset_id,
                    asset_id,
                    item["description"],
                    svg_file,
                ),
            )

            con.execute(
                """
                INSERT INTO asset_location_history(
                    asset_id,
                    from_location_id,
                    to_location_id,
                    action,
                    notes
                )
                VALUES (?, NULL, ?, ?, ?)
                """,
                (
                    new_asset_db_id,
                    location_id,
                    "Asset Created",
                    "Initial asset location",
                ),
            )

            created_count += 1

        con.commit()

        return {
            "success": True,
            "message": (
                f"Successfully created {created_count} "
                f"asset(s) for {item['description']}."
            ),
            "created_count": created_count,
        }

    except Exception as exc:
        con.rollback()

        return {
            "success": False,
            "message": (
                "Asset generation failed. "
                f"No assets were created. {exc}"
            ),
            "created_count": 0,
        }

    finally:
        con.close()