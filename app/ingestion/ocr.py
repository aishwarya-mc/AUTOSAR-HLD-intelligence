from __future__ import annotations

from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from app.core.logging import get_logger

logger = get_logger(__name__)


class OCRProcessor:
    """OCR fallback for scanned or low-text PDF pages."""

    def __init__(self, dpi: int = 200):
        self.dpi = dpi

    def extract_page_text(
        self,
        pdf_path: str | Path,
        page_number: int,
    ) -> str:
        path = Path(pdf_path)

        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        if page_number < 1:
            raise ValueError("Page number must be >= 1.")

        with fitz.open(path) as document:
            if page_number > len(document):
                raise ValueError(
                    f"Page {page_number} does not exist. "
                    f"Document has {len(document)} pages."
                )

            page = document[page_number - 1]

            scale = self.dpi / 72
            matrix = fitz.Matrix(scale, scale)

            pixmap = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )

            image = Image.frombytes(
                "RGB",
                [pixmap.width, pixmap.height],
                pixmap.samples,
            )

            text = pytesseract.image_to_string(image)

            logger.info(
                "OCR completed for %s page %d, characters=%d",
                path.name,
                page_number,
                len(text),
            )

            return text.strip()

    def process_low_text_pages(
        self,
        pdf_path: str | Path,
        page_numbers: list[int],
    ) -> dict[int, str]:
        """OCR multiple pages and return page-number keyed text."""

        results: dict[int, str] = {}

        for page_number in page_numbers:
            try:
                results[page_number] = self.extract_page_text(
                    pdf_path,
                    page_number,
                )
            except Exception as exc:
                logger.exception(
                    "OCR failed for page %d: %s",
                    page_number,
                    exc,
                )
                results[page_number] = ""

        return results
