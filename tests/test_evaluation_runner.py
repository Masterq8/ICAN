import pytest
from test_qa_adapter import evidence

from ican.evaluation.runner import CallJournal, prepare_variant
from ican.qa.schema import QAConfig


def test_budget_persists_and_started_failure_is_not_repeated(tmp_path):
    path = tmp_path / "journal.jsonl"
    journal = CallJournal(path, 1)
    assert journal.reserve("first")
    assert not journal.reserve("first")
    with pytest.raises(RuntimeError, match="budget"):
        journal.reserve("second")
    assert not CallJournal(path, 1).reserve("first")
    with pytest.raises(RuntimeError, match="budget"):
        CallJournal(path, 1).reserve("second")


@pytest.mark.asyncio
async def test_default_settings_registry_contains_only_serialized_ids():
    items = [evidence(str(i), rank=i + 1) for i in range(8)]
    prepared, serialized = await prepare_variant(
        "English question?", items, QAConfig(), "paperqa-default"
    )
    assert len(prepared.registry) == 5
    assert all(cid in serialized for cid in prepared.registry)
    assert len(prepared.dropped_chunk_ids) == 3


@pytest.mark.asyncio
async def test_eval_language_override_keeps_production_prompt_unchanged():
    from ican.qa.prompts import SYSTEM

    prepared, _ = await prepare_variant(
        "English question?", [evidence()], QAConfig(), "adapter"
    )
    assert "使用问题的语言" in prepared.settings.prompts.system
    assert "使用中文" in SYSTEM


@pytest.mark.asyncio
async def test_generation_never_sends_gold_and_resume_skips_started_dispatches(
    monkeypatch, tmp_path
):
    import json

    from test_qa_service import REQUEST, EvidenceService, FakeModel

    from ican.evaluation.data import Case, digest, read_jsonl
    from ican.evaluation.runner import generate

    case = Case("question", "swin", "dev", "window?", "swin_v1", {})
    config_dir = tmp_path / "configs/qa"
    config_dir.mkdir(parents=True)
    (config_dir / "v1.json").write_text(QAConfig().model_dump_json(), encoding="utf-8")
    manifest = {
        "protocol": {"variants": ["adapter", "paperqa-default"]},
        "input_sha256": {},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    search = EvidenceService().search(REQUEST).model_dump()
    (tmp_path / "retrieval.jsonl").write_text(
        json.dumps({"key": case.key, "case": case.record(), "response": search}) + "\n",
        encoding="utf-8",
    )
    manifest["retrieval_sha256"] = digest(tmp_path / "retrieval.jsonl")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    item = search["results"][0]
    monkeypatch.setattr(
        "ican.evaluation.runner.load_chunk_registry",
        lambda _: {
            item["chunk_id"]: {
                **item["source"],
                "text": item["text"],
                "review_required": item["review_required"],
            }
        },
    )
    monkeypatch.setattr(
        "ican.evaluation.runner.load_inputs",
        lambda _: ([case], {case.key: {"gold": "DO_NOT_SEND_GOLD"}}, {}),
    )
    monkeypatch.setattr(
        "ican.evaluation.runner.protocol", lambda *args: manifest["protocol"]
    )
    messages = []

    class Model(FakeModel):
        async def call_single(self, **kwargs):
            messages.extend(m.content for m in kwargs["messages"])
            return await super().call_single(**kwargs)

    model = Model()
    with pytest.raises(RuntimeError, match="budget"):
        await generate(tmp_path, tmp_path, 1, lambda: model)
    assert model.calls == 1
    assert "DO_NOT_SEND_GOLD" not in " ".join(messages)
    await generate(tmp_path, tmp_path, 2, lambda: model)
    await generate(tmp_path, tmp_path, 2, lambda: model)
    assert model.calls == 2
    assert (
        len(
            [
                r
                for r in read_jsonl(tmp_path / "journal.jsonl")
                if r["event"] == "started"
            ]
        )
        == 2
    )
