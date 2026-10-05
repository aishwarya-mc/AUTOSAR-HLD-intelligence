from __future__ import annotations

import hashlib
import re

from app.chunking.section_chunker import DocumentChunk
from app.extraction.entity_schema import (
    ArchitectureEntityRecord,
    EntityEvidence,
    EntityType,
)


class SignalExtractor:
    """
    Extract signal entities while excluding AUTOSAR interface identifiers.

    Signals are identified using common signal naming conventions such as
    Status, Speed, Position, and Command. Interface identifiers beginning
    with 'I' are explicitly excluded.
    """

    SIGNAL_PATTERN = re.compile(
        r"\b[A-Z][A-Za-z0-9_]*(?:Status|Speed|Position|Command)\b"
    )

    def extract(
        self,
        chunks: list[DocumentChunk],
    ) -> list[ArchitectureEntityRecord]:

        entities: dict[str, ArchitectureEntityRecord] = {}

        for chunk in chunks:
            for name in self.SIGNAL_PATTERN.findall(chunk.text):

                # AUTOSAR interfaces such as IDoorStatus and
                # IWindowCommand must not be classified as signals.
                if name.startswith("I") and len(name) > 1 and name[1].isupper():
                    continue

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
                        entity_type=EntityType.SIGNAL,
                        name=name,
                        confidence=0.90,
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
    def _entity_id(
        name: str,
        document_id: str,
        version: str,
    ) -> str:
        raw = f"signal|{name.lower()}|{document_id}|{version}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
        return f"entity_{digest}"