"""Create and recover an isolated synthetic DVC snapshot for the Actions demo."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from kuping_negara.training.data import digest, prepare_dataset
from tests.fixtures.training import create_training_repository


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir()
    _, raw, labels = create_training_repository(root)
    source = Path(__file__).resolve().parents[2]
    shutil.copyfile(source / "pyproject.toml", root / "pyproject.toml")
    (root / "src/kuping_negara").mkdir(parents=True)
    (root / ".gitignore").write_text("data/labeled/\nreports/\n", encoding="utf-8")
    dataset = root / "data/training/synthetic.csv"
    prepare_dataset(root, labels, raw, dataset, "lk05-data-v2", True)

    def dvc(*args: str) -> None:
        subprocess.run([sys.executable, "-m", "dvc", *args], cwd=root, check=True)

    targets = ("data/raw/lk05_dataset.csv.dvc", "data/training/synthetic.csv.dvc")
    dvc("init", "--quiet")
    dvc("add", str(raw.relative_to(root)), str(dataset.relative_to(root)))
    dvc(
        "remote",
        "add",
        "--local",
        "fixture",
        str(root.parent / (root.name + "-remote")),
    )
    dvc("push", "-r", "fixture", *targets)
    expected = {path: digest(path) for path in (raw, dataset)}
    for path in expected:
        path.unlink()
    dvc(
        "config",
        "--local",
        "cache.dir",
        str(root.parent / (root.name + "-fresh-cache")),
    )
    dvc("pull", "-r", "fixture", *targets)
    if any(digest(path) != checksum for path, checksum in expected.items()):
        raise ValueError("Restored synthetic DVC snapshot differs from source")
    print("Synthetic raw and training snapshots restored from a fresh DVC cache")


if __name__ == "__main__":
    main()
