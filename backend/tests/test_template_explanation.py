"""FR-RA-04: the template explanation is always available and describes every value."""

from app.domain.lab_reports import CREATININE, HBA1C, LDL_CHOLESTEROL
from app.infrastructure.template_explanation import (
    DISCLAIMER,
    NO_VALUES_MESSAGE,
    TemplateExplanationGenerator,
)
from app.services.lab_value_parser import LabValueParser

classify = LabValueParser.classify


def test_source_is_template():
    assert TemplateExplanationGenerator().source == "template"


def test_each_value_is_explained_with_its_range():
    text = TemplateExplanationGenerator().explain(
        [classify(HBA1C, 6.8), classify(CREATININE, 0.9)], "")
    assert "HbA1c: 6.8 % is above the normal range (4-5.6 %)." in text
    assert "Creatinine: 0.9 mg/dL is within the normal range (0.6-1.3 mg/dL)." in text


def test_low_value_is_described_as_below():
    text = TemplateExplanationGenerator().explain([classify(CREATININE, 0.4)], "")
    assert "is below the normal range" in text


def test_summary_counts_out_of_range_values():
    values = [classify(HBA1C, 6.8), classify(LDL_CHOLESTEROL, 130), classify(CREATININE, 1.0)]
    text = TemplateExplanationGenerator().explain(values, "")
    assert "2 of 3 results are outside the normal range." in text


def test_summary_when_all_values_are_normal():
    text = TemplateExplanationGenerator().explain([classify(HBA1C, 5.0)], "")
    assert "All detected results are within the normal range." in text


def test_no_values_gives_a_clear_message():
    text = TemplateExplanationGenerator().explain([], "some text")
    assert NO_VALUES_MESSAGE in text


def test_explanation_is_never_empty_and_has_disclaimer():
    for values in ([], [classify(HBA1C, 5.0)]):
        text = TemplateExplanationGenerator().explain(values, "")
        assert text.strip()
        assert text.endswith(DISCLAIMER)
