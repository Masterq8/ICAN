"""Convert QASPER paragraphs and isolated gold annotations for external evaluation."""

from __future__ import annotations

import re
from collections import defaultdict

from .parsers import sha256

DATASET_REVISION = "06806e4608976fc2fac0a090ac425d5b2b29caf4"
CARD_REVISION = "fdc9d8214fbab5dd782958601db4d678e6934a54"


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def convert_papers(papers: list[dict], split: str):
    corpus, questions = [], []
    for paper in papers:
        pid = paper["id"]
        evidence_map = defaultdict(list)
        full = paper["full_text"]
        if len(full["section_name"]) != len(full["paragraphs"]):
            raise ValueError(f"Section/paragraph mismatch: {pid}")
        for section, (heading, paragraphs) in enumerate(
            zip(full["section_name"], full["paragraphs"])
        ):
            for paragraph, text in enumerate(paragraphs):
                if not text.strip():
                    continue
                unit_id = f"qasper:{pid}:section:{section}:paragraph:{paragraph}"
                corpus.append(
                    {
                        "unit_id": unit_id,
                        "paper_id": pid,
                        "split": split,
                        "title": paper["title"],
                        "section": heading,
                        "location": {
                            "section_index": section,
                            "paragraph_index": paragraph,
                        },
                        "text": text,
                        "text_sha256": sha256(text.encode()),
                        "source_url": f"https://arxiv.org/abs/{pid}",
                        "dataset_revision": DATASET_REVISION,
                    }
                )
                evidence_map[normalized(text)].append(unit_id)
        # Preserve figure/table captions as caption evidence, without pretending
        # that cell values or images were supplied by the dataset.
        floats = paper.get("figures_and_tables", {})
        for index, caption in enumerate(floats.get("caption", [])):
            if not caption.strip():
                continue
            unit_id = f"qasper:{pid}:caption:{index}"
            corpus.append(
                {
                    "unit_id": unit_id,
                    "paper_id": pid,
                    "split": split,
                    "title": paper["title"],
                    "section": "figures_and_tables",
                    "location": {"caption_index": index},
                    "text": caption,
                    "text_sha256": sha256(caption.encode()),
                    "source_url": f"https://arxiv.org/abs/{pid}",
                    "dataset_revision": DATASET_REVISION,
                }
            )
            evidence_map[normalized(caption)].append(unit_id)
            evidence_map[normalized("FLOAT SELECTED: " + caption)].append(unit_id)
        qa = paper["qas"]
        if not (len(qa["question_id"]) == len(qa["question"]) == len(qa["answers"])):
            raise ValueError(f"QA arrays mismatch: {pid}")
        for qid, question, annotation_group in zip(
            qa["question_id"], qa["question"], qa["answers"]
        ):
            answers = []
            for answer in annotation_group["answer"]:
                matched, unmatched, ambiguous = [], [], []
                for evidence in answer["evidence"]:
                    ids = evidence_map.get(normalized(evidence), [])
                    matched.extend(ids)
                    if not ids:
                        unmatched.append(evidence)
                    elif len(ids) > 1:
                        ambiguous.append(ids)
                answers.append(
                    {
                        **answer,
                        "evidence_unit_ids": sorted(set(matched)),
                        "unmatched_evidence": unmatched,
                        "ambiguous_evidence_matches": ambiguous,
                    }
                )
            questions.append(
                {
                    "question_id": qid,
                    "paper_id": pid,
                    "split": split,
                    "question": question,
                    "answers": answers,
                }
            )
    return corpus, questions
