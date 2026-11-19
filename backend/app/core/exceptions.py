"""Exception hierarchy shared by all modules.

Services raise these domain errors; they never raise HTTP errors.
The API layer (app.api.error_handlers) maps each one to a status code,
so business logic stays independent of the web framework.
Modules may add subclasses; a subclass inherits its parent's status code.
"""


class AuralisError(Exception):
    """Base class for every expected error in Auralis."""

    code = "auralis_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidReadingError(AuralisError):
    """Input data breaks a business rule (e.g. glucose outside 20-600 mg/dL)."""

    code = "invalid_reading"


class NotFoundError(AuralisError):
    """A requested record does not exist."""

    code = "not_found"


class InvalidFileError(AuralisError):
    """An uploaded file is not a PDF, is too large, or is a duplicate."""

    code = "invalid_file"


class ExtractionError(AuralisError):
    """Text could not be extracted from a PDF."""

    code = "extraction_failed"


class ExplanationError(AuralisError):
    """An explanation generator could not produce an explanation."""

    code = "explanation_failed"


class DuplicateReportError(InvalidFileError):
    """The same PDF was already uploaded by this patient (FR-RA-01, NFR-04)."""

    code = "duplicate_report"


class InvalidMealError(InvalidReadingError):
    """A meal or food search breaks a business rule (module M3).

    Subclass of InvalidReadingError, so it is reported as HTTP 422 without
    changing the central error table.
    """

    code = "invalid_meal"
