from fastapi import APIRouter, Depends

from app.api.deps import audit, ensure_document_access, get_service
from app.core.exceptions import ValidationError
from app.core.schemas import QueryRequest, QueryResponse
from app.core.security import User, get_user

router = APIRouter(prefix="/queries", tags=["Queries"])


@router.post("", response_model=QueryResponse)
def ask(request: QueryRequest, user: User = Depends(get_user)):
    """Evidence-grounded natural-language question about a processed HLD."""
    service = get_service()
    document_id = request.document_id
    if not document_id:
        docs = [
            d for d in service.store.list_documents()
            if user.can_access(d.get("project", "default"))
        ]
        if not docs:
            raise ValidationError("No documents have been processed yet.")
        document_id = docs[0]["document_id"]
    ensure_document_access(user, document_id, "viewer")
    response = service.answerer(document_id).answer(request.question, request.top_k)
    audit(
        user, "query", document_id,
        f"grounded={response.grounded} confidence={response.confidence} q={request.question}",
    )
    return response
