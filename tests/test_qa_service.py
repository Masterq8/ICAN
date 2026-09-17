import asyncio
import re
from pathlib import Path

import pytest
from test_qa_adapter import evidence

from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.qa.schema import QAConfig, QARequest
from ican.qa.service import QAService
from ican.retrieval.schema import SearchResponse


class EvidenceService:
    def __init__(self, items=None):
        self.items = [evidence()] if items is None else items

    def search(self, request):
        return SearchResponse(
            index_fingerprint="a" * 64,
            collection=request.collection,
            query=request.query,
            filters=request.filters,
            results=self.items,
        )


class FakeModel:
    name = "fake-offline"

    def __init__(self, text=None, delay=0):
        self.text = text
        self.delay = delay
        self.calls = 0

    async def call_single(self, *, messages, **kwargs):
        from lmi import LLMResult

        self.calls += 1
        await asyncio.sleep(self.delay)
        cid = re.search(r"\[?(pqac-[a-z0-9]{8})\]?", messages[1].content)[1]
        return LLMResult(
            text=self.text or f"窗口大小为7 ({cid})。",
            model=self.name,
            prompt_count=20,
            completion_count=10,
            reasoning_content="PRIVATE",
        )


def service(model, items=None, config=None):
    return QAService(
        Path("."), EvidenceService(items), config or QAConfig(), lambda: model
    )


REQUEST = QARequest(query="window?", collection="swin_v1")


@pytest.mark.asyncio
async def test_real_paperqa_query_calls_once_and_returns_locatable_citation():
    model = FakeModel()
    result = await service(model).answer(REQUEST)
    assert result.status == "answered"
    assert result.citations[0].evidence == evidence()
    assert "[1]" in result.answer
    assert result.usage.generation_calls == model.calls == 1
    assert result.usage.prompt_tokens == 20
    assert result.usage.cost_usd is None
    assert "PRIVATE" not in result.model_dump_json()


@pytest.mark.parametrize(
    "text", ["fact (pqac-deadbeef)", "fact (pqac-deadbeeff)", "fact"]
)
@pytest.mark.asyncio
async def test_invalid_or_absent_raw_citations_are_not_hidden(text):
    result = await service(FakeModel(text)).answer(REQUEST)
    assert result.status == "citation_invalid"


@pytest.mark.asyncio
async def test_no_evidence_never_constructs_model():
    def fail():
        raise AssertionError("Model must not be constructed")

    qa = service(None, [])
    qa.model_factory = fail
    result = await qa.answer(REQUEST)
    assert result.status == "insufficient_evidence"
    assert result.usage.generation_calls == 0


@pytest.mark.asyncio
async def test_review_flag_and_model_abstention():
    assert (
        await service(FakeModel(), [evidence(review=True)]).answer(REQUEST)
    ).status == "review_required"
    result = await service(FakeModel("[INSUFFICIENT_EVIDENCE] missing data")).answer(
        REQUEST
    )
    assert result.status == "insufficient_evidence"


@pytest.mark.asyncio
async def test_timeout_has_one_attempt():
    model = FakeModel(delay=0.1)
    with pytest.raises(ModelTimeout):
        await service(model, config=QAConfig(timeout_seconds=0.01)).answer(REQUEST)
    assert model.calls == 1


@pytest.mark.asyncio
async def test_missing_configuration_does_not_fallback():
    qa = service(None)

    def unavailable():
        raise ModelUnavailable("missing config")

    qa.model_factory = unavailable
    with pytest.raises(ModelUnavailable):
        await qa.answer(REQUEST)


@pytest.mark.asyncio
async def test_upstream_example_citation_is_not_silently_removed():
    from ican.qa.paperqa_adapter import context_id

    raw = f"fact ({context_id('a')}); unknown (pqac-0f650d59)"
    result = await service(FakeModel(raw)).answer(REQUEST)
    assert result.status == "citation_invalid"
    assert result.invalid_citation_ids == ["pqac-0f650d59"]
