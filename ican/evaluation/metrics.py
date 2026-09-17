from __future__ import annotations

import re


def intervals_cover(
    targets: list[tuple[int, int]], intervals: list[tuple[int, int]]
) -> bool:
    """Half-open intervals; union coverage, never a partial-overlap shortcut."""
    ordered = sorted(intervals)
    for start, end in targets:
        cursor = start
        for left, right in ordered:
            if right <= cursor:
                continue
            if left > cursor:
                break
            cursor = max(cursor, right)
            if cursor >= end:
                break
        if cursor < end:
            return False
    return True


def line_ranges(value: str) -> list[tuple[int, int]]:
    return [
        (int(start), int(end) + 1)
        for start, end in (piece.split("-") for piece in value.split(","))
    ]


def score_swin(required: list[str], specs: dict, chunks: list[dict]) -> dict:
    hits, complete, repository = [], [], []
    for eid in required:
        spec = specs[eid]
        path = spec["path"]
        if spec["type"] == "paper":
            if any(
                c["source_path"] == path and c["location"].get("page") == spec["page"]
                for c in chunks
            ):
                hits.append(eid)
            continue
        repository.append(eid)
        targets = [(path, line_ranges(spec["lines"]))]
        if spec.get("additional_path"):
            additional, lines = spec["additional_path"].rsplit(":", 1)
            targets.append((additional, line_ranges(lines)))
        all_covered, any_hit = True, False
        for relative, ranges in targets:
            full_path = "data/raw/repositories/Swin-Transformer/" + relative
            intervals = [
                (c["location"]["line_start"], c["location"]["line_end"] + 1)
                for c in chunks
                if c["source_path"] == full_path
            ]
            any_hit |= any(
                left < end and start < right
                for start, end in ranges
                for left, right in intervals
            )
            all_covered &= intervals_cover(ranges, intervals)
        if any_hit:
            hits.append(eid)
        if all_covered:
            complete.append(eid)
    return {
        "locator_recall": len(hits) / len(required) if required else None,
        "repository_complete_recall": len(complete) / len(repository)
        if repository
        else None,
        "required_count": len(required),
        "repository_count": len(repository),
        "locator_hit_ids": hits,
        "repository_complete_ids": complete,
        "locator_set_complete": bool(required) and len(hits) == len(required),
    }


def unit_coverage(
    chunks: list[dict], corpus: dict[str, str]
) -> tuple[set[str], set[str]]:
    intervals = {}
    for chunk in chunks:
        intervals.setdefault(chunk["parent_unit_id"], []).append(
            (chunk["char_start"], chunk["char_end"])
        )
    complete = set()
    for unit, ranges in intervals.items():
        text = corpus[unit]
        # Whitespace gaps are immaterial, but every non-whitespace character is required.
        targets = [(match.start(), match.end()) for match in re.finditer(r"\S+", text)]
        if intervals_cover(targets, ranges):
            complete.add(unit)
    return set(intervals), complete


def qasper_references(item: dict) -> list[dict]:
    references = []
    for answer in item["answers"]:
        if answer["unanswerable"]:
            text, kind = "Unanswerable", "none"
        elif answer.get("extractive_spans"):
            text, kind = ", ".join(answer["extractive_spans"]), "extractive"
        elif answer.get("free_form_answer"):
            text, kind = answer["free_form_answer"], "abstractive"
        elif answer.get("yes_no") is not None:
            text, kind = ("Yes" if answer["yes_no"] else "No"), "boolean"
        else:
            raise ValueError("Invalid QASPER answer annotation")
        references.append(
            {
                "answer": text,
                "type": kind,
                "evidence": [] if kind == "none" else answer["evidence"],
            }
        )
    return references


def score_qasper_retrieval(
    item: dict, chunks: list[dict], corpus: dict[str, str]
) -> dict:
    hit, complete = unit_coverage(chunks, corpus)
    refs = [
        a for a in item["answers"] if not a["unanswerable"] and a["evidence_unit_ids"]
    ]

    def recall(units):
        return max(
            (
                len(units.intersection(a["evidence_unit_ids"]))
                / len(a["evidence_unit_ids"])
                for a in refs
            ),
            default=None,
        )

    return {
        "unit_hit_recall": recall(hit),
        "complete_unit_recall": recall(complete),
        "answerable_evidence_annotations": len(refs),
        "annotation_count": len(item["answers"]),
        "unanswerable_annotations": sum(a["unanswerable"] for a in item["answers"]),
        "answerable_without_evidence_annotations": sum(
            not a["unanswerable"] and not a["evidence_unit_ids"]
            for a in item["answers"]
        ),
        "reference_evidence_counts": [
            len(a["evidence_unit_ids"]) for a in item["answers"]
        ],
        "per_reference": [
            {
                "required_count": len(a["evidence_unit_ids"]),
                "unit_hit_count": len(hit.intersection(a["evidence_unit_ids"])),
                "complete_unit_count": len(
                    complete.intersection(a["evidence_unit_ids"])
                ),
                "unanswerable": a["unanswerable"],
            }
            for a in item["answers"]
        ],
        "hit_units": sorted(hit),
        "complete_units": sorted(complete),
        "complete_evidence_set": any(
            set(a["evidence_unit_ids"]).issubset(complete) for a in refs
        ),
    }


def answer_for_official_score(answer: str, abstained: bool) -> str:
    if abstained:
        return "Unanswerable"
    return re.sub(r"\[\d+\]|\bpqac-[A-Za-z0-9_-]+\b", "", answer).strip()
