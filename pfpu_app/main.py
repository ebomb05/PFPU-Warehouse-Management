from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import APP_TITLE, BARCODE_DIR, EXCEL_PATH, STATIC_DIR, TEMPLATE_DIR
from .database import initialize_schema
from .routes import (
    assets,
    barcodes,
    customers,
    dashboard,
    export,
    inventory,
    jobs,
    locations,
    scan,
    vehicles,
)
from .services.excel_service import import_excel


@asynccontextmanager
async def lifespan(app: FastAPI):
    item_count = initialize_schema()
    if item_count == 0 and EXCEL_PATH.exists():
        import_excel(EXCEL_PATH)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE, lifespan=lifespan)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/barcodes", StaticFiles(directory=BARCODE_DIR), name="barcodes")
    app.state.templates = Jinja2Templates(directory=TEMPLATE_DIR)

    app.include_router(dashboard.router)
    app.include_router(inventory.router)
    app.include_router(customers.router)
    app.include_router(vehicles.router)
    app.include_router(assets.router)
    app.include_router(locations.router)
    app.include_router(jobs.router)
    app.include_router(scan.router)
    app.include_router(barcodes.router)
    app.include_router(export.router)

    return app


app = create_app()
