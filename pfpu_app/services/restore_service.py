import json
from pathlib import Path

from ..config import (
    BACKUP_DIR,
    DATA_DIR,
)
from .backup_service import (
    restore_live_database,
    validate_backup_file,
)


RESTORE_REQUEST_PATH = (
    DATA_DIR / "pending_restore.json"
)


def schedule_database_restore(
    backup_name: str,
) -> dict:
    """
    Validate a PFPU backup and schedule it for restore
    during the next application startup.

    The live database is NOT modified by this function.
    """

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Only allow a filename, never a user-supplied path.
    safe_name = Path(
        backup_name
    ).name

    backup_path = (
        BACKUP_DIR / safe_name
    )

    validation = validate_backup_file(
        backup_path
    )

    if not validation["success"]:
        return {
            "success": False,
            "message": validation["message"],
        }

    restore_request = {
        "backup_name": safe_name,
    }

    RESTORE_REQUEST_PATH.write_text(
        json.dumps(
            restore_request,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "success": True,
        "message": (
            f"Restore scheduled from {safe_name}. "
            "Restart PFPU to perform the restore."
        ),
    }


def cancel_scheduled_restore() -> dict:
    """
    Remove a pending restore request.
    """

    if RESTORE_REQUEST_PATH.exists():
        RESTORE_REQUEST_PATH.unlink()

        return {
            "success": True,
            "message": (
                "Scheduled database restore cancelled."
            ),
        }

    return {
        "success": True,
        "message": (
            "No database restore is currently scheduled."
        ),
    }


def get_pending_restore() -> dict | None:
    """
    Return information about the scheduled restore,
    if one exists.
    """

    if not RESTORE_REQUEST_PATH.exists():
        return None

    try:
        restore_request = json.loads(
            RESTORE_REQUEST_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return {
            "backup_name": "Invalid restore request",
        }

    return {
        "backup_name": restore_request.get(
            "backup_name",
            "Unknown",
        ),
    }


def process_pending_restore() -> dict:
    """
    Perform a scheduled restore during application startup.

    This must run before normal PFPU database initialization
    and before the server begins accepting requests.
    """

    if not RESTORE_REQUEST_PATH.exists():
        return {
            "success": True,
            "performed": False,
            "message": (
                "No database restore is scheduled."
            ),
        }

    try:
        restore_request = json.loads(
            RESTORE_REQUEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        backup_name = (
            Path(
                restore_request["backup_name"]
            ).name
        )

    except Exception as exc:

        RESTORE_REQUEST_PATH.unlink(
            missing_ok=True
        )

        return {
            "success": False,
            "performed": False,
            "message": (
                "Invalid pending restore request: "
                f"{exc}"
            ),
        }

    backup_path = (
        BACKUP_DIR / backup_name
    )

    validation = validate_backup_file(
        backup_path
    )

    if not validation["success"]:

        RESTORE_REQUEST_PATH.unlink(
            missing_ok=True
        )

        return {
            "success": False,
            "performed": False,
            "message": (
                "Scheduled restore cancelled: "
                + validation["message"]
            ),
        }

    # Remove the request BEFORE attempting the restore.
    # This prevents an endless restore loop if something
    # unexpected causes startup to fail afterward.
    RESTORE_REQUEST_PATH.unlink(
        missing_ok=True
    )

    restore_result = restore_live_database(
        backup_path
    )

    return {
        "success": restore_result["success"],
        "performed": True,
        "message": restore_result["message"],
    }