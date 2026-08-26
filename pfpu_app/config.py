import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# APPLICATION PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEMPLATE_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

# Development installations keep .env in the project root.
# A future production installer can provide configuration
# through the Windows environment instead.
load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# PERSISTENT DATA ROOT
# ============================================================

# Development default:
#
#     C:\PFPU_Warehouse_Manager_4A
#
# Production installations can override this by setting:
#
#     PFPU_DATA_ROOT
#
# Example:
#
#     C:\ProgramData\Power Factory Productions\
#         Warehouse Manager
#
# This keeps customer data separate from replaceable
# application files during upgrades and reinstalls.

_configured_data_root = os.getenv(
    "PFPU_DATA_ROOT",
    "",
).strip()

if _configured_data_root:
    DATA_ROOT = Path(_configured_data_root).expanduser()
else:
    DATA_ROOT = PROJECT_ROOT


DATA_DIR = DATA_ROOT / "data"
BACKUP_DIR = DATA_ROOT / "backups"
BARCODE_DIR = DATA_ROOT / "barcodes"
LOG_DIR = DATA_ROOT / "logs"

DB_PATH = DATA_DIR / "pfpu_inventory.sqlite3"

EXCEL_PATH = (
    DATA_DIR
    / "PFPU_Inventory_2025_SYSTEM_COPY.xlsx"
)


# ============================================================
# BACKUP SETTINGS
# ============================================================

BACKUP_RETENTION_COUNT = 30


# ============================================================
# APPLICATION SETTINGS
# ============================================================

APP_TITLE = (
    "Power Factory Productions Warehouse Manager"
)

APP_HOST = "0.0.0.0"
APP_PORT = 8000


# ============================================================
# SECURITY
# ============================================================

SESSION_SECRET = os.getenv(
    "PFPU_SESSION_SECRET",
    "",
)

if not SESSION_SECRET:
    raise RuntimeError(
        "PFPU_SESSION_SECRET is not configured. "
        "Create a .env file containing "
        "PFPU_SESSION_SECRET."
    )