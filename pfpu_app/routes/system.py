from urllib.parse import quote

from fastapi import APIRouter, Request
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

    return request.app.state.templates.TemplateResponse(
        "system.html",
        {
            "request": request,
            "integrity": integrity,
            "recent_backups": recent_backups,
            "backup_count": len(backup_files),
            "retention_count": BACKUP_RETENTION_COUNT,
            "database_size_mb": database_size_mb,
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