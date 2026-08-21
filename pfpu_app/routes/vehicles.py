from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect

router = APIRouter()


@router.get("/vehicles", response_class=HTMLResponse)
def vehicles_page(request: Request, q: str = "", message: str = ""):
    con = connect()

    if q:
        vehicles = con.execute(
            """
            SELECT *
            FROM vehicles
            WHERE name LIKE ?
               OR vehicle_number LIKE ?
               OR license_plate LIKE ?
               OR vin LIKE ?
            ORDER BY active DESC, name
            """,
            (
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
            ),
        ).fetchall()
    else:
        vehicles = con.execute(
            """
            SELECT *
            FROM vehicles
            ORDER BY active DESC, name
            """
        ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "vehicles.html",
        {
            "request": request,
            "vehicles": vehicles,
            "q": q,
            "message": message,
        },
    )


@router.post("/vehicles/create")
def create_vehicle(
    name: str = Form(...),
    vehicle_number: str = Form(""),
    license_plate: str = Form(""),
    vin: str = Form(""),
    insurance_provider: str = Form(""),
    insurance_policy: str = Form(""),
    insurance_expiration: str = Form(""),
    last_maintenance_date: str = Form(""),
    next_maintenance_date: str = Form(""),
    notes: str = Form(""),
):
    name = name.strip()

    if not name:
        return RedirectResponse(
            "/vehicles?message=Vehicle name is required",
            status_code=303,
        )

    con = connect()

    con.execute(
        """
        INSERT INTO vehicles(
            name,
            vehicle_number,
            license_plate,
            vin,
            insurance_provider,
            insurance_policy,
            insurance_expiration,
            last_maintenance_date,
            next_maintenance_date,
            notes,
            active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            name,
            vehicle_number.strip(),
            license_plate.strip(),
            vin.strip(),
            insurance_provider.strip(),
            insurance_policy.strip(),
            insurance_expiration.strip(),
            last_maintenance_date.strip(),
            next_maintenance_date.strip(),
            notes.strip(),
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/vehicles?message=Vehicle {name} created",
        status_code=303,
    )


@router.get("/vehicles/{vehicle_id}", response_class=HTMLResponse)
def vehicle_detail(request: Request, vehicle_id: int, message: str = ""):
    con = connect()

    vehicle = con.execute(
        """
        SELECT *
        FROM vehicles
        WHERE id = ?
        """,
        (vehicle_id,),
    ).fetchone()

    if not vehicle:
        con.close()

        return RedirectResponse(
            "/vehicles?message=Vehicle not found",
            status_code=303,
        )

    con.close()

    return request.app.state.templates.TemplateResponse(
        "vehicle_detail.html",
        {
            "request": request,
            "vehicle": vehicle,
            "message": message,
        },
    )


@router.post("/vehicles/{vehicle_id}/update")
def update_vehicle(
    vehicle_id: int,
    name: str = Form(...),
    vehicle_number: str = Form(""),
    license_plate: str = Form(""),
    vin: str = Form(""),
    insurance_provider: str = Form(""),
    insurance_policy: str = Form(""),
    insurance_expiration: str = Form(""),
    last_maintenance_date: str = Form(""),
    next_maintenance_date: str = Form(""),
    notes: str = Form(""),
):
    con = connect()

    vehicle = con.execute(
        """
        SELECT *
        FROM vehicles
        WHERE id = ?
        """,
        (vehicle_id,),
    ).fetchone()

    if not vehicle:
        con.close()

        return RedirectResponse(
            "/vehicles?message=Vehicle not found",
            status_code=303,
        )

    con.execute(
        """
        UPDATE vehicles
        SET name = ?,
            vehicle_number = ?,
            license_plate = ?,
            vin = ?,
            insurance_provider = ?,
            insurance_policy = ?,
            insurance_expiration = ?,
            last_maintenance_date = ?,
            next_maintenance_date = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            name.strip(),
            vehicle_number.strip(),
            license_plate.strip(),
            vin.strip(),
            insurance_provider.strip(),
            insurance_policy.strip(),
            insurance_expiration.strip(),
            last_maintenance_date.strip(),
            next_maintenance_date.strip(),
            notes.strip(),
            vehicle_id,
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/vehicles/{vehicle_id}?message=Vehicle updated successfully",
        status_code=303,
    )


@router.post("/vehicles/{vehicle_id}/toggle-active")
def toggle_vehicle_active(vehicle_id: int):
    con = connect()

    vehicle = con.execute(
        """
        SELECT *
        FROM vehicles
        WHERE id = ?
        """,
        (vehicle_id,),
    ).fetchone()

    if not vehicle:
        con.close()

        return RedirectResponse(
            "/vehicles?message=Vehicle not found",
            status_code=303,
        )

    new_status = 0 if vehicle["active"] else 1

    con.execute(
        """
        UPDATE vehicles
        SET active = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_status, vehicle_id),
    )

    con.commit()
    con.close()

    message = (
        "Vehicle reactivated successfully"
        if new_status
        else "Vehicle retired successfully"
    )

    return RedirectResponse(
        f"/vehicles/{vehicle_id}?message={message}",
        status_code=303,
    )