from ican.ingestion.qasper import convert_papers


def test_qasper_evidence_mapping_and_labels_are_isolated():
    answer = {
        "unanswerable": False,
        "extractive_spans": [],
        "yes_no": None,
        "free_form_answer": "GOLD_SECRET",
        "evidence": ["first paragraph", "FLOAT SELECTED: table caption", "unavailable"],
        "highlighted_evidence": [],
    }
    paper = {
        "id": "0000.00001",
        "title": "paper",
        "full_text": {
            "section_name": ["Intro"],
            "paragraphs": [["first paragraph", "", "other text"]],
        },
        "figures_and_tables": {"caption": ["table caption"]},
        "qas": {
            "question_id": ["q1"],
            "question": ["How?"],
            "answers": [{"answer": [answer]}],
        },
    }
    corpus, questions = convert_papers([paper], "train")
    assert len(corpus) == 3
    assert all(
        "answers" not in u and "question" not in u and "GOLD_SECRET" not in u["text"]
        for u in corpus
    )
    gold = questions[0]["answers"][0]
    assert len(gold["evidence_unit_ids"]) == 2
    assert gold["unmatched_evidence"] == ["unavailable"]
    assert "page" not in corpus[0]["location"]


def test_duplicate_paragraphs_are_reported_as_ambiguous():
    paper = {
        "id": "p",
        "title": "paper",
        "full_text": {"section_name": ["Intro"], "paragraphs": [["same", "same"]]},
        "qas": {
            "question_id": ["q"],
            "question": ["why"],
            "answers": [{"answer": [{"evidence": ["same"]}]}],
        },
    }
    _, questions = convert_papers([paper], "validation")
    gold = questions[0]["answers"][0]
    assert len(gold["evidence_unit_ids"]) == 2
    assert len(gold["ambiguous_evidence_matches"]) == 1
