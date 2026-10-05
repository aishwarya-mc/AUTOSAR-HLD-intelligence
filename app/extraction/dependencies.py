from __future__ import annotations

import hashlib
import re

from app.extraction.entity_schema import (
    ArchitectureEntityRecord,
    EntityEvidence,
    EntityType,
)
from app.ingestion.pdf_parser import ParsedDocument


class DependencyExtractor:
    """
    Extract AUTOSAR dependency relationships from structured
    dependency tables preserved by the PDF parser.

    Expected table schema:

        Source
        Relationship
        Target
        Reason
    """

    REQUIRED_COLUMNS = {
        "source",
        "relationship",
        "target",
        "reason",
    }

    COMPONENT_PATTERN = re.compile(
        r"^[A-Z][A-Za-z0-9_]*(?:Manager|Control|Component)$"
    )

    INTERFACE_PATTERN = re.compile(
        r"^I[A-Z][A-Za-z0-9_]+$"
    )

    VALID_RELATIONSHIPS = {
        "PROVIDES_INTERFACE",
        "REQUIRES_INTERFACE",
    }

    def extract(
        self,
        document: ParsedDocument,
        document_id: str,
        document_version: str,
    ) -> list[ArchitectureEntityRecord]:

        entities: dict[str, ArchitectureEntityRecord] = {}

        for page in document.pages:

            for table in page.tables:

                if not table:
                    continue

                headers = self._normalize_headers(
                    table[0]
                )

                if not self.REQUIRED_COLUMNS.issubset(
                    headers
                ):
                    continue

                column_index = {
                    header: index
                    for index, header in enumerate(headers)
                }

                for row in table[1:]:

                    if len(row) < len(headers):
                        continue

                    source = self._clean_value(
                        row[column_index["source"]]
                    )

                    relationship = self._normalize_relationship(
                        row[column_index["relationship"]]
                    )

                    target = self._clean_value(
                        row[column_index["target"]]
                    )

                    reason = self._clean_value(
                        row[column_index["reason"]]
                    )

                    if not source or not target:
                        continue

                    if relationship not in self.VALID_RELATIONSHIPS:
                        continue

                    if not self._is_valid_endpoint(source):
                        continue

                    if not self._is_valid_endpoint(target):
                        continue

                    name = (
                        f"{source} "
                        f"{relationship} "
                        f"{target}"
                    )

                    entity_id = self._entity_id(
                        name=name,
                        document_id=document_id,
                        version=document_version,
                    )

                    evidence = EntityEvidence(
                        document_id=document_id,
                        document_version=document_version,
                        page_number=page.page_number,
                        section="7. Dependencies",
                        source_text=(
                            f"{source} | "
                            f"{relationship} | "
                            f"{target} | "
                            f"{reason}"
                        ),
                    )

                    if entity_id not in entities:

                        entities[entity_id] = (
                            ArchitectureEntityRecord(
                                entity_id=entity_id,
                                entity_type=EntityType.DEPENDENCY,
                                name=name,
                                description=reason,
                                confidence=0.99,
                                document_id=document_id,
                                document_version=document_version,
                                evidence=[evidence],
                                attributes={
                                    "source": source,
                                    "relationship": relationship,
                                    "target": target,
                                    "reason": reason,
                                },
                            )
                        )

                    else:

                        existing = entities[entity_id]

                        if not any(
                            e.page_number == evidence.page_number
                            and e.source_text == evidence.source_text
                            for e in existing.evidence
                        ):
                            existing.evidence.append(
                                evidence
                            )

        return list(entities.values())

    @staticmethod
    def _normalize_headers(
        headers: list[str],
    ) -> list[str]:

        return [
            re.sub(
                r"[^a-z]",
                "",
                str(header).lower(),
            )
            for header in headers
        ]

    @staticmethod
    def _clean_value(
        value: str,
    ) -> str:

        value = str(value)

        # Normalize all whitespace including \n and \t.
        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        # Remove PDF extraction artifacts.
        value = re.sub(
            r"\s+_+\s*",
            "",
            value,
        )

        return value.strip()

    @classmethod
    def _normalize_relationship(
        cls,
        value: str,
    ) -> str:

        value = cls._clean_value(value)

        # Handle PDF-extracted forms such as:
        #
        # PROVIDES INTERFACE
        # PROVIDES_INTERFACE
        # PROVIDES INTERFACE _
        #
        value = value.replace(
            "_",
            " ",
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

        return value.upper().replace(
            " ",
            "_",
        )

    @classmethod
    def _is_valid_endpoint(
        cls,
        value: str,
    ) -> bool:

        return bool(
            cls.COMPONENT_PATTERN.fullmatch(value)
            or cls.INTERFACE_PATTERN.fullmatch(value)
        )

    @staticmethod
    def _entity_id(
        name: str,
        document_id: str,
        version: str,
    ) -> str:

        raw = (
            f"dependency|"
            f"{name.lower()}|"
            f"{document_id}|"
            f"{version}"
        )

        digest = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:20]

        return f"entity_{digest}"