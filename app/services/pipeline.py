from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from app.chunking.section_chunker import SectionAwareChunker
from app.core.exceptions import ResourceNotFoundError
from app.core.logging import get_logger
from app.core.schemas import ReviewAction
from app.extraction.extractor import ArchitectureExtractor
from app.extraction.structured_model import StructuredModel, build_structured_model, model_from_dict
from app.graph.builder import ArchitectureGraph, build_graph
from app.ingestion.service import DocumentIngestionService
from app.rag.answerer import GroundedAnswerer
from app.storage.store import DocumentStore
from app.validation.rules import ValidationEngine

logger = get_logger(__name__)


class HLDService:
    """Facade that runs the full pipeline and serves stored results to the API/UI."""

    def __init__(self, store: DocumentStore | None = None):
        self.store = store or DocumentStore()
        self.ingestion = DocumentIngestionService()
        self.chunker = SectionAwareChunker()
        self.extractor = ArchitectureExtractor()

    # -- processing --------------------------------------------------------

    def process(self, pdf_path: str | Path, version: str | None = None,
                original_filename: str | None = None) -> dict:
        ingested = self.ingestion.ingest(pdf_path)
        metadata = dict(ingested.metadata)
        if version:
            metadata["version"] = version
        if original_filename:
            metadata["filename"] = original_filename
        doc_id, ver = metadata["document_id"], metadata["version"]

        parsed = ingested.parsed_document
        chunks = self.chunker.chunk_document(parsed, doc_id, ver)
        extraction = self.extractor.extract(parsed, chunks, doc_id, ver)
        model = build_structured_model(parsed)
        chunk_dicts = [
            {"chunk_id": c.chunk_id, "text": c.text, "page_number": c.metadata.page_number,
             "section": c.metadata.section} for c in chunks
        ]
        findings = ValidationEngine(model, chunk_dicts, doc_id, ver).run()

        payload = {
            "chunks": chunk_dicts,
            "entities": [e.model_dump(mode="json") for e in extraction.all_entities],
            "model": asdict(model),
            "findings": [f.model_dump(mode="json") for f in findings],
            "pages": [{"page_number": p.page_number, "word_count": p.word_count}
                      for p in parsed.pages],
        }
        metadata["entity_count"] = extraction.entity_count
        metadata["finding_count"] = len(findings)
        self.store.save_document(metadata, payload)
        logger.info("Processed %s (%s): %d entities, %d findings",
                    metadata["filename"], doc_id, extraction.entity_count, len(findings))
        return metadata

    # -- accessors ---------------------------------------------------------

    def _payload(self, document_id: str) -> dict:
        payload = self.store.get_payload(document_id)
        if payload is None:
            raise ResourceNotFoundError(f"Document '{document_id}' not found.")
        return payload

    def metadata(self, document_id: str) -> dict:
        meta = self.store.get_metadata(document_id)
        if meta is None:
            raise ResourceNotFoundError(f"Document '{document_id}' not found.")
        return meta

    def model(self, document_id: str) -> StructuredModel:
        return model_from_dict(self._payload(document_id)["model"])

    def graph(self, document_id: str) -> ArchitectureGraph:
        return build_graph(self.model(document_id))

    def entities(self, document_id: str, entity_type: str | None = None) -> list[dict]:
        ents = self._payload(document_id)["entities"]
        return [e for e in ents if not entity_type or e["entity_type"] == entity_type]

    def findings(self, document_id: str) -> list[dict]:
        payload = self._payload(document_id)
        reviews = self.store.list_reviews(document_id)
        out = []
        for f in payload["findings"]:
            review = reviews.get(f["finding_id"])
            out.append({**f, "review": review})
        return out

    def review(self, document_id: str, action: ReviewAction) -> dict:
        if action.finding_id not in {f["finding_id"] for f in self._payload(document_id)["findings"]}:
            raise ResourceNotFoundError(f"Finding '{action.finding_id}' not found.")
        self.store.save_review(document_id, action.finding_id, action.status.value,
                               action.reviewer, action.comment)
        return action.model_dump(mode="json")

    def answerer(self, document_id: str) -> GroundedAnswerer:
        meta = self.metadata(document_id)
        payload = self._payload(document_id)
        return GroundedAnswerer(payload["chunks"], build_graph(model_from_dict(payload["model"])),
                                document_id, meta["version"])
