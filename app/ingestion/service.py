from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import DocumentProcessingError
from app.core.logging import get_logger
from app.ingestion.document_validator import validate_document
from app.ingestion.metadata import build_document_metadata
from app.ingestion.ocr import OCRProcessor
from app.ingestion.pdf_parser import ParsedDocument, PDFParser

logger = get_logger(__name__)


@dataclass
class IngestedDocument:
    metadata: dict
    parsed_document: ParsedDocument
    ocr_pages: dict[int, str]


class DocumentIngestionService:
    """Orchestrates document validation, parsing, OCR and metadata."""

    def __init__(
        self,
        parser: PDFParser | None = None,
        ocr_processor: OCRProcessor | None = None,
    ):
        self.parser = parser or PDFParser()
        self.ocr_processor = ocr_processor or OCRProcessor()

    def ingest(self, pdf_path: str | Path) -> IngestedDocument:
        path = Path(pdf_path)

        validation = validate_document(path)

        if not validation.is_valid:
            raise DocumentProcessingError(
                "; ".join(validation.errors)
            )

        try:
            parsed = self.parser.parse(path)

            metadata = build_document_metadata(
                path=path,
                page_count=parsed.page_count,
                pdf_metadata=parsed.metadata,
            )

            ocr_pages = {}

            if parsed.scanned_pages:
                logger.info(
                    "Detected %d scanned pages. Running OCR fallback.",
                    len(parsed.scanned_pages),
                )

                ocr_pages = self.ocr_processor.process_low_text_pages(
                    path,
                    parsed.scanned_pages,
                )

                for page in parsed.pages:
                    if page.page_number in ocr_pages:
                        ocr_text = ocr_pages[page.page_number]

                        if len(ocr_text.split()) > page.word_count:
                            page.text = ocr_text
                            page.word_count = len(ocr_text.split())
                            page.is_low_text = False

            return IngestedDocument(
                metadata=metadata,
                parsed_document=parsed,
                ocr_pages=ocr_pages,
            )

        except DocumentProcessingError:
            raise

        except Exception as exc:
            logger.exception("Document ingestion failed")
            raise DocumentProcessingError(
                f"Failed to process document '{path.name}': {exc}"
            ) from exc
