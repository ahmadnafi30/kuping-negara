"""Check the image contains code and metadata, without local private payloads."""

from pathlib import Path

root = Path("/opt/kuping-negara")
for relative in [
    ".env",
    ".git",
    ".dvc/credentials",
    ".dvc/config.local",
    "docker/airflow/secrets",
    "mlruns",
    "tmp",
    "output",
]:
    assert not (root / relative).exists(), relative
for path in (root / "data").rglob("*"):
    if path.is_file():
        assert path.name in {".gitkeep", ".gitignore"} or path.name.endswith(
            (".dvc", ".manifest.json")
        ), str(path.relative_to(root))
assert (root / "train.py").is_file()
assert (root / "data/training/sentiment_expanded_20261019.manifest.json").is_file()
print("Training image verified: source/metadata only; no dataset or local credentials")
