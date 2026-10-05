from fastapi import APIRouter

from app.api.deps import get_service
from app.core.exceptions import ValidationError
from app.core.schemas import QueryRequest, QueryResponse

router = APIRouter(prefix="/queries", tags=["Queries"])


@router.post("", response_model=QueryResponse)
def ask(request: QueryRequest):
    """Evidence-grounded natural-language question about a processed HLD."""
    service = get_service()
    document_id = request.document_id
    if not document_id:
        docs = service.store.list_documents()
        if not docs:
            raise ValidationError("No documents have been processed yet.")
        document_id = docs[0]["document_id"]
    return service.answerer(document_id).answer(request.question, request.top_k)
