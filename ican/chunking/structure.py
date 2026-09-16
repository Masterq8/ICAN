"""Partition parent text into non-overlapping regions without losing gaps."""

from __future__ import annotations

import re
from itertools import pairwise

from .schema import ParentUnit, Region


def section_path(previous: list[str], heading: str) -> list[str]:
    number = re.match(r"^(A?\d+(?:\.\d+)*)\.?\s+", heading)
    if not number:
        if heading.strip().casefold() not in {
            "abstract",
            "references",
            "acknowledgement",
            "acknowledgments",
            "acknowledgements",
        }:
            # Unnumbered minor headings under a numbered section retain that
            # ancestry. Subsequent numbered siblings replace the minor heading.
            numbered = [p for p in previous if re.match(r"^(A?\d+(?:\.\d+)*)\.?\s+", p)]
            if numbered:
                return numbered + [heading]
        return [heading]
    depth = len(number.group(1).split("."))
    return previous[: depth - 1] + [heading]


def regions(
    unit: ParentUnit, inherited: list[str] | None = None
) -> tuple[list[Region], list[str]]:
    if not unit.structures:
        context = list(unit.metadata.get("section_path", inherited or []))
        kind = (
            "caption"
            if "caption_index" in unit.location
            else "paragraph"
            if unit.source_type == "paper"
            else "file_text"
        )
        return [
            Region(
                char_start=0,
                char_end=len(unit.text),
                kind=kind,
                context=context,
            )
        ], context
    for span in unit.structures:
        if not 0 <= span.char_start < span.char_end <= len(unit.text):
            raise ValueError(f"Invalid parent structure: {unit.unit_id}/{span.name}")
    points = sorted(
        {0, len(unit.text)}
        | {p for s in unit.structures for p in (s.char_start, s.char_end)}
    )
    result = []
    current = list(inherited or [])
    for start, end in pairwise(points):
        active = [
            s for s in unit.structures if s.char_start <= start and s.char_end >= end
        ]
        active.sort(key=lambda s: (-(s.char_end - s.char_start), s.name))
        owner = active[-1] if active else None
        kind = owner.kind if owner else "file_text"
        name = owner.name if owner else ""
        if unit.source_type == "paper":
            if owner and owner.kind in {"section_header", "heading_candidate"}:
                current = section_path(
                    current, unit.text[owner.char_start : owner.char_end]
                )
            context = current[:]
        else:
            context = [s.name for s in active]
        review = any(
            s.kind == "table" or s.metadata.get("review_required", False)
            for s in active
        )
        region = Region(
            char_start=start,
            char_end=end,
            kind=kind,
            name=name,
            context=context,
            review_required=review,
        )
        if result and (
            result[-1].kind,
            result[-1].name,
            result[-1].context,
            result[-1].review_required,
        ) == (kind, name, context, review):
            result[-1].char_end = end
        else:
            result.append(region)
    return result, current
