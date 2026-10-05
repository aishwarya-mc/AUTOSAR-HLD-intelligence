from pathlib import Path

from pydantic import BaseModel, Field


class ValidatedDocument(BaseModel):
    path: Path
    filename: str
    file_size_bytes: int
    extension: str
    is_valid: bool = True
    errors: list[str] = Field(default_factory=list)


SUPPORTED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE_MB = 100


def validate_document(path: str | Path) -> ValidatedDocument:
    """Validate an uploaded HLD document before processing."""

    document_path = Path(path)
    errors: list[str] = []

    if not document_path.exists():
        errors.append("Document does not exist.")

    if not document_path.is_file():
        errors.append("Document path is not a file.")

    extension = document_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        errors.append(
            f"Unsupported document type: {extension}. "
            f"Supported types: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    file_size = document_path.stat().st_size if document_path.exists() else 0
    max_size = MAX_FILE_SIZE_MB * 1024 * 1024

    if file_size > max_size:
        errors.append(
            f"Document exceeds the maximum size of "
            f"{MAX_FILE_SIZE_MB} MB."
        )

    return ValidatedDocument(
        path=document_path,
        filename=document_path.name,
        file_size_bytes=file_size,
        extension=extension,
        is_valid=len(errors) == 0,
        errors=errors,
    )
