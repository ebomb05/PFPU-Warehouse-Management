import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = PROJECT_ROOT / "backups"
BARCODE_DIR = PROJECT_ROOT / "barcodes"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

BACKUP_RETENTION_COUNT = 30

DB_PATH = DATA_DIR / "pfpu_inventory.sqlite3"
EXCEL_PATH = DATA_DIR / "PFPU_Inventory_2025_SYSTEM_COPY.xlsx"

APP_TITLE = "Power Factory Productions Warehouse Manager"
APP_HOST = "0.0.0.0"
APP_PORT = 8000

SESSION_SECRET = os.getenv(
    "PFPU_SESSION_SECRET",
    "",
)

if not SESSION_SECRET:
    raise RuntimeError(
        "PFPU_SESSION_SECRET is not configured. "
        "Create a .env file containing PFPU_SESSION_SECRET."
    )