"""Exercise EDA on the four committed LK-04 sample files."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from kuping_negara.analysis.eda import analyze_processed_runs, render_html
from kuping_negara.preprocessing.x_pipeline import run_preprocessing

ROOT = Path(__file__).resolve().parents[2]


def test_sample_eda_reports_quality_without_exposing_post_text(tmp_path):
    processed_root = tmp_path / "processed"
    sample_files = sorted((ROOT / "data/raw/samples/x").rglob("*.csv"))
    assert len(sample_files) == 4
    for raw_path in sample_files:
        run_preprocessing(
            input_path=raw_path,
            output_root=processed_root,
            config_path=ROOT / "configs/keywords/programs.example.yaml",
            processed_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
        )

    summary = analyze_processed_runs(processed_root)
    page = render_html(summary)
    assert summary["processed_rows"] == 20
    assert summary["eligible_rows"] == 13
    assert summary["unique_annotation_candidates"] == 13
    assert summary["quality_status_counts"]["accepted"] == 13
    assert "<h2>Bahasa dari X</h2>" in page
    source_text = pd.read_csv(sample_files[0])["full_text"].iloc[0]
    assert source_text not in page
    assert "tweet_id" not in page
