from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class FileOut(BaseModel):
    id: str
    purpose: str
    content_type: str
    size_bytes: int
    original_name: str


class FileUrlOut(BaseModel):
    url: str
    expires_at: str


FilePurposeL = Literal["question_image", "material_pdf", "course_cover", "logo"]
