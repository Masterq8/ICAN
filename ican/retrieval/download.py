"""Public pinned model download fallback when a full HTTP response stalls."""

from __future__ import annotations

import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ican.indexing.model import file_digest
from ican.ingestion.pipeline import confined


def download_ranges(root: Path, config, name: str):
    identity = config.files[name]
    if not identity.sha256:
        raise ValueError("Range fallback requires an official SHA-256")
    directory = confined(root, config.local_path, "data/cache")
    parts = confined(
        root, f"data/cache/reranking/downloads/{identity.sha256}", "data/cache"
    )
    parts.mkdir(parents=True, exist_ok=True)
    size = identity.size
    block = 32 * 1024 * 1024
    ranges = [(start, min(start + block, size) - 1) for start in range(0, size, block)]

    def fetch(bounds):
        start, end = bounds
        destination = parts / f"{start}.part"
        if destination.exists() and destination.stat().st_size == end - start + 1:
            return destination
        url = f"https://huggingface.co/{config.repository}/resolve/{config.revision}/{name}?download=true&ican_part={start}"
        request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
        temporary = parts / f"{start}.tmp"
        with urllib.request.urlopen(request, timeout=40) as response:
            if (
                response.status != 206
                or response.headers.get("Content-Range")
                != f"bytes {start}-{end}/{size}"
            ):
                raise ValueError("Server did not honor the requested byte range")
            with temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream, length=1024 * 1024)
        if temporary.stat().st_size != end - start + 1:
            raise ValueError("Incomplete weight range")
        temporary.replace(destination)
        return destination

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, bounds) for bounds in ranges]
        for n, future in enumerate(as_completed(futures), start=1):
            future.result()
            print(f"weight ranges {n}/{len(ranges)}", flush=True)
    merged = parts / "merged.tmp"
    with merged.open("wb") as stream:
        for start, _ in ranges:
            with (parts / f"{start}.part").open("rb") as fragment:
                shutil.copyfileobj(fragment, stream, length=1024 * 1024)
    if merged.stat().st_size != size or file_digest(merged) != identity.sha256:
        raise ValueError("Assembled weights differ from official SHA-256")
    merged.replace(directory / name)
