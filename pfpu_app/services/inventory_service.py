from typing import Optional

from ..database import connect


def next_asset_id(prefix: str) -> str:
    prefix = (prefix or "AST").upper().replace(" ", "")[:8]
    con = connect()
    row = con.execute(
        "SELECT asset_id FROM assets WHERE asset_id LIKE ? ORDER BY asset_id DESC LIMIT 1",
        (f"{prefix}-%",),
    ).fetchone()
    con.close()

    number = 1
    if row:
        try:
            number = int(row["asset_id"].split("-")[-1]) + 1
        except Exception:
            number = 1

    return f"{prefix}-{number:06d}"


def availability(
    item_master_id: int,
    out_date: str,
    return_date: str,
    exclude_job_id: Optional[int] = None,
):
    con = connect()
    total_row = con.execute(
        "SELECT qty_total FROM item_master WHERE id=?",
        (item_master_id,),
    ).fetchone()
    total = total_row[0] if total_row else 0

    query = """
        SELECT COALESCE(SUM(jl.qty_needed),0) reserved
        FROM job_lines jl
        JOIN jobs j ON j.id = jl.job_id
        WHERE jl.item_master_id=?
          AND j.status NOT IN ('Cancelled','Returned')
          AND NOT (j.return_date < ? OR j.out_date > ?)
    """
    params = [item_master_id, out_date, return_date]

    if exclude_job_id:
        query += " AND j.id != ?"
        params.append(exclude_job_id)

    reserved = con.execute(query, params).fetchone()[0] or 0
    con.close()

    return {
        "total": total,
        "reserved": reserved,
        "available": total - reserved,
    }
