from __future__ import annotations

import hashlib
import re

from app.chunking.section_chunker import DocumentChunk
from app.extraction.entity_schema import (
    ArchitectureEntityRecord,
    EntityEvidence,
    EntityType,
)


class FunctionalFlowExtractor:
    """
    Extract explicitly labelled functional flows.

    Expected HLD format:

        Flow F-001: Door State Monitoring
        <flow description>

        Flow F-002: Window Command
        <flow description>

        Flow F-003: Vehicle State Dependency
        <flow description>
    """

    FLOW_PATTERN = re.compile(
        r"Flow\s+(F-\d+)\s*:\s*"
        r"(.*?)(?=\s+Flow\s+F-\d+\s*:|$)",
        re.IGNORECASE | re.DOTALL,
    )

    FLOW_SECTION_PATTERN = re.compile(
        r"^8\.\s+Functional\s+Flows$",
        re.IGNORECASE,
    )

    def extract(
        self,
        chunks: list[DocumentChunk],
    ) -> list[ArchitectureEntityRecord]:

        entities: dict[str, ArchitectureEntityRecord] = {}

        for chunk in chunks:

            if not self.FLOW_SECTION_PATTERN.match(
                chunk.metadata.section
            ):
                continue

            for match in self.FLOW_PATTERN.finditer(
                chunk.text
            ):

                flow_id = match.group(1).upper()

                flow_content = " ".join(
                    match.group(2).split()
                ).strip()

                if not flow_content:
                    continue

                flow_name, description = (
                    self._split_flow_name(
                        flow_content
                    )
                )

                entity_name = (
                    f"{flow_id}: {flow_name}"
                )

                entity_id = self._entity_id(
                    entity_name,
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

                entities[entity_id] = (
                    ArchitectureEntityRecord(
                        entity_id=entity_id,
                        entity_type=EntityType.FUNCTIONAL_FLOW,
                        name=entity_name,
                        description=description,
                        confidence=0.98,
                        document_id=chunk.metadata.document_id,
                        document_version=chunk.metadata.document_version,
                        evidence=[evidence],
                        attributes={
                            "flow_id": flow_id,
                            "flow_name": flow_name,
                            "description": description,
                        },
                    )
                )

        return list(entities.values())

    @staticmethod
    def _split_flow_name(
        content: str,
    ) -> tuple[str, str]:

        # The title is the run of plain words before the first identifier-like token
        # (CamelCase such as DoorControl, or snake_case such as DoorStatus_In).
        words = content.split()
        title: list[str] = []
        for word in words:
            if re.search(r"[a-z][A-Z]", word) or "_" in word or word.endswith("."):
                break
            title.append(word)
        if title and len(title) < len(words):
            return " ".join(title), " ".join(words[len(title):])

        # Fallback: use the first sentence as the flow title.
        match = re.match(
            r"(.+?)(?:\.\s+)(.*)",
            content,
            re.DOTALL,
        )

        if match:
            return (
                match.group(1).strip(),
                match.group(2).strip(),
            )

        return content, content

    @staticmethod
    def _entity_id(
        name: str,
        document_id: str,
        version: str,
    ) -> str:

        raw = (
            f"functional_flow|"
            f"{name.lower()}|"
            f"{document_id}|"
            f"{version}"
        )

        digest = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:20]

        return f"entity_{digest}"
