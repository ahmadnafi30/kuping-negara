"""Validated raw versions preserve history and reject fabricated updates."""

import csv
import json

import pytest

from kuping_negara.data_versioning.snapshots import build_snapshot, sha256
from kuping_negara.ingestion.storage import CollectionError
from kuping_negara.paths import DEFAULT_CONFIG_PATH


@pytest.fixture
def repository(tmp_path):
    config = tmp_path / DEFAULT_CONFIG_PATH
    config.parent.mkdir(parents=True)
    config.write_text("test keyword configuration", encoding="utf-8")
    return tmp_path


def collection(root, program, run, ids):
    source = root / "data/raw/x" / f"program={program}" / f"run_id={run}" / "posts.csv"
    source.parent.mkdir(parents=True)
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["id_str", "full_text", "created_at"]
        )
        writer.writeheader()
        writer.writerows(
            {
                "id_str": value,
                "full_text": "Teks uji",
                "created_at": "2026-10-10T12:00:00Z",
            }
            for value in ids
        )
    manifest = {
        "from_date": "2026-10-04",
        "to_date": "2026-10-10",
        "limit": len(ids),
        "input_sha256": sha256(source),
        "config_sha256": sha256(root / DEFAULT_CONFIG_PATH),
    }
    (source.parent / "collection.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return source


def snapshot(root, sources, append=False, **overrides):
    options = {
        "repository_root": root,
        "inputs": sources,
        "output": root / "data/raw/dataset.csv",
        "metrics_path": root / "reports/metrics.json",
        "append": append,
    }
    return build_snapshot(**(options | overrides))


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_append_preserves_old_rows_and_deduplicates_per_program(repository):
    first = collection(repository, "ckg", "first", ["1", "2"])
    old = snapshot(repository, [first])
    old_rows = read_rows(repository / old["dataset"])
    next_ckg = collection(repository, "ckg", "next", ["2", "3"])
    next_mbg = collection(repository, "mbg", "next", ["1"])
    source_hashes = {p: sha256(p) for p in [first, next_ckg, next_mbg]}
    new = snapshot(repository, [next_ckg, next_mbg], append=True)
    assert (new["previous_rows"], new["rows"], new["new_unique_rows"]) == (2, 4, 2)
    assert new["program_counts"] == {"ckg": 3, "mbg": 1}
    assert new["previous_sha256"] == old["sha256"] != new["sha256"]
    assert read_rows(repository / new["dataset"])[:2] == old_rows
    assert new["sources"][0]["duplicate_keys_skipped"] == 1
    assert all(sha256(p) == original for p, original in source_hashes.items())
    assert new["training_performed"] is False


def test_duplicate_only_append_leaves_snapshot_and_metrics_unchanged(repository):
    source = collection(repository, "ckg", "first", ["1"])
    snapshot(repository, [source])
    files = [repository / "data/raw/dataset.csv", repository / "reports/metrics.json"]
    before = [p.read_bytes() for p in files]
    with pytest.raises(ValueError, match="No new unique rows"):
        snapshot(repository, [source], append=True)
    assert [p.read_bytes() for p in files] == before


def test_invalid_later_input_cannot_publish_partial_append(repository):
    first = collection(repository, "ckg", "first", ["1"])
    snapshot(repository, [first])
    valid = collection(repository, "ckg", "next", ["2"])
    invalid = collection(repository, "mbg", "next", ["3"])
    invalid.write_text(
        invalid.read_text(encoding="utf-8-sig") + "tampered", encoding="utf-8"
    )
    original = (repository / "data/raw/dataset.csv").read_bytes()
    with pytest.raises(CollectionError, match="hash has changed"):
        snapshot(repository, [valid, invalid], append=True)
    assert (repository / "data/raw/dataset.csv").read_bytes() == original


def test_overwrite_requires_explicit_append(repository):
    source = collection(repository, "ckg", "first", ["1"])
    snapshot(repository, [source])
    with pytest.raises(ValueError, match="explicit append"):
        snapshot(repository, [source])


@pytest.mark.parametrize(
    "field,location",
    [("output", "outside.csv"), ("metrics_path", "data/raw/protected.csv")],
)
def test_output_boundaries_prevent_overwriting_sources(repository, field, location):
    source = collection(repository, "ckg", "first", ["1"])
    with pytest.raises(ValueError, match="must stay inside"):
        snapshot(repository, [source], **{field: repository / location})
    assert not (repository / "data/raw/dataset.csv").exists()
