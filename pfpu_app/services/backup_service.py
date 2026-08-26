import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import (
    BACKUP_DIR,
    BACKUP_RETENTION_COUNT,
    DB_PATH,
)


def check_database_integrity() -> dict:
    """
    Run SQLite's integrity check against the live PFPU database.
    """

    if not DB_PATH.exists():
        return {
            "success": False,
            "message": "Database file does not exist.",
        }

    con = sqlite3.connect(DB_PATH)

    try:
        result = con.execute(
            "PRAGMA integrity_check"
        ).fetchone()

        integrity_result = (
            result[0]
            if result
            else "No result"
        )

        if integrity_result.lower() == "ok":
            return {
                "success": True,
                "message": "Database integrity check passed.",
            }

        return {
            "success": False,
            "message": (
                "Database integrity check failed: "
                f"{integrity_result}"
            ),
        }

    finally:
        con.close()


def cleanup_old_backups() -> int:
    """
    Keep only the newest configured number of PFPU backups.

    Returns the number of old backup files removed.
    """

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    backups = sorted(
        BACKUP_DIR.glob(
            "pfpu_inventory_*.sqlite3"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    removed = 0

    for backup_path in backups[
        BACKUP_RETENTION_COUNT:
    ]:
        backup_path.unlink()
        removed += 1

    return removed


def create_database_backup(
    reason: str = "manual",
) -> dict:
    """
    Create a consistent SQLite backup of the PFPU database.

    SQLite's backup API is used instead of copying the live
    database file directly.
    """

    if not DB_PATH.exists():
        return {
            "success": False,
            "message": "Database file does not exist.",
            "path": None,
        }

    integrity = check_database_integrity()

    if not integrity["success"]:
        return {
            "success": False,
            "message": integrity["message"],
            "path": None,
        }

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S_%f"
    )

    safe_reason = "".join(
        character
        if character.isalnum() or character in ("-", "_")
        else "_"
        for character in reason.strip()
    )

    if not safe_reason:
        safe_reason = "backup"

    backup_path = (
        BACKUP_DIR
        / (
            f"pfpu_inventory_"
            f"{timestamp}_"
            f"{safe_reason}.sqlite3"
        )
    )

    source = sqlite3.connect(DB_PATH)
    destination = sqlite3.connect(
        backup_path
    )

    try:
        source.backup(destination)
        destination.commit()

    except Exception:
        destination.close()
        source.close()

        if backup_path.exists():
            backup_path.unlink()

        raise

    else:
        destination.close()
        source.close()

    # Verify the newly created backup itself.
    backup_con = sqlite3.connect(
        backup_path
    )

    try:
        backup_check = backup_con.execute(
            "PRAGMA integrity_check"
        ).fetchone()

        backup_result = (
            backup_check[0]
            if backup_check
            else "No result"
        )

    finally:
        backup_con.close()

    if backup_result.lower() != "ok":

        if backup_path.exists():
            backup_path.unlink()

        return {
            "success": False,
            "message": (
                "Backup was created but failed "
                "its integrity check."
            ),
            "path": None,
        }

    removed = cleanup_old_backups()

    message = (
        f"Database backup created: "
        f"{backup_path.name}"
    )

    if removed:
        message += (
            f" Removed {removed} old backup"
        )

        if removed != 1:
            message += "s"

        message += "."

    return {
        "success": True,
        "message": message,
        "path": backup_path,
    }