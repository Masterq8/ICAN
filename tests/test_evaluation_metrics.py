from ican.evaluation.metrics import (
    intervals_cover,
    qasper_references,
    score_qasper_retrieval,
    score_swin,
    unit_coverage,
)


def test_intervals_require_union_without_gaps():
    assert intervals_cover([(2, 8)], [(0, 4), (4, 9)])
    assert not intervals_cover([(2, 8)], [(2, 4), (5, 8)])


def test_additional_path_is_required_for_complete_repository_evidence():
    spec = {
        "id": "R13",
        "type": "repository",
        "path": "optimizer.py",
        "lines": "1-3",
        "additional_path": "models/swin.py:5-6",
    }
    chunks = [
        {
            "source_path": "data/raw/repositories/Swin-Transformer/optimizer.py",
            "location": {"line_start": 1, "line_end": 3},
        }
    ]
    result = score_swin(["R13"], {"R13": spec}, chunks)
    assert result["locator_recall"] == 1
    assert result["repository_complete_recall"] == 0


def test_page_hit_is_explicitly_a_proxy_and_not_strict_completion():
    spec = {"P01": {"type": "paper", "path": "p.pdf", "page": 3}}
    result = score_swin(
        ["P01"], spec, [{"source_path": "p.pdf", "location": {"page": 3}}]
    )
    assert result["locator_recall"] == 1
    assert result["repository_complete_recall"] is None


def test_split_paragraph_needs_complete_non_whitespace_coverage():
    corpus = {"u": "abc def"}
    first = {"parent_unit_id": "u", "char_start": 0, "char_end": 3}
    second = {"parent_unit_id": "u", "char_start": 4, "char_end": 7}
    assert unit_coverage([first], corpus) == ({"u"}, set())
    assert unit_coverage([first, second], corpus) == ({"u"}, {"u"})


def test_multiple_official_references_include_false_boolean():
    refs = qasper_references(
        {
            "answers": [
                {
                    "unanswerable": False,
                    "extractive_spans": [],
                    "free_form_answer": "",
                    "yes_no": False,
                    "evidence": [],
                    "evidence_unit_ids": [],
                },
                {"unanswerable": True, "evidence": [], "evidence_unit_ids": []},
            ]
        }
    )
    assert [r["answer"] for r in refs] == ["No", "Unanswerable"]


def test_evidence_free_annotations_have_explicit_denominators():
    item = {
        "answers": [
            {"unanswerable": False, "evidence_unit_ids": []},
            {"unanswerable": True, "evidence_unit_ids": []},
            {"unanswerable": False, "evidence_unit_ids": ["u"]},
        ]
    }
    result = score_qasper_retrieval(item, [], {"u": "text"})
    assert result["answerable_without_evidence_annotations"] == 1
    assert result["unanswerable_annotations"] == 1
    assert result["reference_evidence_counts"] == [0, 0, 1]
    assert result["complete_unit_recall"] == 0
