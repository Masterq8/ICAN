"""Reuse Docling layout/table extraction with page-local provenance."""

from __future__ import annotations

from pathlib import Path

from .parsers import sha256
from .schema import ParsedUnit, StructureSpan


def convert_pdf(path: Path):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    from .docling_models import ensure_models

    options = PdfPipelineOptions(
        do_ocr=False, do_table_structure=True, artifacts_path=ensure_models()
    )
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
    )
    result = converter.convert(path)
    if str(result.status.value) != "success":
        raise ValueError(f"Docling conversion incomplete: {result.status}")
    return result.document


def compact_table(item, document):
    lines = []
    for line in item.export_to_markdown(doc=document).splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.split("|")]
            cells = [
                "---" if cell and set(cell) <= {"-", ":"} else cell for cell in cells
            ]
            line = "|".join(cells)
        lines.append(line)
    return "\n".join(lines)


def adapt_page(document, page_number, page, original_pdf=None):
    from docling_core.types.doc import TableItem

    pieces, spans, issues, offset, line = [], [], [], 0, 1
    for item, _ in document.iterate_items(page_no=page_number):
        all_prov = getattr(item, "prov", [])
        prov = [p for p in all_prov if p.page_no == page_number]
        if not prov:
            continue
        boxes = []
        for p in prov:
            bbox = p.bbox.to_top_left_origin(page_height=page.size.height)
            boxes.append([bbox.l, bbox.t, bbox.r, bbox.b])
        metadata = {
            "provenance_bboxes": boxes,
            "provenance_charspans": [list(p.charspan) for p in prov],
        }
        if isinstance(item, TableItem):
            # Rendered table offsets do not correspond to PDF character spans.
            if len({p.page_no for p in all_prov}) != 1:
                issues.append(
                    {
                        "severity": "error",
                        "code": "cross_page_table_unsupported",
                        "page": page_number,
                        "message": item.self_ref,
                    }
                )
                continue
            content = compact_table(item, document)
            metadata["review_required"] = True
            issues.append(
                {
                    "severity": "warning",
                    "code": "table_structure_requires_review",
                    "page": page_number,
                    "message": f"{item.self_ref}: cell relationships are unverified candidates",
                }
            )
        else:
            original = getattr(item, "orig", "") or getattr(item, "text", "")
            if not original.strip():
                continue
            if len({p.page_no for p in all_prov}) == 1:
                content = original
            else:
                ranges = sorted(p.charspan for p in prov)
                if any(
                    start < 0 or end > len(original) or end < start
                    for start, end in ranges
                ):
                    if original_pdf is None:
                        issues.append(
                            {
                                "severity": "error",
                                "code": "invalid_cross_page_charspan",
                                "page": page_number,
                                "message": item.self_ref,
                            }
                        )
                        continue
                    # Recover only this page's positioned region from the raw
                    # PDF; stale item offsets must never place text on another page.
                    content = "\n".join(
                        original_pdf[page_number - 1].get_text("text", clip=box).strip()
                        for box in boxes
                    )
                    metadata["text_backend"] = "pymupdf_positioned_fallback"
                    issues.append(
                        {
                            "severity": "warning",
                            "code": "cross_page_text_recovered_from_pdf",
                            "page": page_number,
                            "message": item.self_ref,
                        }
                    )
                else:
                    content = "\n".join(original[start:end] for start, end in ranges)
        if not content.strip():
            continue
        union = [
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        ]
        spans.append(
            StructureSpan(
                kind=item.label.value,
                name=item.self_ref,
                line_start=line,
                line_end=line + len(content.splitlines()) - 1,
                char_start=offset,
                char_end=offset + len(content),
                bbox=union,
                metadata=metadata,
            )
        )
        pieces.append(content)
        offset += len(content) + 2
        line += content.count("\n") + 2
    return "\n\n".join(pieces), spans, issues


def adapt_document(
    document,
    *,
    source_id: str,
    relative_path: str,
    version: str,
    pdf_path: Path | None = None,
):
    import pymupdf

    original_pdf = pymupdf.open(pdf_path) if pdf_path is not None else None
    units, issues = [], []
    from docling_core.types.doc import TableItem

    for item, _ in document.iterate_items():
        if not (
            getattr(item, "orig", "") or getattr(item, "text", "")
        ).strip() and not isinstance(item, TableItem):
            continue
        prov = getattr(item, "prov", [])
        if not prov:
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_provenance",
                    "message": item.self_ref,
                }
            )
        elif any(p.page_no not in document.pages for p in prov):
            issues.append(
                {
                    "severity": "error",
                    "code": "orphan_provenance",
                    "message": item.self_ref,
                }
            )
    for page_number, page in sorted(document.pages.items()):
        try:
            text, spans, page_issues = adapt_page(
                document, page_number, page, original_pdf
            )
            issues.extend(page_issues)
            if not text.strip():
                issues.append(
                    {
                        "severity": "error",
                        "code": "pdf_no_text",
                        "page": page_number,
                        "message": "Docling produced no positioned text",
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
                    structures=spans,
                    metadata={
                        "parser": "docling",
                        "page_count": len(document.pages),
                        "page_width": page.size.width,
                        "page_height": page.size.height,
                        "coordinate_origin": "top-left",
                        "table_format": "markdown_candidate",
                        "table_review_required": any(s.kind == "table" for s in spans),
                        "limitations": [
                            "Table relationships require visual review",
                            "Invalid cross-page provenance is excluded and reported",
                        ],
                    },
                )
            )
        except Exception as error:  # noqa: BLE001 -- preserve other pages on third-party extraction failure
            issues.append(
                {
                    "severity": "error",
                    "code": "pdf_page_failed",
                    "page": page_number,
                    "message": f"{type(error).__name__}: {error}",
                }
            )
    if original_pdf is not None:
        original_pdf.close()
    return units, issues
