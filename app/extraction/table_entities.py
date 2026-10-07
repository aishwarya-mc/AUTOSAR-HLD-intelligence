from __future__ import annotations

import hashlib

from app.extraction.entity_schema import (
    ArchitectureEntityRecord,
    EntityEvidence,
    EntityType,
)
from app.extraction.structured_model import StructuredModel


def _entity_id(kind: str, name: str, document_id: str, version: str) -> str:
    raw = f"{kind}|{name.lower()}|{document_id}|{version}"
    return "entity_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


class TableEntityExtractor:
    """
    Create entities straight from the HLD tables (components, interfaces, ports, signals).

    Pattern-based extraction depends on naming conventions (for example signal names ending in
    Status/Speed/Position/Command). Tables are the authoritative definition in an HLD, so reading
    them makes extraction independent of naming style. Results are merged with the pattern-based
    entities by the normaliser, which also merges their evidence.
    """

    def extract(
        self, model: StructuredModel, document_id: str, version: str
    ) -> dict[EntityType, list[ArchitectureEntityRecord]]:
        out: dict[EntityType, list[ArchitectureEntityRecord]] = {
            t: [] for t in (EntityType.COMPONENT, EntityType.INTERFACE,
                            EntityType.PORT, EntityType.SIGNAL)
        }

        def add(kind: EntityType, name: str, page: int, section: str, text: str,
                description: str = "", attributes: dict | None = None) -> None:
            if not name:
                return
            out[kind].append(ArchitectureEntityRecord(
                entity_id=_entity_id(kind.value, name, document_id, version),
                entity_type=kind, name=name, description=description, confidence=0.99,
                document_id=document_id, document_version=version,
                evidence=[EntityEvidence(document_id=document_id, document_version=version,
                                         page_number=page, section=section, source_text=text)],
                attributes=attributes or {},
            ))

        for c in model.components:
            add(EntityType.COMPONENT, c.name, c.page, "3. Software Components",
                f"{c.name} | {c.role} | {c.responsibility}", c.responsibility, {"role": c.role})
        for i in model.interfaces:
            add(EntityType.INTERFACE, i.name, i.page, "4. Interfaces",
                f"{i.name} | {i.provider} | {i.consumer} | {', '.join(i.signals)}",
                attributes={"provider": i.provider, "consumer": i.consumer})
        for p in model.ports:
            add(EntityType.PORT, p.name, p.page, "5. Ports",
                f"{p.component} | {p.name} | {p.direction} | {p.interface}",
                attributes={"component": p.component, "direction": p.direction,
                            "interface": p.interface})
        for s in model.signals:
            add(EntityType.SIGNAL, s.name, s.page, "6. Signals",
                f"{s.name} | {s.data_type} | {s.source} | {s.destination}",
                attributes={"data_type": s.data_type, "source": s.source,
                            "destination": s.destination})
        return out
