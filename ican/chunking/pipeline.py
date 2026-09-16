from __future__ import annotations

import importlib.metadata
from collections import Counter
from pathlib import Path

from ican.ingestion.parsers import sha256
from ican.ingestion.pipeline import confined, write_json, write_jsonl

from .artifacts import artifact_path
from .budget import TokenBudget
from .chunker import chunks_for_region
from .inputs import load_dataset
from .schema import ChunkConfig, DatasetConfig
from .structure import regions
from .verification import validate_chunks


def build_dataset(root: Path, config: ChunkConfig, dataset: DatasetConfig):
    output = confined(root, dataset.output_dir, "data/processed")
    protected = [
        confined(root, p, "data/processed")
        for p in [
            dataset.parent_manifest,
            *dataset.inputs.values(),
            *([dataset.sources] if dataset.sources else []),
        ]
    ]
    if any(
        p.is_relative_to(output) or output.is_relative_to(p.parent) for p in protected
    ):
        raise ValueError("Output must not overwrite or mix with parent input directory")
    output.mkdir(parents=True, exist_ok=True)
    # Invalidate a previous successful build before reading new input. A failed
    # rebuild must not leave a passed manifest pointing to old chunks.
    manifest_path = output / "chunk_manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()
    for name in [
        "chunks.jsonl",
        "chunk_report.json",
        "chunk_failures.jsonl",
        "review_samples.md",
        "chunk_manifest.json",
        "verification_report.json",
        "rebuild_verification.json",
    ]:
        artifact_path(output, name)
    for name in ["verification_report.json", "rebuild_verification.json"]:
        (output / name).unlink(missing_ok=True)
    try:
        parents, input_hashes = load_dataset(root, dataset)
        budget = TokenBudget(config.tokenizer)
        chunks, empty, inherited = [], [], {}
        for split, units in parents.items():
            for unit in units:
                if not unit.text.strip():
                    empty.append(unit.unit_id)
                    continue
                source_regions, path = regions(unit, inherited.get(unit.source_id, []))
                inherited[unit.source_id] = path
                for region in source_regions:
                    chunks.extend(
                        chunks_for_region(
                            unit,
                            region,
                            config,
                            budget,
                            dataset_id=dataset.dataset_id,
                            split=split,
                        )
                    )
        chunks.sort(
            key=lambda c: (c.split, c.source_id, c.parent_unit_id, c.char_start)
        )
        if not chunks or len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("Empty output or duplicate chunk IDs")
        validation = validate_chunks(parents, chunks, config, dataset.dataset_id)
        write_jsonl(output / "chunks.jsonl", chunks)
        report = {
            "status": "passed",
            "dataset_id": dataset.dataset_id,
            "chunks": len(chunks),
            "parent_units": sum(len(us) for us in parents.values()),
            "empty_parent_units": empty,
            "by_source_type": dict(
                sorted(Counter(c.source_type for c in chunks).items())
            ),
            "by_structure_kind": dict(
                sorted(Counter(c.structure_kind for c in chunks).items())
            ),
            "by_split": dict(sorted(Counter(c.split for c in chunks).items())),
            "review_required_chunks": sum(c.review_required for c in chunks),
            "oversized_structure_chunks": sum(
                c.metadata["split_inside_structure"] for c in chunks
            ),
            "truncated_context_chunks": sum(
                c.metadata["context_truncated"] for c in chunks
            ),
            "max_embedding_tokens": max(c.embedding_tokens for c in chunks),
            "max_text_tokens": max(c.text_tokens for c in chunks),
            "config_sha256": sha256(config.model_dump_json().encode()),
            "validation": validation,
        }
        write_json(output / "chunk_report.json", report)
        manifest = {
            "status": "passed",
            "schema_version": config.schema_version,
            "dataset_id": dataset.dataset_id,
            "config": config.model_dump(),
            "config_sha256": report["config_sha256"],
            "parent_manifest": dataset.parent_manifest,
            "parent_manifest_sha256": dataset.expected_manifest_sha256,
            "parent_input_sha256": input_hashes,
            "tokenizer": {
                "name": config.tokenizer,
                "package": "tiktoken",
                "version": importlib.metadata.version("tiktoken"),
                "purpose": "P2.2 token budget only; recheck actual embedding tokenizer in P2.3",
            },
            "index_allowlist": [(output / "chunks.jsonl").relative_to(root).as_posix()],
            "artifacts_sha256": {
                name: sha256((output / name).read_bytes())
                for name in ["chunks.jsonl", "chunk_report.json"]
            },
        }
        write_jsonl(output / "chunk_failures.jsonl", [])
        samples = []
        for c in chunks:
            if len(samples) >= 12:
                break
            if not any(
                s["type"] == c.source_type and s["kind"] == c.structure_kind
                for s in samples
            ):
                samples.append(
                    {"type": c.source_type, "kind": c.structure_kind, "chunk": c}
                )
        text = "# 分块定位抽查样本\n\n" + "\n".join(
            f"## {s['type']} / {s['kind']}\n\nID：{s['chunk'].chunk_id}\n\n来源：{s['chunk'].source_path}；版本：{s['chunk'].source_version}；位置：{s['chunk'].location}；原字符范围：[{s['chunk'].char_start}, {s['chunk'].char_end})；候选需核验：{s['chunk'].review_required}\n\n```text\n{s['chunk'].text}\n```\n"
            for s in samples
        )
        (output / "review_samples.md").write_text(text, encoding="utf-8")
        # Publish success only after every build artifact has been written.
        write_json(manifest_path, manifest)
        return report
    except Exception as error:
        manifest_path.unlink(missing_ok=True)
        report = {
            "status": "failed",
            "dataset_id": dataset.dataset_id,
            "error": f"{type(error).__name__}: {error}",
        }
        write_json(output / "chunk_report.json", report)
        write_jsonl(output / "chunk_failures.jsonl", [report])
        raise


def build_all(root: Path, config: ChunkConfig):
    outputs = [confined(root, d.output_dir, "data/processed") for d in config.datasets]
    protected = [
        confined(root, p, "data/processed")
        for d in config.datasets
        for p in [
            d.parent_manifest,
            *d.inputs.values(),
            *([d.sources] if d.sources else []),
        ]
    ]
    for index, output in enumerate(outputs):
        if any(
            output.is_relative_to(other) or other.is_relative_to(output)
            for other in outputs[:index]
        ):
            raise ValueError("Dataset output directories must be disjoint")
        if any(
            p.is_relative_to(output) or output.is_relative_to(p.parent)
            for p in protected
        ):
            raise ValueError("Dataset output conflicts with a parent input directory")
    return [
        build_dataset(root.resolve(), config, dataset) for dataset in config.datasets
    ]
