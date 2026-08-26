from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..services.auth_service import authenticate_user
from ..services.bootstrap_service import (
    create_initial_administrator,
    system_needs_bootstrap,
)


router = APIRouter()


@router.get(
    "/setup",
    response_class=HTMLResponse,
)
def setup_page(
    request: Request,
    message: str = "",
):
    if not system_needs_bootstrap():
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    return request.app.state.templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "message": message,
        },
    )


@router.post("/setup")
def setup_submit(
    request: Request,
    display_name: str = Form(...),
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    result = create_initial_administrator(
        username=username,
        display_name=display_name,
        email=email,
        password=password,
        confirm_password=confirm_password,
    )

    if not result["success"]:
        return RedirectResponse(
            "/setup?message="
            + quote(result["message"]),
            status_code=303,
        )

    user = result["user"]

    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["display_name"] = (
        user["display_name"]
    )

    return RedirectResponse(
        "/",
        status_code=303,
    )


@router.get(
    "/login",
    response_class=HTMLResponse,
)
def login_page(
    request: Request,
    message: str = "",
):
    if system_needs_bootstrap():
        return RedirectResponse(
            "/setup",
            status_code=303,
        )

    return request.app.state.templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "message": message,
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if system_needs_bootstrap():
        return RedirectResponse(
            "/setup",
            status_code=303,
        )

    result = authenticate_user(
        username,
        password,
    )

    if not result["success"]:
        return RedirectResponse(
            "/login?message="
            + quote(result["message"]),
            status_code=303,
        )

    user = result["user"]

    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["display_name"] = (
        user["display_name"]
    )

    return RedirectResponse(
        "/",
        status_code=303,
    )


@router.post("/logout")
def logout(
    request: Request,
):
    request.session.clear()

    return RedirectResponse(
        "/login?message="
        + quote("Logged out"),
        status_code=303,
    )