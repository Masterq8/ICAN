from ican.agent.schema import AgentRequest, ToolInputError
from ican.research.schema import (
    ClaimDraft,
    CodeCondition,
    ExtractionDraft,
    ExtractionFieldDraft,
    ResearchReportRequest,
    ScreeningDraft,
)
from ican.research.service import ResearchService
from ican.research.store import ResearchStore
from ican.retrieval.schema import EvidenceResult, EvidenceSource

SOURCE = """def forward(x):
    H, W = x.shape
    assert H % 2 == 0 and W % 2 == 0
    return x
"""


class Corpus:
    def __init__(self):
        self.items = {
            "paper": EvidenceResult(
                rank=1,
                score=0,
                chunk_id="paper",
                text="The model uses a patch size of 4.",
                review_required=False,
                source=EvidenceSource(
                    source_id="paper-source",
                    source_type="paper",
                    source_path="paper.pdf",
                    source_version="v1",
                    location={"page": 3},
                ),
            ),
            "merge": EvidenceResult(
                rank=1,
                score=0,
                chunk_id="merge",
                text=SOURCE,
                review_required=False,
                source=EvidenceSource(
                    source_id="paper-source",
                    source_type="code",
                    source_path="repo/model.py",
                    source_version="commit",
                    location={"line_start": 1, "line_end": 4},
                ),
            ),
        }

    def evidence(self, chunk_id):
        if chunk_id not in self.items:
            raise ToolInputError("Evidence ID is absent or outside the task scope")
        return self.items[chunk_id]

    def source_text(self, path):
        if path != "repo/model.py":
            raise ToolInputError("Source file is absent or outside the task scope")
        return SOURCE


def request():
    return AgentRequest(query="Swin merge", collection="swin_v1")


def service(tmp_path):
    corpus = Corpus()
    return ResearchService(
        tmp_path,
        None,
        None,
        corpus_factory=lambda root, config, evidence, req: corpus,
        store=ResearchStore(tmp_path / "records"),
    )


def verbatim_claim():
    return ClaimDraft(
        statement="Patch size is 4.",
        kind="verbatim",
        evidence_ids=["paper"],
        quote="patch size of 4",
    )


def blocked_claim():
    return ClaimDraft(
        statement="The next merge can execute.",
        kind="code_execution",
        evidence_ids=["merge"],
        conditions=[CodeCondition(chunk_id="merge", bindings={"H": 7, "W": 7})],
    )


def test_screening_revisions_are_append_only_and_validate_subject(tmp_path):
    research = service(tmp_path)
    first = research.submit_screening(
        request(),
        ScreeningDraft(
            subject_source_id="paper-source",
            decision="include",
            claims=[verbatim_claim()],
        ),
    )
    second = research.submit_screening(
        request(),
        ScreeningDraft(
            subject_source_id="paper-source",
            decision="hold",
            claims=[verbatim_claim()],
            revision_of=first.record_id,
        ),
    )
    assert research.store.load(first.record_id).decision == "include"
    assert research.store.load(second.record_id).revision_of == first.record_id
    assert first.record_id != second.record_id


def test_extraction_and_report_keep_blocked_claim_and_locations(tmp_path):
    research = service(tmp_path)
    record = research.submit_extraction(
        request(),
        ExtractionDraft(
            subject_source_id="paper-source",
            fields=[
                ExtractionFieldDraft(
                    name="model", value="Swin-T", claims=[verbatim_claim()]
                ),
                ExtractionFieldDraft(
                    name="limitation", value="112 input grid", claims=[blocked_claim()]
                ),
            ],
        ),
    )
    report = research.build_report(ResearchReportRequest(record_ids=[record.record_id]))
    assert "blocked_by_precondition" in report.markdown
    assert "repo/model.py:3" in report.markdown
    assert "paper.pdf:p.3" in report.markdown


def test_invalid_revision_and_unknown_report_id_are_rejected(tmp_path):
    research = service(tmp_path)
    bad = ScreeningDraft(
        subject_source_id="paper-source",
        decision="include",
        claims=[verbatim_claim()],
        revision_of="00000000-0000-4000-8000-000000000001",
    )
    try:
        research.submit_screening(request(), bad)
    except ToolInputError as error:
        assert "revision" in str(error)
    else:
        raise AssertionError("missing revision must fail")
    try:
        research.build_report(
            ResearchReportRequest(record_ids=["00000000-0000-4000-8000-000000000001"])
        )
    except ToolInputError as error:
        assert "record" in str(error)
    else:
        raise AssertionError("unknown report ID must fail")


def test_store_does_not_allow_path_like_record_ids(tmp_path):
    store = ResearchStore(tmp_path / "records")
    try:
        store.load("../.env")
    except ToolInputError:
        pass
    else:
        raise AssertionError("unsafe ID must fail")
