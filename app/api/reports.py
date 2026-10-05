from dataclasses import asdict

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.api.deps import get_service
from app.comparison.differ import compare_models
from app.reporting.report import build_report

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{document_id}", response_class=PlainTextResponse)
def report(document_id: str, compare_with: str | None = None):
    """Markdown engineering report; optionally includes a diff against another revision."""
    service = get_service()
    comparison, other = None, None
    if compare_with:
        other = service.metadata(compare_with)
        comparison = compare_models(service.model(compare_with), service.model(document_id))
    return PlainTextResponse(
        build_report(service.metadata(document_id), asdict(service.model(document_id)),
                     service.findings(document_id), comparison, other),
        media_type="text/markdown",
    )
