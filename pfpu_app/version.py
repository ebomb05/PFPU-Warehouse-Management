"""
PFPU Warehouse Manager application version.

This is the installed software release version.
It is separate from the database schema version.
"""

APP_VERSION = "0.1.0"


def get_version() -> str:
    return APP_VERSION


def get_version_display() -> str:
    return f"v{APP_VERSION}"