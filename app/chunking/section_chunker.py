from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.pdf_parser import PageContent, ParsedDocument

logger = get_logger(__name__)
settings = get_settings()


@dataclass(frozen=True)
class ChunkMetadata:
    document_id: str
    document_version: str
    chunk_id: str
    page_number: int
    section: str
    chunk_index: int
    total_chunks: int
    word_count: int
    architecture_entities: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    metadata: ChunkMetadata


class SectionAwareChunker:
    """
    Create deterministic, section-aware chunks while preserving
    HLD evidence context.

    Unlike page-level chunking, this implementation tracks section
    headings within each page so that a page containing multiple
    sections does not incorrectly assign all chunks to the final
    heading on that page.
    """

    # Matches headings such as:
    #
    # 1. System Overview
    # 2. Software Architecture
    # 7. Dependencies
    # 8. Functional Flows
    # 10. Engineering Traceability
    #
    SECTION_PATTERN = re.compile(
        r"^\s*(\d+\.\s+[A-Za-z][A-Za-z0-9 /&_-]*)\s*$"
    )

    ENTITY_PATTERNS = {
        "component": re.compile(
            r"\b[A-Z][A-Za-z0-9_]*(?:Component|Manager|Control)\b"
        ),
        "interface": re.compile(
            r"\bI[A-Z][A-Za-z0-9_]+\b"
        ),
        "port": re.compile(
            r"\b[A-Za-z0-9_]*(?:_In|_Out)\b"
        ),
        "signal": re.compile(
            r"\b[A-Z][A-Za-z0-9_]*(?:Status|Speed|Position|Command)\b"
        ),
    }

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.chunk_size = (
            chunk_size
            if chunk_size is not None
            else settings.chunk_size
        )

        self.chunk_overlap = (
            chunk_overlap
            if chunk_overlap is not None
            else settings.chunk_overlap
        )

        if self.chunk_size <= 0:
            raise ValueError(
                "chunk_size must be greater than zero"
            )

        if self.chunk_overlap < 0:
            raise ValueError(
                "chunk_overlap cannot be negative"
            )

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size"
            )

    def chunk_document(
        self,
        document: ParsedDocument,
        document_id: str,
        document_version: str,
    ) -> list[DocumentChunk]:
        """
        Chunk the complete parsed document while preserving
        page number and section information.
        """

        raw_chunks: list[tuple[int, str, str]] = []

        for page in document.pages:
            page_chunks = self._chunk_page(page)

            raw_chunks.extend(page_chunks)

        total_chunks = len(raw_chunks)

        result: list[DocumentChunk] = []

        for index, (
            page_number,
            section,
            text,
        ) in enumerate(raw_chunks):

            chunk_id = self._build_chunk_id(
                document_id=document_id,
                document_version=document_version,
                page_number=page_number,
                chunk_index=index,
                text=text,
            )

            entities = tuple(
                sorted(
                    self._detect_architecture_entities(text)
                )
            )

            metadata = ChunkMetadata(
                document_id=document_id,
                document_version=document_version,
                chunk_id=chunk_id,
                page_number=page_number,
                section=section,
                chunk_index=index,
                total_chunks=total_chunks,
                word_count=len(text.split()),
                architecture_entities=entities,
            )

            result.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=text,
                    metadata=metadata,
                )
            )

        logger.info(
            "Created %d chunks for document=%s version=%s",
            len(result),
            document_id,
            document_version,
        )

        return result

    def _chunk_page(
        self,
        page: PageContent,
    ) -> list[tuple[int, str, str]]:
        """
        Split a page into section-aware chunks.

        A single PDF page can contain multiple sections. Therefore,
        section detection happens before word-based chunking.
        """

        lines = [
            line.strip()
            for line in page.text.splitlines()
            if line.strip()
        ]

        if not lines:
            return []

        sections: list[tuple[str, list[str]]] = []

        current_section = "Unclassified"
        current_lines: list[str] = []

        for line in lines:

            section_match = self.SECTION_PATTERN.match(line)

            if section_match:

                # Save the previous section before starting
                # the new one.
                if current_lines:
                    sections.append(
                        (
                            current_section,
                            current_lines,
                        )
                    )

                current_section = section_match.group(1)
                current_lines = [line]

            else:
                current_lines.append(line)

        # Save the final section.
        if current_lines:
            sections.append(
                (
                    current_section,
                    current_lines,
                )
            )

        chunks: list[tuple[int, str, str]] = []

        for section, section_lines in sections:

            text = " ".join(
                section_lines
            ).strip()

            if not text:
                continue

            section_chunks = self._split_text(
                page_number=page.page_number,
                section=section,
                text=text,
            )

            chunks.extend(section_chunks)

        return chunks

    def _split_text(
        self,
        page_number: int,
        section: str,
        text: str,
    ) -> list[tuple[int, str, str]]:
        """
        Split section text into overlapping word-based chunks.
        """

        words = text.split()

        if not words:
            return []

        chunks: list[tuple[int, str, str]] = []

        step = self.chunk_size - self.chunk_overlap

        start = 0

        while start < len(words):

            end = min(
                start + self.chunk_size,
                len(words),
            )

            chunk_text = " ".join(
                words[start:end]
            ).strip()

            if chunk_text:
                chunks.append(
                    (
                        page_number,
                        section,
                        chunk_text,
                    )
                )

            if end >= len(words):
                break

            start += step

        return chunks

    @staticmethod
    def _build_chunk_id(
        document_id: str,
        document_version: str,
        page_number: int,
        chunk_index: int,
        text: str,
    ) -> str:
        """
        Generate a deterministic chunk ID.

        The same document, version, position and text will always
        produce the same ID.
        """

        payload = (
            f"{document_id}|"
            f"{document_version}|"
            f"{page_number}|"
            f"{chunk_index}|"
            f"{text}"
        )

        digest = hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()[:20]

        return f"chunk_{digest}"

    @classmethod
    def _detect_architecture_entities(
        cls,
        text: str,
    ) -> set[str]:
        """
        Detect architecture-related identifiers appearing
        inside a chunk.
        """

        entities: set[str] = set()

        for pattern in cls.ENTITY_PATTERNS.values():

            entities.update(
                match.group(0)
                for match in pattern.finditer(text)
            )

        return entities