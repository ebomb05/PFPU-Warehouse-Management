import sqlite3

from .config import BARCODE_DIR, DATA_DIR, DB_PATH, EXCEL_PATH
from .migrations import run_migrations


def connect():
    DATA_DIR.mkdir(exist_ok=True)
    BARCODE_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_schema():
    con = connect()
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS item_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_row INTEGER,
            category TEXT,
            prefix TEXT,
            description TEXT NOT NULL,
            qty_total INTEGER DEFAULT 0,
            unit_value REAL DEFAULT 0,
            total_value REAL DEFAULT 0,
            tracking_priority TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT UNIQUE NOT NULL,
            barcode_value TEXT UNIQUE NOT NULL,
            item_master_id INTEGER,
            description TEXT,
            category TEXT,
            serial_number TEXT,
            status TEXT DEFAULT 'Available',
            current_location TEXT DEFAULT 'Warehouse',
            assigned_job_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT UNIQUE NOT NULL,
            customer TEXT NOT NULL,
            event_name TEXT,
            out_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            status TEXT DEFAULT 'Planning',
            prep_location TEXT DEFAULT 'Prep Area',
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS job_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            item_master_id INTEGER NOT NULL,
            qty_needed INTEGER NOT NULL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            item_master_id INTEGER NOT NULL,
            qty_reserved INTEGER NOT NULL,
            status TEXT DEFAULT 'Reserved'
        );

        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            location_type TEXT DEFAULT 'Warehouse'
        );

        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode_value TEXT,
            asset_id TEXT,
            action TEXT,
            from_location TEXT,
            to_location TEXT,
            job_id INTEGER,
            notes TEXT,
            scanned_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS barcode_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT,
            barcode_value TEXT,
            description TEXT,
            svg_file TEXT,
            printed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    for loc, typ in [
        ("Warehouse", "Warehouse"),
        ("Prep Area", "Prep"),
        ("Repair", "Service"),
        ("Cleaning", "Service"),
        ("Truck 1", "Truck"),
        ("Truck 2", "Truck"),
        ("Truck 3", "Truck"),
        ("Customer / Job Site", "Out"),
    ]:
        cur.execute(
            "INSERT OR IGNORE INTO locations(name, location_type) VALUES(?, ?)",
            (loc, typ),
        )

    con.commit()

    # Apply all database upgrades after the baseline tables exist.
    run_migrations(con)

    count = con.execute(
        "SELECT COUNT(*) FROM item_master"
    ).fetchone()[0]

    con.close()
    return count
