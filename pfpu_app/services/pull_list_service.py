from ..database import connect


def build_pull_list(job_id: int):
    """
    Build a location-based pull plan for a job.

    Job requirements remain quantity-based.
    Storage locations determine where warehouse staff should pull from.

    The same item may be split across multiple locations.
    Lower storage priority numbers are pulled first.
    """

    con = connect()

    job_lines = con.execute(
        """
        SELECT
            jl.item_master_id,
            jl.qty_needed,
            jl.notes,
            im.description,
            im.category,
            im.qty_total
        FROM job_lines jl
        JOIN item_master im
            ON im.id = jl.item_master_id
        WHERE jl.job_id = ?
        ORDER BY im.category, im.description
        """,
        (job_id,),
    ).fetchall()

    groups = {}
    unassigned = []

    total_required = 0
    total_located = 0

    for line in job_lines:
        required = max(0, line["qty_needed"] or 0)
        remaining = required

        total_required += required

        storage_rows = con.execute(
            """
            SELECT
                isl.location_id,
                isl.qty_assigned,
                isl.priority,
                isl.notes AS storage_notes,
                wl.code AS location_code,
                wl.name AS location_name,
                wl.location_type
            FROM item_storage_locations isl
            JOIN warehouse_locations wl
                ON wl.id = isl.location_id
            WHERE isl.item_master_id = ?
              AND isl.active = 1
              AND wl.active = 1
              AND isl.qty_assigned > 0
            ORDER BY isl.priority, wl.code
            """,
            (line["item_master_id"],),
        ).fetchall()

        for storage in storage_rows:

            if remaining <= 0:
                break

            quantity_here = max(
                0,
                storage["qty_assigned"] or 0,
            )

            if quantity_here <= 0:
                continue

            pull_quantity = min(
                remaining,
                quantity_here,
            )

            location_id = storage["location_id"]

            if location_id not in groups:
                groups[location_id] = {
                    "location_id": location_id,
                    "location_code": storage["location_code"],
                    "location_name": storage["location_name"],
                    "location_type": storage["location_type"],
                    "priority": storage["priority"],
                    "items": [],
                }

            # If several items use the same location,
            # keep the best (lowest) pull priority.
            groups[location_id]["priority"] = min(
                groups[location_id]["priority"],
                storage["priority"],
            )

            groups[location_id]["items"].append(
                {
                    "item_master_id": line["item_master_id"],
                    "description": line["description"],
                    "category": line["category"],
                    "qty_to_pull": pull_quantity,
                    "storage_notes": storage["storage_notes"],
                }
            )

            remaining -= pull_quantity
            total_located += pull_quantity

        if remaining > 0:
            unassigned.append(
                {
                    "item_master_id": line["item_master_id"],
                    "description": line["description"],
                    "category": line["category"],
                    "qty_missing_location": remaining,
                }
            )

    pull_groups = sorted(
        groups.values(),
        key=lambda group: (
            group["priority"],
            group["location_code"],
        ),
    )

    con.close()

    return {
        "groups": pull_groups,
        "unassigned": unassigned,
        "total_required": total_required,
        "total_located": total_located,
        "total_unassigned": total_required - total_located,
    }