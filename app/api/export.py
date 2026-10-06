import csv
import io
from dataclasses import asdict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.deps import DocAccess, audit, get_service
from app.core.exceptions import ValidationError
from app.core.security import User

router = APIRouter(prefix="/export", tags=["Export"])


def _csv(rows: list[dict], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


@router.get("/{document_id}.json")
def export_json(document_id: str, user: User = Depends(DocAccess("viewer"))):
    """Complete structured export for downstream tools (inventory, graph, findings, reviews)."""
    service = get_service()
    audit(user, "export", document_id, "json")
    graph = service.graph(document_id).to_dict()
    return JSONResponse(
        {
            "document": service.metadata(document_id),
            "inventory": asdict(service.model(document_id)),
            "entities": service.entities(document_id),
            "relationships": graph["edges"],
            "findings": service.findings(document_id),
        },
        headers={"Content-Disposition": f'attachment; filename="{document_id}.json"'},
    )


@router.get("/{document_id}/{dataset}.csv")
def export_csv(document_id: str, dataset: str, user: User = Depends(DocAccess("viewer"))):
    """CSV export of one dataset: entities, relationships or findings."""
    service = get_service()
    audit(user, "export", document_id, dataset)
    if dataset == "entities":
        rows = [
            {
                "entity_type": e["entity_type"],
                "name": e["name"],
                "confidence": e["confidence"],
                "pages": ";".join(str(x["page_number"]) for x in e["evidence"]),
                "sections": ";".join(sorted({x["section"] for x in e["evidence"]})),
                "description": e["description"],
            }
            for e in service.entities(document_id)
        ]
        cols = ["entity_type", "name", "confidence", "pages", "sections", "description"]
    elif dataset == "relationships":
        rows = service.graph(document_id).to_dict()["edges"]
        cols = ["source", "relation", "target", "page"]
        rows = [{**r, "target": r["target"]} for r in rows]
    elif dataset == "findings":
        rows = [
            {
                "finding_id": f["finding_id"],
                "rule_id": f["rule_id"],
                "severity": f["severity"],
                "title": f["title"],
                "description": f["description"],
                "confidence": f["confidence"],
                "page": f["evidence"][0]["page_number"] if f["evidence"] else "",
                "section": f["evidence"][0]["section"] if f["evidence"] else "",
                "review_status": (f["review"] or {}).get("status", "pending"),
                "reviewer": (f["review"] or {}).get("reviewer", ""),
            }
            for f in service.findings(document_id)
        ]
        cols = ["finding_id", "rule_id", "severity", "title", "description", "confidence",
                "page", "section", "review_status", "reviewer"]
    else:
        raise ValidationError("dataset must be one of: entities, relationships, findings")
    return PlainTextResponse(
        _csv(rows, cols),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{document_id}_{dataset}.csv"'},
    )
