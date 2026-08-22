from datetime import datetime


CURRENT_SCHEMA_VERSION = 5


def run_migrations(con):
    """
    Apply database migrations safely.

    Each migration is numbered and applied only once.
    Existing warehouse data is preserved.
    """

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )

    row = con.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()

    current_version = row["version"] if row else 0

    # ---------------------------------------------------------
    # Migration 1
    # ---------------------------------------------------------
    if current_version < 1:
        con.execute(
            """
            INSERT INTO schema_migrations(version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (
                1,
                "Step 4A baseline schema",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        current_version = 1

    # ---------------------------------------------------------
    # Migration 2
    # ---------------------------------------------------------
    if current_version < 2:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_name TEXT,
                phone TEXT,
                email TEXT,
                billing_notes TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                email TEXT,
                password_hash TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS user_positions (
                user_id INTEGER NOT NULL,
                position_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, position_id)
            );

            CREATE TABLE IF NOT EXISTS position_permissions (
                position_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                allowed INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (position_id, permission_id)
            );

            CREATE TABLE IF NOT EXISTS warehouse_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT,
                location_type TEXT NOT NULL,
                row_number INTEGER,
                section_number INTEGER,
                height_number INTEGER,
                parent_location_id INTEGER,
                photo_path TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS asset_location_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                from_location_id INTEGER,
                to_location_id INTEGER,
                action TEXT NOT NULL,
                user_id INTEGER,
                job_id INTEGER,
                notes TEXT,
                moved_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                vehicle_number TEXT,
                license_plate TEXT,
                vin TEXT,
                insurance_provider TEXT,
                insurance_policy TEXT,
                insurance_expiration TEXT,
                insurance_card_photo TEXT,
                last_maintenance_date TEXT,
                next_maintenance_date TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS job_vehicles (
                job_id INTEGER NOT NULL,
                vehicle_id INTEGER NOT NULL,
                PRIMARY KEY (job_id, vehicle_id)
            );

            CREATE TABLE IF NOT EXISTS repair_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                issue TEXT,
                notes TEXT,
                parts_needed TEXT,
                opened_by INTEGER,
                opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                asset_id INTEGER,
                exception_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'Warning',
                message TEXT NOT NULL,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'Open',
                resolved_by INTEGER,
                resolved_at TEXT,
                resolution_notes TEXT
            );
            """
        )

        default_positions = [
            ("System Administrator", "Full technical and system administration access"),
            ("General Manager", "Full operational management access"),
            ("Warehouse Manager", "Warehouse, inventory, jobs, repairs, and exception management"),
            ("Warehouse Crew", "Scanning, pulling, loading, returns, moves, and audits"),
            ("Driver / Event Crew", "Assigned jobs, vehicle loading/unloading, and issue reporting"),
            ("Repair / Maintenance", "Repair queue and equipment service workflow"),
            ("Office / Sales", "Customers, jobs, pricing, and job paperwork"),
        ]

        for name, description in default_positions:
            con.execute(
                """
                INSERT OR IGNORE INTO positions(name, description)
                VALUES (?, ?)
                """,
                (name, description),
            )

        default_permissions = [
            ("dashboard.view", "View Today's Command Center"),
            ("jobs.view", "View jobs"),
            ("jobs.create", "Create jobs"),
            ("jobs.edit", "Edit jobs"),
            ("jobs.finalize", "Finalize jobs"),
            ("customers.view", "View customers"),
            ("customers.create", "Create customers"),
            ("customers.edit", "Edit customers"),
            ("inventory.view", "View inventory"),
            ("inventory.edit", "Edit inventory"),
            ("assets.create", "Create individual assets"),
            ("assets.move", "Move assets"),
            ("scan.checkout", "Scan equipment out"),
            ("scan.checkin", "Scan equipment in"),
            ("locations.view", "View locations"),
            ("locations.manage", "Create/edit/retire locations"),
            ("repairs.view", "View repair records"),
            ("repairs.update", "Update repair records"),
            ("vehicles.view", "View vehicles"),
            ("vehicles.manage", "Manage vehicles"),
            ("audits.perform", "Perform inventory audits"),
            ("exceptions.view", "View exceptions"),
            ("exceptions.resolve", "Resolve exceptions"),
            ("users.manage", "Manage users"),
            ("positions.manage", "Manage positions and permissions"),
            ("system.settings", "Manage system settings"),
            ("system.export", "Export data"),
        ]

        for code, description in default_permissions:
            con.execute(
                """
                INSERT OR IGNORE INTO permissions(code, description)
                VALUES (?, ?)
                """,
                (code, description),
            )

        con.execute(
            """
            INSERT INTO schema_migrations(version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (
                2,
                "Core warehouse management foundation",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        current_version = 2

    # ---------------------------------------------------------
    # Migration 3
    # ---------------------------------------------------------
    if current_version < 3:
        asset_columns = [
            row["name"]
            for row in con.execute("PRAGMA table_info(assets)").fetchall()
        ]

        if "location_id" not in asset_columns:
            con.execute(
                """
                ALTER TABLE assets
                ADD COLUMN location_id INTEGER
                REFERENCES warehouse_locations(id)
                """
            )

        default_locations = [
            ("WAREHOUSE", "Warehouse", "Warehouse"),
            ("PREP", "Prep Area", "Prep"),
            ("REPAIR", "Repair", "Repair"),
            ("LOST-FOUND", "Lost / Found", "Lost/Found"),
            ("TRUCK-1", "Truck 1", "Vehicle"),
            ("TRUCK-2", "Truck 2", "Vehicle"),
            ("JOB-SITE", "Customer / Job Site", "Job Site"),
        ]

        for code, name, location_type in default_locations:
            con.execute(
                """
                INSERT OR IGNORE INTO warehouse_locations(
                    code,
                    name,
                    location_type,
                    active
                )
                VALUES (?, ?, ?, 1)
                """,
                (code, name, location_type),
            )

        text_to_code = {
            "Warehouse": "WAREHOUSE",
            "Prep Area": "PREP",
            "Repair": "REPAIR",
            "Truck 1": "TRUCK-1",
            "Truck 2": "TRUCK-2",
            "Customer / Job Site": "JOB-SITE",
        }

        for old_text, new_code in text_to_code.items():
            location = con.execute(
                """
                SELECT id
                FROM warehouse_locations
                WHERE code=?
                """,
                (new_code,),
            ).fetchone()

            if location:
                con.execute(
                    """
                    UPDATE assets
                    SET location_id=?
                    WHERE current_location=?
                      AND location_id IS NULL
                    """,
                    (location["id"], old_text),
                )

        con.execute(
            """
            INSERT INTO schema_migrations(version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (
                3,
                "Warehouse locations and asset location IDs",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

    con.commit()


    # ---------------------------------------------------------
    # Migration 4
    # Upgrade jobs for customers and future job workflow.
    # ---------------------------------------------------------
    if current_version < 4:
        job_columns = [
            row["name"]
            for row in con.execute("PRAGMA table_info(jobs)").fetchall()
        ]

        if "customer_id" not in job_columns:
            con.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN customer_id INTEGER
                REFERENCES customers(id)
                """
            )

        if "venue" not in job_columns:
            con.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN venue TEXT
                """
            )

        if "out_time" not in job_columns:
            con.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN out_time TEXT
                """
            )

        if "return_time" not in job_columns:
            con.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN return_time TEXT
                """
            )

        if "created_at" not in job_columns:
            con.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN created_at TEXT
                """
            )

        if "updated_at" not in job_columns:
            con.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN updated_at TEXT
                """
            )

        con.execute(
            """
            UPDATE jobs
            SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
            """
        )

        con.execute(
            """
            INSERT INTO schema_migrations(version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (
                4,
                "Upgrade jobs for customer relationships and workflow",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        current_version = 4

    con.commit()

    # ---------------------------------------------------------
    # Migration 5
    # Reusable Job Pack templates.
    # ---------------------------------------------------------
    if current_version < 5:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS job_packs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS job_pack_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_pack_id INTEGER NOT NULL,
                item_master_id INTEGER NOT NULL,
                qty_needed INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (job_pack_id)
                    REFERENCES job_packs(id),

                FOREIGN KEY (item_master_id)
                    REFERENCES item_master(id),

                UNIQUE(job_pack_id, item_master_id)
            );
            """
        )

        con.execute(
            """
            INSERT INTO schema_migrations(
                version,
                name,
                applied_at
            )
            VALUES (?, ?, ?)
            """,
            (
                5,
                "Add reusable Job Pack templates",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        current_version = 5

    con.commit()


def get_schema_version(con):
    try:
        row = con.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        ).fetchone()

        return row["version"] if row else 0

    except Exception:
        return 0