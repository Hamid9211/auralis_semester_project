"""Factory Method that decides which explanation generator to use.

ReportService never creates a concrete generator itself; it receives the
product of create(). Adding a new LLM provider means a new adapter class and
one new branch here, with no change to ReportService.
"""

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.domain.lab_reports import ExplanationGenerator
from app.infrastructure.groq_adapter import GroqExplanationAdapter
from app.infrastructure.template_explanation import TemplateExplanationGenerator

logger = get_logger("reports.factory")


class ExplanationGeneratorFactory:
    """Creates the primary ExplanationGenerator from the configuration."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self) -> ExplanationGenerator:
        """Return the Groq adapter when an API key is set, otherwise the template generator."""
        if self._settings.llm_enabled:
            logger.info("Using Groq model %s for explanations", self._settings.groq_model)
            return GroqExplanationAdapter.from_settings(self._settings)
        logger.info("No GROQ_API_KEY set; using template explanations")
        return TemplateExplanationGenerator()

    @staticmethod
    def create_fallback() -> ExplanationGenerator:
        """Return the generator used when the primary one fails (never fails itself)."""
        return TemplateExplanationGenerator()
