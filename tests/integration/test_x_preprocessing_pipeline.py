from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from kuping_negara.preprocessing.x_pipeline import (
    PreprocessingPipelineError,
    main,
    parse_raw_partition_path,
    run_preprocessing,
)


JAKARTA_TIMEZONE = ZoneInfo("Asia/Jakarta")


def _write_raw_fixture(root: Path) -> Path:
    raw_directory = (
        root
        / "data"
        / "raw"
        / "x"
        / "collected_date=2026-09-21"
        / "program=mbg"
        / "run_id=20260921T182524+0700"
    )
    raw_directory.mkdir(parents=True)
    raw_path = raw_directory / "mbg_2026-09-14_2026-09-21.csv"
    pd.DataFrame(
        [
            {
                "conversation_id_str": "1000000000000000001",
                "created_at": "Mon Sep 21 11:15:29 +0000 2026",
                "favorite_count": "3",
                "full_text": "@warga MBG bagus 😊 https://t.co/example",
                "id_str": "2000000000000000001",
                "image_url": "",
                "in_reply_to_screen_name": "warga",
                "lang": "in",
                "location": "",
                "quote_count": "0",
                "reply_count": "1",
                "retweet_count": "2",
                "tweet_url": "https://x.com/example/status/1",
                "user_id_str": "3000000000000000001",
                "username": "private_user",
            }
        ]
    ).to_csv(raw_path, index=False, encoding="utf-8-sig")
    return raw_path


def _write_config(root: Path) -> Path:
    config_path = root / "configs" / "keywords" / "programs.example.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        """
schema_version: 1
programs:
  mbg:
    display_name: Makan Bergizi Gratis
    keywords:
      - mbg
      - makan bergizi gratis
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_parse_raw_partition_path_extracts_lineage_metadata(tmp_path: Path) -> None:
    raw_path = _write_raw_fixture(tmp_path)

    metadata = parse_raw_partition_path(raw_path)

    assert metadata.program_id == "mbg"
    assert metadata.ingestion_run_id == "20260921T182524+0700"
    assert metadata.collected_at.isoformat() == "2026-09-21T18:25:24+07:00"


def test_run_preprocessing_writes_private_safe_output_and_quality_report(
    tmp_path: Path,
) -> None:
    raw_path = _write_raw_fixture(tmp_path)
    config_path = _write_config(tmp_path)
    original_checksum = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    artifacts = run_preprocessing(
        input_path=raw_path,
        output_root=tmp_path / "data" / "processed" / "x",
        config_path=config_path,
        processed_at=datetime(
            2026, 9, 21, 19, 0, 0, tzinfo=JAKARTA_TIMEZONE
        ),
    )

    assert artifacts.records_path.relative_to(tmp_path).as_posix() == (
        "data/processed/x/processed_date=2026-09-21/program=mbg/"
        "run_id=20260921T182524+0700/"
        "mbg_2026-09-14_2026-09-21_processed.csv"
    )
    processed = pd.read_csv(artifacts.records_path, dtype=str)
    assert processed["tweet_id"].tolist() == ["2000000000000000001"]
    assert processed["cleaned_text"].tolist() == ["mbg bagus 😊"]
    assert "username" not in processed.columns
    assert "user_id_str" not in processed.columns
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == original_checksum

    report = json.loads(artifacts.report_path.read_text(encoding="utf-8"))
    assert report["input_sha256"] == original_checksum
    assert report["program_id"] == "mbg"
    assert report["source_rows"] == 1
    assert report["eligible_for_labeling"] == 1
    assert report["processed_at"] == "2026-09-21T19:00:00+07:00"


def test_run_preprocessing_refuses_to_overwrite_existing_run(
    tmp_path: Path,
) -> None:
    raw_path = _write_raw_fixture(tmp_path)
    config_path = _write_config(tmp_path)
    parameters = {
        "input_path": raw_path,
        "output_root": tmp_path / "data" / "processed" / "x",
        "config_path": config_path,
        "processed_at": datetime(
            2026, 9, 21, 19, 0, 0, tzinfo=JAKARTA_TIMEZONE
        ),
    }
    run_preprocessing(**parameters)

    with pytest.raises(PreprocessingPipelineError, match="already exists"):
        run_preprocessing(**parameters)


def test_cli_reports_created_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw_path = _write_raw_fixture(tmp_path)
    config_path = _write_config(tmp_path)

    exit_code = main(
        [
            "--input",
            str(raw_path),
            "--output-root",
            str(tmp_path / "data" / "processed" / "x"),
            "--config",
            str(config_path),
            "--processed-at",
            "2026-09-21T19:00:00+07:00",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Processed rows: 1" in output
    assert "Eligible for labeling: 1" in output
    assert "Quality report:" in output


def test_cli_returns_error_for_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "--input",
            str(tmp_path / "missing.csv"),
            "--output-root",
            str(tmp_path / "processed"),
            "--config",
            str(tmp_path / "missing.yaml"),
        ]
    )

    error = capsys.readouterr().err
    assert exit_code == 1
    assert "raw CSV not found" in error
