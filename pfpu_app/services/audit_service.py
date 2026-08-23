from ..database import connect


def start_location_audit(
    location_id: int,
    *,
    notes: str = "",
    user_id=None,
):
    """
    Start a physical audit for one warehouse location.

    The audit snapshots every tracked asset currently recorded
    at that location so later movement does not change what was
    expected when the audit began.
    """

    con = connect()

    location = con.execute(
        """
        SELECT
            id,
            code,
            name,
            location_type,
            active
        FROM warehouse_locations
        WHERE id = ?
        """,
        (location_id,),
    ).fetchone()

    if not location:
        con.close()

        return {
            "success": False,
            "message": "Audit location not found",
        }

    if not location["active"]:
        con.close()

        return {
            "success": False,
            "message": "Cannot audit a retired location",
        }

    existing = con.execute(
        """
        SELECT id
        FROM audit_sessions
        WHERE location_id = ?
          AND status = 'Open'
        ORDER BY id DESC
        LIMIT 1
        """,
        (location_id,),
    ).fetchone()

    if existing:
        con.close()

        return {
            "success": False,
            "message": (
                f"An open audit already exists for "
                f"{location['code']}"
            ),
            "audit_session_id": existing["id"],
        }

    cursor = con.execute(
        """
        INSERT INTO audit_sessions(
            audit_type,
            location_id,
            status,
            notes,
            started_by,
            started_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            "Location",
            location_id,
            "Open",
            notes.strip(),
            user_id,
        ),
    )

    audit_session_id = cursor.lastrowid

    expected_assets = con.execute(
        """
        SELECT
            id,
            location_id,
            status,
            assigned_job_id
        FROM assets
        WHERE location_id = ?
        ORDER BY id
        """,
        (location_id,),
    ).fetchall()

    for asset in expected_assets:
        con.execute(
            """
            INSERT INTO audit_expected_assets(
                audit_session_id,
                asset_id,
                expected_location_id,
                expected_status,
                expected_job_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                audit_session_id,
                asset["id"],
                asset["location_id"],
                asset["status"],
                asset["assigned_job_id"],
            ),
        )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"Audit started for {location['code']} "
            f"with {len(expected_assets)} expected asset(s)"
        ),
        "audit_session_id": audit_session_id,
        "location_id": location["id"],
        "location_code": location["code"],
        "location_name": location["name"],
        "expected_count": len(expected_assets),
    }

def scan_audit_asset(
    audit_session_id: int,
    barcode_value: str,
    *,
    notes: str = "",
    user_id=None,
):
    """
    Scan one asset into an open audit session.

    Results:
    - Correct: expected for this audit location
    - Duplicate: already scanned in this audit
    - Wrong Location: known asset, but recorded somewhere else
    - Unexpected: known asset, recorded at this location but not in snapshot
    - Unknown: barcode / asset ID not found
    """

    barcode_value = barcode_value.strip()

    if not barcode_value:
        return {
            "success": False,
            "message": "Asset ID / QR value is required",
        }

    con = connect()

    audit = con.execute(
        """
        SELECT
            s.*,
            wl.code AS location_code,
            wl.name AS location_name
        FROM audit_sessions s
        LEFT JOIN warehouse_locations wl
            ON wl.id = s.location_id
        WHERE s.id = ?
        """,
        (audit_session_id,),
    ).fetchone()

    if not audit:
        con.close()

        return {
            "success": False,
            "message": "Audit session not found",
        }

    if audit["status"] != "Open":
        con.close()

        return {
            "success": False,
            "message": "Audit session is not open",
        }

    asset = con.execute(
        """
        SELECT
            id,
            asset_id,
            barcode_value,
            item_master_id,
            status,
            assigned_job_id,
            location_id,
            current_location
        FROM assets
        WHERE barcode_value = ?
           OR asset_id = ?
        """,
        (
            barcode_value,
            barcode_value,
        ),
    ).fetchone()

    if not asset:
        con.execute(
            """
            INSERT INTO audit_scans(
                audit_session_id,
                barcode_value,
                asset_id,
                scanned_location_id,
                scan_result,
                notes,
                scanned_by
            )
            VALUES (?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                audit_session_id,
                barcode_value,
                audit["location_id"],
                "Unknown",
                notes.strip(),
                user_id,
            ),
        )

        con.commit()
        con.close()

        return {
            "success": False,
            "message": f"{barcode_value} is not a known asset",
            "scan_result": "Unknown",
        }

    duplicate = con.execute(
        """
        SELECT id
        FROM audit_scans
        WHERE audit_session_id = ?
          AND asset_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (
            audit_session_id,
            asset["id"],
        ),
    ).fetchone()

    if duplicate:
        con.execute(
            """
            INSERT INTO audit_scans(
                audit_session_id,
                barcode_value,
                asset_id,
                scanned_location_id,
                scan_result,
                notes,
                scanned_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_session_id,
                barcode_value,
                asset["id"],
                audit["location_id"],
                "Duplicate",
                notes.strip(),
                user_id,
            ),
        )

        con.commit()
        con.close()

        return {
            "success": False,
            "message": (
                f"{asset['asset_id']} was already scanned "
                f"in this audit"
            ),
            "scan_result": "Duplicate",
            "asset_code": asset["asset_id"],
        }

    expected = con.execute(
        """
        SELECT *
        FROM audit_expected_assets
        WHERE audit_session_id = ?
          AND asset_id = ?
        """,
        (
            audit_session_id,
            asset["id"],
        ),
    ).fetchone()

    if expected:
        scan_result = "Correct"

    elif asset["location_id"] != audit["location_id"]:
        scan_result = "Wrong Location"

    else:
        scan_result = "Unexpected"

    con.execute(
        """
        INSERT INTO audit_scans(
            audit_session_id,
            barcode_value,
            asset_id,
            scanned_location_id,
            scan_result,
            notes,
            scanned_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_session_id,
            barcode_value,
            asset["id"],
            audit["location_id"],
            scan_result,
            notes.strip(),
            user_id,
        ),
    )

    con.commit()
    con.close()

    return {
        "success": True,
        "message": (
            f"{asset['asset_id']} audit result: {scan_result}"
        ),
        "scan_result": scan_result,
        "asset_code": asset["asset_id"],
        "asset_status": asset["status"],
        "recorded_location": asset["current_location"],
        "audit_location": audit["location_code"],
    }

