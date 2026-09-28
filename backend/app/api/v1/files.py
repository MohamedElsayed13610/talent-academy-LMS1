from __future__ import annotations

from fastapi import APIRouter, Depends, File as UploadFileParam, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_admin
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models.identity import User
from app.schemas.files import FileOut, FileUrlOut
from app.services import files as svc

router = APIRouter(prefix="/admin/files", tags=["admin:files"])


@router.post("", response_model=FileOut, status_code=201)
async def upload_file(
    file: UploadFile = UploadFileParam(...),
    purpose: str = Form(...),
    admin: User = Depends(require_admin),
    academy_id: int = Depends(current_academy_id),
    db: Session = Depends(get_db),
):
    content = await file.read()
    row = svc.save_upload(db, academy_id, purpose, content, file.filename or "", admin)
    return FileOut(id=row.id, purpose=row.purpose.value, content_type=row.content_type, size_bytes=row.size_bytes, original_name=row.original_name)


@router.get("/{file_id}/url", response_model=FileUrlOut)
def file_url(file_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = svc.signed_url(db, file_id)
    if not result:
        raise NotFoundError(code="FILE_NOT_FOUND", message="الملف غير موجود")
    url, expires_at = result
    return FileUrlOut(url=url, expires_at=expires_at.isoformat())
