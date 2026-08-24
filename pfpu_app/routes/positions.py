from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..services.auth_service import request_has_permission
from ..services.permission_service import (
    create_position,
    get_position_permissions,
    get_positions,
    save_position_permissions,
    set_position_active,
    update_position,
)

router = APIRouter()


@router.get("/positions", response_class=HTMLResponse)
def positions_page(
    request: Request,
    message: str = "",
):
    if not request_has_permission(
        request,
        "positions.manage",
    ):
        return RedirectResponse(
            "/?message=Access denied",
            status_code=303,
        )

    positions = get_positions()

    return request.app.state.templates.TemplateResponse(
        "positions.html",
        {
            "request": request,
            "positions": positions,
            "message": message,
        },
    )


@router.get("/positions/{position_id}", response_class=HTMLResponse)
def position_detail(
    request: Request,
    position_id: int,
    message: str = "",
):
    if not request_has_permission(
        request,
        "positions.manage",
    ):
        return RedirectResponse(
            "/?message=Access denied",
            status_code=303,
        )

    result = get_position_permissions(position_id)

    if not result["success"]:
        return RedirectResponse(
            "/positions?message=" + quote(result["message"]),
            status_code=303,
        )

    return request.app.state.templates.TemplateResponse(
        "position_detail.html",
        {
            "request": request,
            "position": result["position"],
            "permissions": result["permissions"],
            "message": message,
        },
    )


@router.post("/positions/{position_id}/permissions")
def position_permissions_save(
    request: Request,
    position_id: int,
    permission_ids: list[int] = Form(default=[]),
):
    if not request_has_permission(
        request,
        "positions.manage",
    ):
        return RedirectResponse(
            "/?message=Access denied",
            status_code=303,
        )

    result = save_position_permissions(
        position_id,
        permission_ids,
    )

    return RedirectResponse(
        (
            f"/positions/{position_id}"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )


@router.post("/positions/create")
def position_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
):
    if not request_has_permission(
        request,
        "positions.manage",
    ):
        return RedirectResponse(
            "/?message=Access denied",
            status_code=303,
        )

    result = create_position(
        name,
        description,
    )

    if result["success"]:
        return RedirectResponse(
            (
                f"/positions/{result['position_id']}"
                f"?message={quote(result['message'])}"
            ),
            status_code=303,
        )

    return RedirectResponse(
        "/positions?message=" + quote(result["message"]),
        status_code=303,
    )


@router.post("/positions/{position_id}/edit")
def position_edit(
    request: Request,
    position_id: int,
    name: str = Form(...),
    description: str = Form(""),
):
    if not request_has_permission(
        request,
        "positions.manage",
    ):
        return RedirectResponse(
            "/?message=Access denied",
            status_code=303,
        )

    result = update_position(
        position_id,
        name,
        description,
    )

    return RedirectResponse(
        (
            f"/positions/{position_id}"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )


@router.post("/positions/{position_id}/active")
def position_active(
    request: Request,
    position_id: int,
    active: int = Form(...),
):
    if not request_has_permission(
        request,
        "positions.manage",
    ):
        return RedirectResponse(
            "/?message=Access denied",
            status_code=303,
        )

    result = set_position_active(
        position_id,
        bool(active),
    )

    return RedirectResponse(
        (
            f"/positions/{position_id}"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )