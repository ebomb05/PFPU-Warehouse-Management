import re
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from ..config import BARCODE_DIR
from ..database import connect
from ..services.asset_service import move_asset
from ..services.auth_service import request_has_permission
from ..services.barcode_service import make_location_qr_svg

router = APIRouter()

SHELF_PATTERN = re.compile(r"^\d{3}\.\d{3}\.\d{3}$")


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/locations", response_class=HTMLResponse)
def locations_page(
    request: Request,
    message: str = "",
):
    if not request_has_permission(
        request,
        "locations.view",
    ):
        return deny_access()

    con = connect()

    rows = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        ORDER BY
            CASE
                WHEN location_type = 'Shelf' THEN 0
                ELSE 1
            END,
            code
        """
    ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "locations.html",
        {
            "request": request,
            "locations": rows,
            "message": message,
        },
    )


@router.post("/locations/create")
def create_location(
    request: Request,
    code: str = Form(...),
    name: str = Form(""),
    location_type: str = Form("Shelf"),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "locations.manage",
    ):
        return deny_access()

    code = code.strip().upper()
    name = name.strip()
    notes = notes.strip()

    row_number = None
    section_number = None
    height_number = None

    if location_type == "Shelf":
        if not SHELF_PATTERN.match(code):
            return RedirectResponse(
                (
                    "/locations?message="
                    "Shelf locations must use format 001.002.003"
                ),
                status_code=303,
            )

        row_text, section_text, height_text = code.split(".")

        row_number = int(row_text)
        section_number = int(section_text)
        height_number = int(height_text)

        if not name:
            name = f"Shelf {code}"

    elif not code:
        return RedirectResponse(
            "/locations?message=Location code is required",
            status_code=303,
        )

    con = connect()

    existing = con.execute(
        """
        SELECT id
        FROM warehouse_locations
        WHERE code = ?
        """,
        (code,),
    ).fetchone()

    if existing:
        con.close()

        return RedirectResponse(
            "/locations?message=That location already exists",
            status_code=303,
        )

    con.execute(
        """
        INSERT INTO warehouse_locations(
            code,
            name,
            location_type,
            row_number,
            section_number,
            height_number,
            notes,
            active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            code,
            name,
            location_type,
            row_number,
            section_number,
            height_number,
            notes,
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/locations?message=Location {code} created",
        status_code=303,
    )


@router.get("/locations/{location_id}", response_class=HTMLResponse)
def location_detail(
    request: Request,
    location_id: int,
    message: str = "",
):
    if not request_has_permission(
        request,
        "locations.view",
    ):
        return deny_access()

    con = connect()

    location = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE id = ?
        """,
        (location_id,),
    ).fetchone()

    if not location:
        con.close()

        return RedirectResponse(
            "/locations?message=Location not found",
            status_code=303,
        )

    assets = con.execute(
        """
        SELECT
            id,
            asset_id,
            description,
            status
        FROM assets
        WHERE location_id = ?
        ORDER BY description, asset_id
        """,
        (location_id,),
    ).fetchall()

    con.close()

    location_qr_filename = make_location_qr_svg(
        location["code"],
        location["name"] or "",
    )

    return request.app.state.templates.TemplateResponse(
        "location_detail.html",
        {
            "request": request,
            "location": location,
            "assets": assets,
            "asset_count": len(assets),
            "location_qr_filename": location_qr_filename,
            "message": message,
        },
    )


@router.get("/location-assignment", response_class=HTMLResponse)
def rapid_location_assignment(
    request: Request,
    message: str = "",
    result: str = "",
):
    if not request_has_permission(
        request,
        "assets.move",
    ):
        return deny_access()

    selected_location = None

    selected_location_id = request.session.get(
        "rapid_location_id"
    )

    if selected_location_id:
        con = connect()

        selected_location = con.execute(
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
            (selected_location_id,),
        ).fetchone()

        con.close()

        if (
            not selected_location
            or not selected_location["active"]
        ):
            request.session.pop(
                "rapid_location_id",
                None,
            )
            selected_location = None

    return request.app.state.templates.TemplateResponse(
        "location_assign.html",
        {
            "request": request,
            "selected_location": selected_location,
            "message": message,
            "result": result,
        },
    )


@router.post("/location-assignment")
def rapid_location_assignment_scan(
    request: Request,
    barcode_value: str = Form(...),
):
    if not request_has_permission(
        request,
        "assets.move",
    ):
        return deny_access()

    barcode_value = barcode_value.strip()

    if not barcode_value:
        return RedirectResponse(
            "/location-assignment?result=error&message="
            + quote("Scan a Location QR or Asset QR."),
            status_code=303,
        )

    location_prefix = "PFPU:LOCATION:"

    # ---------------------------------------------------------
    # LOCATION QR
    # ---------------------------------------------------------

    if barcode_value.upper().startswith(location_prefix):

        location_code = barcode_value[
            len(location_prefix):
        ].strip()

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
            WHERE UPPER(code) = UPPER(?)
            """,
            (location_code,),
        ).fetchone()

        con.close()

        if not location:
            return RedirectResponse(
                "/location-assignment?result=error&message="
                + quote(
                    f"Location {location_code} was not found."
                ),
                status_code=303,
            )

        if not location["active"]:
            return RedirectResponse(
                "/location-assignment?result=error&message="
                + quote(
                    f"Location {location['code']} is retired."
                ),
                status_code=303,
            )

        request.session["rapid_location_id"] = location["id"]

        return RedirectResponse(
            "/location-assignment?result=success&message="
            + quote(
                f"Target location set to {location['code']}."
            ),
            status_code=303,
        )

    # ---------------------------------------------------------
    # ASSET QR / ASSET ID
    # ---------------------------------------------------------

    selected_location_id = request.session.get(
        "rapid_location_id"
    )

    if not selected_location_id:
        return RedirectResponse(
            "/location-assignment?result=error&message="
            + quote(
                "Scan a Location QR before scanning assets."
            ),
            status_code=303,
        )

    con = connect()

    asset = con.execute(
        """
        SELECT
            id,
            asset_id
        FROM assets
        WHERE barcode_value = ?
           OR asset_id = ?
        """,
        (
            barcode_value,
            barcode_value,
        ),
    ).fetchone()

    con.close()

    if not asset:
        return RedirectResponse(
            "/location-assignment?result=error&message="
            + quote(
                f"Asset / QR not found: {barcode_value}"
            ),
            status_code=303,
        )

    move_result = move_asset(
        asset_id=asset["id"],
        to_location_id=selected_location_id,
        action="Rapid Location Assignment",
        user_id=request.state.user_id,
    )

    result_type = (
        "success"
        if move_result["success"]
        else "error"
    )

    return RedirectResponse(
        f"/location-assignment?result={result_type}&message="
        + quote(move_result["message"]),
        status_code=303,
    )

