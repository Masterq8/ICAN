from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from rank_bm25 import BM25Okapi


def tokens(text: str) -> list[str]:
    output = []
    for word in re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*(?:[./-][A-Za-z0-9_]+)*|\d+(?:\.\d+)?|[\u4e00-\u9fff]+",
        text,
    ):
        if re.fullmatch(r"[\u4e00-\u9fff]+", word):
            output.extend(word)
            output.extend(word[i : i + 2] for i in range(len(word) - 1))
        else:
            output.append(word.lower())
            for part in re.split(r"[./-]", word):
                if part != word:
                    output.append(part.lower())
                parts = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", part).split("_")
                output.extend(
                    p.lower() for p in parts if p and p.lower() != word.lower()
                )
    return output


ALIASES = {
    "--batch-size": ["DATA.BATCH_SIZE"],
    "--accumulation-steps": ["TRAIN.ACCUMULATION_STEPS", "train_one_epoch"],
    "学习率": ["BASE_LR", "linear_scaled_lr", "BATCH_SIZE", "ACCUMULATION_STEPS"],
    "linear embedding": ["PatchEmbed", "Conv2d"],
    "配置链": [
        "_update_config_from_file",
        "update_config",
        "merge_from_file",
        "merge_from_list",
    ],
    "覆盖": ["update_config", "merge_from_list"],
    "--opts": ["merge_from_list", "update_config"],
    "梯度累积": ["ACCUMULATION_STEPS", "train_one_epoch", "loss", "linear_scaled_lr"],
    "weight_decay": ["set_weight_decay", "no_weight_decay", "no_weight_decay_keywords"],
    "layernorm": ["PATCH_NORM", "PatchEmbed", "norm_layer"],
    "hook": ["BasicLayer.forward", "downsample"],
}


def expand_query(query: str) -> list[str]:
    expanded = []
    for term, replacements in ALIASES.items():
        if term in query.lower():
            expanded.extend(replacements)
    for arg in re.findall(r"--([A-Za-z][A-Za-z0-9-]*)", query):
        expanded.append(arg.replace("-", "_").upper())
    return list(dict.fromkeys(expanded))


class LexicalIndex:
    def __init__(self, chunks: list[dict], k1=1.5, b=0.75):
        self.rows = sorted(chunks, key=lambda c: c["chunk_id"])
        if not self.rows or len({c["chunk_id"] for c in self.rows}) != len(self.rows):
            raise ValueError("BM25 requires nonempty unique chunks")
        corpus = [
            tokens(c["text"])
            + tokens(c["source_path"]) * 2
            + tokens(c.get("structure_name", "")) * 3
            + tokens(" ".join(c.get("context_path", [])))
            for c in self.rows
        ]
        self.bm25 = BM25Okapi(corpus, k1=k1, b=b)
        # Positive BM25 IDF; common exact symbols must not rank below nonmatches.
        df = Counter(term for doc in corpus for term in set(doc))
        n = len(corpus)
        self.bm25.idf = {
            t: math.log1p((n - f + 0.5) / (f + 0.5)) for t, f in df.items()
        }

    def search(
        self, query: str, allowed: set[str], limit: int
    ) -> list[tuple[str, float]]:
        scores = self.bm25.get_scores(tokens(query))
        hits = [
            (c["chunk_id"], float(s))
            for c, s in zip(self.rows, scores, strict=True)
            if c["chunk_id"] in allowed and s > 0
        ]
        return sorted(hits, key=lambda r: (-r[1], r[0]))[:limit]


def fuse(rankings: list[list[str]], k=60) -> list[tuple[str, float]]:
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, identifier in enumerate(dict.fromkeys(ranking), start=1):
            scores[identifier] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda row: (-row[1], row[0]))
