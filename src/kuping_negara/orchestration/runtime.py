"""Atomic, retry-safe file operations for scheduled collection and preprocessing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from kuping_negara.configuration import load_programs
from kuping_negara.ingestion.browser import build_tweet_harvest_environment
from kuping_negara.ingestion.queries import (
    build_output_name,
    build_search_query,
    build_tweet_harvest_command,
)
from kuping_negara.ingestion.storage import CollectionError, finalize_output
from kuping_negara.ingestion.validation import (
    validate_collection,
    validate_collection_manifest,
)
from kuping_negara.paths import DEFAULT_CONFIG_PATH, JAKARTA_TIMEZONE
from kuping_negara.preprocessing.x_pipeline import (
    PreprocessingPipelineError,
    run_preprocessing,
)
from kuping_negara.preprocessing.x_posts import PreprocessingError

CollectorRunner = Callable[[list[str], Path, dict[str, str]], None]


def sha256(path: Path) -> str:
    """Hash file content without loading the complete dataset into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def execution_key(execution_id: str) -> str:
    """Map an Airflow run ID to a filesystem-safe, isolated namespace."""
    if not execution_id:
        raise ValueError("execution_id must not be empty")
    return hashlib.sha256(execution_id.encode()).hexdigest()[:24]


def collection_window(scheduled_at: datetime, days: int = 7) -> tuple[date, date]:
    """Select preceding complete calendar days in Jakarta, excluding today."""
    if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
        raise ValueError("scheduled_at must be timezone-aware")
    if days < 1:
        raise ValueError("lookback_days must be positive")
    end = scheduled_at.astimezone(JAKARTA_TIMEZONE).date() - timedelta(days=1)
    return end - timedelta(days=days - 1), end


def _run_collector(command: list[str], cwd: Path, environment: dict[str, str]) -> None:
    # Upstream output/errors may contain sensitive context. Persist only our
    # sanitized result and discard browser screenshots with the temporary tree.
    with subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
    ) as process:
        try:
            code = process.wait(timeout=900)
            if code:
                raise CollectionError(
                    "Collector failed; check token validity and X/browser availability"
                )
        except subprocess.TimeoutExpired as error:
            raise CollectionError("Collector exceeded its 15-minute timeout") from error
        finally:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()


