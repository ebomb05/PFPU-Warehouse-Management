from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BARCODE_DIR = PROJECT_ROOT / "barcodes"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

DB_PATH = DATA_DIR / "pfpu_inventory.sqlite3"
EXCEL_PATH = DATA_DIR / "PFPU_Inventory_2025_SYSTEM_COPY.xlsx"

APP_TITLE = "Power Factory Productions Warehouse Manager"
APP_HOST = "0.0.0.0"
APP_PORT = 8000
