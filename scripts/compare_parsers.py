"""Run each backend in an independent process; retain outputs and measurements."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def worker(backend: str, output: Path, condition: str):
    import psutil

    from ican.ingestion.parsers import parse_pdf, sha256

    output.mkdir(parents=True, exist_ok=True)
    process = psutil.Process()
    peak = [process.memory_info().rss]
    done = threading.Event()

    def sample():
        while not done.wait(0.05):
            peak[0] = max(peak[0], process.memory_info().rss)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.perf_counter()
    config = json.loads(
        (ROOT / "configs/ingestion/swin-v1.json").read_text(encoding="utf-8")
    )
    paper = config["sources"][0]
    path = ROOT / paper["path"]
    raw_hash = sha256(path.read_bytes())
    if raw_hash != paper["expected_sha256"]:
        raise ValueError("Swin PDF hash mismatch")
    kwargs = {
        "source_id": "comparison:swin",
        "relative_path": paper["path"],
        "version": paper["version"],
    }
    metrics = {"backend": backend, "input_sha256": raw_hash, "run_condition": condition}
    try:
        if backend == "docling":
            from ican.ingestion.docling_adapter import adapt_document, convert_pdf

            document = convert_pdf(path)
            document.save_as_json(output / "document.json")
            document.save_as_markdown(output / "document.md")
            units, issues = adapt_document(document, pdf_path=path, **kwargs)
            metrics["versions"] = {
                name: importlib.metadata.version(name)
                for name in (
                    "docling-slim",
                    "docling-core",
                    "docling-parse",
                    "docling-ibm-models",
                )
            }
            metrics["tables"] = len(document.tables)
        else:
            units, issues = parse_pdf(path, **kwargs)
            metrics["versions"] = {"pymupdf": importlib.metadata.version("pymupdf")}
        (output / "parsed_units.jsonl").write_text(
            "".join(u.model_dump_json() + "\n" for u in units), encoding="utf-8"
        )
        (output / "issues.json").write_text(
            json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        metrics.update(
            status="success",
            pages=len(units),
            characters=sum(len(u.text) for u in units),
            positioned_spans=sum(len(u.structures) for u in units),
            issues=len(issues),
        )
    except Exception as error:
        metrics.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        done.set()
        sampler.join()
        metrics.update(
            seconds=round(time.perf_counter() - started, 3),
            peak_rss_mb=round(peak[0] / 2**20, 1),
        )
        (output / "metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(metrics, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["pymupdf", "docling"])
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/processed/parser-comparison"
    )
    parser.add_argument(
        "--condition",
        default="Includes imports and initialization; model cache state must be documented separately",
    )
    args = parser.parse_args()
    if args.backend:
        worker(args.backend, args.output, args.condition)
    else:
        for backend in ("pymupdf", "docling"):
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--backend",
                    backend,
                    "--output",
                    str(args.output / backend),
                    "--condition",
                    args.condition,
                ],
                check=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                cwd=ROOT,
            )