def collect_scheduled(
    *,
    repository_root: Path,
    program_id: str,
    scheduled_at: datetime,
    execution_id: str,
    lookback_days: int = 7,
    limit: int = 50,
    window_end: date | None = None,
    config_path: Path | None = None,
    runner: CollectorRunner = _run_collector,
) -> Path:
    """Publish only successful collection; retries reuse verified raw content."""
    root = repository_root.resolve()
    config_path = (config_path or root / DEFAULT_CONFIG_PATH).resolve()
    if not config_path.is_relative_to(root / "configs"):
        raise ValueError("Scheduled keyword configuration must stay inside configs")
    programs = load_programs(config_path)
    if program_id not in programs or limit < 1:
        raise ValueError("Unknown program or invalid collection limit")
    start, end = collection_window(scheduled_at, lookback_days)
    if window_end is not None:
        if window_end >= scheduled_at.astimezone(JAKARTA_TIMEZONE).date():
            raise ValueError("Backfill window must end before the collection day")
        end = window_end
        start = end - timedelta(days=lookback_days - 1)
    timestamp = scheduled_at.astimezone(JAKARTA_TIMEZONE)
    run_id = timestamp.strftime("%Y%m%dT%H%M%S%z")
    output_name = build_output_name(program_id, start, end)
    query = build_search_query(
        programs[program_id]["keywords"],
        language=programs[program_id].get("search_language"),
        context_keywords=programs[program_id].get("search_context_keywords", ()),
    )
    raw_root = root / "data/raw/x"
    destination = (
        raw_root
        / f"execution={execution_key(execution_id)}"
        / f"collected_date={timestamp.date().isoformat()}"
        / f"program={program_id}"
        / f"run_id={run_id}"
    )
    csv_path = destination / f"{output_name}.csv"
    metadata = {
        "query": query,
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "limit": limit,
        "config_sha256": sha256(config_path),
        "config_snapshot": "collection_config.yaml",
    }
    if destination.exists():
        manifest = json.loads((destination / "collection.json").read_text())
        existing = {
            key: value for key, value in manifest.items() if key != "validation"
        }
        if existing != {**metadata, "input_sha256": sha256(csv_path)}:
            raise CollectionError("Existing raw run has changed; refusing to overwrite")
        validate_collection_manifest(csv_path, config_path=config_path)
        return csv_path

    token_file = Path(os.environ.get("KUPING_NEGARA_TOKEN_FILE", ""))
    if not token_file.is_file() or not token_file.stat().st_size:
        raise CollectionError(
            "Configure the x_auth_token Docker secret before collection"
        )
    collector = Path(os.environ["KUPING_NEGARA_COLLECTOR"])
    browser = Path(os.environ["KUPING_NEGARA_BROWSER_EXECUTABLE"])
    command = build_tweet_harvest_command(
        query=query,
        from_date=start.strftime("%d-%m-%Y"),
        to_date=end.strftime("%d-%m-%Y"),
        limit=limit,
        tab="LATEST",
        output_name=output_name,
    )
    # Use the installed lockfile version, never download via npx during a run.
    command = ["node", str(collector), *command[3:]]
    environment = build_tweet_harvest_environment(
        repository_root=root,
        browser_executable=browser,
        base_environment=os.environ,
        collection_start=start,
        collection_end=end,
    )
    environment["NODE_OPTIONS"] += (
        f' --require="{root / "scripts/tweet_harvest_secret_hook.cjs"}"'
    )
    environment["HEADLESS_MODE"] = "true"
    environment["ENABLE_EXPONENTIAL_BACKOFF"] = "true"
    raw_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".collect-", dir=raw_root) as temporary:
        staging = Path(temporary)
        runner(command, staging, environment)
        candidate = staging / "tweets-data" / f"{output_name}.csv"
        if not candidate.is_file():
            raise CollectionError("Collector did not produce a CSV")
        validation = validate_collection(candidate, start=start, end=end, limit=limit)
        collected = finalize_output(
            repository_root=staging,
            output_name=output_name,
            program_id=program_id,
            run_id=run_id,
            collected_date=timestamp.date(),
        )
        (collected.parent / "collection_config.yaml").write_bytes(
            config_path.read_bytes()
        )
        if sha256(config_path) != metadata["config_sha256"]:
            raise CollectionError("Configuration changed during collection")
        (collected.parent / "collection.json").write_text(
            json.dumps(
                {
                    **metadata,
                    "input_sha256": sha256(collected),
                    "validation": validation,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        collected.parent.rename(destination)
    return csv_path


def preprocess_scheduled(
    *,
    repository_root: Path,
    raw_path: Path,
    scheduled_at: datetime,
    execution_id: str,
) -> dict[str, str]:
    """Atomically publish records and quality report, validating existing retries."""
    collection_window(scheduled_at)  # Validate an aware timestamp.
    root = repository_root.resolve()
    raw_path = raw_path.resolve()
    if not raw_path.is_relative_to(root / "data/raw/x"):
        raise ValueError("Scheduled preprocessing input must be in data/raw/x")
    artifacts = run_preprocessing(
        input_path=raw_path,
        output_root=root / "data/processed/x",
        config_path=root / DEFAULT_CONFIG_PATH,
        processed_at=scheduled_at.astimezone(JAKARTA_TIMEZONE),
        namespace=f"execution={execution_key(execution_id)}",
        reuse_existing=True,
        require_manifest=True,
    )
    return {
        "records_path": str(artifacts.records_path),
        "report_path": str(artifacts.report_path),
    }


def main() -> None:
    """Run inside the isolated project virtual environment from an Airflow task."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["collect", "preprocess"])
    parser.add_argument(
        "--repository-root", type=Path, default=Path("/opt/kuping-negara")
    )
    parser.add_argument("--scheduled-at", required=True, type=datetime.fromisoformat)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--program")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--window-end", type=date.fromisoformat)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    shared = {
        "repository_root": args.repository_root,
        "scheduled_at": args.scheduled_at,
        "execution_id": args.execution_id,
    }
    if args.action == "collect":
        if not args.program:
            parser.error("--program is required for collect")
        raw = collect_scheduled(
            **shared,
            program_id=args.program,
            lookback_days=args.lookback_days,
            limit=args.limit,
            window_end=args.window_end,
            config_path=args.config,
        )
        result = {"raw_path": str(raw)}
    else:
        if not args.input:
            parser.error("--input is required for preprocess")
        result = preprocess_scheduled(**shared, raw_path=args.input)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except (
        CollectionError,
        PreprocessingError,
        PreprocessingPipelineError,
        ValueError,
    ) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from None
