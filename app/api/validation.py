from collections import Counter

from fastapi import APIRouter

from app.api.deps import get_service
from app.core.schemas import ReviewAction

router = APIRouter(prefix="/validation", tags=["Validation"])


@router.get("/{document_id}")
def findings(document_id: str):
    items = get_service().findings(document_id)
    return {
        "summary": dict(Counter(f["severity"] for f in items)),
        "findings": items,
    }


@router.post("/{document_id}/review")
def review(document_id: str, action: ReviewAction):
    """Record a human accept/reject/needs-review decision on a finding."""
    return get_service().review(document_id, action)
