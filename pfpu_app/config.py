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
# CONFIGURATION FILES
# ============================================================

# Development configuration.
#
# Existing Windows environment variables always take priority.

load_dotenv(
    PROJECT_ROOT / ".env",
    override=False,
)


# Production installers can set:
#
# PFPU_CONFIG_FILE=
# C:\ProgramData\Power Factory Productions\
# Warehouse Manager\config\pfpu.env
#
# Values already supplied through the Windows environment
# remain higher priority than values in this file.

_config_file_value = os.getenv(
    "PFPU_CONFIG_FILE",
    "",
).strip()

CONFIG_FILE = (
    Path(_config_file_value).expanduser()
    if _config_file_value
    else None
)

if (
    CONFIG_FILE is not None
    and CONFIG_FILE.exists()
):
    load_dotenv(
        CONFIG_FILE,
        override=False,
    )


# ============================================================
# HELPERS
# ============================================================

def _env_text(
    name: str,
    default: str = "",
) -> str:
    return os.getenv(
        name,
        default,
    ).strip()


def _env_int(
    name: str,
    default: int,
) -> int:
    value = _env_text(
        name,
        str(default),
    )

    try:
        return int(value)

    except ValueError:
        raise RuntimeError(
            f"{name} must be an integer."
        )


def _env_bool(
    name: str,
    default: bool = False,
) -> bool:
    value = _env_text(
        name,
        "true" if default else "false",
    ).lower()

    if value in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True

    if value in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False

    raise RuntimeError(
        f"{name} must be true or false."
    )


# ============================================================
# PERSISTENT DATA ROOT
# ============================================================

_configured_data_root = _env_text(
    "PFPU_DATA_ROOT"
)

if _configured_data_root:
    DATA_ROOT = Path(
        _configured_data_root
    ).expanduser()

else:
    DATA_ROOT = PROJECT_ROOT


DATA_DIR = DATA_ROOT / "data"
BACKUP_DIR = DATA_ROOT / "backups"
BARCODE_DIR = DATA_ROOT / "barcodes"
LOG_DIR = DATA_ROOT / "logs"
CONFIG_DIR = DATA_ROOT / "config"
UPLOAD_DIR = DATA_ROOT / "uploads"

DB_PATH = (
    DATA_DIR
    / "pfpu_inventory.sqlite3"
)

EXCEL_PATH = (
    DATA_DIR
    / "PFPU_Inventory_2025_SYSTEM_COPY.xlsx"
)


# ============================================================
# APPLICATION SETTINGS
# ============================================================

APP_TITLE = _env_text(
    "PFPU_APP_TITLE",
    "Power Factory Productions Warehouse Manager",
)

APP_HOST = _env_text(
    "PFPU_APP_HOST",
    "0.0.0.0",
)

APP_PORT = _env_int(
    "PFPU_APP_PORT",
    8000,
)

PRODUCTION_MODE = _env_bool(
    "PFPU_PRODUCTION_MODE",
    False,
)


# ============================================================
# BACKUP SETTINGS
# ============================================================

BACKUP_RETENTION_COUNT = _env_int(
    "PFPU_BACKUP_RETENTION_COUNT",
    30,
)


# ============================================================
# RELEASE / HOSTING SETTINGS
# ============================================================

UPDATE_CHANNEL = _env_text(
    "PFPU_UPDATE_CHANNEL",
    "stable",
)

UPDATE_SERVER_URL = _env_text(
    "PFPU_UPDATE_SERVER_URL",
    "",
)

LICENSE_SERVER_URL = _env_text(
    "PFPU_LICENSE_SERVER_URL",
    "",
)

CLOUD_MODE = _env_bool(
    "PFPU_CLOUD_MODE",
    False,
)


# ============================================================
# SECURITY
# ============================================================

SESSION_SECRET = _env_text(
    "PFPU_SESSION_SECRET"
)

if not SESSION_SECRET:
    raise RuntimeError(
        "PFPU_SESSION_SECRET is not configured. "
        "Development installs can store it in .env. "
        "Production installs should provide it through "
        "the machine configuration or Windows environment."
    )