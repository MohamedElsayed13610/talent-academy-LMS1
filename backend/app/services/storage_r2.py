"""Cloudflare R2 via the S3 API (spec §1, §12). Private bucket only — the frontend never talks to
R2 directly; every URL a client sees is a short-lived presigned one generated here.

In local dev, docker-compose.dev.yml points R2_ENDPOINT_URL at the bundled MinIO service, which
speaks the same S3 API, so this code is identical in dev and production.
"""

from __future__ import annotations

import uuid

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.errors import ValidationAppError

# Magic-byte sniffing (spec §9: "Validate MIME type ... file type/size checks") — the declared
# Content-Type header is never trusted on its own, since a client can set it to anything.
_SIGNATURES: dict[bytes, str] = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"RIFF": "image/webp",  # narrowed below (RIFF....WEBP)
}

ALLOWED_BY_PURPOSE: dict[str, tuple[set[str], int]] = {
    # purpose -> (allowed content types, max size in bytes)
    "material_pdf": ({"application/pdf"}, 20 * 1024 * 1024),
    "course_cover": ({"image/png", "image/jpeg", "image/webp"}, 2 * 1024 * 1024),
    "logo": ({"image/png", "image/jpeg", "image/webp"}, 2 * 1024 * 1024),
    "question_image": ({"image/png", "image/jpeg", "image/webp"}, 800_000),
    "passage_image": ({"image/png", "image/jpeg", "image/webp"}, 2 * 1024 * 1024),
}


def sniff_content_type(content: bytes) -> str | None:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _client(endpoint_url: str | None = None):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name=settings.r2_region,
        # Path-style URLs work with both Cloudflare R2 and local MinIO and avoid generating a
        # browser-unresolvable host such as talent-files.localhost in development.
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def validate_upload(purpose: str, content: bytes) -> str:
    """Returns the sniffed content type, or raises a 422 if it fails the purpose's allow-list."""
    allowed, max_bytes = ALLOWED_BY_PURPOSE.get(purpose, (set(), 0))
    if not content:
        raise ValidationAppError(code="FILE_EMPTY", message="الملف فارغ")
    if len(content) > max_bytes:
        raise ValidationAppError(code="FILE_TOO_LARGE", message=f"حجم الملف أكبر من الحد المسموح ({max_bytes // 1024} كيلوبايت)")
    sniffed = sniff_content_type(content)
    if not sniffed or sniffed not in allowed:
        raise ValidationAppError(code="FILE_TYPE_NOT_ALLOWED", message="نوع الملف غير مسموح")
    return sniffed


def upload_bytes(bucket: str, key: str, content: bytes, content_type: str) -> None:
    _client().put_object(Bucket=bucket, Key=key, Body=content, ContentType=content_type)


def delete_object(bucket: str, key: str) -> bool:
    """Returns True on success (including "already gone") so the cleanup job can retire the row."""
    try:
        _client().delete_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def presigned_get_url(bucket: str, key: str, expires_in: int = 300) -> str:
    public_endpoint = settings.r2_public_endpoint_url or settings.r2_endpoint_url
    return _client(public_endpoint).generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )


def new_storage_key(academy_id: int, purpose: str, ext: str) -> str:
    return f"{purpose}/{academy_id}/{uuid.uuid4().hex}.{ext}"


_EXT_BY_TYPE = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def ext_for_content_type(content_type: str) -> str:
    return _EXT_BY_TYPE.get(content_type, "bin")


def ensure_bucket(bucket: str) -> None:
    """Creates the bucket if missing — only needed for local MinIO; R2 buckets are created once by
    hand in the Cloudflare dashboard in production."""
    client = _client()
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)
