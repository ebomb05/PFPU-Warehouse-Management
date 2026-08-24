from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..services.auth_service import (
    request_has_permission,
    set_user_password,
)
from ..services.user_service import (
    create_user,
    get_user,
    get_users,
    save_user_positions,
    set_user_active,
    update_user,
)

router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    message: str = "",
):
    if not request_has_permission(
        request,
        "users.manage",
    ):
        return deny_access()

    users = get_users()

    return request.app.state.templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": users,
            "message": message,
        },
    )


@router.post("/users/create")
def user_create(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    email: str = Form(""),
):
    if not request_has_permission(
        request,
        "users.manage",
    ):
        return deny_access()

    result = create_user(
        username,
        display_name,
        email,
    )

    if result["success"]:
        return RedirectResponse(
            (
                f"/users/{result['user_id']}"
                f"?message={quote(result['message'])}"
            ),
            status_code=303,
        )

    return RedirectResponse(
        "/users?message=" + quote(result["message"]),
        status_code=303,
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
def user_detail(
    request: Request,
    user_id: int,
    message: str = "",
):
    if not request_has_permission(
        request,
        "users.manage",
    ):
        return deny_access()

    result = get_user(user_id)

    if not result["success"]:
        return RedirectResponse(
            "/users?message=" + quote(result["message"]),
            status_code=303,
        )

    return request.app.state.templates.TemplateResponse(
        "user_detail.html",
        {
            "request": request,
            "user": result["user"],
            "positions": result["positions"],
            "message": message,
        },
    )


@router.post("/users/{user_id}/edit")
def user_edit(
    request: Request,
    user_id: int,
    username: str = Form(...),
    display_name: str = Form(...),
    email: str = Form(""),
):
    if not request_has_permission(
        request,
        "users.manage",
    ):
        return deny_access()

    result = update_user(
        user_id,
        username,
        display_name,
        email,
    )

    return RedirectResponse(
        (
            f"/users/{user_id}"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )


@router.post("/users/{user_id}/positions")
def user_positions_save(
    request: Request,
    user_id: int,
    position_ids: list[int] = Form(default=[]),
):
    if not request_has_permission(
        request,
        "users.manage",
    ):
        return deny_access()

    result = save_user_positions(
        user_id,
        position_ids,
    )

    return RedirectResponse(
        (
            f"/users/{user_id}"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )


@router.post("/users/{user_id}/password")
def user_password_set(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    if not request_has_permission(
        request,
        "users.manage",
    ):
        return deny_access()

    if new_password != confirm_password:
        return RedirectResponse(
            (
                f"/users/{user_id}"
                "?message="
                + quote("Passwords do not match")
            ),
            status_code=303,
        )

    result = set_user_password(
        user_id,
        new_password,
    )

    return RedirectResponse(
        (
            f"/users/{user_id}"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )


@router.post("/users/{user_id}/active")
def user_active(
    request: Request,
    user_id: int,
    active: int = Form(...),
):
    if not request_has_permission(
        request,
        "users.manage",
    ):
        return deny_access()

    result = set_user_active(
        user_id,
        bool(active),
    )

    return RedirectResponse(
        (
            f"/users/{user_id}"
            f"?message={quote(result['message'])}"
        ),
        status_code=303,
    )