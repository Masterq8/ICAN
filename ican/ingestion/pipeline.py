"""Allowlisted, version-checked ingestion with deterministic rebuild artifacts."""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
from pathlib import Path

from .parsers import parse_pdf, parse_text_file, sha256
from .schema import IngestionConfig, SourceRecord


def write_json(path: Path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, records):
    path.write_text(
        "".join(
            json.dumps(
                x.model_dump() if hasattr(x, "model_dump") else x,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
            for x in records
        ),
        encoding="utf-8",
    )


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout


def confined(root: Path, relative: str, area: str) -> Path:
    path = (root / relative).resolve()
    if (
        not path.is_relative_to((root / area).resolve())
        or path == (root / area).resolve()
    ):
        raise ValueError(f"Path must stay under {area}: {relative}")
    return path


def ingest(root: Path, config: IngestionConfig) -> dict:
    root = root.resolve()
    output = confined(root, config.output_dir, "data/processed")
    records, units, issues, skipped = [], [], [], []
    output.mkdir(parents=True, exist_ok=True)
    for spec in config.sources:
        source_id = f"src:{sha256((spec.path + '@' + spec.version).encode())[:20]}"
        source_units, source_issues, raw_hash = [], [], ""
        try:
            path = confined(root, spec.path, "data/raw")
            if spec.kind == "paper":
                raw_hash = sha256(path.read_bytes())
                if spec.expected_sha256 is None or raw_hash != spec.expected_sha256:
                    raise ValueError("Missing or mismatched expected PDF SHA-256")
                if config.pdf_backend == "docling":
                    from .docling_adapter import adapt_document, convert_pdf

                    document = convert_pdf(path)
                    document.save_as_json(
                        output / f"{source_id.replace(':', '_')}.docling.json"
                    )
                    source_units, source_issues = adapt_document(
                        document,
                        source_id=source_id,
                        relative_path=spec.path,
                        version=spec.version,
                        pdf_path=path,
                    )
                else:
                    source_units, source_issues = parse_pdf(
                        path,
                        source_id=source_id,
                        relative_path=spec.path,
                        version=spec.version,
                    )
            else:
                head = git(path, "rev-parse", "HEAD").decode().strip()
                if head != spec.version:
                    raise ValueError(f"Repository commit mismatch: {head}")
                # Untracked files never enter the allowlist. Tracked edits are rejected.
                git(path, "diff", "--exit-code", "HEAD", "--")
                entries = git(path, "ls-files", "-z").decode("utf-8").split("\0")
                # Git status/diff can hide edits behind skip-worktree or
                # assume-unchanged. Verify bytes against the actual pinned blob.
                # Only checkout line-ending conversion is accepted.
                prepared = []
                for relative in sorted(filter(None, entries)):
                    file = (path / relative).resolve()
                    if not file.is_relative_to(path):
                        raise ValueError(f"Repository file escapes source: {relative}")
                    if (
                        file.suffix.lower() not in config.extensions
                        and file.name not in config.filenames
                    ):
                        skipped.append(
                            {
                                "path": file.relative_to(root).as_posix(),
                                "reason": "extension_not_allowed",
                            }
                        )
                        continue
                    try:
                        if file.stat().st_size > config.max_file_bytes:
                            skipped.append(
                                {
                                    "path": file.relative_to(root).as_posix(),
                                    "reason": "size_limit",
                                }
                            )
                            continue
                        raw = file.read_bytes()
                    except OSError as error:
                        file_id = f"{source_id}:file:{sha256(relative.encode())[:16]}"
                        source_issues.append(
                            {
                                "severity": "error",
                                "code": "file_failed",
                                "path": file.relative_to(root).as_posix(),
                                "source_id": file_id,
                                "message": f"{type(error).__name__}: {error}",
                            }
                        )
                        continue
                    original = git(
                        path, "cat-file", "blob", f"{spec.version}:{relative}"
                    )
                    if raw.replace(b"\r\n", b"\n") != original.replace(b"\r\n", b"\n"):
                        raise ValueError(
                            f"Worktree bytes differ from pinned commit: {relative}"
                        )
                    prepared.append((relative, file, raw))
                fingerprints = []
                for issue in source_issues:
                    if issue["code"] == "file_failed":
                        relative = (root / issue["path"]).relative_to(path).as_posix()
                        records.append(
                            SourceRecord(
                                source_id=issue["source_id"],
                                kind="repository",
                                path=issue["path"],
                                version=spec.version,
                                url=f"{spec.url}/blob/{spec.version}/{relative}",
                                raw_sha256="",
                                status="failed",
                                unit_count=0,
                                metadata={
                                    "parent_source_id": source_id,
                                    "hash_unavailable": True,
                                },
                            )
                        )
                for relative, file, raw in prepared:
                    rel = file.relative_to(root).as_posix()
                    file_id = f"{source_id}:file:{sha256(relative.encode())[:16]}"
                    file_hash = ""
                    try:
                        file_hash = sha256(raw)
                        fingerprints.append((relative, file_hash))
                        unit, warnings = parse_text_file(
                            file,
                            source_id=file_id,
                            relative_path=rel,
                            version=spec.version,
                            raw=raw,
                        )
                        source_units.append(unit)
                        source_issues.extend(
                            {**w, "path": rel, "source_id": file_id} for w in warnings
                        )
                        records.append(
                            SourceRecord(
                                source_id=file_id,
                                kind="repository",
                                path=rel,
                                version=spec.version,
                                url=f"{spec.url}/blob/{spec.version}/{relative}",
                                raw_sha256=file_hash,
                                status="partial" if warnings else "parsed",
                                unit_count=1,
                                metadata={"parent_source_id": source_id},
                            )
                        )
                    except Exception as error:  # noqa: BLE001 -- per-file third-party parser isolation
                        source_issues.append(
                            {
                                "severity": "error",
                                "code": "file_failed",
                                "path": rel,
                                "source_id": file_id,
                                "message": f"{type(error).__name__}: {error}",
                            }
                        )
                        records.append(
                            SourceRecord(
                                source_id=file_id,
                                kind="repository",
                                path=rel,
                                version=spec.version,
                                url=f"{spec.url}/blob/{spec.version}/{relative}",
                                raw_sha256=file_hash,
                                status="failed",
                                unit_count=0,
                            )
                        )
                raw_hash = sha256(
                    json.dumps(
                        fingerprints, ensure_ascii=False, sort_keys=True
                    ).encode()
                )
            units.extend(source_units)
            issues.extend(
                {"source_id": source_id, "path": spec.path, **issue}
                for issue in source_issues
            )
            status = "partial" if source_issues else "parsed"
            if not source_units:
                status = "empty"
                issues.append(
                    {
                        "source_id": source_id,
                        "path": spec.path,
                        "severity": "error",
                        "code": "empty_source",
                        "message": "Source produced no units",
                    }
                )
            records.append(
                SourceRecord(
                    source_id=source_id,
                    kind=spec.kind,
                    path=spec.path,
                    version=spec.version,
                    url=spec.url,
                    raw_sha256=raw_hash,
                    status=status,
                    unit_count=len(source_units),
                    metadata={
                        "hash_kind": "included_file_manifest"
                        if spec.kind == "repository"
                        else "raw_file"
                    },
                )
            )
        except Exception as error:  # noqa: BLE001 -- one rejected source must not hide other source results
            issues.append(
                {
                    "source_id": source_id,
                    "path": spec.path,
                    "severity": "error",
                    "code": "source_rejected",
                    "message": f"{type(error).__name__}: {error}",
                }
            )
            records.append(
                SourceRecord(
                    source_id=source_id,
                    kind=spec.kind,
                    path=spec.path,
                    version=spec.version,
                    url=spec.url,
                    raw_sha256=raw_hash,
                    status="failed",
                    unit_count=0,
                )
            )
    records.sort(key=lambda x: x.source_id)
    units.sort(key=lambda x: x.unit_id)
    if len({u.unit_id for u in units}) != len(units):
        raise ValueError("Duplicate parsed unit IDs")
    write_jsonl(output / "sources.jsonl", records)
    write_jsonl(output / "parsed_units.jsonl", units)
    write_jsonl(output / "parse_failures.jsonl", issues)
    errors = sum(x["severity"] == "error" for x in issues)
    report = {
        "dataset_id": config.dataset_id,
        "pdf_backend": config.pdf_backend,
        "config_sha256": sha256(config.model_dump_json().encode()),
        "versions": {
            name: importlib.metadata.version(name)
            for name in (
                ["docling-slim", "docling-core", "docling-parse", "docling-ibm-models"]
                if config.pdf_backend == "docling"
                else ["pymupdf"]
            )
        },
        "source_records": len(records),
        "units": len(units),
        "pdf_pages": sum(u.page is not None for u in units),
        "errors": errors,
        "warnings": len(issues) - errors,
        "skipped": skipped,
        "status": "passed" if errors == 0 else "failed",
        "artifact_sha256": {
            name: sha256((output / name).read_bytes())
            for name in ["sources.jsonl", "parsed_units.jsonl", "parse_failures.jsonl"]
        },
    }
    write_json(output / "parse_report.json", report)
    headings = []
    for unit in units:
        selected = []
        if unit.page in {3, 4, 5, 12}:
            selected = unit.structures[:3]
        elif unit.path.endswith("configs/swin/swin_tiny_patch4_window7_224.yaml"):
            selected = unit.structures
        elif unit.path.endswith("models/swin_transformer.py"):
            selected = [
                s
                for s in unit.structures
                if s.name in {"SwinTransformer", "SwinTransformerBlock.forward"}
            ]
        elif unit.path.endswith("config.py"):
            selected = [
                s for s in unit.structures if s.name == "_update_config_from_file"
            ]
        for span in selected:
            content = unit.text[span.char_start : span.char_end]
            headings.append(
                f"## {unit.path}\n\n版本：{unit.version}；页码：{unit.page}；行号：{span.line_start}–{span.line_end}；结构：{span.name}；坐标：{span.bbox}\n\n```text\n{content[:3000]}\n```\n"
            )
    (output / "review_samples.md").write_text(
        "# 解析定位抽查样本\n\n" + "\n".join(headings), encoding="utf-8"
    )
    return report
