from ..database import connect


ADMIN_PERMISSION_CODES = {
    "users.manage",
    "positions.manage",
}


def _position_ids_grant_admin_access(
    con,
    position_ids,
):
    """
    Determine whether a proposed set of positions grants
    both required administrative permissions.
    """

    position_ids = set(position_ids)

    if not position_ids:
        return False

    placeholders = ",".join(
        "?"
        for _ in position_ids
    )

    rows = con.execute(
        f"""
        SELECT DISTINCT
            p.code
        FROM position_permissions pp
        JOIN permissions p
            ON p.id = pp.permission_id
        JOIN positions pos
            ON pos.id = pp.position_id
        WHERE pp.position_id IN ({placeholders})
          AND pp.allowed = 1
          AND pos.active = 1
          AND p.code IN (
              'users.manage',
              'positions.manage'
          )
        """,
        tuple(position_ids),
    ).fetchall()

    permission_codes = {
        row["code"]
        for row in rows
    }

    return ADMIN_PERMISSION_CODES.issubset(
        permission_codes
    )


def _user_has_admin_access(
    con,
    user_id: int,
):
    """
    Return True when this user is currently a usable
    administrator.

    A usable administrator must:
    - be active
    - have a configured password
    - inherit users.manage
    - inherit positions.manage
    """

    user = con.execute(
        """
        SELECT
            id,
            active,
            password_hash
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        return False

    if not user["active"]:
        return False

    if not user["password_hash"]:
        return False

    rows = con.execute(
        """
        SELECT DISTINCT
            p.code
        FROM user_positions up
        JOIN positions pos
            ON pos.id = up.position_id
        JOIN position_permissions pp
            ON pp.position_id = pos.id
           AND pp.allowed = 1
        JOIN permissions p
            ON p.id = pp.permission_id
        WHERE up.user_id = ?
          AND pos.active = 1
          AND p.code IN (
              'users.manage',
              'positions.manage'
          )
        """,
        (user_id,),
    ).fetchall()

    permission_codes = {
        row["code"]
        for row in rows
    }

    return ADMIN_PERMISSION_CODES.issubset(
        permission_codes
    )


def _count_other_admin_users(
    con,
    exclude_user_id: int,
):
    """
    Count usable administrator accounts other than
    the supplied user.
    """

    rows = con.execute(
        """
        SELECT
            u.id
        FROM users u
        WHERE u.id != ?
          AND u.active = 1
          AND u.password_hash IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM user_positions up
              JOIN positions pos
                  ON pos.id = up.position_id
              JOIN position_permissions pp
                  ON pp.position_id = pos.id
                 AND pp.allowed = 1
              JOIN permissions p
                  ON p.id = pp.permission_id
              WHERE up.user_id = u.id
                AND pos.active = 1
                AND p.code = 'users.manage'
          )
          AND EXISTS (
              SELECT 1
              FROM user_positions up
              JOIN positions pos
                  ON pos.id = up.position_id
              JOIN position_permissions pp
                  ON pp.position_id = pos.id
                 AND pp.allowed = 1
              JOIN permissions p
                  ON p.id = pp.permission_id
              WHERE up.user_id = u.id
                AND pos.active = 1
                AND p.code = 'positions.manage'
          )
        """,
        (exclude_user_id,),
    ).fetchall()

    return len(rows)


def get_users():
    """
    Return all users with their assigned positions.
    """

    con = connect()

    users = con.execute(
        """
        SELECT
            u.id,
            u.username,
            u.display_name,
            u.email,
            u.active,
            u.created_at,
            u.updated_at,
            GROUP_CONCAT(p.name, ', ') AS positions
        FROM users u
        LEFT JOIN user_positions up
            ON up.user_id = u.id
        LEFT JOIN positions p
            ON p.id = up.position_id
        GROUP BY u.id
        ORDER BY
            u.active DESC,
            u.display_name COLLATE NOCASE
        """
    ).fetchall()

    con.close()

    return [
        dict(row)
        for row in users
    ]


def get_user(user_id: int):
    """
    Return one user plus all positions and current assignments.
    """

    con = connect()

    user = con.execute(
        """
        SELECT
            id,
            username,
            display_name,
            email,
            active,
            created_at,
            updated_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        con.close()

        return {
            "success": False,
            "message": "User not found",
        }

    positions = con.execute(
        """
        SELECT
            p.id,
            p.name,
            p.description,
            p.active,
            CASE
                WHEN up.user_id IS NOT NULL
                THEN 1
                ELSE 0
            END AS assigned
        FROM positions p
        LEFT JOIN user_positions up
            ON up.position_id = p.id
           AND up.user_id = ?
        ORDER BY
            p.active DESC,
            p.name COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()

    con.close()

    return {
        "success": True,
        "user": dict(user),
        "positions": [
            dict(row)
            for row in positions
        ],
    }


def create_user(
    username: str,
    display_name: str,
    email: str = "",
):
    """
    Create a user account.
    """

    username = username.strip()
    display_name = display_name.strip()
    email = email.strip()

    if not username:
        return {
            "success": False,
            "message": "Username is required",
        }

    if not display_name:
        return {
            "success": False,
            "message": "Display name is required",
        }

    con = connect()

    existing = con.execute(
        """
        SELECT id
        FROM users
        WHERE LOWER(username) = LOWER(?)
        """,
        (username,),
    ).fetchone()

    if existing:
        con.close()

        return {
            "success": False,
            "message": "That username already exists",
        }

    cursor = con.execute(
        """
        INSERT INTO users(
            username,
            display_name,
            email,
            active
        )
        VALUES (?, ?, ?, 1)
        """,
        (
            username,
            display_name,
            email or None,
        ),
    )

    user_id = cursor.lastrowid

    con.commit()
    con.close()

    return {
        "success": True,
        "message": f"User created: {display_name}",
        "user_id": user_id,
    }


def update_user(
    user_id: int,
    username: str,
    display_name: str,
    email: str = "",
):
    """
    Update basic user account information.
    """

    username = username.strip()
    display_name = display_name.strip()
    email = email.strip()

    if not username:
        return {
            "success": False,
            "message": "Username is required",
        }

    if not display_name:
        return {
            "success": False,
            "message": "Display name is required",
        }

    con = connect()

    user = con.execute(
        """
        SELECT id
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        con.close()

        return {
            "success": False,
            "message": "User not found",
        }

    duplicate = con.execute(
        """
        SELECT id
        FROM users
        WHERE LOWER(username) = LOWER(?)
          AND id != ?
        """,
        (
            username,
            user_id,
        ),
    ).fetchone()

    if duplicate:
        con.close()

        return {
            "success": False,
            "message": (
                "Another user already uses that username"
            ),
        }

    con.execute(
        """
        UPDATE users
        SET username = ?,
            display_name = ?,
            email = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            username,
            display_name,
            email or None,
            user_id,
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": f"User updated: {display_name}",
    }


def save_user_positions(
    user_id: int,
    position_ids,
):
    """
    Replace a user's position assignments.

    Prevents removal of administrative access from the
    last usable administrator account.
    """

    position_ids = {
        int(position_id)
        for position_id in position_ids
    }

    con = connect()

    user = con.execute(
        """
        SELECT
            id,
            display_name,
            active,
            password_hash
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        con.close()

        return {
            "success": False,
            "message": "User not found",
        }

    valid_positions = {
        row["id"]
        for row in con.execute(
            """
            SELECT id
            FROM positions
            WHERE active = 1
            """
        ).fetchall()
    }

    invalid_ids = position_ids - valid_positions

    if invalid_ids:
        con.close()

        return {
            "success": False,
            "message": (
                "Invalid or retired position selected"
            ),
        }

    currently_admin = _user_has_admin_access(
        con,
        user_id,
    )

    proposed_admin = (
        bool(user["active"])
        and bool(user["password_hash"])
        and _position_ids_grant_admin_access(
            con,
            position_ids,
        )
    )

    if (
        currently_admin
        and not proposed_admin
        and _count_other_admin_users(
            con,
            user_id,
        ) == 0
    ):
        con.close()

        return {
            "success": False,
            "message": (
                "Cannot remove administrative access. "
                "This is the last active administrator "
                "account with a configured password."
            ),
        }

    con.execute(
        """
        DELETE FROM user_positions
        WHERE user_id = ?
        """,
        (user_id,),
    )

    for position_id in sorted(position_ids):
        con.execute(
            """
            INSERT INTO user_positions(
                user_id,
                position_id
            )
            VALUES (?, ?)
            """,
            (
                user_id,
                position_id,
            ),
        )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"Positions updated for "
            f"{user['display_name']}"
        ),
        "position_count": len(position_ids),
    }


def set_user_active(
    user_id: int,
    active: bool,
):
    """
    Activate or deactivate a user account.

    Prevents deactivation of the last usable
    administrator account.
    """

    con = connect()

    user = con.execute(
        """
        SELECT
            id,
            display_name,
            active
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        con.close()

        return {
            "success": False,
            "message": "User not found",
        }

    if (
        user["active"]
        and not active
        and _user_has_admin_access(
            con,
            user_id,
        )
        and _count_other_admin_users(
            con,
            user_id,
        ) == 0
    ):
        con.close()

        return {
            "success": False,
            "message": (
                "Cannot deactivate this account. "
                "It is the last active administrator "
                "with a configured password."
            ),
        }

    con.execute(
        """
        UPDATE users
        SET active = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            1 if active else 0,
            user_id,
        ),
    )

    con.commit()
    con.close()

    state = (
        "activated"
        if active
        else "deactivated"
    )

    return {
        "success": True,
        "message": (
            f"{user['display_name']} {state}"
        ),
    }