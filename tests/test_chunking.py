from __future__ import annotations

from itertools import pairwise

import pytest

from ican.chunking.budget import TokenBudget
from ican.chunking.chunker import chunks_for_region
from ican.chunking.schema import ChunkConfig, ParentUnit
from ican.chunking.structure import regions, section_path
from ican.chunking.verification import validate_chunks
from ican.ingestion.parsers import (
    config_structures,
    markdown_structures,
    python_structures,
    sha256,
)
from ican.ingestion.schema import StructureSpan


def parent(text, *, source_type="code", structures=None, location=None, metadata=None):
    return ParentUnit(
        unit_id="unit",
        source_id="source",
        source_type=source_type,
        input_path="data/processed/input.jsonl",
        path="model.py",
        source_url="https://example.org/code",
        version="fixed",
        source_sha256=sha256(b"raw"),
        text=text,
        text_sha256=sha256(text.encode()),
        structures=structures or [],
        location=location or {"line_start": 1, "line_end": len(text.splitlines())},
        metadata=metadata or {},
    )


def chunk(unit, config=None, inherited=None):
    config = config or ChunkConfig(
        datasets=[], max_tokens=128, max_context_tokens=24, overlap_tokens=12
    )
    rs, path = regions(unit, inherited)
    result = [
        c
        for r in rs
        for c in chunks_for_region(
            unit, r, config, TokenBudget(), dataset_id="test", split="default"
        )
    ]
    validate_chunks({"default": [unit]}, result, config, "test")
    return result, path


def test_nested_python_decorators_crlf_and_module_gaps():
    text = "import math\r\nGLOBAL = 1\r\n@decorate\r\nclass A:\r\n    label = '模型'\r\n    def run(self):\r\n        return GLOBAL\r\n# end\r\n"
    unit = parent(text, structures=python_structures(text))
    chunks, _ = chunk(unit)
    assert any(
        c.structure_name == "A.run" and c.location["line_start"] == 6 for c in chunks
    )
    assert any("@decorate\r\n" in c.text for c in chunks)
    assert any(
        "GLOBAL = 1" in c.text and c.structure_kind == "file_text" for c in chunks
    )
    assert "".join(c.text for c in chunks) == text
    assert all(c.metadata["overlap_tokens"] == 0 for c in chunks)


def test_config_deepest_field_keeps_ancestor_context():
    text = "MODEL:\r\n  SWIN:\r\n    DEPTHS: [2, 2, 6, 2]\r\n    WINDOW_SIZE: 7\r\n"
    chunks, _ = chunk(
        parent(text, source_type="config", structures=config_structures(text))
    )
    depths = next(c for c in chunks if c.structure_name == "MODEL.SWIN.DEPTHS")
    assert depths.context_path == ["MODEL", "MODEL.SWIN", "MODEL.SWIN.DEPTHS"]
    assert depths.location == {"line_start": 3, "line_end": 3}


def test_markdown_nested_heading_and_fence():
    text = "# Main\n```python\n# hidden\n```\n## Child\nhello\n# Next\nend\n"
    chunks, _ = chunk(
        parent(text, source_type="documentation", structures=markdown_structures(text))
    )
    child = next(c for c in chunks if c.structure_name == "Child")
    assert child.context_path == ["Main", "Child"]
    assert not any(c.structure_name == "hidden" for c in chunks)


@pytest.mark.parametrize(
    "text",
    ["🙂漢字🧪" * 600, "uninterrupted_" * 600, ("中文 <|endoftext|> code\r\n" * 300)],
)
def test_long_structure_unicode_budget_overlap_and_complete_coverage(text):
    chunks, _ = chunk(parent(text))
    assert len(chunks) > 1
    assert all(
        c.embedding_tokens <= 128 and c.metadata["overlap_tokens"] <= 12 for c in chunks
    )
    assert all(c.text == text[c.char_start : c.char_end] for c in chunks)
    assert all(b.char_start > a.char_start for a, b in pairwise(chunks))


def test_long_table_header_metadata_review_and_bbox():
    text = "| Model | Acc |\n| --- | --- |\n" + "| Swin-T | 81.3 |\n" * 200
    span = StructureSpan(
        kind="table",
        name="table:0",
        line_start=1,
        line_end=202,
        char_start=0,
        char_end=len(text),
        bbox=[1, 2, 3, 4],
        metadata={"review_required": True},
    )
    chunks, _ = chunk(
        parent(text, source_type="paper", location={"page": 5}, structures=[span])
    )
    assert len(chunks) > 1 and all(c.review_required for c in chunks)
    assert all(
        c.metadata["table_header_context"] == "| Model | Acc |\n| --- | --- |"
        for c in chunks
    )
    assert all(c.provenance[0]["bbox"] == [1, 2, 3, 4] for c in chunks)
    assert all(c.location == {"page": 5} for c in chunks)


