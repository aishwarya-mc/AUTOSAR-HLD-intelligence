from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PageContent:
    page_number: int
    text: str
    word_count: int
    is_low_text: bool
    image_count: int = 0
    headings: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    filename: str
    page_count: int
    metadata: dict[str, Any]
    pages: list[PageContent]
    total_word_count: int
    low_text_pages: list[int]
    scanned_pages: list[int] = field(default_factory=list)


class PDFParser:
    """Extract structured, page-preserving content from AUTOSAR HLD PDFs."""

    LOW_TEXT_THRESHOLD = 20

    def parse(self, pdf_path: str | Path) -> ParsedDocument:
        path = Path(pdf_path)

        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected PDF document, received: {path.suffix}")

        logger.info("Parsing PDF: %s", path.name)

        pages: list[PageContent] = []

        with fitz.open(path) as document:
            metadata = dict(document.metadata or {})

            for page_index, page in enumerate(document):
                page_number = page_index + 1

                text = self._extract_text(page)
                words = text.split()

                low_text = len(words) < self.LOW_TEXT_THRESHOLD
                headings = self._detect_headings(text)
                tables = self._extract_tables(page)

                pages.append(
                    PageContent(
                        page_number=page_number,
                        text=text,
                        word_count=len(words),
                        is_low_text=low_text,
                        image_count=len(page.get_images()),
                        headings=headings,
                        tables=tables,
                    )
                )

        total_words = sum(page.word_count for page in pages)

        low_text_pages = [
            page.page_number
            for page in pages
            if page.is_low_text
        ]

        # A short page is only treated as scanned if it carries images or has no text layer;
        # a text page that is simply nearly empty (e.g. the tail of a section) needs no OCR.
        scanned_pages = [
            page.page_number
            for page in pages
            if page.is_low_text and (page.image_count > 0 or page.word_count == 0)
        ]

        logger.info(
            "Parsed %s: pages=%d words=%d low_text_pages=%d",
            path.name,
            len(pages),
            total_words,
            len(low_text_pages),
        )

        return ParsedDocument(
            filename=path.name,
            page_count=len(pages),
            metadata=metadata,
            pages=pages,
            total_word_count=total_words,
            low_text_pages=low_text_pages,
            scanned_pages=scanned_pages,
        )

    @staticmethod
    def _extract_text(page: fitz.Page) -> str:
        """Extract and normalize text while preserving page boundaries."""

        raw_text = page.get_text("text") or ""

        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in raw_text.splitlines()
        ]

        return "\n".join(line for line in lines if line)

    @classmethod
    def _detect_headings(cls, text: str) -> list[str]:
        """Detect likely HLD headings using conservative heuristics."""

        headings: list[str] = []

        for line in text.splitlines():
            value = line.strip()

            if not value or len(value) > 160:
                continue

            numbered = re.match(
                r"^(?:\d+(?:\.\d+)*|[A-Z](?:\.\d+)*)[\s.)-]+.+",
                value,
            )

            uppercase = (
                len(value.split()) <= 12
                and value.upper() == value
                and any(char.isalpha() for char in value)
            )

            if numbered or uppercase:
                headings.append(value)

        return list(dict.fromkeys(headings))

    @staticmethod
    def _extract_tables(page: fitz.Page) -> list[list[list[str]]]:
        """
        Extract tables when PyMuPDF detects them.

        The parser deliberately keeps table extraction separate from OCR
        because scanned tables require a different processing path.
        """

        tables: list[list[list[str]]] = []

        try:
            finder = page.find_tables()

            for table in finder.tables:
                extracted = table.extract()

                if extracted:
                    tables.append(
                        [
                            [
                                cell.strip() if cell else ""
                                for cell in row
                            ]
                            for row in extracted
                        ]
                    )

        except Exception as exc:
            logger.warning(
                "Table extraction failed on page %d: %s",
                page.number + 1,
                exc,
            )

        return tables
