from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..services.auth_service import authenticate_user

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    message: str = "",
):
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
    result = authenticate_user(
        username,
        password,
    )

    if not result["success"]:
        return RedirectResponse(
            "/login?message=" + quote(result["message"]),
            status_code=303,
        )

    user = result["user"]

    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["display_name"] = user["display_name"]

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
        "/login?message=" + quote("Logged out"),
        status_code=303,
    )