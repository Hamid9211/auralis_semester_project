"""FR-RA-03: detect the four lab values and classify them (EP + BVA on reference ranges)."""

import pytest

from app.domain.lab_reports import (
    CREATININE,
    FASTING_GLUCOSE,
    HBA1C,
    LDL_CHOLESTEROL,
    REFERENCE_RANGES,
    LabValue,
)
from app.services.lab_value_parser import LabValueParser

SAMPLE_REPORT = """
City Diagnostic Laboratory
Patient: Demo Patient
HbA1c (%)                     6.8        4.0 - 5.6
Fasting Blood Glucose         126 mg/dL  70 - 99
LDL Cholesterol               130 mg/dL  < 100
Serum Creatinine              0.9 mg/dL  0.6 - 1.3
"""


@pytest.fixture(name="parser")
def fixture_parser() -> LabValueParser:
    return LabValueParser()


def _by_name(values: list[LabValue]) -> dict[str, LabValue]:
    return {v.test_name: v for v in values}


# --- Boundary value analysis on the normal ranges -------------------------------

@pytest.mark.parametrize(
    ("test_name", "value", "expected_normal"),
    [
        (HBA1C, 3.9, False), (HBA1C, 4.0, True), (HBA1C, 5.6, True), (HBA1C, 5.7, False),
        (FASTING_GLUCOSE, 69, False), (FASTING_GLUCOSE, 70, True),
        (FASTING_GLUCOSE, 99, True), (FASTING_GLUCOSE, 100, False),
        (LDL_CHOLESTEROL, 99, True), (LDL_CHOLESTEROL, 100, False),
        (CREATININE, 0.5, False), (CREATININE, 0.6, True),
        (CREATININE, 1.3, True), (CREATININE, 1.4, False),
    ],
)
def test_classification_at_range_boundaries(test_name, value, expected_normal):
    result = LabValueParser.classify(test_name, value)
    assert result.is_normal is expected_normal
    assert result.unit == REFERENCE_RANGES[test_name].unit


# --- Detection -------------------------------------------------------------------

def test_detects_all_four_values_in_a_typical_report(parser):
    values = _by_name(parser.parse(SAMPLE_REPORT))
    assert set(values) == {HBA1C, FASTING_GLUCOSE, LDL_CHOLESTEROL, CREATININE}
    assert values[HBA1C].value == 6.8 and values[HBA1C].is_normal is False
    assert values[FASTING_GLUCOSE].value == 126
    assert values[LDL_CHOLESTEROL].value == 130
    assert values[CREATININE].value == 0.9 and values[CREATININE].is_normal is True


@pytest.mark.parametrize(
    ("text", "test_name", "value"),
    [
        ("HbA1c: 7.2 %", HBA1C, 7.2),
        ("Hb A1c 5.4", HBA1C, 5.4),
        ("Glycated Haemoglobin (A1c) 6.1", HBA1C, 6.1),
        ("FBS 92 mg/dL", FASTING_GLUCOSE, 92),
        ("Fasting Plasma Glucose : 101", FASTING_GLUCOSE, 101),
        ("LDL-C 88", LDL_CHOLESTEROL, 88),
        ("Low Density Lipoprotein 145 mg/dL", LDL_CHOLESTEROL, 145),
        ("CREATININE 1.1", CREATININE, 1.1),
    ],
)
def test_detects_common_label_variants(parser, text, test_name, value):
    values = _by_name(parser.parse(text))
    assert values[test_name].value == value


def test_label_case_does_not_matter(parser):
    assert _by_name(parser.parse("hba1c 6.0"))[HBA1C].value == 6.0


def test_text_without_supported_values_gives_empty_list(parser):
    assert parser.parse("Complete Blood Count\nHaemoglobin 13.5 g/dL") == []


def test_empty_text_gives_empty_list(parser):
    assert parser.parse("") == []


def test_value_in_another_unit_is_ignored(parser):
    # 48 mmol/mol is a valid HbA1c, but not a percentage, so it must not be read as 48 %.
    assert parser.parse("HbA1c 48 mmol/mol") == []


def test_first_plausible_value_is_used(parser):
    values = _by_name(parser.parse("HbA1c 48 mmol/mol\nHbA1c 6.5 %"))
    assert values[HBA1C].value == 6.5


def test_number_on_the_next_line_is_not_taken(parser):
    assert parser.parse("Creatinine\n\n1.0") == []


def test_values_are_immutable(parser):
    value = parser.parse("HbA1c 6.0")[0]
    with pytest.raises(AttributeError):
        value.value = 5.0  # type: ignore[misc]