def test_page_without_structure_inherits_section():
    text = "3 Architecture\n3.2 Shifted Window\nBody"
    headings = [
        StructureSpan(
            kind="section_header",
            name="h1",
            line_start=1,
            line_end=1,
            char_start=0,
            char_end=14,
        ),
        StructureSpan(
            kind="section_header",
            name="h2",
            line_start=2,
            line_end=2,
            char_start=15,
            char_end=33,
        ),
    ]
    first = parent(text, source_type="paper", location={"page": 1}, structures=headings)
    second = parent(
        "continued explanation", source_type="paper", location={"page": 2}
    ).model_copy(update={"unit_id": "page2"})
    config = ChunkConfig(
        datasets=[], max_tokens=128, max_context_tokens=24, overlap_tokens=12
    )
    chunks, inherited = [], []
    for u in [first, second]:
        rs, inherited = regions(u, inherited)
        chunks.extend(
            c
            for r in rs
            for c in chunks_for_region(
                u, r, config, TokenBudget(), dataset_id="test", split="default"
            )
        )
    validate_chunks({"default": [first, second]}, chunks, config, "test")
    assert inherited == ["3 Architecture", "3.2 Shifted Window"]
    assert chunks[-1].context_path == inherited and chunks[-1].location["page"] == 2


def test_unnumbered_minor_heading_keeps_numbered_ancestry():
    path = section_path(
        ["3. Method", "3.2. Shifted Windows"], "Efficient batch computation"
    )
    assert path == ["3. Method", "3.2. Shifted Windows", "Efficient batch computation"]
    assert section_path(path, "3.3. Architecture Variants") == [
        "3. Method",
        "3.3. Architecture Variants",
    ]
    assert section_path(path, "References") == ["References"]


def test_qasper_keeps_paragraph_identity_and_no_fake_page():
    chunks, _ = chunk(
        parent(
            "External paper paragraph",
            source_type="paper",
            location={"paper_id": "x", "section_index": 2, "paragraph_index": 4},
            metadata={"section_path": ["Experiments", "Ablation"]},
        )
    )
    assert chunks[0].structure_kind == "paragraph"
    assert chunks[0].context_path == ["Experiments", "Ablation"]
    assert "page" not in chunks[0].location


def test_independent_verifier_rejects_missing_original_content():
    config = ChunkConfig(
        datasets=[], max_tokens=128, max_context_tokens=24, overlap_tokens=12
    )
    unit = parent("x " * 1000)
    chunks, _ = chunk(unit, config)
    with pytest.raises(ValueError, match="Uncovered"):
        validate_chunks({"default": [unit]}, chunks[:-1], config, "test")


def test_independent_verifier_rejects_changed_source_location():
    unit = parent("hello\nworld")
    chunks, _ = chunk(unit)
    altered = chunks[0].model_copy(
        update={"location": {"line_start": 9, "line_end": 9}}
    )
    with pytest.raises(ValueError, match="location"):
        validate_chunks(
            {"default": [unit]}, [altered], ChunkConfig(datasets=[]), "test"
        )


def test_parent_excerpt_keeps_original_line_offset():
    chunks, _ = chunk(
        parent("a=1\nb=2\n", location={"line_start": 100, "line_end": 101})
    )
    assert chunks[0].location == {"line_start": 100, "line_end": 101}


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85", "\x0b", "\x0c"])
def test_unicode_string_separator_does_not_create_physical_lines(separator):
    text = f"s = 'before{separator}after'\nprint(s)\ndef f():\n    return s\n"
    unit = parent(
        text,
        structures=python_structures(text),
        location={"line_start": 1, "line_end": 4},
    )
    chunks, _ = chunk(unit)
    assert chunks[0].location == {"line_start": 1, "line_end": 2}
    function = next(c for c in chunks if c.structure_name == "f")
    assert function.location == {"line_start": 3, "line_end": 4}
    assert function.text == "def f():\n    return s\n"


@pytest.mark.parametrize(
    "field",
    ["table_header_context", "structure_kind", "context_path", "embedding_context"],
)
def test_verifier_rejects_invented_structure_or_context(field):
    text = "| Model | Acc |\n| --- | --- |\n| Swin-T | 81.3 |\n"
    span = StructureSpan(
        kind="table",
        name="table:0",
        line_start=1,
        line_end=3,
        char_start=0,
        char_end=len(text),
    )
    unit = parent(text, source_type="paper", location={"page": 5}, structures=[span])
    config = ChunkConfig(
        datasets=[], max_tokens=128, max_context_tokens=24, overlap_tokens=12
    )
    chunks, _ = chunk(unit, config)
    c = chunks[0]
    if field == "table_header_context":
        changes = {"metadata": {**c.metadata, field: "invented header"}}
    elif field == "embedding_context":
        embedding = "invented context\n\n" + c.text
        changes = {
            field: "invented context",
            "embedding_text": embedding,
            "embedding_tokens": TokenBudget().count(embedding),
        }
    else:
        changes = {
            field: ["invented context"] if field == "context_path" else "function"
        }
    with pytest.raises(ValueError, match="mismatch"):
        validate_chunks(
            {"default": [unit]}, [c.model_copy(update=changes)], config, "test"
        )


def test_qasper_caption_is_distinct_from_paragraph():
    chunks, _ = chunk(
        parent(
            "Figure 1: Overview",
            source_type="paper",
            location={"paper_id": "x", "caption_index": 1},
        )
    )
    assert chunks[0].structure_kind == "caption"
