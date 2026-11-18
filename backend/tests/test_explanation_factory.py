"""Factory Method: the configuration decides which generator is created."""

from app.core.config import Settings
from app.infrastructure.explanation_factory import ExplanationGeneratorFactory
from app.infrastructure.groq_adapter import GroqExplanationAdapter
from app.infrastructure.template_explanation import TemplateExplanationGenerator


def test_without_api_key_creates_template_generator():
    generator = ExplanationGeneratorFactory(Settings(groq_api_key=None)).create()
    assert isinstance(generator, TemplateExplanationGenerator)


def test_with_api_key_creates_groq_adapter_with_configured_model():
    settings = Settings(groq_api_key="test-key", groq_model="test-model")
    generator = ExplanationGeneratorFactory(settings).create()
    assert isinstance(generator, GroqExplanationAdapter)
    assert generator.model == "test-model"
    assert generator.source == "llm"


def test_fallback_is_always_the_template_generator():
    assert isinstance(ExplanationGeneratorFactory.create_fallback(),
                      TemplateExplanationGenerator)
