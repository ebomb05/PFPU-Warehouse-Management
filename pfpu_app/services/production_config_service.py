import secrets
from pathlib import Path


DEFAULT_PRODUCTION_ROOT = Path(
    r"C:\ProgramData\Power Factory Productions\Warehouse Manager"
)


def ensure_production_directories(
    data_root: Path = DEFAULT_PRODUCTION_ROOT,
) -> dict:
    """
    Create the persistent PFPU production directory structure.
    """

    data_root = Path(data_root)

    directories = {
        "root": data_root,
        "data": data_root / "data",
        "backups": data_root / "backups",
        "barcodes": data_root / "barcodes",
        "logs": data_root / "logs",
        "config": data_root / "config",
        "uploads": data_root / "uploads",
    }

    try:
        for path in directories.values():
            path.mkdir(
                parents=True,
                exist_ok=True,
            )

    except OSError as exc:
        return {
            "success": False,
            "message": (
                "Unable to create production directories: "
                f"{exc}"
            ),
            "directories": directories,
        }

    return {
        "success": True,
        "message": (
            "PFPU production directories are ready."
        ),
        "directories": directories,
    }


def generate_session_secret() -> str:
    """
    Generate a strong random session secret.
    """

    return secrets.token_urlsafe(48)


def write_production_env(
    data_root: Path = DEFAULT_PRODUCTION_ROOT,
    *,
    app_port: int = 8000,
    backup_retention_count: int = 30,
) -> dict:
    """
    Create the production PFPU environment file.

    This file is stored outside the application directory so
    upgrades can replace application files without replacing
    the machine configuration.
    """

    directory_result = ensure_production_directories(
        data_root
    )

    if not directory_result["success"]:
        return directory_result

    config_dir = (
        directory_result["directories"]["config"]
    )

    env_path = config_dir / "pfpu.env"

    if env_path.exists():
        return {
            "success": True,
            "created": False,
            "message": (
                "Production configuration already exists."
            ),
            "path": env_path,
        }

    session_secret = generate_session_secret()

    contents = "\n".join(
        [
            "# Power Factory Productions Warehouse Manager",
            "# Machine production configuration",
            "",
            f"PFPU_DATA_ROOT={data_root}",
            "PFPU_PRODUCTION_MODE=true",
            "PFPU_APP_HOST=0.0.0.0",
            f"PFPU_APP_PORT={app_port}",
            (
                "PFPU_BACKUP_RETENTION_COUNT="
                f"{backup_retention_count}"
            ),
            "PFPU_UPDATE_CHANNEL=stable",
            "PFPU_CLOUD_MODE=false",
            f"PFPU_SESSION_SECRET={session_secret}",
            "",
        ]
    )

    try:
        env_path.write_text(
            contents,
            encoding="utf-8",
        )

    except OSError as exc:
        return {
            "success": False,
            "message": (
                "Unable to write production configuration: "
                f"{exc}"
            ),
            "path": None,
        }

    return {
        "success": True,
        "created": True,
        "message": (
            "Production configuration created."
        ),
        "path": env_path,
    }