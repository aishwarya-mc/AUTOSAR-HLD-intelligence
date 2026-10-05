from __future__ import annotations

from dataclasses import dataclass

from app.chunking.section_chunker import DocumentChunk
from app.core.logging import get_logger
from app.extraction.components import ComponentExtractor
from app.extraction.dependencies import DependencyExtractor
from app.extraction.entity_schema import ArchitectureEntityRecord
from app.extraction.functional_flows import FunctionalFlowExtractor
from app.extraction.interfaces import InterfaceExtractor
from app.extraction.ports import PortExtractor
from app.extraction.signals import SignalExtractor
from app.ingestion.pdf_parser import ParsedDocument

logger = get_logger(__name__)


@dataclass(frozen=True)
class ArchitectureExtractionResult:
    """Complete architecture extraction result for one document version."""

    document_id: str
    document_version: str

    components: tuple[ArchitectureEntityRecord, ...]
    interfaces: tuple[ArchitectureEntityRecord, ...]
    ports: tuple[ArchitectureEntityRecord, ...]
    signals: tuple[ArchitectureEntityRecord, ...]
    dependencies: tuple[ArchitectureEntityRecord, ...]
    functional_flows: tuple[ArchitectureEntityRecord, ...]

    @property
    def all_entities(self) -> tuple[ArchitectureEntityRecord, ...]:
        return (
            self.components
            + self.interfaces
            + self.ports
            + self.signals
            + self.dependencies
            + self.functional_flows
        )

    @property
    def entity_count(self) -> int:
        return len(self.all_entities)


class ArchitectureExtractor:
    """
    Orchestrate all architecture entity extractors.

    The extractor keeps the document-level structured-table extraction
    separate from chunk-based text extraction because different
    architecture artifacts have different evidence sources.
    """

    def __init__(self) -> None:
        self.component_extractor = ComponentExtractor()
        self.interface_extractor = InterfaceExtractor()
        self.port_extractor = PortExtractor()
        self.signal_extractor = SignalExtractor()
        self.dependency_extractor = DependencyExtractor()
        self.functional_flow_extractor = FunctionalFlowExtractor()

    def extract(
        self,
        document: ParsedDocument,
        chunks: list[DocumentChunk],
        document_id: str,
        document_version: str,
    ) -> ArchitectureExtractionResult:

        components = self.component_extractor.extract(chunks)

        interfaces = self.interface_extractor.extract(chunks)

        ports = self.port_extractor.extract(chunks)

        signals = self.signal_extractor.extract(chunks)

        dependencies = self.dependency_extractor.extract(
            document=document,
            document_id=document_id,
            document_version=document_version,
        )

        functional_flows = self.functional_flow_extractor.extract(
            chunks
        )

        result = ArchitectureExtractionResult(
            document_id=document_id,
            document_version=document_version,
            components=tuple(components),
            interfaces=tuple(interfaces),
            ports=tuple(ports),
            signals=tuple(signals),
            dependencies=tuple(dependencies),
            functional_flows=tuple(functional_flows),
        )

        logger.info(
            "Architecture extraction completed: "
            "document=%s version=%s entities=%d",
            document_id,
            document_version,
            result.entity_count,
        )

        return result