from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from kuping_negara.data_pipeline import main as pipeline_main
from kuping_negara.ingestion import tweet_harvest as collector
from kuping_negara.preprocessing.x_pipeline import (
    has_verified_output,
    parse_raw_partition_path,
)
from kuping_negara.preprocessing.x_pipeline import (
    main as preprocess_main,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_cached_runtime_rejects_a_different_package_version(tmp_path: Path) -> None:
    package = tmp_path / "_npx/test/node_modules/tweet-harvest"
    (package / "dist").mkdir(parents=True)
    executable = package / "dist/bin.js"
    executable.touch()
    metadata = package / "package.json"
    metadata.write_text('{"version":"2.7.0"}')
    assert (
        collector.find_cached_tweet_harvest(
            environment={"NPM_CONFIG_CACHE": str(tmp_path)},
        )
        is None
    )
    metadata.write_text('{"version":"2.7.1"}')
    assert (
        collector.find_cached_tweet_harvest(
            explicit_path=executable,
        )
        == executable.resolve()
    )


def test_timeout_stops_crawler_without_promoting_output(tmp_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(collector.CollectionError, match="timed out"):
        collector.execute_collection(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            cwd=tmp_path,
            environment=dict(os.environ),
            timeout=0.1,
            non_interactive=True,
        )
    assert list(tmp_path.iterdir()) == []
    assert time.monotonic() - started < 8


@pytest.fixture
def pipeline_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "src" / "kuping_negara").mkdir(parents=True)
    (tmp_path / "pyproject.toml").touch()
    (tmp_path / "configs" / "keywords").mkdir(parents=True)
    shutil.copyfile(
        PROJECT_ROOT / "configs/keywords/programs.example.yaml",
        tmp_path / "configs/keywords/programs.example.yaml",
    )
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(
        PROJECT_ROOT / "scripts/tweet_harvest_browser_hook.cjs",
        tmp_path / "scripts/tweet_harvest_browser_hook.cjs",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_repeated_replay_preserves_original_and_creates_distinct_runs(
    pipeline_root: Path,
) -> None:
    sample_root = PROJECT_ROOT / "data/raw/samples/x"
    originals = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sample_root.rglob("*.csv")
    }
    assert len(originals) == 4
    assert (
        pipeline_main(
            [
                "--replay-dir",
                str(sample_root),
                "--preprocess",
                "--cycles",
                "2",
                "--interval-seconds",
                "0",
            ]
        )
        == 0
    )
    raw_paths = list((pipeline_root / "data/raw/x").rglob("*.csv"))
    processed_paths = list((pipeline_root / "data/processed/x").rglob("*.csv"))
    assert len(raw_paths) == len(processed_paths) == 8
    assert len({parse_raw_partition_path(p).ingestion_run_id for p in raw_paths}) == 2
    for path, checksum in originals.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum
    for report_path in (pipeline_root / "data/raw/x").rglob("ingestion_report.json"):
        assert json.loads(report_path.read_text())["source"] == "offline_replay"


def test_collector_retries_without_promoting_stale_csv(
    pipeline_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collector.shutil, "which", lambda _: "npx")
    monkeypatch.setattr(collector, "detect_browser_executable", lambda **_: None)
    monkeypatch.setattr(collector.time, "sleep", lambda _: None)
    attempts: list[Path] = []

    def fake_execution(command: list[str], **kwargs: object) -> None:
        cwd = kwargs["cwd"]
        assert isinstance(cwd, Path)
        attempts.append(cwd)
        staging = cwd / "tweets-data"
        staging.mkdir()
        filename = command[command.index("-o") + 1] + ".csv"
        if len(attempts) == 1:
            (staging / filename).write_text("id_str,full_text\n1,stale\n")
            raise collector.CollectionError("connection failed")
        (staging / filename).write_text(
            "id_str,full_text,created_at\n"
            "2,fresh,Mon Sep 21 11:15:29 +0000 2026\n"
        )

    monkeypatch.setattr(collector, "execute_collection", fake_execution)
    code, paths = collector.run_collection(
        [
            "--program",
            "mbg",
            "--from-date",
            "21-09-2026",
            "--to-date",
            "21-09-2026",
            "--attempts",
            "2",
            "--retry-delay",
            "0",
        ]
    )
    assert code == 0 and len(paths) == 1
    assert len(attempts) == 2 and attempts[0] != attempts[1]
    assert "fresh" in paths[0].read_text()
    assert "stale" not in paths[0].read_text()


def test_unattended_without_secret_fails_before_starting_a_process(
    pipeline_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("X_AUTH_TOKEN", raising=False)
    code, paths = collector.run_collection(["--non-interactive"])
    assert code == 1 and paths == []
    assert not (pipeline_root / "tweets-data").exists()


def test_failed_collection_does_not_publish_a_raw_dataset(
    pipeline_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collector.shutil, "which", lambda _: "npx")
    monkeypatch.setattr(collector, "detect_browser_executable", lambda **_: None)

    def fail(*args: object, **kwargs: object) -> None:
        raise collector.CollectionError("unavailable")

    monkeypatch.setattr(collector, "execute_collection", fail)
    code, paths = collector.run_collection(
        [
            "--program",
            "mbg",
            "--attempts",
            "2",
            "--retry-delay",
            "0",
        ]
    )
    assert code == 1 and paths == []
    assert not (pipeline_root / "data/raw/x").exists()


def test_microsecond_run_id_has_unambiguous_lineage() -> None:
    metadata = parse_raw_partition_path(
        Path(
            "collected_date=2026-09-28/program=mbg/"
            "run_id=20260928T120000123456+0700/input.csv"
        )
    )
    assert metadata.collected_at == datetime.fromisoformat(
        "2026-09-28T12:00:00.123456+07:00"
    )


def test_batch_preprocessing_skips_only_intact_outputs(
    pipeline_root: Path,
) -> None:
    raw_root = PROJECT_ROOT / "data/raw/samples/x"
    output_root = pipeline_root / "data/processed/x"
    config = pipeline_root / "configs/keywords/programs.example.yaml"
    options = [
        "--input-dir",
        str(raw_root),
        "--output-root",
        str(output_root),
        "--config",
        str(config),
        "--skip-existing",
    ]
    assert preprocess_main(options) == 0
    assert preprocess_main(options) == 0
    assert len(list(output_root.rglob("*_processed.csv"))) == 4
    input_path = next(raw_root.rglob("*.csv"))
    assert has_verified_output(input_path, output_root, config)
    config.write_text(config.read_text() + "\n# changed configuration\n")
    assert not has_verified_output(input_path, output_root, config)


def test_hook_answers_only_expected_prompts_without_logging_secret(
    pipeline_root: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise the Tweet Harvest hook")
    package_root = pipeline_root / "node_modules/tweet-harvest"
    (package_root / "dist").mkdir(parents=True)
    prompts_root = pipeline_root / "node_modules/prompts"
    prompts_root.mkdir()
    (prompts_root / "index.js").write_text(
        "module.exports = () => { throw new Error('unexpected prompt'); };"
    )
    token = "a" * 40
    script = package_root / "dist/bin.js"
    script.write_text(
        "const prompts = require('prompts');\n"
        "(async () => {\n"
        "const answers = await prompts([{name:'token'}, {name:'exportFormat'}]);\n"
        "if (answers.token !== process.env.X_AUTH_TOKEN) process.exit(2);\n"
        "if (answers.exportFormat !== 'csv') process.exit(3);\n"
        "try { await prompts([{name:'other'}]); process.exit(4); }\n"
        "catch (error) { console.log('Expected prompt guard'); }\n"
        "})();\n"
    )
    result = subprocess.run(
        [
            node,
            "--require",
            str(pipeline_root / "scripts/tweet_harvest_browser_hook.cjs"),
            str(script),
        ],
        env={**os.environ, "KUPING_NEGARA_NON_INTERACTIVE": "1", "X_AUTH_TOKEN": token},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert token not in result.stdout + result.stderr
    assert "Expected prompt guard" in result.stdout


def test_empty_and_url_only_records_are_not_marked_ready() -> None:
    from kuping_negara.preprocessing.x_posts import (
        PreprocessingError,
        preprocess_tweet_harvest_frame,
    )

    raw_path = next((PROJECT_ROOT / "data/raw/samples/x").rglob("*.csv"))
    source = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
    parameters = {
        "program_id": "mbg",
        "ingestion_run_id": "test",
        "collected_at": datetime.fromisoformat("2026-09-28T12:00:00+07:00"),
        "keywords": ["mbg"],
    }
    with pytest.raises(PreprocessingError, match="at least one row"):
        preprocess_tweet_harvest_frame(source.iloc[0:0], **parameters)
    source = source.iloc[[0]].copy()
    source["full_text"] = "@mbg https://example.test/mbg"
    source["lang"] = "in"
    result = preprocess_tweet_harvest_frame(source, **parameters)
    assert result.records["quality_status"].tolist() == ["review_empty_cleaned_text"]
    assert result.report["eligible_for_labeling"] == 0
