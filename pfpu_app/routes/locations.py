import re

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.auth_service import request_has_permission

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

    return request.app.state.templates.TemplateResponse(
        "location_detail.html",
        {
            "request": request,
            "location": location,
            "assets": assets,
            "asset_count": len(assets),
            "message": message,
        },
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