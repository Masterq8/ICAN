from __future__ import annotations

import posixpath
import re
from pathlib import PurePosixPath

from .schema import SearchRequest


def resolve_family(query: str, collection: str, requested: str) -> tuple[str, str]:
    if requested != "auto":
        return requested, "explicit_request"
    found = set()
    for family, pattern in {
        "swin_v2": r"swin[\s_-]*(?:transformer[\s_-]*)?v2",
        "swin_moe": r"swin[\s_-]*moe|swin_transformer_moe",
        "swin_mlp": r"swin[\s_-]*mlp",
        "simmim": r"simmim",
    }.items():
        if re.search(pattern, query, re.IGNORECASE):
            found.add(family)
    if re.search(
        r"swin[\s_-]*t(?![a-z0-9])|swin[\s_-]*(?:transformer[\s_-]*)?v1",
        query,
        re.IGNORECASE,
    ):
        found.add("swin_v1")
    if len(found) > 1:
        return "all", "multiple_query_families"
    if found:
        return found.pop(), "explicit_query_family"
    return (
        ("swin_v1", "collection_default_swin_v1")
        if collection == "swin_v1"
        else ("all", "no_family_context")
    )


def path_family(path: str) -> str | None:
    path = path.lower()
    if "simmim" in path:
        return "simmim"
    if "swinmoe" in path or "_moe" in path:
        return "swin_moe"
    if "swinmlp" in path or "swin_mlp" in path:
        return "swin_mlp"
    if "swinv2" in path or "swin_transformer_v2" in path:
        return "swin_v2"
    if "/configs/swin/" in "/" + path or path.endswith("models/swin_transformer.py"):
        return "swin_v1"
    return None  # Shared entry points and documentation remain eligible.


def eligible(chunk: dict, request: SearchRequest, family: str) -> bool:
    filters = request.filters
    if filters.source_types and chunk["source_type"] not in filters.source_types:
        return False
    if filters.path_prefixes and not any(
        chunk["source_path"].startswith(p) for p in filters.path_prefixes
    ):
        return False
    assigned = path_family(chunk["source_path"])
    if family != "all" and assigned is not None and assigned != family:
        return False
    # A named model size limits YAMLs, while shared Python/academic text survives.
    if chunk["source_type"] == "config":
        sizes = set()
        for size, letter in {
            "tiny": "t",
            "small": "s",
            "base": "b",
            "large": "l",
        }.items():
            if re.search(
                rf"swin[\s_-]*{letter}(?![a-z0-9])|swin_{size}\b",
                request.query,
                re.IGNORECASE,
            ):
                sizes.add(size)
        if len(sizes) == 1:
            size = next(iter(sizes))
            detected = re.search(
                r"swin(?:v2)?_(tiny|small|base|large)_",
                chunk["source_path"],
                re.IGNORECASE,
            )
            if detected and detected.group(1).lower() != size:
                return False
    return True


def query_config_paths(rows: list[dict], query: str) -> set[str] | None:
    """Named YAML files and their static BASE references; no configuration execution."""
    import yaml

    names = set(re.findall(r"[a-zA-Z0-9_.-]+\.ya?ml(?![a-zA-Z0-9_.-])", query))
    if not names:
        return None
    paths = {r["source_path"] for r in rows if r["source_type"] == "config"}
    selected = {p for p in paths if PurePosixPath(p).name in names}
    if not selected:
        return set()  # Unknown filenames are not replaced with another YAML entity.
    pending = list(selected)
    while pending:
        path = pending.pop()
        for row in rows:
            if row["source_path"] != path or row.get("structure_name") != "BASE":
                continue
            value = yaml.safe_load(row["text"])
            bases = value.get("BASE", []) if isinstance(value, dict) else []
            if not isinstance(bases, list):
                continue
            for base in bases:
                if not isinstance(base, str) or not base:
                    continue
                # Normalize POSIX references lexically; never read a new file.
                target = posixpath.normpath(str(PurePosixPath(path).parent / base))
                if target in paths and target not in selected:
                    selected.add(target)
                    pending.append(target)
    return selected
