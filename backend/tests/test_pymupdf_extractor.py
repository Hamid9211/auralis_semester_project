"""The PyMuPDF adapter extracts text and translates library errors (FR-RA-03, NFR-03)."""

from pathlib import Path

import pytest

from app.core.exceptions import ExtractionError
from app.infrastructure.pymupdf_extractor import PyMuPDFTextExtractor
from app.services.lab_value_parser import LabValueParser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(name="extractor")
def fixture_extractor() -> PyMuPDFTextExtractor:
    return PyMuPDFTextExtractor()


def test_extracts_text_from_a_real_pdf(extractor):
    text = extractor.extract((FIXTURES / "sample_lab_report.pdf").read_bytes())
    assert "City Diagnostic Laboratory" in text
    assert "HbA1c" in text


def test_extracted_text_contains_all_four_lab_values(extractor):
    text = extractor.extract((FIXTURES / "sample_lab_report.pdf").read_bytes())
    assert len(LabValueParser().parse(text)) == 4


@pytest.mark.parametrize("data", [b"%PDF-1.4\nthis is not really a pdf", b"not a pdf at all"])
def test_corrupt_file_raises_extraction_error(extractor, data):
    with pytest.raises(ExtractionError):
        extractor.extract(data)


def test_pdf_without_text_raises_extraction_error(extractor):
    with pytest.raises(ExtractionError, match="No text"):
        extractor.extract((FIXTURES / "no_text.pdf").read_bytes())
