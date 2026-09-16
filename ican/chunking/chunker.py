from __future__ import annotations

import bisect

from ican.ingestion.parsers import line_offsets, sha256

from .budget import TokenBudget
from .schema import Chunk, ChunkConfig, ParentUnit, Region


def region_context(unit: ParentUnit, region: Region) -> str:
    parts = [f"Source: {unit.path}", f"Version: {unit.version}"]
    if unit.title:
        parts.append(f"Title: {unit.title}")
    if region.context:
        parts.append("Context: " + " > ".join(region.context))
    if region.name and region.name not in region.context:
        parts.append(f"Structure: {region.name}")
    if region.review_required:
        parts.insert(0, "Table structure candidate; manual verification required.")
    return "\n".join(parts)


def chunks_for_region(
    unit: ParentUnit,
    region: Region,
    config: ChunkConfig,
    budget: TokenBudget,
    *,
    dataset_id: str,
    split: str,
):
    if not unit.text[region.char_start : region.char_end].strip():
        return []
    context, truncated = budget.bounded_context(
        region_context(unit, region), config.max_context_tokens
    )
    limit = config.max_tokens - budget.count(context) - 4
    result, previous_end = [], region.char_start
    offsets = line_offsets(unit.text)
    for start, end in budget.windows(
        unit.text, region.char_start, region.char_end, limit, config.overlap_tokens
    ):
        text = unit.text[start:end]
        if not text.strip():
            continue
        embedding_text = context + "\n\n" + text if context else text
        # Boundary retokenization can change BPE counts. Account for it rather
        # than trusting the sum of separately counted pieces.
        if budget.count(embedding_text) > config.max_tokens:
            raise ValueError(
                "Combined embedding budget exceeded; no chunk is silently truncated"
            )
        location = unit.location.copy()
        if unit.source_type != "paper":
            origin = unit.location["line_start"] - 1
            location["line_start"] = origin + bisect.bisect_right(offsets, start)
            location["line_end"] = origin + bisect.bisect_right(offsets, end - 1)
        provenance = []
        for span in unit.structures:
            if span.char_start < end and span.char_end > start:
                provenance.append(
                    {
                        "kind": span.kind,
                        "name": span.name,
                        "parent_char_start": span.char_start,
                        "parent_char_end": span.char_end,
                        "overlap_char_start": max(start, span.char_start),
                        "overlap_char_end": min(end, span.char_end),
                        "bbox": span.bbox,
                        "metadata": span.metadata,
                    }
                )
        digest = sha256(text.encode())
        identity = "|".join(
            [dataset_id, split, unit.unit_id, str(start), str(end), digest]
        )
        result.append(
            Chunk(
                schema_version=config.schema_version,
                chunk_id=f"chunk:{sha256(identity.encode())}",
                dataset_id=dataset_id,
                split=split,
                parent_unit_id=unit.unit_id,
                source_id=unit.source_id,
                source_type=unit.source_type,
                source_path=unit.path,
                source_url=unit.source_url,
                source_version=unit.version,
                source_sha256=unit.source_sha256,
                parent_text_sha256=unit.text_sha256,
                parent_input_path=unit.input_path,
                text=text,
                text_sha256=digest,
                char_start=start,
                char_end=end,
                location=location,
                structure_kind=region.kind,
                structure_name=region.name,
                context_path=region.context,
                provenance=provenance,
                review_required=region.review_required,
                embedding_context=context,
                embedding_text=embedding_text,
                text_tokens=budget.count(text),
                embedding_tokens=budget.count(embedding_text),
                tokenizer=config.tokenizer,
                metadata={
                    "region_char_start": region.char_start,
                    "region_char_end": region.char_end,
                    "context_truncated": truncated,
                    "context_token_limit": config.max_context_tokens,
                    "overlap_char_start": start,
                    "overlap_char_end": max(start, previous_end),
                    "overlap_tokens": budget.count(
                        unit.text[start : max(start, previous_end)]
                    ),
                    "split_inside_structure": start > region.char_start
                    or end < region.char_end,
                    "table_header_context": table_header(unit, region)
                    if region.kind == "table"
                    else "",
                    "text_backend": sorted(
                        {
                            p["metadata"].get("text_backend", "docling")
                            for p in provenance
                        }
                    )
                    if unit.source_type == "paper" and provenance
                    else [],
                    "parent_metadata": unit.metadata,
                },
            )
        )
        previous_end = end
    return result


def table_header(unit: ParentUnit, region: Region) -> str:
    lines = unit.text[region.char_start : region.char_end].splitlines()
    for index, line in enumerate(lines):
        if line.startswith("|"):
            return "\n".join(lines[index : index + 2])
    return ""
