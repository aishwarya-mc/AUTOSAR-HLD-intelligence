from __future__ import annotations

import hashlib
import re

from app.chunking.section_chunker import DocumentChunk
from app.extraction.entity_schema import (
    ArchitectureEntityRecord,
    EntityEvidence,
    EntityType,
)


class InterfaceExtractor:

    INTERFACE_PATTERN = re.compile(
        r"\bI[A-Z][A-Za-z0-9_]+\b"
    )

    def extract(
        self,
        chunks: list[DocumentChunk],
    ) -> list[ArchitectureEntityRecord]:

        entities: dict[str, ArchitectureEntityRecord] = {}

        for chunk in chunks:
            for name in self.INTERFACE_PATTERN.findall(chunk.text):

                entity_id = self._entity_id(
                    name,
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
                        entity_type=EntityType.INTERFACE,
                        name=name,
                        confidence=0.95,
                        document_id=chunk.metadata.document_id,
                        document_version=chunk.metadata.document_version,
                        evidence=[evidence],
                    )

        return list(entities.values())

    @staticmethod
    def _entity_id(name: str, document_id: str, version: str) -> str:
        raw = f"interface|{name.lower()}|{document_id}|{version}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:20]
        return f"entity_{digest}"