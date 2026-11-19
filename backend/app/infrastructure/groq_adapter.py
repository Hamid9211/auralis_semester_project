"""Adapter from the Groq SDK to the ExplanationGenerator interface (Adapter pattern).

Only this module knows the Groq SDK. Groq exceptions are translated into
ExplanationError, so no vendor exception crosses the module boundary.
"""

from typing import Any

import groq

from app.core.config import Settings
from app.core.exceptions import ExplanationError
from app.domain.lab_reports import REFERENCE_RANGES, ExplanationGenerator, LabValue

SYSTEM_PROMPT = (
    "You explain lab results to a patient with diabetes in plain, friendly language. "
    "For each value say what the test measures and what the result means. Do not "
    "diagnose and do not suggest medicines. Keep it under 150 words and end by "
    "advising the patient to discuss the results with their doctor."
)
TEMPERATURE = 0.2
MAX_TOKENS = 400
MAX_RETRIES = 1


def build_user_prompt(values: list[LabValue]) -> str:
    """Describe the detected values only.

    The raw report text is never sent, because it contains the patient's
    name and other personal details.
    """
    if not values:
        return "No supported lab values were found in the report."
    lines = []
    for value in values:
        reference = REFERENCE_RANGES[value.test_name]
        status = "normal" if value.is_normal else "out of range"
        lines.append(f"- {reference.display_name}: {value.value:g} {value.unit} "
                     f"(normal range {reference.describe()}, {status})")
    return "Lab results:\n" + "\n".join(lines)


class GroqExplanationAdapter(ExplanationGenerator):
    """Explains lab values using a Groq-hosted LLM."""

    source = "llm"

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def from_settings(cls, settings: Settings) -> "GroqExplanationAdapter":
        """Create the adapter with a real Groq client (no network call happens here)."""
        client = groq.Groq(api_key=settings.groq_api_key,
                           timeout=settings.llm_timeout_seconds,
                           max_retries=MAX_RETRIES)
        return cls(client, settings.groq_model)

    @property
    def model(self) -> str:
        """Name of the Groq model used."""
        return self._model

    def explain(self, values: list[LabValue], report_text: str) -> str:
        """Ask the LLM for an explanation; raise ExplanationError on any API problem."""
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(values)},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
        except groq.APIError as exc:
            raise ExplanationError(
                f"LLM request failed ({type(exc).__name__})."
            ) from exc

        choices = getattr(completion, "choices", None) or []
        content = (choices[0].message.content or "").strip() if choices else ""
        if not content:
            raise ExplanationError("LLM returned an empty explanation.")
        return content
