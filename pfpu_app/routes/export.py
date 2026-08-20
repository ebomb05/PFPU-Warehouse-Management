from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..services.excel_service import export_excel_file

router = APIRouter()


@router.get("/export")
def export_excel():
    output = export_excel_file()
    return FileResponse(output, filename=output.name)
