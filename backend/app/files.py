"""Saving and deleting uploaded item photos."""
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from .config import MAX_UPLOAD_BYTES, UPLOAD_DIR


def _sniff_extension(data: bytes) -> Optional[str]:
    """Decide the file type from its first bytes, not from what the client claims."""
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def save_image(data: bytes) -> str:
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Photo is larger than 5 MB")
    extension = _sniff_extension(data)
    if extension is None:
        raise HTTPException(status_code=400, detail="Only JPG, PNG or WEBP photos are allowed")
    name = f"{uuid.uuid4().hex}{extension}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / name).write_bytes(data)
    return f"/uploads/{name}"


def delete_upload(image_url: Optional[str]) -> None:
    if not image_url or not image_url.startswith("/uploads/"):
        return
    try:
        (UPLOAD_DIR / Path(image_url).name).unlink(missing_ok=True)
    except OSError:
        pass
