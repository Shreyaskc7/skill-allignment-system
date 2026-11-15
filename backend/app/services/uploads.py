"""Validated storage for profile images and resumes.

Files are identified by their content (magic bytes), never by the client's file
name or Content-Type, renamed to a random key, and stored outside the web root.
The database stores only the key; files are served through authenticated endpoints.
"""

import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Kind:
    folder: str
    max_bytes: int
    types: dict  # magic-bytes check -> (extension, media type)
    label: str


def _is_webp(b: bytes) -> bool:
    return b[:4] == b"RIFF" and b[8:12] == b"WEBP"


IMAGE = Kind("images", settings.max_image_bytes, {
    (lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")): ("png", "image/png"),
    (lambda b: b.startswith(b"\xff\xd8\xff")): ("jpg", "image/jpeg"),
    _is_webp: ("webp", "image/webp"),
}, "a PNG, JPEG or WebP image")

RESUME = Kind("resumes", settings.max_resume_bytes, {
    (lambda b: b.startswith(b"%PDF-")): ("pdf", "application/pdf"),
}, "a PDF document")

MEDIA_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "pdf": "application/pdf"}


def upload_root() -> Path:
    root = Path(settings.upload_dir)
    return root if root.is_absolute() else BACKEND_DIR / root


async def save(file: UploadFile, kind: Kind) -> str:
    data = await file.read(kind.max_bytes + 1)
    if not data:
        raise HTTPException(400, "The file is empty.")
    if len(data) > kind.max_bytes:
        raise HTTPException(413, f"The file is too large (maximum {kind.max_bytes // (1024 * 1024)} MB).")
    ext = next((e for check, (e, _) in kind.types.items() if check(data[:16])), None)
    if ext is None:
        raise HTTPException(415, f"Upload {kind.label}.")
    folder = upload_root() / kind.folder
    folder.mkdir(parents=True, exist_ok=True)
    key = f"{kind.folder}/{secrets.token_hex(16)}.{ext}"
    (upload_root() / key).write_bytes(data)
    return key


def path_for(key: str | None) -> Path | None:
    """Resolve a stored key, refusing anything that escapes the upload directory."""
    if not key:
        return None
    root = upload_root().resolve()
    p = (root / key).resolve()
    if root not in p.parents or not p.is_file():
        return None
    return p


def delete(key: str | None) -> None:
    p = path_for(key)
    if p:
        p.unlink(missing_ok=True)
