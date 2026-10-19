"""Reject stale training images, then run the ordinary training entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

root = Path("/opt/kuping-negara")
source_paths = [
    "src",
    "configs",
    "train.py",
    "pyproject.toml",
    "uv.lock",
    "docker/mlflow",
]
result = subprocess.run(
    ["git", "diff", "--quiet", "HEAD", "--", *source_paths], cwd=root, check=False
)
if result.returncode:
    raise SystemExit("Image source differs from Git HEAD; rebuild the mlflow image")
raise SystemExit(
    subprocess.call([sys.executable, str(root / "train.py"), *sys.argv[1:]], cwd=root)
)
