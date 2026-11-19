"""Adapter from PyMuPDF to the TextExtractor interface (Adapter pattern).

Only this module knows PyMuPDF. Its exceptions are translated into ExtractionError.
"""

import pymupdf

from app.core.exceptions import ExtractionError
from app.domain.lab_reports import TextExtractor


class PyMuPDFTextExtractor(TextExtractor):
    """Reads the text layer of every page of a PDF."""

    def extract(self, pdf_bytes: bytes) -> str:
        """Return the PDF text; raise ExtractionError for corrupt or image-only PDFs."""
        try:
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
                text = "\n".join(page.get_text() for page in document)
        # PyMuPDF raises FileDataError (a RuntimeError) for damaged files and
        # ValueError for empty input.
        except (RuntimeError, ValueError) as exc:
            raise ExtractionError("The file could not be read as a PDF.") from exc
        if not text.strip():
            raise ExtractionError(
                "No text was found in the PDF. It may be a scanned image."
            )
        return text
