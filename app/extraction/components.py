from __future__ import annotations

import hashlib
import re

from app.chunking.section_chunker import DocumentChunk
from app.extraction.entity_schema import (
    ArchitectureEntityRecord,
    EntityEvidence,
    EntityType,
)


class ComponentExtractor:
    """
    Extract AUTOSAR software components from document chunks.

    The first extraction layer intentionally uses deterministic patterns.
    This provides reproducible results and auditable evidence.
    """

    COMPONENT_PATTERN = re.compile(
        r"\b[A-Z][A-Za-z0-9_]*(?:Component|Manager|Control)\b"
    )

    def extract(
        self,
        chunks: list[DocumentChunk],
    ) -> list[ArchitectureEntityRecord]:

        entities: dict[str, ArchitectureEntityRecord] = {}

        for chunk in chunks:
            matches = self.COMPONENT_PATTERN.findall(chunk.text)

            for name in matches:
                normalized = self._normalize(name)

                entity_id = self._entity_id(
                    EntityType.COMPONENT,
                    normalized,
                    chunk.metadata.document_id,
                    chunk.metadata.document_version,
                )

                evidence = EntityEvidence(
                    document_id=chunk.metadata.document_id,
                    document_version=chunk.metadata.document_version,
                    page_number=chunk.metadata.page_number,
                    section=chunk.metadata.section,
                    source_text=chunk.text,
                )

                if entity_id not in entities:
                    entities[entity_id] = ArchitectureEntityRecord(
                        entity_id=entity_id,
                        entity_type=EntityType.COMPONENT,
                        name=normalized,
                        confidence=0.95,
                        document_id=chunk.metadata.document_id,
                        document_version=chunk.metadata.document_version,
                        evidence=[evidence],
                    )
                else:
                    if not any(
                        e.page_number == evidence.page_number
                        and e.section == evidence.section
                        for e in entities[entity_id].evidence
                    ):
                        entities[entity_id].evidence.append(evidence)

        return list(entities.values())

    @staticmethod
    def _normalize(name: str) -> str:
        return re.sub(r"\s+", " ", name).strip()

    @staticmethod
    def _entity_id(
        entity_type: EntityType,
        name: str,
        document_id: str,
        document_version: str,
    ) -> str:
        raw = f"{entity_type.value}|{name.lower()}|{document_id}|{document_version}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
        return f"entity_{digest}"