@router.get("/locations/{location_id}/qr/print", response_class=HTMLResponse)
def location_qr_print(
    request: Request,
    location_id: int,
):
    if not request_has_permission(
        request,
        "locations.view",
    ):
        return deny_access()

    con = connect()

    location = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE id = ?
        """,
        (location_id,),
    ).fetchone()

    con.close()

    if not location:
        return RedirectResponse(
            "/locations?message=Location not found",
            status_code=303,
        )

    make_location_qr_svg(
        location["code"],
        location["name"] or "",
    )

    return request.app.state.templates.TemplateResponse(
        "location_label_print.html",
        {
            "request": request,
            "location": location,
        },
    )

@router.get("/locations/{location_id}/qr")
def location_qr(
    request: Request,
    location_id: int,
):
    if not request_has_permission(
        request,
        "locations.view",
    ):
        return deny_access()

    con = connect()

    location = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE id = ?
        """,
        (location_id,),
    ).fetchone()

    con.close()

    if not location:
        return RedirectResponse(
            "/locations?message=Location not found",
            status_code=303,
        )

    filename = make_location_qr_svg(
        location["code"],
        location["name"] or "",
    )

    qr_path = BARCODE_DIR / filename

    return FileResponse(
        qr_path,
        media_type="image/svg+xml",
        filename=filename,
    )

@router.post("/locations/{location_id}/update")
def update_location(
    request: Request,
    location_id: int,
    name: str = Form(""),
    location_type: str = Form(...),
    notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "locations.manage",
    ):
        return deny_access()

    con = connect()

    location = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE id = ?
        """,
        (location_id,),
    ).fetchone()

    if not location:
        con.close()

        return RedirectResponse(
            "/locations?message=Location not found",
            status_code=303,
        )

    con.execute(
        """
        UPDATE warehouse_locations
        SET name = ?,
            location_type = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            name.strip(),
            location_type,
            notes.strip(),
            location_id,
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        (
            f"/locations/{location_id}"
            "?message=Location updated successfully"
        ),
        status_code=303,
    )


@router.post("/locations/{location_id}/toggle-active")
def toggle_location_active(
    request: Request,
    location_id: int,
):
    if not request_has_permission(
        request,
        "locations.manage",
    ):
        return deny_access()

    con = connect()

    location = con.execute(
        """
        SELECT *
        FROM warehouse_locations
        WHERE id = ?
        """,
        (location_id,),
    ).fetchone()

    if not location:
        con.close()

        return RedirectResponse(
            "/locations?message=Location not found",
            status_code=303,
        )

    # If active, we're attempting to retire it.
    if location["active"]:
        asset_count = con.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE location_id = ?
            """,
            (location_id,),
        ).fetchone()[0]

        if asset_count > 0:
            con.close()

            return RedirectResponse(
                (
                    f"/locations/{location_id}"
                    f"?message=Cannot retire location. "
                    f"{asset_count} asset(s) must be moved first."
                ),
                status_code=303,
            )

        new_status = 0
        message = "Location retired successfully"

    else:
        new_status = 1
        message = "Location reactivated successfully"

    con.execute(
        """
        UPDATE warehouse_locations
        SET active = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            new_status,
            location_id,
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/locations/{location_id}?message={message}",
        status_code=303,
    )
