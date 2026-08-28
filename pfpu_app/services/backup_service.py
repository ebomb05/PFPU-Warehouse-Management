import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import (
    BACKUP_DIR,
    BACKUP_RETENTION_COUNT,
    DB_PATH,
)


def _check_integrity(
    database_path: Path,
) -> dict:
    """
    Run SQLite integrity_check against a database file.
    """

    if not database_path.exists():
        return {
            "success": False,
            "message": (
                f"Database file does not exist: "
                f"{database_path.name}"
            ),
        }

    con = sqlite3.connect(database_path)

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
                "message": (
                    "Database integrity check passed."
                ),
            }

        return {
            "success": False,
            "message": (
                "Database integrity check failed: "
                f"{integrity_result}"
            ),
        }

    except sqlite3.DatabaseError as exc:
        return {
            "success": False,
            "message": (
                "Unable to read database: "
                f"{exc}"
            ),
        }

    finally:
        con.close()


def check_database_integrity() -> dict:
    """
    Run SQLite's integrity check against the live PFPU database.
    """

    return _check_integrity(DB_PATH)


def validate_backup_file(
    backup_path: Path,
) -> dict:
    """
    Validate a candidate PFPU backup before it can be restored.
    """

    backup_path = Path(backup_path)

    if not backup_path.exists():
        return {
            "success": False,
            "message": "Backup file does not exist.",
        }

    if backup_path.suffix.lower() != ".sqlite3":
        return {
            "success": False,
            "message": (
                "Selected file is not a SQLite backup."
            ),
        }

    try:
        resolved_backup = backup_path.resolve()
        resolved_backup_dir = BACKUP_DIR.resolve()

        if (
            resolved_backup_dir
            not in resolved_backup.parents
        ):
            return {
                "success": False,
                "message": (
                    "Backup file is outside the PFPU "
                    "backup directory."
                ),
            }

    except OSError:
        return {
            "success": False,
            "message": (
                "Unable to validate backup path."
            ),
        }

    integrity = _check_integrity(
        backup_path
    )

    if not integrity["success"]:
        return integrity

    con = sqlite3.connect(
        backup_path
    )

    try:
        required_tables = {
            "item_master",
            "assets",
            "jobs",
            "job_lines",
        }

        table_rows = con.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        table_names = {
            row[0]
            for row in table_rows
        }

        missing_tables = (
            required_tables - table_names
        )

        if missing_tables:
            return {
                "success": False,
                "message": (
                    "Backup is missing required tables: "
                    + ", ".join(
                        sorted(missing_tables)
                    )
                ),
            }

    finally:
        con.close()

    return {
        "success": True,
        "message": (
            f"Backup verified: "
            f"{backup_path.name}"
        ),
    }


def cleanup_old_backups() -> int:
    """
    Keep only the newest configured number of PFPU backups.

    A backup that cannot be removed because it is locked or
    protected by Windows is skipped so backup cleanup can
    never prevent PFPU from starting.

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
        try:
            backup_path.unlink()
            removed += 1
        except (PermissionError, OSError) as exc:
            print(
                "[PFPU] WARNING: Could not remove old backup "
                f"{backup_path.name}: {exc}"
            )

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
        if character.isalnum()
        or character in ("-", "_")
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

    backup_integrity = _check_integrity(
        backup_path
    )

    if not backup_integrity["success"]:

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


def restore_database_to_file(
    backup_path: Path,
    destination_path: Path,
) -> dict:
    """
    Restore a backup into another database file.

    This is used for isolated restore testing and verification.
    It does not modify the live PFPU database.
    """

    backup_path = Path(
        backup_path
    )

    destination_path = Path(
        destination_path
    )

    validation = validate_backup_file(
        backup_path
    )

    if not validation["success"]:
        return {
            "success": False,
            "message": validation["message"],
            "path": None,
        }

    destination_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination_path.exists():
        destination_path.unlink()

    source = sqlite3.connect(
        backup_path
    )

    destination = sqlite3.connect(
        destination_path
    )

    try:
        source.backup(destination)
        destination.commit()

    except Exception as exc:

        destination.close()
        source.close()

        if destination_path.exists():
            destination_path.unlink()

        return {
            "success": False,
            "message": (
                "Restore test failed: "
                f"{exc}"
            ),
            "path": None,
        }

    else:
        destination.close()
        source.close()

    integrity = _check_integrity(
        destination_path
    )

    if not integrity["success"]:

        if destination_path.exists():
            destination_path.unlink()

        return {
            "success": False,
            "message": (
                "Restored database failed "
                "integrity verification."
            ),
            "path": None,
        }

    return {
        "success": True,
        "message": (
            f"Backup restored successfully to "
            f"{destination_path.name}"
        ),
        "path": destination_path,
    }


def restore_live_database(
    backup_path: Path,
) -> dict:
    """
    Restore a verified PFPU backup over the live database.

    Safety sequence:
    1. Validate selected backup.
    2. Create pre-restore backup of current live DB.
    3. Restore selected backup through SQLite backup API.
    4. Verify restored live DB.
    5. Roll back automatically if verification fails.
    """

    backup_path = Path(
        backup_path
    )

    validation = validate_backup_file(
        backup_path
    )

    if not validation["success"]:
        return {
            "success": False,
            "message": validation["message"],
        }

    safety_backup = create_database_backup(
        "pre-restore"
    )

    if not safety_backup["success"]:
        return {
            "success": False,
            "message": (
                "Restore cancelled because the "
                "pre-restore safety backup failed. "
                + safety_backup["message"]
            ),
        }

    source = sqlite3.connect(
        backup_path
    )

    destination = sqlite3.connect(
        DB_PATH
    )

    try:
        source.backup(destination)
        destination.commit()

    except Exception as exc:

        destination.close()
        source.close()

        return {
            "success": False,
            "message": (
                "Restore failed before completion: "
                f"{exc}. Current safety backup: "
                f"{safety_backup['path'].name}"
            ),
        }

    else:
        destination.close()
        source.close()

    restored_integrity = (
        check_database_integrity()
    )

    if restored_integrity["success"]:
        return {
            "success": True,
            "message": (
                "Database restored successfully from "
                f"{backup_path.name}. "
                "Pre-restore safety backup: "
                f"{safety_backup['path'].name}"
            ),
        }

    # -----------------------------------------------------
    # AUTOMATIC ROLLBACK
    # -----------------------------------------------------

    rollback_source = sqlite3.connect(
        safety_backup["path"]
    )

    rollback_destination = sqlite3.connect(
        DB_PATH
    )

    try:
        rollback_source.backup(
            rollback_destination
        )

        rollback_destination.commit()

    finally:
        rollback_destination.close()
        rollback_source.close()

    rollback_integrity = (
        check_database_integrity()
    )

    if rollback_integrity["success"]:
        return {
            "success": False,
            "message": (
                "Selected backup failed after restore. "
                "PFPU automatically restored the "
                "pre-restore safety database."
            ),
        }

    return {
        "success": False,
        "message": (
            "CRITICAL: Restore failed and automatic "
            "rollback could not be verified. "
            "Manual database recovery is required."
        ),
    }