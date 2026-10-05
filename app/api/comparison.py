from fastapi import APIRouter

from app.api.deps import get_service
from app.comparison.differ import compare_models

router = APIRouter(prefix="/comparison", tags=["Comparison"])


@router.get("")
def compare(old_document_id: str, new_document_id: str):
    """Structured diff between two HLD revisions with change-impact analysis."""
    service = get_service()
    result = compare_models(service.model(old_document_id), service.model(new_document_id))
    return {
        "old": service.metadata(old_document_id),
        "new": service.metadata(new_document_id),
        **result,
    }
