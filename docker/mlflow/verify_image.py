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
assert not list((root / "data/raw").glob("*.csv"))
assert not list((root / "data/training").glob("*.csv"))
assert (root / "train.py").is_file()
assert (root / "data/training/sentiment_expanded_20261019.manifest.json").is_file()
print("Training image verified: source/metadata only; no dataset or local credentials")
