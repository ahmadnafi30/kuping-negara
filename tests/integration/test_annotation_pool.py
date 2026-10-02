"""Check cross-run deduplication using the committed LK-04 source sample."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from kuping_negara.preprocessing.x_pipeline import run_preprocessing
from kuping_negara.training.candidates import (
    CandidatePoolError,
    build_annotation_pool,
    load_verified_run,
)

ROOT = Path(__file__).resolve().parents[2]


def test_annotation_pool_keeps_one_candidate_from_repeated_runs(tmp_path):
    raw_path = next((ROOT / "data/raw/samples/x").rglob("*.csv"))
    processed_root = tmp_path / "processed"
    config_path = ROOT / "configs/keywords/programs.example.yaml"
    first = run_preprocessing(
        input_path=raw_path,
        output_root=processed_root,
        config_path=config_path,
        processed_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )
    run_preprocessing(
        input_path=raw_path,
        output_root=processed_root,
        config_path=config_path,
        processed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )

    csv_path, report_path = build_annotation_pool(
        processed_root, tmp_path / "pool", build_id="sample-v1"
    )
    candidates = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    first_report = json.loads(first.report_path.read_text(encoding="utf-8"))
    assert len(candidates) == first_report["eligible_for_labeling"]
    assert report["duplicates_removed_across_runs"] == len(candidates)
    assert candidates[["target_program", "tweet_id"]].duplicated().sum() == 0
    assert candidates["quality_status"].eq("accepted").all()
    assert csv_path.parent.name == "build_id=sample-v1"
    default_csv, _ = build_annotation_pool(processed_root, tmp_path / "default-pool")
    assert default_csv.parent.name.endswith("WIB")


def test_pool_rejects_a_processed_csv_changed_after_reporting(tmp_path):
    raw_path = next((ROOT / "data/raw/samples/x").rglob("*.csv"))
    artifact = run_preprocessing(
        input_path=raw_path,
        output_root=tmp_path / "processed",
        config_path=ROOT / "configs/keywords/programs.example.yaml",
        processed_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )
    artifact.records_path.write_bytes(artifact.records_path.read_bytes() + b" ")
    with pytest.raises(CandidatePoolError, match="does not match quality report"):
        load_verified_run(artifact.records_path)