def get_audit_summary(audit_session_id: int):
    """
    Build a summary of an audit session.
    """

    con = connect()

    audit = con.execute(
        """
        SELECT
            s.*,
            wl.code AS location_code,
            wl.name AS location_name
        FROM audit_sessions s
        LEFT JOIN warehouse_locations wl
            ON wl.id = s.location_id
        WHERE s.id = ?
        """,
        (audit_session_id,),
    ).fetchone()

    if not audit:
        con.close()

        return {
            "success": False,
            "message": "Audit session not found",
        }

    expected_assets = con.execute(
        """
        SELECT
            ae.asset_id,
            a.asset_id AS asset_code,
            a.description,
            ae.expected_status,
            ae.expected_location_id,
            ae.expected_job_id
        FROM audit_expected_assets ae
        JOIN assets a
            ON a.id = ae.asset_id
        WHERE ae.audit_session_id = ?
        ORDER BY a.asset_id
        """,
        (audit_session_id,),
    ).fetchall()

    scanned_asset_ids = {
        row["asset_id"]
        for row in con.execute(
            """
            SELECT DISTINCT asset_id
            FROM audit_scans
            WHERE audit_session_id = ?
              AND asset_id IS NOT NULL
              AND scan_result != 'Duplicate'
            """,
            (audit_session_id,),
        ).fetchall()
    }

    missing_assets = [
        dict(asset)
        for asset in expected_assets
        if asset["asset_id"] not in scanned_asset_ids
    ]

    scan_counts = con.execute(
        """
        SELECT
            scan_result,
            COUNT(*) AS count
        FROM audit_scans
        WHERE audit_session_id = ?
        GROUP BY scan_result
        """,
        (audit_session_id,),
    ).fetchall()

    counts = {
        "Correct": 0,
        "Wrong Location": 0,
        "Unexpected": 0,
        "Duplicate": 0,
        "Unknown": 0,
    }

    for row in scan_counts:
        counts[row["scan_result"]] = row["count"]

    scans = con.execute(
        """
        SELECT
            s.id,
            s.barcode_value,
            s.scan_result,
            s.notes,
            s.scanned_at,
            a.asset_id AS asset_code,
            a.description
        FROM audit_scans s
        LEFT JOIN assets a
            ON a.id = s.asset_id
        WHERE s.audit_session_id = ?
        ORDER BY s.id
        """,
        (audit_session_id,),
    ).fetchall()

    con.close()

    return {
        "success": True,
        "audit": dict(audit),
        "expected_count": len(expected_assets),
        "correct_count": counts["Correct"],
        "missing_count": len(missing_assets),
        "wrong_location_count": counts["Wrong Location"],
        "unexpected_count": counts["Unexpected"],
        "duplicate_count": counts["Duplicate"],
        "unknown_count": counts["Unknown"],
        "missing_assets": missing_assets,
        "scans": [dict(row) for row in scans],
    }


def complete_audit(
    audit_session_id: int,
    *,
    user_id=None,
):
    """
    Complete an open audit session and return the final summary.
    """

    summary = get_audit_summary(audit_session_id)

    if not summary["success"]:
        return summary

    if summary["audit"]["status"] != "Open":
        return {
            "success": False,
            "message": "Audit session is already completed",
        }

    con = connect()

    con.execute(
        """
        UPDATE audit_sessions
        SET status = 'Completed',
            completed_by = ?,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            user_id,
            audit_session_id,
        ),
    )

    con.commit()
    con.close()

    final_summary = get_audit_summary(audit_session_id)

    final_summary["message"] = (
        f"Audit completed for "
        f"{final_summary['audit']['location_code']}"
    )

    return final_summary