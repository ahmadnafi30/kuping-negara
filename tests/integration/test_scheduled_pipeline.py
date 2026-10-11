"""Exercise scheduled retries and atomic publication without a real X account."""

import csv
import shutil
from datetime import date, datetime
from pathlib import Path

import pytest

from kuping_negara.ingestion.storage import CollectionError
from kuping_negara.orchestration.runtime import (
    collect_scheduled,
    collection_window,
    preprocess_scheduled,
)
from kuping_negara.paths import JAKARTA_TIMEZONE
from kuping_negara.preprocessing.x_pipeline import PreprocessingPipelineError

SCHEDULE = datetime(2026, 10, 12, 23, 59, tzinfo=JAKARTA_TIMEZONE)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    config = tmp_path / "configs/keywords/programs.example.yaml"
    config.parent.mkdir(parents=True)
    shutil.copyfile(Path("configs/keywords/programs.example.yaml"), config)
    token = tmp_path / "token"
    token.write_text("a" * 40)  # Synthetic credential, never a real account.
    monkeypatch.setenv("KUPING_NEGARA_TOKEN_FILE", str(token))
    monkeypatch.setenv("KUPING_NEGARA_COLLECTOR", str(tmp_path / "collector.js"))
    browser = tmp_path / "chromium"
    browser.touch()
    monkeypatch.setenv("KUPING_NEGARA_BROWSER_EXECUTABLE", str(browser))
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/tweet_harvest_browser_hook.cjs").touch()
    return tmp_path


def write_collection(command, cwd, environment):
    assert "a" * 40 not in " ".join(command)
    assert "a" * 40 not in str(environment)
    assert command[0] == "node"
    assert "tweet_harvest_secret_hook.cjs" in environment["NODE_OPTIONS"]
    assert command[command.index("--to") + 1] == "12-10-2026"
    target = cwd / "tweets-data" / f"{command[command.index('-o') + 1]}.csv"
    target.parent.mkdir()
    with target.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "id_str",
                "full_text",
                "created_at",
                "tweet_url",
                "lang",
                "conversation_id_str",
                "favorite_count",
                "quote_count",
                "reply_count",
                "retweet_count",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "id_str": "1234567890123456789",
                "full_text": "Program MBG membantu siswa",
                "created_at": "2026-10-11T12:00:00Z",
                "tweet_url": "https://x.com/example/status/1234567890123456789",
                "lang": "in",
                "conversation_id_str": "1234567890123456789",
                "favorite_count": "0",
                "quote_count": "0",
                "reply_count": "0",
                "retweet_count": "0",
            }
        )


def collect(repository, runner=write_collection, execution_id="scheduled__example"):
    return collect_scheduled(
        repository_root=repository,
        program_id="mbg",
        scheduled_at=SCHEDULE,
        execution_id=execution_id,
        runner=runner,
    )


def test_window_uses_previous_seven_complete_jakarta_days():
    assert collection_window(SCHEDULE) == (date(2026, 10, 5), date(2026, 10, 11))
    assert collection_window(datetime.fromisoformat("2027-01-01T00:30:00+07:00")) == (
        date(2026, 12, 25),
        date(2026, 12, 31),
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        collection_window(datetime(2026, 10, 12))


def test_collection_retry_reuses_only_verified_result(repository):
    raw = collect(repository)
    original = raw.read_bytes()

    def must_not_run(*args):
        pytest.fail("Retry must reuse existing successful collection")

    assert collect(repository, must_not_run) == raw
    assert raw.read_bytes() == original
    assert not list((repository / "data/raw/x").glob(".collect-*"))
    raw.write_text("changed")
    with pytest.raises(CollectionError, match="changed"):
        collect(repository, must_not_run)


def test_collection_failure_does_not_publish_partial_csv(repository):
    def failed(command, cwd, environment):
        write_collection(command, cwd, environment)
        raise CollectionError("Upstream failed after writing partial output")

    with pytest.raises(CollectionError, match="partial"):
        collect(repository, failed)
    assert not list((repository / "data/raw/x").rglob("*.csv"))


def test_empty_result_is_not_success(repository):
    def empty(command, cwd, environment):
        target = cwd / "tweets-data" / f"{command[command.index('-o') + 1]}.csv"
        target.parent.mkdir()
        target.write_text("id_str,full_text\n")

    with pytest.raises(CollectionError, match="no tweet rows"):
        collect(repository, empty)
    assert not list((repository / "data/raw/x").rglob("*.csv"))


def test_missing_secret_fails_before_starting_collector(repository, monkeypatch):
    monkeypatch.setenv("KUPING_NEGARA_TOKEN_FILE", str(repository / "absent"))
    with pytest.raises(CollectionError, match="secret"):
        collect(repository)


def test_separate_airflow_runs_do_not_collide(repository):
    first = collect(repository)
    second = collect(repository, execution_id="manual__example")
    assert first != second
    assert first.read_bytes() == second.read_bytes()


def test_preprocessing_retry_and_tamper_detection(repository):
    raw = collect(repository)
    shared = {
        "repository_root": repository,
        "raw_path": raw,
        "scheduled_at": SCHEDULE,
        "execution_id": "scheduled__example",
    }
    result = preprocess_scheduled(**shared)
    assert preprocess_scheduled(**shared) == result
    assert raw.is_file()
    assert Path(result["report_path"]).is_file()
    assert not list((repository / "data/processed/x").glob(".preprocess-*"))
    Path(result["records_path"]).write_text("changed")
    with pytest.raises(PreprocessingPipelineError, match="changed"):
        preprocess_scheduled(**shared)


def test_preprocessing_rejects_external_path(repository):
    with pytest.raises(ValueError, match="data/raw/x"):
        preprocess_scheduled(
            repository_root=repository,
            raw_path=repository / "outside.csv",
            scheduled_at=SCHEDULE,
            execution_id="manual",
        )


def test_config_change_refuses_collection_retry(repository):
    collect(repository)
    config = repository / "configs/keywords/programs.example.yaml"
    config.write_text(config.read_text() + "\n# Changed configuration\n")
    with pytest.raises(CollectionError, match="changed"):
        collect(repository)


def test_preprocessing_failure_never_publishes_a_run(repository):
    raw = collect(repository)
    raw.write_text("id_str,full_text\n1,invalid schema\n")
    from kuping_negara.preprocessing.x_posts import PreprocessingError

    with pytest.raises(PreprocessingError, match="missing required columns"):
        preprocess_scheduled(
            repository_root=repository,
            raw_path=raw,
            scheduled_at=SCHEDULE,
            execution_id="scheduled__example",
        )
    assert not list((repository / "data/processed/x").rglob("*.csv"))
    assert not list((repository / "data/processed/x").glob(".preprocess-*"))
