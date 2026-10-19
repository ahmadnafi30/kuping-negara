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
    with pytest.raises(PreprocessingPipelineError, match="changed"):
        preprocess_scheduled(
            repository_root=repository,
            raw_path=raw,
            scheduled_at=SCHEDULE,
            execution_id="scheduled__example",
        )
    assert not list((repository / "data/processed/x").rglob("*.csv"))
    assert not list((repository / "data/processed/x").glob(".preprocess-*"))


@pytest.mark.parametrize("timestamp", ["2026-10-04T16:59:59Z", "2026-10-11T17:00:00Z"])
def test_out_of_window_collection_never_publishes(repository, timestamp):
    def wrong_date(command, cwd, environment):
        write_collection(command, cwd, environment)
        target = next((cwd / "tweets-data").glob("*.csv"))
        target.write_text(target.read_text().replace("2026-10-11T12:00:00Z", timestamp))

    with pytest.raises(CollectionError, match="outside requested Jakarta window"):
        collect(repository, wrong_date)
    assert not list((repository / "data/raw/x").rglob("*.csv"))


def test_over_limit_collection_never_publishes(repository):
    def too_many(command, cwd, environment):
        write_collection(command, cwd, environment)
        target = next((cwd / "tweets-data").glob("*.csv"))
        lines = target.read_text().splitlines()
        target.write_text(lines[0] + "\n" + (lines[1] + "\n") * 60)

    with pytest.raises(CollectionError, match="exceeds requested limit"):
        collect(repository, too_many)
    assert not list((repository / "data/raw/x").rglob("*.csv"))


def test_legacy_raw_retry_cannot_bypass_new_quality_gates(repository):
    import json

    from kuping_negara.ingestion.validation import sha256_file

    raw = collect(repository)
    raw.write_text(
        raw.read_text().replace("2026-10-11T12:00:00Z", "2026-10-12T12:00:00Z")
    )
    manifest_path = raw.parent / "collection.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["input_sha256"] = sha256_file(raw)
    manifest.pop("validation")
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(CollectionError, match="outside requested Jakarta window"):
        collect(repository)
    with pytest.raises(
        PreprocessingPipelineError, match="outside requested Jakarta window"
    ):
        preprocess_scheduled(
            repository_root=repository,
            raw_path=raw,
            scheduled_at=SCHEDULE,
            execution_id="scheduled__example",
        )
    assert not list((repository / "data/processed/x").rglob("*.csv"))


def test_cross_run_duplicate_keeps_rows_but_blocks_second_labeling(repository):
    import json

    import pandas as pd

    first = collect(repository)
    second = collect(repository, execution_id="manual__second")

    def process(raw, execution):
        return preprocess_scheduled(
            repository_root=repository,
            raw_path=raw,
            scheduled_at=SCHEDULE,
            execution_id=execution,
        )

    first_result = process(first, "scheduled__example")
    second_result = process(second, "manual__second")
    second_frame = pd.read_csv(second_result["records_path"], dtype=str)
    assert second_frame["quality_status"].tolist() == ["duplicate"]
    assert second_frame["is_eligible_for_labeling"].tolist() == ["False"]
    report = json.loads(Path(second_result["report_path"]).read_text())
    assert report["duplicate_tweet_ids_across_runs"] == 1
    assert report["eligible_for_labeling"] == 0
    assert process(first, "scheduled__example") == first_result
    assert (
        pd.read_csv(first_result["records_path"]).iloc[0]["quality_status"]
        == "accepted"
    )


def test_concurrent_preprocessing_publishes_one_eligible_copy(repository):
    import json
    from concurrent.futures import ThreadPoolExecutor

    inputs = [collect(repository, execution_id=name) for name in ("run_a", "run_b")]

    def process(pair):
        raw, name = pair
        return preprocess_scheduled(
            repository_root=repository,
            raw_path=raw,
            scheduled_at=SCHEDULE,
            execution_id=name,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(process, zip(inputs, ("run_a", "run_b"), strict=True)))
    eligible = [
        json.loads(Path(result["report_path"]).read_text())["eligible_for_labeling"]
        for result in results
    ]
    assert sorted(eligible) == [0, 1]


def test_unusable_previous_row_does_not_poison_future_labeling(repository):
    import pandas as pd

    def irrelevant(command, cwd, environment):
        write_collection(command, cwd, environment)
        target = next((cwd / "tweets-data").glob("*.csv"))
        target.write_text(
            target.read_text().replace("Program MBG membantu siswa", "Berita lain")
        )

    first = collect(repository, irrelevant)
    first_result = preprocess_scheduled(
        repository_root=repository,
        raw_path=first,
        scheduled_at=SCHEDULE,
        execution_id="scheduled__example",
    )
    second = collect(repository, execution_id="new_run")
    second_result = preprocess_scheduled(
        repository_root=repository,
        raw_path=second,
        scheduled_at=SCHEDULE,
        execution_id="new_run",
    )
    assert (
        pd.read_csv(first_result["records_path"]).iloc[0]["quality_status"]
        == "review_relevance"
    )
    assert (
        pd.read_csv(second_result["records_path"]).iloc[0]["quality_status"]
        == "accepted"
    )


def test_quarantine_preserves_raw_and_old_output(repository):
    import json

    from kuping_negara.orchestration.audit import audit_existing_outputs

    raw = collect(repository)
    original = raw.read_bytes()
    result = preprocess_scheduled(
        repository_root=repository,
        raw_path=raw,
        scheduled_at=SCHEDULE,
        execution_id="scheduled__example",
    )
    output = Path(result["records_path"]).read_bytes()
    report_path = Path(result["report_path"])
    report = json.loads(report_path.read_text())
    report.pop("preprocessing_version")
    report_path.write_text(json.dumps(report))
    audit = audit_existing_outputs(repository)
    assert audit["quarantined_runs"] == 1
    assert raw.read_bytes() == original
    assert not Path(result["records_path"]).exists()
    saved = next((repository / "data/quarantine/x/processed").rglob("*_processed.csv"))
    assert saved.read_bytes() == output
    assert audit_existing_outputs(repository)["quarantined_runs"] == 0


