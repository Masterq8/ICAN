"""Extract text and positions without importing or executing repository code."""

from __future__ import annotations

import ast
import bisect
import hashlib
import io
import json
import re
import tokenize
from itertools import pairwise
from pathlib import Path

import pymupdf
import yaml

from .schema import ParsedUnit, StructureSpan


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def line_offsets(text: str) -> list[int]:
    """Physical CR/LF/CRLF lines; Unicode separators inside strings are content."""
    offsets = [0]
    offsets.extend(match.end() for match in re.finditer(r"\r\n|\r|\n", text))
    if offsets[-1] != len(text):
        offsets.append(len(text))
    return offsets


def make_span(text: str, kind: str, name: str, start: int, end: int) -> StructureSpan:
    offsets = line_offsets(text)
    return StructureSpan(
        kind=kind,
        name=name,
        line_start=start,
        line_end=end,
        char_start=offsets[start - 1],
        char_end=offsets[end],
    )


def python_structures(text: str) -> list[StructureSpan]:
    tree = ast.parse(text)
    result: list[StructureSpan] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope: list[str] = []

        def definition(
            self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ) -> None:
            start = min([node.lineno] + [item.lineno for item in node.decorator_list])
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            name = ".".join(self.scope + [node.name])
            result.append(make_span(text, kind, name, start, node.end_lineno))
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_ClassDef = definition
        visit_FunctionDef = definition
        visit_AsyncFunctionDef = definition

    Visitor().visit(tree)
    return sorted(result, key=lambda item: (item.line_start, -item.line_end))


def config_structures(text: str) -> list[StructureSpan]:
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    result: list[StructureSpan] = []
    offsets = line_offsets(text)

    def visit(node: yaml.Node, prefix: str, ancestors: set[int]) -> None:
        if id(node) in ancestors:
            return  # Recursive YAML aliases must not create infinite traversal.
        ancestors = ancestors | {id(node)}
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                name = f"{prefix}.{key.value}" if prefix else str(key.value)
                # YAML also recognizes Unicode separators; map its absolute
                # character marks back to physical source-file lines.
                start = bisect.bisect_right(offsets, key.start_mark.index)
                end = max(
                    start,
                    bisect.bisect_right(offsets, max(0, value.end_mark.index - 1)),
                )
                result.append(make_span(text, "config_field", name, start, end))
                visit(value, name, ancestors)
        elif isinstance(node, yaml.SequenceNode):
            for index, value in enumerate(node.value):
                visit(value, f"{prefix}[{index}]", ancestors)

    if root is not None:
        visit(root, "", set())
    return result


