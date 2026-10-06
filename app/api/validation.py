from collections import Counter

from fastapi import APIRouter, Depends

from app.api.deps import DocAccess, audit, get_service
from app.core.schemas import ReviewAction
from app.core.security import User

router = APIRouter(prefix="/validation", tags=["Validation"])


@router.get("/{document_id}")
def findings(document_id: str, user: User = Depends(DocAccess("viewer"))):
    items = get_service().findings(document_id)
    return {"summary": dict(Counter(f["severity"] for f in items)), "findings": items}


@router.post("/{document_id}/review")
def review(document_id: str, action: ReviewAction, user: User = Depends(DocAccess("reviewer"))):
    """Record a human accept/reject/needs-review decision.

    With authentication on, the reviewer recorded is the authenticated user.
    """
    if user.name != "anonymous":
        action = action.model_copy(update={"reviewer": user.name})
    result = get_service().review(document_id, action)
    audit(user, "review", document_id, f"{action.finding_id} -> {action.status.value}")
    return result
