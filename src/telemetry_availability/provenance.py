from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy
import yaml


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(arguments: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _git_dirty() -> bool | None:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return bool(completed.stdout.strip())


def environment_manifest() -> dict[str, Any]:
    github = {
        key: os.environ[key]
        for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "GITHUB_REF")
        if key in os.environ
    }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "dependencies": {
            "numpy": numpy.__version__,
            "PyYAML": yaml.__version__,
        },
        "git": {
            "commit": _git_value(["rev-parse", "HEAD"]),
            "dirty": _git_dirty(),
        },
        "github": github,
    }
