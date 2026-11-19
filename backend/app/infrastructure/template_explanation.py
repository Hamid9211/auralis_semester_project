"""Rule-based explanation used when no LLM is configured or the LLM fails (FR-RA-04)."""

from app.domain.lab_reports import REFERENCE_RANGES, ExplanationGenerator, LabValue

DISCLAIMER = ("This explanation is for information only and is not a diagnosis. "
              "Please discuss your results with your doctor.")
NO_VALUES_MESSAGE = ("No supported lab values (HbA1c, fasting glucose, LDL cholesterol, "
                     "creatinine) were found in this report.")


class TemplateExplanationGenerator(ExplanationGenerator):
    """Builds a fixed-wording explanation; never fails, so it is the safe fallback."""

    source = "template"

    def explain(self, values: list[LabValue], report_text: str) -> str:
        """Return one line per value, a summary and the disclaimer."""
        if not values:
            return f"{NO_VALUES_MESSAGE}\n\n{DISCLAIMER}"
        lines = [self._describe(value) for value in values]
        flagged = sum(1 for value in values if not value.is_normal)
        if flagged:
            summary = f"{flagged} of {len(values)} results are outside the normal range."
        else:
            summary = "All detected results are within the normal range."
        return "\n".join([*lines, "", summary, "", DISCLAIMER])

    @staticmethod
    def _describe(value: LabValue) -> str:
        reference = REFERENCE_RANGES[value.test_name]
        if value.is_normal:
            position = "within"
        elif value.value < reference.normal_low:
            position = "below"
        else:
            position = "above"
        return (f"{reference.display_name}: {value.value:g} {value.unit} is {position} "
                f"the normal range ({reference.describe()}).")
