"""Verify emitted excerpts against parent text without rerunning the chunker."""

from __future__ import annotations

import re
from collections import defaultdict

from ican.ingestion.parsers import sha256

from .budget import TokenBudget
from .schema import Chunk, ChunkConfig, ParentUnit
from .structure import regions


def validate_chunks(
    parents: dict[str, list[ParentUnit]],
    chunks: list[Chunk],
    config: ChunkConfig,
    dataset_id: str,
) -> dict:
    units = {(split, u.unit_id): u for split, us in parents.items() for u in us}
    grouped = defaultdict(list)
    budget = TokenBudget(config.tokenizer)
    ids = set()
    expected_regions, inherited = {}, {}
    for split, us in parents.items():
        for u in us:
            rs, path = regions(u, inherited.get(u.source_id, []))
            inherited[u.source_id] = path
            expected_regions[(split, u.unit_id)] = {
                (r.char_start, r.char_end): r for r in rs
            }
    for c in chunks:
        if c.chunk_id in ids:
            raise ValueError("Duplicate chunk ID")
        ids.add(c.chunk_id)
        key = (c.split, c.parent_unit_id)
        if key not in units or c.dataset_id != dataset_id:
            raise ValueError("Unknown parent/split/dataset")
        u = units[key]
        if (
            not 0 <= c.char_start < c.char_end <= len(u.text)
            or c.text != u.text[c.char_start : c.char_end]
        ):
            raise ValueError("Excerpt differs from original parent range")
        digest = sha256(c.text.encode())
        identity = "|".join(
            [dataset_id, c.split, u.unit_id, str(c.char_start), str(c.char_end), digest]
        )
        if (
            c.text_sha256 != digest
            or c.chunk_id != f"chunk:{sha256(identity.encode())}"
        ):
            raise ValueError("Chunk hash/identity mismatch")
        expected_identity = (
            u.source_id,
            u.source_type,
            u.path,
            u.source_url,
            u.version,
            u.source_sha256,
            u.text_sha256,
            u.input_path,
        )
        actual_identity = (
            c.source_id,
            c.source_type,
            c.source_path,
            c.source_url,
            c.source_version,
            c.source_sha256,
            c.parent_text_sha256,
            c.parent_input_path,
        )
        if actual_identity != expected_identity:
            raise ValueError("Chunk source identity mismatch")
        location = u.location.copy()
        if u.source_type != "paper":
            # Independent line calculation; CRLF remains two original characters.
            offsets = [0] + [
                m.end()
                for m in re.finditer(r"\r\n|\r|\n", u.text)
                if m.end() < len(u.text)
            ]
            location.update(
                line_start=u.location["line_start"]
                - 1
                + sum(p <= c.char_start for p in offsets),
                line_end=u.location["line_start"]
                - 1
                + sum(p <= c.char_end - 1 for p in offsets),
            )
        if c.location != location:
            raise ValueError("Chunk location mismatch")
        provenance = []
        review = False
        for s in u.structures:
            if s.char_start < c.char_end and s.char_end > c.char_start:
                provenance.append(
                    {
                        "kind": s.kind,
                        "name": s.name,
                        "parent_char_start": s.char_start,
                        "parent_char_end": s.char_end,
                        "overlap_char_start": max(c.char_start, s.char_start),
                        "overlap_char_end": min(c.char_end, s.char_end),
                        "bbox": s.bbox,
                        "metadata": s.metadata,
                    }
                )
                review |= s.kind == "table" or s.metadata.get("review_required", False)
        if c.provenance != provenance or c.review_required != review:
            raise ValueError("Chunk provenance/review flag mismatch")
        if (
            c.tokenizer != config.tokenizer
            or c.text_tokens != budget.count(c.text)
            or c.embedding_tokens != budget.count(c.embedding_text)
        ):
            raise ValueError("Token counts mismatch")
        if (
            c.embedding_tokens > config.max_tokens
            or budget.count(c.embedding_context) > config.max_context_tokens
        ):
            raise ValueError("Token budget exceeded")
        a, b = c.metadata["region_char_start"], c.metadata["region_char_end"]
        if not 0 <= a <= c.char_start < c.char_end <= b <= len(u.text):
            raise ValueError("Chunk outside structure region")
        r = expected_regions[key].get((a, b))
        if r is None or (c.structure_kind, c.structure_name, c.context_path) != (
            r.kind,
            r.name,
            r.context,
        ):
            raise ValueError("Structure boundary/name/context mismatch")
        # Construct the expected embedding prefix from provenance fields rather
        # than invoking chunks_for_region or trusting its serialized metadata.
        parts = [f"Source: {u.path}", f"Version: {u.version}"]
        if u.title:
            parts.append(f"Title: {u.title}")
        if r.context:
            parts.append("Context: " + " > ".join(r.context))
        if r.name and r.name not in r.context:
            parts.append(f"Structure: {r.name}")
        if r.review_required:
            parts.insert(0, "Table structure candidate; manual verification required.")
        context, truncated = budget.bounded_context(
            "\n".join(parts), config.max_context_tokens
        )
        if (
            c.embedding_context != context
            or c.metadata["context_truncated"] != truncated
        ):
            raise ValueError("Embedding context/truncation mismatch")
        if c.metadata["context_token_limit"] != config.max_context_tokens:
            raise ValueError("Context limit mismatch")
        lines = u.text[a:b].splitlines()
        header = ""
        if r.kind == "table":
            for index, line in enumerate(lines):
                if line.startswith("|"):
                    header = "\n".join(lines[index : index + 2])
                    break
        if c.metadata["table_header_context"] != header:
            raise ValueError("Table header context mismatch")
        if c.metadata["split_inside_structure"] != (c.char_start > a or c.char_end < b):
            raise ValueError("Structure split flag mismatch")
        if c.metadata["parent_metadata"] != u.metadata:
            raise ValueError("Parent metadata mismatch")
        grouped[key].append(c)
    nonwhite = 0
    for key, u in units.items():
        covered = bytearray(len(u.text))
        previous_by_region = {}
        last = None
        for c in sorted(grouped[key], key=lambda c: c.char_start):
            covered[c.char_start : c.char_end] = b"\x01" * len(c.text)
            region = (c.metadata["region_char_start"], c.metadata["region_char_end"])
            if (
                last
                and c.char_start < last.char_end
                and region
                != (
                    last.metadata["region_char_start"],
                    last.metadata["region_char_end"],
                )
            ):
                raise ValueError("Overlap across different structure regions")
            previous = previous_by_region.get(region)
            overlap_end = max(
                c.char_start, previous.char_end if previous else c.char_start
            )
            overlap = budget.count(u.text[c.char_start : overlap_end])
            if (
                overlap > config.overlap_tokens
                or c.metadata["overlap_tokens"] != overlap
            ):
                raise ValueError("Overlap budget/metadata mismatch")
            if (c.metadata["overlap_char_start"], c.metadata["overlap_char_end"]) != (
                c.char_start,
                overlap_end,
            ):
                raise ValueError("Overlap range mismatch")
            if previous and c.char_start <= previous.char_start:
                raise ValueError("Chunk windows did not advance")
            previous_by_region[region] = c
            last = c
        for index, character in enumerate(u.text):
            if not character.isspace():
                nonwhite += 1
                if not covered[index]:
                    raise ValueError(f"Uncovered parent content: {u.unit_id}:{index}")
    return {
        "status": "passed",
        "chunks": len(chunks),
        "parent_units": len(units),
        "covered_nonwhitespace_characters": nonwhite,
        "checks": [
            "original_excerpt",
            "identity_and_hashes",
            "location",
            "provenance_and_review_flags",
            "token_budget",
            "overlap",
            "nonwhitespace_coverage",
            "structure_context_and_table_headers",
        ],
    }
