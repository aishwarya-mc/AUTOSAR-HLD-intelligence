from __future__ import annotations

import re
from collections.abc import Iterable

from app.extraction.entity_schema import ArchitectureEntityRecord


class EntityNormalizer:
    """
    Normalize and deduplicate extracted architecture entities.

    Normalization is intentionally conservative because AUTOSAR
    identifiers are meaningful and may be case-sensitive.

    We normalize formatting noise such as repeated whitespace,
    but we do not arbitrarily remove underscores, hyphens, or
    change identifier casing.
    """

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize formatting noise without changing the semantic
        identifier.

        Examples:
            " BodyControlManager " -> "BodyControlManager"
            "DoorStatus_Out"      -> "DoorStatus_Out"
            "IDoorStatus"         -> "IDoorStatus"
        """
        value = str(name)

        # Normalize all whitespace, including newlines/tabs.
        value = re.sub(r"\s+", " ", value)

        return value.strip()

    @classmethod
    def canonical_key(
        cls,
        entity: ArchitectureEntityRecord,
    ) -> tuple[str, str, str, str]:
        """
        Build a stable deduplication key.

        Entity type and document/version are included so that
        identical names in different architecture contexts do
        not accidentally collapse into one entity.
        """
        normalized_name = cls.normalize_name(entity.name)

        return (
            entity.document_id,
            entity.document_version,
            entity.entity_type.value,
            normalized_name.casefold(),
        )

    @classmethod
    def normalize(
        cls,
        entity: ArchitectureEntityRecord,
    ) -> ArchitectureEntityRecord:
        """
        Return a normalized copy of an entity.
        """
        normalized_name = cls.normalize_name(entity.name)

        if normalized_name == entity.name:
            return entity

        return entity.model_copy(
            update={
                "name": normalized_name,
            }
        )

    @classmethod
    def deduplicate(
        cls,
        entities: Iterable[ArchitectureEntityRecord],
    ) -> list[ArchitectureEntityRecord]:
        """
        Deduplicate entities while preserving evidence.

        When duplicate entities are found:
        - The first entity ID is retained.
        - The highest confidence is retained.
        - Unique evidence is merged.
        - Non-empty descriptions are preserved.
        - Attributes from later records are merged.
        """
        unique: dict[
            tuple[str, str, str, str],
            ArchitectureEntityRecord,
        ] = {}

        for raw_entity in entities:
            entity = cls.normalize(raw_entity)
            key = cls.canonical_key(entity)

            if key not in unique:
                unique[key] = entity
                continue

            existing = unique[key]

            # Merge unique evidence.
            existing_evidence = {
                (
                    evidence.document_id,
                    evidence.document_version,
                    evidence.page_number,
                    evidence.section,
                    evidence.source_text,
                )
                for evidence in existing.evidence
            }

            for evidence in entity.evidence:
                evidence_key = (
                    evidence.document_id,
                    evidence.document_version,
                    evidence.page_number,
                    evidence.section,
                    evidence.source_text,
                )

                if evidence_key not in existing_evidence:
                    existing.evidence.append(evidence)
                    existing_evidence.add(evidence_key)

            # Keep the strongest confidence.
            if entity.confidence > existing.confidence:
                existing.confidence = entity.confidence

            # Preserve the most informative description.
            if len(entity.description) > len(existing.description):
                existing.description = entity.description

            # Merge attributes without destroying existing values.
            for key_name, value in entity.attributes.items():
                if key_name not in existing.attributes:
                    existing.attributes[key_name] = value

        return list(unique.values())


def normalize_and_deduplicate(
    entities: Iterable[ArchitectureEntityRecord],
) -> list[ArchitectureEntityRecord]:
    """
    Convenience function for callers that do not need the
    EntityNormalizer class directly.
    """
    return EntityNormalizer.deduplicate(entities)