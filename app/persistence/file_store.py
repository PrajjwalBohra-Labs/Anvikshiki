"""
File store (§23): local disk storage for pdfs, images, notes, exports.
Documents are treated as immutable once written — full enforcement of
that rule is part of §19's ingestion pipeline (Step 4); this module
just provides the underlying write/read primitives.
"""

import uuid
from pathlib import Path

from app.config import get_settings

_CATEGORIES = {"pdfs", "images", "notes", "exports"}


def _category_dir(category: str) -> Path:
    if category not in _CATEGORIES:
        raise ValueError(
            f"Unknown file category: {category!r}. Expected one of {_CATEGORIES}"
        )
    settings = get_settings()
    directory = Path(settings.file_store_path) / category
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_file(category: str, filename: str, content: bytes) -> str:
    directory = _category_dir(category)
    safe_name = f"{uuid.uuid4()}_{filename}"
    path = directory / safe_name
    path.write_bytes(content)
    return str(path)


def read_file(path: str) -> bytes:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(path)
    return file_path.read_bytes()


def list_files(category: str) -> list[str]:
    directory = _category_dir(category)
    return [str(p) for p in directory.iterdir() if p.is_file()]
