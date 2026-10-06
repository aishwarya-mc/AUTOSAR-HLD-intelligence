import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import get_service
from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundError, ValidationError

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", status_code=201)
async def upload_document(file: UploadFile = File(...), version: str | None = Form(None)):
    """Upload an HLD PDF and run ingestion, chunking, extraction and validation."""
    settings = get_settings()
    name = Path(file.filename or "upload.pdf").name
    if not name.lower().endswith(".pdf"):
        raise ValidationError("Only PDF documents are supported.")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / f"{uuid.uuid4().hex}_{name}"
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    with target.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                target.unlink(missing_ok=True)
                raise ValidationError(f"File exceeds the {settings.max_upload_mb} MB limit.")
            out.write(chunk)
    if not target.read_bytes()[:5].startswith(b"%PDF"):
        target.unlink(missing_ok=True)
        raise ValidationError("File is not a valid PDF.")

    return get_service().process(target, version=version, original_filename=name)


@router.post("/sample", status_code=201)
def load_sample(version: str | None = None):
    """Process the bundled synthetic sample HLD (handy for demos)."""
    sample = get_settings().sample_data_dir / "sample_hld.pdf"
    if not sample.exists():
        raise ResourceNotFoundError("Sample document is not available.")
    return get_service().process(sample, version=version)


@router.get("")
def list_documents():
    return get_service().store.list_documents()


@router.get("/{document_id}")
def get_document(document_id: str):
    return get_service().metadata(document_id)


@router.delete("/{document_id}")
def delete_document(document_id: str):
    if not get_service().delete(document_id):
        raise ResourceNotFoundError(f"Document '{document_id}' not found.")
    return {"deleted": document_id}
