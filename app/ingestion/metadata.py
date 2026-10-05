from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


def generate_document_id() -> str:
    return f"doc_{uuid4().hex}"


def generate_version() -> str:
    return "v1"


def build_document_metadata(
    path: str | Path,
    page_count: int,
    pdf_metadata: dict,
    document_id: str | None = None,
    version: str | None = None,
) -> dict:
    """Build normalized metadata for a processed HLD document."""

    document_path = Path(path)

    metadata = {
        "document_id": document_id or generate_document_id(),
        "version": version or generate_version(),
        "filename": document_path.name,
        "file_type": document_path.suffix.lower(),
        "file_size_bytes": document_path.stat().st_size,
        "page_count": page_count,
        "title": pdf_metadata.get("title") or document_path.stem,
        "author": pdf_metadata.get("author") or "",
        "subject": pdf_metadata.get("subject") or "",
        "creator": pdf_metadata.get("creator") or "",
        "producer": pdf_metadata.get("producer") or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Created metadata for document=%s version=%s",
        metadata["document_id"],
        metadata["version"],
    )

    return metadata
