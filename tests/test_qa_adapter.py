import pytest

from ican.qa.paperqa_adapter import prepare_evidence
from ican.qa.schema import QAConfig
from ican.retrieval.schema import EvidenceResult


def evidence(chunk_id="a", text="WINDOW_SIZE: 7", review=False, rank=1):
    return EvidenceResult.model_validate(
        {
            "rank": rank,
            "score": 0.87,
            "chunk_id": chunk_id,
            "text": text,
            "review_required": review,
            "source": {
                "source_id": "source-" + chunk_id,
                "source_type": "config",
                "source_path": "configs/" + chunk_id + ".yaml",
                "source_version": "commit-1",
                "location": {"line_start": 12, "line_end": 14},
            },
        }
    )


@pytest.mark.asyncio
async def test_real_package_adapter_preserves_text_location_version_and_hashability():
    first, second = evidence(), evidence("b")
    prepared = await prepare_evidence("window?", [first, second], QAConfig())
    assert len(prepared.docs.docs) == 2
    assert len({hash(t) for t in prepared.docs.texts}) == 2
    for context, item in zip(prepared.session.contexts, [first, second], strict=True):
        assert context.text.text == item.text
        assert prepared.registry[context.id] == item
        assert context.score == 1  # Admission, not a fabricated LLM relevance score.
    assert prepared.session.contexts[0].id != prepared.session.contexts[1].id
    again = await prepare_evidence("different question", [first], QAConfig())
    assert again.session.contexts[0].id == prepared.session.contexts[0].id


@pytest.mark.asyncio
async def test_budget_drops_whole_trailing_chunks():
    prepared = await prepare_evidence(
        "q", [evidence(text="x" * 8), evidence("b")], QAConfig(max_context_chars=10)
    )
    assert list(prepared.registry.values()) == [evidence(text="x" * 8)]
    assert prepared.dropped_chunk_ids == ["b"]


@pytest.mark.asyncio
async def test_id_collision_is_rejected(monkeypatch):
    monkeypatch.setattr("ican.qa.paperqa_adapter.context_id", lambda _: "pqac-deadbeef")
    with pytest.raises(ValueError, match="collision"):
        await prepare_evidence("q", [evidence(), evidence("b")], QAConfig())


@pytest.mark.parametrize(
    "location", [{"page": 3}, {"section": "Method", "paragraph": 2}]
)
@pytest.mark.asyncio
async def test_paper_and_external_paragraph_locations_are_not_rewritten(location):
    item = evidence().model_copy(deep=True)
    item.source.source_type = "paper"
    item.source.location = location
    prepared = await prepare_evidence("q", [item], QAConfig())
    assert (
        prepared.registry[prepared.session.contexts[0].id].source.location == location
    )
    assert prepared.docs.texts[0].embedding is None
