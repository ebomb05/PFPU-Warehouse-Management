# Step 4A Architecture

The prototype's single `app.py` has been converted into a modular FastAPI application.

## Structure

- `main.py` — production/dev entry point
- `app.py` — legacy compatibility shim
- `pfpu_app/main.py` — FastAPI app factory/lifespan
- `pfpu_app/config.py` — file paths and app settings
- `pfpu_app/database.py` — database connection/schema bootstrap
- `pfpu_app/routes/` — HTTP route modules
- `pfpu_app/services/` — reusable business/service logic
- `templates/` — existing UI preserved
- `static/` — existing CSS preserved
- `data/` — existing database + Excel import source preserved
- `docs/` — project architecture/specification documents

## Step 4A rule

This milestone is a structural refactor, not a feature milestone.
Behavior is intentionally kept as close as possible to the known-working prototype.
