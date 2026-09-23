from ican.research.auto_schema import CardFieldDraft
from ican.research.confidence import project_fields
from ican.retrieval.schema import EvidenceResult, EvidenceSource


def evidence(source_id="paper-a", text="ImageNet top-1 accuracy is 84.2%."):
    return EvidenceResult(
        rank=1,
        score=1.0,
        chunk_id="e1",
        text=text,
        review_required=False,
        source=EvidenceSource(
            source_id=source_id,
            source_type="paper",
            source_path=f"papers/{source_id}.pdf",
            source_version="v1",
            location={"page": 1},
        ),
    )


def test_projector_requires_same_paper_exact_quote_and_no_rule_conflict():
    fields = [
        CardFieldDraft(
            name="dataset", value="ImageNet", quote="ImageNet", evidence_id="e1"
        ),
        CardFieldDraft(
            name="result",
            value="the ImageNet dataset",
            quote="ImageNet",
            evidence_id="e1",
        ),
        CardFieldDraft(
            name="metric",
            value="top-1 accuracy",
            quote="top 1 accuracy",
            evidence_id="e1",
        ),
        CardFieldDraft(name="model", value="Swin", quote="Swin", evidence_id="outside"),
    ]
    high, review = project_fields("paper-a", [evidence()], fields)
    assert [(item.occurrence, item.name) for item in high] == [(0, "dataset")]
    assert "field_rule:result_is_dataset" in review[0].reason_codes
    assert review[0].allowed_actions == [
        "open_evidence",
        "search_same_paper",
        "edit_and_save",
        "ignore",
    ]
    assert review[1].reason_codes == ["quote_not_exact"]
    assert review[2].reason_codes == ["evidence_out_of_scope"]


def test_cross_paper_evidence_never_becomes_high_confidence():
    field = CardFieldDraft(
        name="dataset", value="ImageNet", quote="ImageNet", evidence_id="e1"
    )
    high, review = project_fields("paper-a", [evidence(source_id="paper-b")], [field])
    assert high == []
    assert review[0].reason_codes == ["evidence_out_of_scope"]
