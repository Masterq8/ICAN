"""Pin the actual Docling model revisions, not mutable upstream tags."""

from pathlib import Path

MODEL_REVISIONS = {
    "docling-project/docling-layout-heron": "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
    "docling-project/docling-models": "fc0f2d45e2218ea24bce5045f58a389aed16dc23",
}


def ensure_models() -> Path:
    from huggingface_hub import snapshot_download

    from .parsers import sha256
    from .pipeline import write_json

    root = Path(__file__).resolve().parents[2]
    artifacts = root / "data/cache/docling"
    manifest = []
    for repo, revision in MODEL_REVISIONS.items():
        folder = artifacts / repo.replace("/", "--")
        patterns = (
            ["*.json", "*.safetensors", "README.md"]
            if repo.endswith("heron")
            else ["model_artifacts/tableformer/accurate/*", "README.md", "config.json"]
        )
        if not (folder / ".ready").exists():
            # Reuse the previously downloaded pinned cache; copy only the models
            # selected for this pipeline. Fall back to pinned official downloads.
            import shutil

            try:
                cached = Path(
                    snapshot_download(repo, revision=revision, local_files_only=True)
                )
            except FileNotFoundError:
                cached = Path(
                    snapshot_download(repo, revision=revision, allow_patterns=patterns)
                )
            for file in cached.rglob("*"):
                if file.is_file() and any(
                    file.relative_to(cached).as_posix() == p
                    or file.relative_to(cached).match(p)
                    for p in patterns
                ):
                    destination = folder / file.relative_to(cached)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, destination)
            (folder / ".ready").write_text(revision, encoding="utf-8")
        if (folder / ".ready").read_text(encoding="utf-8") != revision:
            raise ValueError(f"Model revision mismatch: {folder}")
        manifest.append(
            {
                "repo_id": repo,
                "revision": revision,
                "source_url": f"https://huggingface.co/{repo}/tree/{revision}",
                "files": [
                    {
                        "path": p.relative_to(root).as_posix(),
                        "sha256": sha256(p.read_bytes()),
                        "bytes": p.stat().st_size,
                    }
                    for p in sorted(folder.rglob("*"))
                    if p.is_file() and p.name != ".ready"
                ],
            }
        )
    write_json(root / "data/catalog/docling-models.json", manifest)
    return artifacts
