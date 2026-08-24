from fastapi import APIRouter, Request
from fastapi.responses import (
    FileResponse,
    RedirectResponse,
)

from ..services.auth_service import request_has_permission
from ..services.excel_service import export_excel_file

router = APIRouter()


@router.get("/export")
def export_excel(
    request: Request,
):
    if not request_has_permission(
        request,
        "system.export",
    ):
        return RedirectResponse(
            "/?message=Access denied",
            status_code=303,
        )

    output = export_excel_file()

    return FileResponse(
        output,
        filename=output.name,
    )