import uvicorn

from pfpu_app.config import (
    APP_HOST,
    APP_PORT,
)
from pfpu_app.main import app


def main():
    uvicorn.run(
        app,
        host=APP_HOST,
        port=APP_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()