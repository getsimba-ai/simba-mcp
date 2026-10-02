"""Shared numeric summaries, serialisation and reproducible source provenance."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import statistics
import subprocess
from pathlib import Path
from typing import Any


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def provenance() -> dict:
    packages = {}
    for name in ("simba-mcp", "mcp", "httpx", "pydantic", "tiktoken"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    source = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(source.rglob("*.py")):
        digest.update(path.relative_to(source).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    root = source.parents[1]
    revision, dirty = None, None
    if (root / "pyproject.toml").is_file():
        try:
            revision = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True,
            ).strip()
            dirty = bool(
                subprocess.check_output(
                    ["git", "-C", str(root), "status", "--porcelain"],
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    text=True,
                ).strip()
            )
        except (OSError, subprocess.SubprocessError):
            revision, dirty = None, None
    return {
        "packages": packages,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "git_revision": revision,
        "git_dirty": dirty,
        "python_source_sha256": digest.hexdigest(),
    }


def distribution(values: list[float]) -> dict:
    ordered = sorted(values)
    return {
        "samples": len(values),
        "min": ordered[0],
        "median": statistics.median(values),
        "p95": ordered[math.ceil(len(values) * 0.95) - 1],
        "max": ordered[-1],
    }
