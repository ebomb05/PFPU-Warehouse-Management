from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import connect
from ..services.auth_service import request_has_permission

router = APIRouter()


def deny_access():
    return RedirectResponse(
        "/?message=Access denied",
        status_code=303,
    )


@router.get("/customers", response_class=HTMLResponse)
def customers_page(
    request: Request,
    q: str = "",
    message: str = "",
):
    if not request_has_permission(
        request,
        "customers.view",
    ):
        return deny_access()

    con = connect()

    if q:
        customers = con.execute(
            """
            SELECT *
            FROM customers
            WHERE name LIKE ?
               OR contact_name LIKE ?
               OR phone LIKE ?
               OR email LIKE ?
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
        customers = con.execute(
            """
            SELECT *
            FROM customers
            ORDER BY active DESC, name
            """
        ).fetchall()

    con.close()

    return request.app.state.templates.TemplateResponse(
        "customers.html",
        {
            "request": request,
            "customers": customers,
            "q": q,
            "message": message,
        },
    )


@router.post("/customers/create")
def create_customer(
    request: Request,
    name: str = Form(...),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    billing_notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "customers.create",
    ):
        return deny_access()

    name = name.strip()

    if not name:
        return RedirectResponse(
            "/customers?message=Customer name is required",
            status_code=303,
        )

    con = connect()

    existing = con.execute(
        """
        SELECT id
        FROM customers
        WHERE LOWER(name) = LOWER(?)
        """,
        (name,),
    ).fetchone()

    if existing:
        con.close()

        return RedirectResponse(
            "/customers?message=Customer already exists",
            status_code=303,
        )

    con.execute(
        """
        INSERT INTO customers(
            name,
            contact_name,
            phone,
            email,
            billing_notes,
            active
        )
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            name,
            contact_name.strip(),
            phone.strip(),
            email.strip(),
            billing_notes.strip(),
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        f"/customers?message=Customer {name} created",
        status_code=303,
    )


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail(
    request: Request,
    customer_id: int,
    message: str = "",
):
    if not request_has_permission(
        request,
        "customers.view",
    ):
        return deny_access()

    con = connect()

    customer = con.execute(
        """
        SELECT *
        FROM customers
        WHERE id = ?
        """,
        (customer_id,),
    ).fetchone()

    if not customer:
        con.close()

        return RedirectResponse(
            "/customers?message=Customer not found",
            status_code=303,
        )

    con.close()

    return request.app.state.templates.TemplateResponse(
        "customer_detail.html",
        {
            "request": request,
            "customer": customer,
            "message": message,
        },
    )


@router.post("/customers/{customer_id}/update")
def update_customer(
    request: Request,
    customer_id: int,
    name: str = Form(...),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    billing_notes: str = Form(""),
):
    if not request_has_permission(
        request,
        "customers.edit",
    ):
        return deny_access()

    con = connect()

    customer = con.execute(
        """
        SELECT *
        FROM customers
        WHERE id = ?
        """,
        (customer_id,),
    ).fetchone()

    if not customer:
        con.close()

        return RedirectResponse(
            "/customers?message=Customer not found",
            status_code=303,
        )

    con.execute(
        """
        UPDATE customers
        SET name = ?,
            contact_name = ?,
            phone = ?,
            email = ?,
            billing_notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            name.strip(),
            contact_name.strip(),
            phone.strip(),
            email.strip(),
            billing_notes.strip(),
            customer_id,
        ),
    )

    con.commit()
    con.close()

    return RedirectResponse(
        (
            f"/customers/{customer_id}"
            "?message=Customer updated successfully"
        ),
        status_code=303,
    )


@router.post("/customers/{customer_id}/toggle-active")
def toggle_customer_active(
    request: Request,
    customer_id: int,
):
    if not request_has_permission(
        request,
        "customers.edit",
    ):
        return deny_access()

    con = connect()

    customer = con.execute(
        """
        SELECT *
        FROM customers
        WHERE id = ?
        """,
        (customer_id,),
    ).fetchone()

    if not customer:
        con.close()

        return RedirectResponse(
            "/customers?message=Customer not found",
            status_code=303,
        )

    new_status = 0 if customer["active"] else 1

    con.execute(
        """
        UPDATE customers
        SET active = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            new_status,
            customer_id,
        ),
    )

    con.commit()
    con.close()

    message = (
        "Customer reactivated successfully"
        if new_status
        else "Customer retired successfully"
    )

    return RedirectResponse(
        f"/customers/{customer_id}?message={message}",
        status_code=303,
    )