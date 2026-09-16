from pathlib import Path


def artifact_path(output: Path, name: str) -> Path:
    """Refuse existing artifact links before writes can follow them."""
    path = output / name
    if path.is_symlink() or path.resolve().parent != output.resolve():
        raise ValueError(f"Artifact must be a direct file inside output: {name}")
    if path.exists() and path.stat().st_nlink > 1:
        raise ValueError(
            f"Artifact must not share a hard link with another file: {name}"
        )
    return path
