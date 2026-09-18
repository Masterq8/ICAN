import pytest

from ican.agent.schema import ToolInputError
from ican.research.claims import verify_claim
from ican.research.schema import ClaimDraft, CodeCondition, NumericCalculation
from ican.retrieval.schema import EvidenceResult, EvidenceSource

SOURCE = """def forward(x):
    H, W = x.shape
    assert H % 2 == 0 and W % 2 == 0, 'grid must be even'
    return x
"""


class Corpus:
    def __init__(self):
        self.source = SOURCE
        self.items = {
            "merge": EvidenceResult(
                rank=1,
                score=0,
                chunk_id="merge",
                text=SOURCE,
                review_required=False,
                source=EvidenceSource(
                    source_id="paper-and-code",
                    source_type="code",
                    source_path="repo/model.py",
                    source_version="fixed",
                    location={"line_start": 1, "line_end": 4},
                ),
            ),
            "paper": EvidenceResult(
                rank=1,
                score=0,
                chunk_id="paper",
                text="The model uses a patch size of 4.",
                review_required=False,
                source=EvidenceSource(
                    source_id="paper-and-code",
                    source_type="paper",
                    source_path="paper.pdf",
                    source_version="v1",
                    location={"page": 3},
                ),
            ),
            "review": EvidenceResult(
                rank=1,
                score=0,
                chunk_id="review",
                text="A parser warning applies.",
                review_required=True,
                source=EvidenceSource(
                    source_id="paper-and-code",
                    source_type="paper",
                    source_path="paper.pdf",
                    source_version="v1",
                    location={"page": 4},
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
        return self.source


@pytest.fixture
def corpus():
    return Corpus()


def test_even_grid_assert_blocks_execution_claim(corpus):
    verdict = verify_claim(
        corpus,
        ClaimDraft(
            statement="The next merge can execute.",
            kind="code_execution",
            evidence_ids=["merge"],
            conditions=[CodeCondition(chunk_id="merge", bindings={"H": 7, "W": 7})],
        ),
    )
    assert verdict.status == "blocked_by_precondition"
    assert verdict.conditions[0].expression == "H % 2 == 0 and W % 2 == 0"
    assert verdict.conditions[0].status == "failed"


def test_even_grid_assert_passes_only_when_all_bindings_are_valid(corpus):
    verdict = verify_claim(
        corpus,
        ClaimDraft(
            statement="The next merge can execute under the supplied grid dimensions.",
            kind="code_execution",
            evidence_ids=["merge"],
            conditions=[CodeCondition(chunk_id="merge", bindings={"H": 14, "W": 14})],
        ),
    )
    assert verdict.status == "supported"
    missing = verify_claim(
        corpus,
        ClaimDraft(
            statement="The next merge can execute.",
            kind="code_execution",
            evidence_ids=["merge"],
            conditions=[CodeCondition(chunk_id="merge", bindings={"H": 14})],
        ),
    )
    assert missing.status == "insufficient_evidence"


def test_verbatim_inference_review_and_numeric_claim_states(corpus):
    verbatim = verify_claim(
        corpus,
        ClaimDraft(
            statement="Patch size is 4.",
            kind="verbatim",
            evidence_ids=["paper"],
            quote="patch size of 4",
        ),
    )
    assert verbatim.status == "supported"
    absent = verify_claim(
        corpus,
        ClaimDraft(
            statement="Patch size is 8.",
            kind="verbatim",
            evidence_ids=["paper"],
            quote="patch size of 8",
        ),
    )
    assert absent.status == "insufficient_evidence"
    inference = verify_claim(
        corpus,
        ClaimDraft(
            statement="Patch size improves accuracy.",
            kind="inference",
            evidence_ids=["paper"],
        ),
    )
    assert inference.status == "requires_review"
    numeric = verify_claim(
        corpus,
        ClaimDraft(
            statement="Scaled value is 0.002.",
            kind="numeric",
            evidence_ids=["paper"],
            calculation=NumericCalculation(expression="5e-4*128*8/512*2"),
        ),
    )
    assert numeric.status == "supported"
    assert numeric.calculation.result == "0.002"
    review = verify_claim(
        corpus,
        ClaimDraft(
            statement="Parser result applies.",
            kind="verbatim",
            evidence_ids=["review"],
            quote="parser warning",
        ),
    )
    assert review.status == "requires_review"


def test_unsupported_condition_safely_becomes_insufficient_evidence(corpus):
    corpus.source = "def forward(x):\n    assert x.shape[0] > 0\n"
    corpus.items["merge"] = corpus.items["merge"].model_copy(
        update={
            "text": "def forward(x):\n    assert x.shape[0] > 0\n",
            "source": corpus.items["merge"].source.model_copy(
                update={"location": {"line_start": 1, "line_end": 2}}
            ),
        }
    )
    verdict = verify_claim(
        corpus,
        ClaimDraft(
            statement="The function can execute.",
            kind="code_execution",
            evidence_ids=["merge"],
            conditions=[CodeCondition(chunk_id="merge", bindings={"x": 1})],
        ),
    )
    assert verdict.status == "insufficient_evidence"
