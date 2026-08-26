from ..database import connect
from .auth_service import hash_password


def system_needs_bootstrap() -> bool:
    """
    Return True only when the PFPU database contains no users.
    """

    con = connect()

    try:
        count = con.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        return count == 0

    finally:
        con.close()


def create_initial_administrator(
    username: str,
    display_name: str,
    password: str,
    confirm_password: str,
    email: str = "",
) -> dict:
    """
    Create PFPU's first System Administrator.

    This operation is protected by a BEGIN IMMEDIATE transaction
    so two simultaneous first-run requests cannot both create
    bootstrap administrator accounts.
    """

    username = username.strip()
    display_name = display_name.strip()
    email = email.strip()

    if not username:
        return {
            "success": False,
            "message": "Username is required.",
        }

    if not display_name:
        return {
            "success": False,
            "message": "Display name is required.",
        }

    if len(password) < 8:
        return {
            "success": False,
            "message": (
                "Password must be at least 8 characters long."
            ),
        }

    if password != confirm_password:
        return {
            "success": False,
            "message": "Passwords do not match.",
        }

    hashed_password = hash_password(password)

    con = connect()

    try:
        # Lock the database for this bootstrap operation.
        con.execute("BEGIN IMMEDIATE")

        user_count = con.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        if user_count != 0:
            con.rollback()

            return {
                "success": False,
                "message": (
                    "Initial setup has already been completed."
                ),
            }

        admin_position = con.execute(
            """
            SELECT id
            FROM positions
            WHERE name = ?
              AND active = 1
            """,
            ("System Administrator",),
        ).fetchone()

        if not admin_position:
            con.rollback()

            return {
                "success": False,
                "message": (
                    "System Administrator position was not found."
                ),
            }

        cursor = con.execute(
            """
            INSERT INTO users(
                username,
                display_name,
                email,
                password_hash,
                active
            )
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                username,
                display_name,
                email or None,
                hashed_password,
            ),
        )

        user_id = cursor.lastrowid

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
                admin_position["id"],
            ),
        )

        con.commit()

        return {
            "success": True,
            "message": (
                "System Administrator created successfully."
            ),
            "user": {
                "id": user_id,
                "username": username,
                "display_name": display_name,
                "email": email,
            },
        }

    except Exception as exc:
        con.rollback()

        return {
            "success": False,
            "message": (
                "Unable to create the initial administrator: "
                f"{exc}"
            ),
        }

    finally:
        con.close()