def markdown_structures(text: str) -> list[StructureSpan]:
    headings: list[tuple[int, int, str]] = []
    fence: tuple[str, int] | None = None
    offsets = line_offsets(text)
    lines = [text[a:b].rstrip("\r\n") for a, b in pairwise(offsets)]
    for number, line in enumerate(lines, start=1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            continue
        if fence is not None:
            continue
        match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.append((number, len(match.group(1)), match.group(2)))
    result = []
    for index, (start, level, title) in enumerate(headings):
        end = next(
            (
                line - 1
                for line, later_level, _ in headings[index + 1 :]
                if later_level <= level
            ),
            len(lines),
        )
        result.append(make_span(text, "markdown_section", title, start, end))
    return result


def parse_text_file(
    path: Path,
    *,
    source_id: str,
    relative_path: str,
    version: str,
    raw: bytes | None = None,
) -> tuple[ParsedUnit, list[dict]]:
    raw = path.read_bytes() if raw is None else raw
    if b"\x00" in raw:
        raise ValueError("Binary NUL byte in a declared text file")
    suffix = path.suffix.lower()
    encoding = (
        tokenize.detect_encoding(io.BytesIO(raw).readline)[0]
        if suffix == ".py"
        else "utf-8-sig"
    )
    text = raw.decode(encoding)
    issues: list[dict] = []
    structures: list[StructureSpan] = []
    source_type = "documentation"
    parser = None
    if suffix == ".py":
        source_type, parser = "code", python_structures
    elif suffix in {".yaml", ".yml", ".json"}:
        source_type, parser = "config", config_structures
    elif suffix == ".sh":
        source_type = "code"
    elif suffix == ".md":
        parser = markdown_structures
    if parser is not None:
        try:
            if suffix == ".json":
                json.loads(text)
            structures = parser(text)
        except (SyntaxError, ValueError, yaml.YAMLError, RecursionError) as error:
            issues.append(
                {
                    "severity": "warning",
                    "code": "structure_parse_failed",
                    "message": f"{type(error).__name__}: {error}",
                }
            )
    unit = ParsedUnit(
        unit_id=f"{source_id}:file",
        source_id=source_id,
        source_type=source_type,
        path=relative_path,
        version=version,
        text=text,
        text_sha256=sha256(text.encode("utf-8")),
        line_start=1,
        line_end=max(1, len(line_offsets(text)) - 1),
        structures=structures,
        metadata={
            "encoding": encoding,
            "language": suffix.lstrip("."),
            "empty": not bool(text.strip()),
        },
    )
    return unit, issues


def split_merged_columns(blocks: list[dict], width: float) -> list[dict]:
    """PyMuPDF can merge separate left/right lines into one full-width block."""
    midpoint = width / 2
    result = []
    for block in blocks:
        left = [line for line in block["lines"] if line["bbox"][2] < midpoint]
        right = [line for line in block["lines"] if line["bbox"][0] >= midpoint]
        if left and right and len(left) + len(right) == len(block["lines"]):
            for lines in (left, right):
                bbox = [
                    min(x["bbox"][0] for x in lines),
                    min(x["bbox"][1] for x in lines),
                    max(x["bbox"][2] for x in lines),
                    max(x["bbox"][3] for x in lines),
                ]
                result.append({**block, "bbox": bbox, "lines": lines})
        else:
            result.append(block)
    return result


def order_pdf_blocks(blocks: list[dict], width: float, height: float) -> list[dict]:
    """Read left/right columns within bands separated by full-width blocks.

    Text at the very bottom is retained after the body. Bboxes are kept in the
    output so formulas, tables and unusual layouts can be reviewed later.
    """
    midpoint = width / 2
    footer = [block for block in blocks if block["bbox"][1] >= height - 55]
    body = [block for block in blocks if block["bbox"][1] < height - 55]
    wide = sorted(
        [
            block
            for block in body
            if block["bbox"][0] < midpoint - 8 and block["bbox"][2] > midpoint + 8
        ],
        key=lambda block: (block["bbox"][1], block["bbox"][0]),
    )
    remaining = [block for block in body if not any(block is item for item in wide)]
    result = []

    def column_order(items: list[dict]) -> list[dict]:
        return sorted(
            items,
            key=lambda block: (
                int(block["bbox"][0] >= midpoint),
                block["bbox"][1],
                block["bbox"][0],
            ),
        )

    for separator in wide:
        band = [block for block in remaining if block["bbox"][1] < separator["bbox"][1]]
        result.extend(column_order(band))
        remaining = [
            block for block in remaining if not any(block is item for item in band)
        ]
        result.append(separator)
    result.extend(column_order(remaining))
    result.extend(
        sorted(footer, key=lambda block: (block["bbox"][1], block["bbox"][0]))
    )
    return result


def is_section_candidate(block: dict, text: str) -> bool:
    first_line = text.splitlines()[0] if text else ""
    numbered = re.match(
        r"^(?:\d+(?:\.\d+)*\.?|A\d+(?:\.\d+)*\.?)\s+[A-Za-z]", first_line
    )
    bold = any(
        "bold" in span.get("font", "").lower()
        for line in block["lines"]
        for span in line["spans"]
    )
    return bool(
        (numbered or first_line in {"Abstract", "References", "Appendix"})
        and bold
        and len(text) < 150
    )


def parse_pdf(
    path: Path, *, source_id: str, relative_path: str, version: str
) -> tuple[list[ParsedUnit], list[dict]]:
    units: list[ParsedUnit] = []
    issues: list[dict] = []
    with pymupdf.open(path) as document:
        if document.needs_pass:
            raise ValueError("Encrypted PDF requires a password")
        for page_index in range(len(document)):
            page_number = page_index + 1
            try:
                page = document[page_index]
                blocks = [
                    block
                    for block in page.get_text("dict")["blocks"]
                    if block["type"] == 0
                ]
                blocks = order_pdf_blocks(
                    split_merged_columns(blocks, page.rect.width),
                    page.rect.width,
                    page.rect.height,
                )
                pieces = []
                structures = []
                char_offset, line_number = 0, 1
                for block in blocks:
                    content = "\n".join(
                        "".join(span["text"] for span in line["spans"])
                        for line in block["lines"]
                    )
                    if not content.strip():
                        continue
                    heading = is_section_candidate(block, content)
                    structures.append(
                        StructureSpan(
                            kind="heading_candidate" if heading else "pdf_block",
                            name=content.splitlines()[0]
                            if heading
                            else f"block_{len(structures) + 1}",
                            line_start=line_number,
                            line_end=line_number + len(content.splitlines()) - 1,
                            char_start=char_offset,
                            char_end=char_offset + len(content),
                            bbox=list(block["bbox"]),
                        )
                    )
                    pieces.append(content)
                    char_offset += len(content) + 2
                    line_number += content.count("\n") + 2
                text = "\n\n".join(pieces)
                if not text.strip():
                    issues.append(
                        {
                            "severity": "error",
                            "code": "pdf_no_text",
                            "page": page_number,
                            "message": "No extractable text; OCR or a text PDF is required",
                        }
                    )
                    continue
                units.append(
                    ParsedUnit(
                        unit_id=f"{source_id}:page:{page_number:04d}",
                        source_id=source_id,
                        source_type="paper",
                        path=relative_path,
                        version=version,
                        text=text,
                        text_sha256=sha256(text.encode("utf-8")),
                        page=page_number,
                        structures=structures,
                        metadata={
                            "page_count": len(document),
                            "page_width": page.rect.width,
                            "page_height": page.rect.height,
                            "layout_strategy": "two_column_bands",
                            "section_candidates": [
                                item.name
                                for item in structures
                                if item.kind == "heading_candidate"
                            ],
                            "limitations": [
                                "Equation and table relationships require visual verification",
                                "Section labels are heuristic candidates",
                            ],
                        },
                    )
                )
            except Exception as error:  # noqa: BLE001 -- isolate third-party page extraction failures
                issues.append(
                    {
                        "severity": "error",
                        "code": "pdf_page_failed",
                        "page": page_number,
                        "message": f"{type(error).__name__}: {error}",
                    }
                )
    return units, issues
