from urllib.parse import quote

from fastapi import (
    APIRouter,
    File,
    Form,
    Request,
    UploadFile,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from ..services.auth_service import (
    request_has_permission,
)
from ..services.inventory_import_service import (
    analyze_inventory_file,
    confirm_inventory_import,
    get_staged_import_path,
    inventory_is_empty,
    stage_inventory_file,
)


router = APIRouter()


def _can_import(request: Request) -> bool:
    """
    Initial inventory import is restricted to users with
    system-level export/data access.
    """

    return request_has_permission(
        request,
        "system.export",
    )


@router.get(
    "/inventory/import",
    response_class=HTMLResponse,
)
def inventory_import_page(
    request: Request,
    message: str = "",
):
    if not _can_import(request):
        return RedirectResponse(
            "/?message=Access%20denied",
            status_code=303,
        )

    return request.app.state.templates.TemplateResponse(
        "inventory_import.html",
        {
            "request": request,
            "message": message,
            "inventory_empty": inventory_is_empty(),
            "analysis": None,
            "token": "",
            "filename": "",
        },
    )


@router.post(
    "/inventory/import/preview",
    response_class=HTMLResponse,
)
def inventory_import_preview(
    request: Request,
    inventory_file: UploadFile = File(...),
):
    if not _can_import(request):
        return RedirectResponse(
            "/?message=Access%20denied",
            status_code=303,
        )

    if not inventory_is_empty():
        return RedirectResponse(
            "/inventory/import?message="
            + quote(
                "Inventory already contains items. "
                "Initial Excel import is available only "
                "for an empty inventory database."
            ),
            status_code=303,
        )

    staged = stage_inventory_file(
        inventory_file.file,
        inventory_file.filename or "",
    )

    if not staged["success"]:
        return request.app.state.templates.TemplateResponse(
            "inventory_import.html",
            {
                "request": request,
                "message": staged["message"],
                "inventory_empty": True,
                "analysis": None,
                "token": "",
                "filename": "",
            },
        )

    analysis = analyze_inventory_file(
        staged["path"]
    )

    if not analysis["success"]:
        try:
            staged["path"].unlink()
        except OSError:
            pass

        return request.app.state.templates.TemplateResponse(
            "inventory_import.html",
            {
                "request": request,
                "message": analysis["message"],
                "inventory_empty": True,
                "analysis": None,
                "token": "",
                "filename": staged["filename"],
            },
        )

    return request.app.state.templates.TemplateResponse(
        "inventory_import.html",
        {
            "request": request,
            "message": "",
            "inventory_empty": True,
            "analysis": analysis,
            "token": staged["token"],
            "filename": staged["filename"],
        },
    )


@router.post("/inventory/import/confirm")
def inventory_import_confirm(
    request: Request,
    token: str = Form(...),
):
    if not _can_import(request):
        return RedirectResponse(
            "/?message=Access%20denied",
            status_code=303,
        )

    result = confirm_inventory_import(
        token
    )

    if not result["success"]:
        return RedirectResponse(
            "/inventory/import?message="
            + quote(result["message"]),
            status_code=303,
        )

    return RedirectResponse(
        "/inventory?message="
        + quote(result["message"]),
        status_code=303,
    )
