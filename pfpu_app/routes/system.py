from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import (
    BACKUP_DIR,
    BACKUP_RETENTION_COUNT,
    DB_PATH,
)
from ..services.auth_service import request_has_permission
from ..services.backup_service import (
    check_database_integrity,
    create_database_backup,
    validate_backup_file,
)
from ..services.restore_service import (
    cancel_scheduled_restore,
    get_pending_restore,
    schedule_database_restore,
)


router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get(
    "/system",
    response_class=HTMLResponse,
)
def system_page(
    request: Request,
    message: str = "",
    result: str = "",
):
    if not request_has_permission(
        request,
        "system.export",
    ):
        return deny_access()

    integrity = check_database_integrity()

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    backup_files = sorted(
        BACKUP_DIR.glob(
            "pfpu_inventory_*.sqlite3"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    recent_backups = []

    for backup_path in backup_files[:10]:
        stat = backup_path.stat()

        recent_backups.append(
            {
                "name": backup_path.name,
                "size_mb": round(
                    stat.st_size / 1024 / 1024,
                    2,
                ),
                "modified": (
                    __import__("datetime")
                    .datetime.fromtimestamp(
                        stat.st_mtime
                    )
                    .strftime(
                        "%Y-%m-%d %I:%M %p"
                    )
                ),
            }
        )

    database_size_mb = 0

    if DB_PATH.exists():
        database_size_mb = round(
            DB_PATH.stat().st_size
            / 1024
            / 1024,
            2,
        )

    pending_restore = get_pending_restore()

    return request.app.state.templates.TemplateResponse(
        "system.html",
        {
            "request": request,
            "integrity": integrity,
            "recent_backups": recent_backups,
            "backup_count": len(backup_files),
            "retention_count": BACKUP_RETENTION_COUNT,
            "database_size_mb": database_size_mb,
            "pending_restore": pending_restore,
            "message": message,
            "result": result,
        },
    )


@router.post("/system/backup")
def manual_backup(
    request: Request,
):
    if not request_has_permission(
        request,
        "system.export",
    ):
        return deny_access()

    backup_result = create_database_backup(
        "manual"
    )

    result_type = (
        "success"
        if backup_result["success"]
        else "error"
    )

    return RedirectResponse(
        "/system"
        f"?result={result_type}"
        "&message="
        + quote(backup_result["message"]),
        status_code=303,
    )


@router.get(
    "/system/restore",
    response_class=HTMLResponse,
)
def restore_confirm_page(
    request: Request,
    backup_name: str = "",
):
    if not request_has_permission(
        request,
        "system.export",
    ):
        return deny_access()

    backup_path = (
        BACKUP_DIR
        / backup_name
    )

    validation = validate_backup_file(
        backup_path
    )

    if not validation["success"]:
        return RedirectResponse(
            "/system?result=error&message="
            + quote(validation["message"]),
            status_code=303,
        )

    return request.app.state.templates.TemplateResponse(
        "system_restore.html",
        {
            "request": request,
            "backup_name": backup_name,
        },
    )


@router.post(
    "/system/restore/schedule"
)
def schedule_restore(
    request: Request,
    backup_name: str = Form(...),
    confirmation: str = Form(...),
):
    if not request_has_permission(
        request,
        "system.export",
    ):
        return deny_access()

    if confirmation.strip().upper() != "RESTORE":
        return RedirectResponse(
            "/system/restore"
            f"?backup_name={quote(backup_name)}"
            "&message="
            + quote(
                "Type RESTORE exactly to confirm."
            ),
            status_code=303,
        )

    restore_result = schedule_database_restore(
        backup_name
    )

    result_type = (
        "success"
        if restore_result["success"]
        else "error"
    )

    return RedirectResponse(
        "/system"
        f"?result={result_type}"
        "&message="
        + quote(restore_result["message"]),
        status_code=303,
    )


@router.post(
    "/system/restore/cancel"
)
def cancel_restore(
    request: Request,
):
    if not request_has_permission(
        request,
        "system.export",
    ):
        return deny_access()

    result = cancel_scheduled_restore()

    return RedirectResponse(
        "/system?result=success&message="
        + quote(result["message"]),
        status_code=303,
    )