from fastapi import APIRouter, Query

from app.api.deps import get_service
from app.core.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/architecture", tags=["Architecture"])


@router.get("/{document_id}/entities")
def entities(document_id: str, entity_type: str | None = None):
    return get_service().entities(document_id, entity_type)


@router.get("/{document_id}/model")
def model(document_id: str):
    from dataclasses import asdict

    return asdict(get_service().model(document_id))


@router.get("/{document_id}/graph")
def graph(document_id: str):
    return get_service().graph(document_id).to_dict()


@router.get("/{document_id}/impact/{element}")
def impact(document_id: str, element: str, depth: int = Query(3, ge=1, le=6)):
    """Traceability / change-impact: everything connected to an element."""
    g = get_service().graph(document_id)
    if element not in g.nodes:
        raise ResourceNotFoundError(f"Element '{element}' not found in the architecture graph.")
    return {
        "element": element,
        "type": g.nodes[element],
        "relationships": [e.__dict__ for e in g.neighbors(element)],
        "impacted": g.impact(element, depth),
    }
