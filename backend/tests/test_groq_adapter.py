"""The Groq adapter honours the ExplanationGenerator contract (FR-RA-04, NFR-03)."""

from types import SimpleNamespace

import groq
import httpx
import pytest

from app.core.exceptions import ExplanationError
from app.domain.lab_reports import HBA1C, LDL_CHOLESTEROL
from app.infrastructure.groq_adapter import GroqExplanationAdapter, build_user_prompt
from app.services.lab_value_parser import LabValueParser

VALUES = [LabValueParser.classify(HBA1C, 6.8), LabValueParser.classify(LDL_CHOLESTEROL, 80)]
_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


class FakeCompletions:
    """Stands in for client.chat.completions; records the call it receives."""

    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.reply


def _client(completions: FakeCompletions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _reply(content):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_returns_the_llm_text():
    completions = FakeCompletions(reply=_reply("  Your HbA1c is high.  "))
    adapter = GroqExplanationAdapter(_client(completions), "test-model")
    assert adapter.explain(VALUES, "raw text") == "Your HbA1c is high."
    assert adapter.source == "llm"


def test_sends_values_but_never_the_raw_report_text():
    completions = FakeCompletions(reply=_reply("ok"))
    GroqExplanationAdapter(_client(completions), "test-model").explain(
        VALUES, "Patient: Ali Khan, CNIC 12345")
    call = completions.calls[0]
    assert call["model"] == "test-model"
    sent = " ".join(m["content"] for m in call["messages"])
    assert "HbA1c: 6.8 %" in sent and "out of range" in sent
    assert "Ali Khan" not in sent


@pytest.mark.parametrize(
    "error",
    [
        groq.APIConnectionError(request=_REQUEST),
        groq.APITimeoutError(request=_REQUEST),
        groq.RateLimitError("rate limited", response=httpx.Response(429, request=_REQUEST),
                            body=None),
        groq.AuthenticationError("bad key", response=httpx.Response(401, request=_REQUEST),
                                 body=None),
    ],
)
def test_groq_errors_become_explanation_error(error):
    adapter = GroqExplanationAdapter(_client(FakeCompletions(error=error)), "m")
    with pytest.raises(ExplanationError) as info:
        adapter.explain(VALUES, "")
    assert isinstance(info.value.__cause__, groq.APIError)


@pytest.mark.parametrize("reply", [_reply(""), _reply(None), _reply("   "),
                                   SimpleNamespace(choices=[])])
def test_empty_reply_becomes_explanation_error(reply):
    adapter = GroqExplanationAdapter(_client(FakeCompletions(reply=reply)), "m")
    with pytest.raises(ExplanationError):
        adapter.explain(VALUES, "")


def test_prompt_for_no_values():
    assert build_user_prompt([]) == "No supported lab values were found in the report."