def test_same_tweet_can_be_labeled_for_two_programs_with_shared_group(repository):
    import pandas as pd

    def both_programs(command, cwd, environment):
        write_collection(command, cwd, environment)
        target = next((cwd / "tweets-data").glob("*.csv"))
        frame = pd.read_csv(target, dtype=str, keep_default_na=False)
        frame.loc[0, "full_text"] = "MBG membantu siswa, CKG belum merata"
        frame.to_csv(target, index=False, encoding="utf-8")

    first = collect(repository, both_programs)
    second = collect_scheduled(
        repository_root=repository,
        program_id="ckg",
        scheduled_at=SCHEDULE,
        execution_id="ckg_run",
        runner=both_programs,
    )
    frames = []
    for raw, name in [(first, "scheduled__example"), (second, "ckg_run")]:
        result = preprocess_scheduled(
            repository_root=repository,
            raw_path=raw,
            scheduled_at=SCHEDULE,
            execution_id=name,
        )
        frames.append(pd.read_csv(result["records_path"], dtype=str))
    assert [frame.iloc[0]["quality_status"] for frame in frames] == [
        "accepted",
        "accepted",
    ]
    assert frames[0].iloc[0]["split_group_id"] == frames[1].iloc[0]["split_group_id"]


def test_same_text_new_id_across_runs_cannot_enter_second_labeling_sample(repository):
    import pandas as pd

    first = collect(repository)
    first_result = preprocess_scheduled(
        repository_root=repository,
        raw_path=first,
        scheduled_at=SCHEDULE,
        execution_id="scheduled__example",
    )

    def different_id(command, cwd, environment):
        write_collection(command, cwd, environment)
        target = next((cwd / "tweets-data").glob("*.csv"))
        target.write_text(
            target.read_text().replace("1234567890123456789", "2234567890123456789")
        )

    second = collect(repository, different_id, execution_id="second_id")
    result = preprocess_scheduled(
        repository_root=repository,
        raw_path=second,
        scheduled_at=SCHEDULE,
        execution_id="second_id",
    )
    frame = pd.read_csv(result["records_path"], dtype=str)
    assert frame.iloc[0]["quality_status"] == "duplicate_text"
    assert frame.iloc[0]["is_eligible_for_labeling"] == "False"
    assert (
        frame.iloc[0]["split_group_id"]
        == pd.read_csv(first_result["records_path"], dtype=str).iloc[0][
            "split_group_id"
        ]
    )


def test_modified_opinion_across_runs_is_retained_for_review(repository):
    import pandas as pd

    positive = "Program MBG sangat membantu siswa mendapatkan makanan sehat setiap hari"
    negative = (
        "Program MBG tidak sangat membantu siswa mendapatkan makanan sehat setiap hari"
    )

    def runner(text, identity):
        def write(command, cwd, environment):
            write_collection(command, cwd, environment)
            target = next((cwd / "tweets-data").glob("*.csv"))
            target.write_text(
                target.read_text()
                .replace("Program MBG membantu siswa", text)
                .replace("1234567890123456789", identity)
            )

        return write

    first = collect(repository, runner(positive, "1234567890123456789"))
    preprocess_scheduled(
        repository_root=repository,
        raw_path=first,
        scheduled_at=SCHEDULE,
        execution_id="scheduled__example",
    )
    second = collect(
        repository, runner(negative, "2234567890123456789"), execution_id="negative_run"
    )
    result = preprocess_scheduled(
        repository_root=repository,
        raw_path=second,
        scheduled_at=SCHEDULE,
        execution_id="negative_run",
    )
    frame = pd.read_csv(result["records_path"], dtype=str)
    assert frame.iloc[0]["quality_status"] == "review_similar_text"
    assert "tidak" in frame.iloc[0]["model_text"]
    assert frame.iloc[0]["is_eligible_for_labeling"] == "False"
    assert frame.iloc[0]["is_duplicate_text"] == "False"


def test_backfill_uses_explicit_dates_but_real_collection_timestamp(repository):
    import json

    def historical(command, cwd, environment):
        # Fixture writer expects the normal end; assert the backfill independently.
        assert command[command.index("--to") + 1] == "05-10-2026"
        adjusted = command.copy()
        adjusted[adjusted.index("--to") + 1] = "12-10-2026"
        write_collection(adjusted, cwd, environment)
        target = next((cwd / "tweets-data").glob("*.csv"))
        target.write_text(
            target.read_text().replace("2026-10-11T12:00:00Z", "2026-10-04T12:00:00Z")
        )

    raw = collect_scheduled(
        repository_root=repository,
        program_id="mbg",
        scheduled_at=SCHEDULE,
        execution_id="backfill",
        window_end=date(2026, 10, 4),
        runner=historical,
    )
    manifest = json.loads(raw.with_name("collection.json").read_text())
    assert manifest["from_date"] == "2026-09-28"
    assert manifest["to_date"] == "2026-10-04"
    assert "collected_date=2026-10-12" in str(raw)
    assert raw.with_name("collection_config.yaml").is_file()
    with pytest.raises(ValueError, match="before the collection day"):
        collect_scheduled(
            repository_root=repository,
            program_id="mbg",
            scheduled_at=SCHEDULE,
            execution_id="invalid-future",
            window_end=date(2026, 10, 12),
            runner=historical,
        )
