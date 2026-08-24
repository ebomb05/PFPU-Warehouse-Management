from ..database import connect


def get_positions():
    """
    Return all positions.
    """

    con = connect()

    positions = con.execute(
        """
        SELECT
            id,
            name,
            description,
            active
        FROM positions
        ORDER BY active DESC, name
        """
    ).fetchall()

    con.close()

    return [
        dict(row)
        for row in positions
    ]


def get_position_permissions(position_id: int):
    """
    Return one position and the complete permission list,
    including whether each permission is enabled.
    """

    con = connect()

    position = con.execute(
        """
        SELECT
            id,
            name,
            description,
            active
        FROM positions
        WHERE id = ?
        """,
        (position_id,),
    ).fetchone()

    if not position:
        con.close()

        return {
            "success": False,
            "message": "Position not found",
        }

    permissions = con.execute(
        """
        SELECT
            p.id,
            p.code,
            p.description,
            COALESCE(pp.allowed, 0) AS allowed
        FROM permissions p
        LEFT JOIN position_permissions pp
            ON pp.permission_id = p.id
           AND pp.position_id = ?
        ORDER BY p.description COLLATE NOCASE, p.code
        """,
        (position_id,),
    ).fetchall()

    con.close()

    return {
        "success": True,
        "position": dict(position),
        "permissions": [
            dict(row)
            for row in permissions
        ],
    }


def save_position_permissions(
    position_id: int,
    permission_ids,
):
    """
    Replace the allowed permission set for one position.

    permission_ids should be an iterable of permission IDs.

    Existing rows are replaced so the database exactly matches
    the checkboxes selected in the UI.
    """

    permission_ids = {
        int(permission_id)
        for permission_id in permission_ids
    }

    con = connect()

    position = con.execute(
        """
        SELECT
            id,
            name
        FROM positions
        WHERE id = ?
        """,
        (position_id,),
    ).fetchone()

    protected_permission_roles = {
        "System Administrator",
        "General Manager",
    }

    if position["name"] in protected_permission_roles:
        manage_permission = con.execute(
            """
            SELECT id
            FROM permissions
            WHERE code = ?
            """,
            ("positions.manage",),
        ).fetchone()

        if manage_permission:
            permission_ids.add(
                manage_permission["id"]
            )

    if not position:
        con.close()

        return {
            "success": False,
            "message": "Position not found",
        }

    valid_permissions = {
        row["id"]
        for row in con.execute(
            """
            SELECT id
            FROM permissions
            """
        ).fetchall()
    }

    invalid_ids = permission_ids - valid_permissions

    if invalid_ids:
        con.close()

        return {
            "success": False,
            "message": "Invalid permission selection",
        }

    con.execute(
        """
        DELETE FROM position_permissions
        WHERE position_id = ?
        """,
        (position_id,),
    )

    for permission_id in sorted(permission_ids):
        con.execute(
            """
            INSERT INTO position_permissions(
                position_id,
                permission_id,
                allowed
            )
            VALUES (?, ?, 1)
            """,
            (
                position_id,
                permission_id,
            ),
        )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"Permissions updated for {position['name']}"
        ),
        "position_id": position_id,
        "permission_count": len(permission_ids),
    }

def create_position(
    name: str,
    description: str = "",
):
    name = name.strip()
    description = description.strip()

    if not name:
        return {
            "success": False,
            "message": "Position name is required",
        }

    con = connect()

    existing = con.execute(
        """
        SELECT id
        FROM positions
        WHERE LOWER(name) = LOWER(?)
        """,
        (name,),
    ).fetchone()

    if existing:
        con.close()

        return {
            "success": False,
            "message": "A position with that name already exists",
        }

    cursor = con.execute(
        """
        INSERT INTO positions(
            name,
            description,
            active
        )
        VALUES (?, ?, 1)
        """,
        (
            name,
            description,
        ),
    )

    position_id = cursor.lastrowid

    con.commit()
    con.close()

    return {
        "success": True,
        "message": f"Position created: {name}",
        "position_id": position_id,
    }


def update_position(
    position_id: int,
    name: str,
    description: str = "",
):
    name = name.strip()
    description = description.strip()

    if not name:
        return {
            "success": False,
            "message": "Position name is required",
        }

    con = connect()

    position = con.execute(
        """
        SELECT id, name
        FROM positions
        WHERE id = ?
        """,
        (position_id,),
    ).fetchone()

    if not position:
        con.close()

        return {
            "success": False,
            "message": "Position not found",
        }

    duplicate = con.execute(
        """
        SELECT id
        FROM positions
        WHERE LOWER(name) = LOWER(?)
          AND id != ?
        """,
        (
            name,
            position_id,
        ),
    ).fetchone()

    if duplicate:
        con.close()

        return {
            "success": False,
            "message": "Another position already uses that name",
        }

    con.execute(
        """
        UPDATE positions
        SET name = ?,
            description = ?
        WHERE id = ?
        """,
        (
            name,
            description,
            position_id,
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": f"Position updated: {name}",
    }


def set_position_active(
    position_id: int,
    active: bool,
):
    con = connect()

    position = con.execute(
        """
        SELECT id, name
        FROM positions
        WHERE id = ?
        """,
        (position_id,),
    ).fetchone()

    if not position:
        con.close()

        return {
            "success": False,
            "message": "Position not found",
        }

    protected_positions = {
        "System Administrator",
        "General Manager",
    }

    if (
        position["name"] in protected_positions
        and not active
    ):
        con.close()

        return {
            "success": False,
            "message": (
                f"{position['name']} cannot be retired"
            ),
        }

    con.execute(
        """
        UPDATE positions
        SET active = ?
        WHERE id = ?
        """,
        (
            1 if active else 0,
            position_id,
        ),
    )

    con.commit()
    con.close()

    state = "reactivated" if active else "retired"

    return {
        "success": True,
        "message": (
            f"{position['name']} {state}"
        ),
    }