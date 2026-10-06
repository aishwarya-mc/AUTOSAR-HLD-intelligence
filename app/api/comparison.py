from fastapi import APIRouter, Depends

from app.api.deps import audit, ensure_document_access, get_service
from app.comparison.differ import compare_models
from app.core.security import User, get_user

router = APIRouter(prefix="/comparison", tags=["Comparison"])


@router.get("")
def compare(old_document_id: str, new_document_id: str, user: User = Depends(get_user)):
    """Structured diff between two HLD revisions with change-impact analysis."""
    ensure_document_access(user, old_document_id)
    ensure_document_access(user, new_document_id)
    service = get_service()
    result = compare_models(service.model(old_document_id), service.model(new_document_id))
    audit(user, "compare", new_document_id, f"against {old_document_id}")
    return {
        "old": service.metadata(old_document_id),
        "new": service.metadata(new_document_id),
        **result,
    }
