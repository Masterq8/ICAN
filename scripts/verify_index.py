from __future__ import annotations

import argparse
import json
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ican.chunking.artifacts import artifact_path
from ican.indexing.inputs import load_chunks
from ican.indexing.model import DenseEncoder, verified_model
from ican.indexing.pipeline import index_directory, index_identity
from ican.indexing.schema import IndexConfig
from ican.indexing.verification import verify_artifacts
from ican.ingestion.pipeline import write_json


def verify(root: Path, config: IndexConfig, *, smoke=False):
    rows, snapshots = load_chunks(root, config)
    _, ledger_hash = verified_model(root, config.model)
    identity = index_identity(config, snapshots, ledger_hash)
    directory = index_directory(root, config, identity)
    marker = artifact_path(directory, "verification_report.json")
    marker.unlink(missing_ok=True)
    result = verify_artifacts(directory, rows, config, identity)
    encoder = DenseEncoder(root, config.model)
    lengths = encoder.lengths([r["chunk"]["embedding_text"] for r in rows])
    from ican.chunking.inputs import read_lines

    persisted = read_lines(directory / "points.jsonl")
    if lengths != [r["actual_tokens"] for r in persisted]:
        raise ValueError("Saved token lengths differ from actual model tokenizer")
    if (
        encoder.descriptor
        != json.loads((directory / "index_manifest.json").read_text(encoding="utf-8"))[
            "encoder"
        ]
    ):
        raise ValueError("Actual encoder descriptor mismatch")
    result["actual_tokenizer_rechecked"] = True
    if smoke:
        from qdrant_client import QdrantClient, models

        queries = [
            "Swin Transformer shifted window attention cyclic shift",
            "Swin-T 的窗口大小配置是多少？",
        ]
        vectors = encoder.encode(queries)
        examples = []
        collection = next(
            s.collections["default"]
            for s in config.sources
            if s.dataset_id == "swin_chunks_v1"
        )
        with closing(QdrantClient(path=str(directory / "qdrant"))) as client:
            for query, vector in zip(queries, vectors, strict=True):
                found = client.query_points(
                    collection,
                    query=vector.tolist(),
                    limit=3,
                    query_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="chunk.source_type",
                                match=models.MatchValue(
                                    value="config" if "窗口大小" in query else "paper"
                                ),
                            )
                        ]
                    ),
                ).points
                if not found:
                    raise ValueError("Functional smoke query returned no evidence")
                examples.append(
                    {
                        "query": query,
                        "results": [
                            {
                                "id": str(p.id),
                                "score": p.score,
                                "chunk_id": p.payload["chunk"]["chunk_id"],
                                "path": p.payload["chunk"]["source_path"],
                                "location": p.payload["chunk"]["location"],
                                "review_required": p.payload["chunk"][
                                    "review_required"
                                ],
                                "text": p.payload["chunk"]["text"],
                            }
                            for p in found
                        ],
                    }
                )
        write_json(
            artifact_path(directory, "smoke_queries.json"),
            {
                "purpose": "functional smoke only; no gold accuracy claims",
                "examples": examples,
            },
        )
        result["smoke_queries"] = len(examples)
    write_json(marker, result)
    return {"directory": directory.relative_to(root).as_posix(), "verification": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/indexing/v1.json")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config = IndexConfig.model_validate_json(
        (ROOT / args.config).read_text(encoding="utf-8")
    )
    print(
        json.dumps(verify(ROOT, config, smoke=args.smoke), ensure_ascii=False, indent=2)
    )
