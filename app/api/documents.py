import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import DocAccess, audit, get_service
from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.core.security import User, get_user, require_role

router = APIRouter(prefix="/documents", tags=["Documents"])


def _check_project(user: User, project: str) -> None:
    if not user.can_access(project):
        raise HTTPException(403, f"You do not have access to project '{project}'.")


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    version: str | None = Form(None),
    project: str = Form("default"),
    user: User = Depends(require_role("reviewer")),
):
    """Upload an HLD PDF and run ingestion, chunking, extraction, indexing and validation."""
    _check_project(user, project)
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

    meta = get_service().process(target, version=version, original_filename=name, project=project)
    audit(user, "upload", meta["document_id"], f"{name} version={meta['version']} project={project}")
    return meta


@router.post("/sample", status_code=201)
def load_sample(
    version: str | None = None,
    project: str = "default",
    user: User = Depends(require_role("reviewer")),
):
    """Process the bundled synthetic sample HLD (handy for demos)."""
    _check_project(user, project)
    sample = get_settings().sample_data_dir / "sample_hld.pdf"
    if not sample.exists():
        raise ResourceNotFoundError("Sample document is not available.")
    meta = get_service().process(sample, version=version, project=project)
    audit(user, "load_sample", meta["document_id"], f"project={project}")
    return meta


@router.get("")
def list_documents(project: str | None = None, user: User = Depends(get_user)):
    docs = [
        d for d in get_service().store.list_documents()
        if user.can_access(d.get("project", "default"))
    ]
    return [d for d in docs if project is None or d.get("project", "default") == project]


@router.get("/{document_id}")
def get_document(document_id: str, user: User = Depends(DocAccess("viewer"))):
    return get_service().metadata(document_id)


@router.delete("/{document_id}")
def delete_document(document_id: str, user: User = Depends(DocAccess("admin"))):
    if not get_service().delete(document_id):
        raise ResourceNotFoundError(f"Document '{document_id}' not found.")
    audit(user, "delete", document_id)
    return {"deleted": document_id}
