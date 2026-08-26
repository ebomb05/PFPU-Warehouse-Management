from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from .services.backup_service import create_database_backup

from .config import (
    APP_TITLE,
    BARCODE_DIR,
    EXCEL_PATH,
    SESSION_SECRET,
    STATIC_DIR,
    TEMPLATE_DIR,
)
from .database import connect, initialize_schema
from .routes import (
    assets,
    audits,
    auth,
    barcodes,
    customers,
    dashboard,
    export,
    inventory,
    job_packs,
    jobs,
    locations,
    lost_found,
    positions,
    repairs,
    scan,
    system,
    users,
    vehicles,
)
from .services.auth_service import get_user_permissions
from .services.excel_service import import_excel


@asynccontextmanager
async def lifespan(app: FastAPI):
    item_count = initialize_schema()

    if item_count == 0 and EXCEL_PATH.exists():
        import_excel(EXCEL_PATH)

    backup_result = create_database_backup(
        "startup"
    )

    if backup_result["success"]:
        print(
            "[PFPU Backup] "
            + backup_result["message"]
        )
    else:
        print(
            "[PFPU Backup WARNING] "
            + backup_result["message"]
        )

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_TITLE,
        lifespan=lifespan,
    )

    # ---------------------------------------------------------
    # LOGIN / SESSION VALIDATION
    # ---------------------------------------------------------

    @app.middleware("http")
    async def require_login(
        request: Request,
        call_next,
    ):
        path = request.url.path

        public_paths = {
            "/login",
        }

        public_prefixes = (
            "/static/",
            "/barcodes/",
        )

        user_id = request.session.get("user_id")

        request.state.user_id = None
        request.state.permissions = set()

        request.state.can = (
            lambda permission_code:
            permission_code in request.state.permissions
)

        # Validate an existing login session.
        if user_id:
            con = connect()

            user = con.execute(
                """
                SELECT
                    id,
                    username,
                    display_name,
                    active
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

            con.close()

            if not user or not user["active"]:
                request.session.clear()

                return RedirectResponse(
                    "/login?message=Account%20is%20inactive",
                    status_code=303,
                )

            request.state.user_id = user["id"]

            request.state.permissions = get_user_permissions(
                user["id"]
            )

        # Require authentication everywhere except public paths.
        if (
            path not in public_paths
            and not path.startswith(public_prefixes)
            and not request.state.user_id
        ):
            return RedirectResponse(
                "/login",
                status_code=303,
            )

        response = await call_next(request)

        return response

    # ---------------------------------------------------------
    # SESSION SUPPORT
    #
    # Registered AFTER require_login intentionally.
    # Starlette wraps middleware in reverse registration order,
    # so request.session is available inside require_login.
    # ---------------------------------------------------------

    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        same_site="lax",
        https_only=False,
    )

    # ---------------------------------------------------------
    # STATIC FILES / TEMPLATES
    # ---------------------------------------------------------

    app.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR),
        name="static",
    )

    app.mount(
        "/barcodes",
        StaticFiles(directory=BARCODE_DIR),
        name="barcodes",
    )

    app.state.templates = Jinja2Templates(
        directory=TEMPLATE_DIR
    )

    # ---------------------------------------------------------
    # ROUTES
    # ---------------------------------------------------------

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(positions.router)
    app.include_router(users.router)
    app.include_router(inventory.router)
    app.include_router(customers.router)
    app.include_router(vehicles.router)
    app.include_router(assets.router)
    app.include_router(locations.router)
    app.include_router(lost_found.router)
    app.include_router(job_packs.router)
    app.include_router(jobs.router)
    app.include_router(repairs.router)
    app.include_router(scan.router)
    app.include_router(barcodes.router)
    app.include_router(export.router)
    app.include_router(audits.router)
    app.include_router(system.router)

    return app


app = create_app()