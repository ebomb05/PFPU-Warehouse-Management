from pwdlib import PasswordHash

from ..database import connect


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Securely hash a password for database storage.
    """

    return password_hash.hash(password)


def verify_password(
    password: str,
    stored_hash: str,
) -> bool:
    """
    Verify a plaintext password against its stored hash.
    """

    if not stored_hash:
        return False

    try:
        return password_hash.verify(
            password,
            stored_hash,
        )

    except Exception:
        return False


def set_user_password(
    user_id: int,
    new_password: str,
):
    """
    Set or replace a user's password.
    """

    if len(new_password) < 8:
        return {
            "success": False,
            "message": (
                "Password must be at least 8 characters long"
            ),
        }

    con = connect()

    user = con.execute(
        """
        SELECT
            id,
            username,
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

    hashed = hash_password(new_password)

    con.execute(
        """
        UPDATE users
        SET password_hash = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            hashed,
            user_id,
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"Password updated for {user['display_name']}"
        ),
    }


def authenticate_user(
    username: str,
    password: str,
):
    """
    Validate an active user account and password.
    """

    username = username.strip()

    con = connect()

    user = con.execute(
        """
        SELECT
            id,
            username,
            display_name,
            email,
            password_hash,
            active
        FROM users
        WHERE LOWER(username) = LOWER(?)
        """,
        (username,),
    ).fetchone()

    con.close()

    if not user:
        return {
            "success": False,
            "message": "Invalid username or password",
        }

    if not user["active"]:
        return {
            "success": False,
            "message": "This account is inactive",
        }

    if not user["password_hash"]:
        return {
            "success": False,
            "message": "Password has not been configured for this account",
        }

    if not verify_password(
        password,
        user["password_hash"],
    ):
        return {
            "success": False,
            "message": "Invalid username or password",
        }

    return {
        "success": True,
        "message": "Authentication successful",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "email": user["email"],
        },
    }

def get_user_permissions(user_id: int):
    """
    Return the effective permission set for a user.

    Permissions are combined across every active position
    assigned to the user.
    """

    con = connect()

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
        ORDER BY p.code
        """,
        (user_id,),
    ).fetchall()

    con.close()

    return {
        row["code"]
        for row in rows
    }


def user_has_permission(
    user_id: int,
    permission_code: str,
):
    """
    Check whether a user has one effective permission.
    """

    permissions = get_user_permissions(user_id)

    return permission_code in permissions

from fastapi import Request


def request_has_permission(
    request: Request,
    permission_code: str,
):
    """
    Check the permission set already loaded onto request.state.
    """

    permissions = getattr(
        request.state,
        "permissions",
        set(),
    )

    return permission_code in permissions