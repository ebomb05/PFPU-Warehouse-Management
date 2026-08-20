"""
Legacy compatibility entry point.

The application was restructured in Step 4A.
Existing commands that use `uvicorn app:app` will still work.
"""
from pfpu_app.main import app
