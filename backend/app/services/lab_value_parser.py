"""Detection and classification of lab values in report text (FR-RA-03)."""

import re
from dataclasses import dataclass

from app.domain.lab_reports import (
    CREATININE,
    FASTING_GLUCOSE,
    HBA1C,
    LDL_CHOLESTEROL,
    REFERENCE_RANGES,
    LabValue,
    ReferenceRange,
)

# Up to 40 characters of label text (no digits, no line break) between the
# test name and its number, e.g. "HbA1c (%) : 6.8" or "LDL-C ........ 130".
_GAP = r"[^\d\n]{0,40}?"
# A number not glued to a letter, so the "1" in "(A1c)" is not read as a value.
_NUMBER = r"(?<![A-Za-z])(\d+(?:\.\d+)?)"

_NAME_PATTERNS: dict[str, str] = {
    HBA1C: r"\b(?:hb\s*a1c|a1c|glycated\s+ha?emoglobin)",
    FASTING_GLUCOSE: r"\b(?:fasting\s+(?:blood\s+|plasma\s+)?(?:glucose|sugar)|fbs|fpg)\b",
    LDL_CHOLESTEROL: r"\b(?:ldl(?:[\s-]*c(?:holesterol)?)?|low[\s-]density\s+lipoprotein)\b",
    CREATININE: r"\b(?:serum\s+)?creatinine\b",
}


@dataclass(frozen=True)
class _CompiledTest:
    reference: ReferenceRange
    pattern: re.Pattern[str]


class LabValueParser:
    """Finds the four supported lab values in text and marks each normal or not."""

    def __init__(self) -> None:
        self._tests = [
            _CompiledTest(REFERENCE_RANGES[name],
                          re.compile(pattern + _GAP + _NUMBER, re.IGNORECASE))
            for name, pattern in _NAME_PATTERNS.items()
        ]

    @staticmethod
    def classify(test_name: str, value: float) -> LabValue:
        """Build a LabValue with its normal/out-of-range flag."""
        reference = REFERENCE_RANGES[test_name]
        return LabValue(test_name=test_name, value=value, unit=reference.unit,
                        is_normal=reference.is_normal(value))

    def parse(self, text: str) -> list[LabValue]:
        """Return the first plausible value found for each supported test."""
        found: list[LabValue] = []
        for test in self._tests:
            for match in test.pattern.finditer(text):
                value = float(match.group(1))
                if test.reference.is_plausible(value):
                    found.append(self.classify(test.reference.test_name, value))
                    break
        return found
