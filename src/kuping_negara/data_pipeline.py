"""Coordinate repeated X ingestion, replay simulation, and preprocessing."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from kuping_negara.ingestion.tweet_harvest import (
    JAKARTA_TIMEZONE,
    CollectionError,
    finalize_output,
    find_repository_root,
    run_collection,
)
from kuping_negara.preprocessing.x_pipeline import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_ROOT,
    parse_raw_partition_path,
)
from kuping_negara.preprocessing.x_pipeline import (
    main as preprocess_main,
)


def replay_samples(repository_root: Path, sample_root: Path) -> list[Path]:
    """Copy saved source samples into a new immutable run for offline testing.

    This is an explicit replay, not evidence of fetching new posts from X.
    Published timestamps and source rows are retained without modification.
    """
    if not sample_root.is_dir():
        raise CollectionError("replay directory not found")
    input_paths = sorted(sample_root.rglob("*.csv"))
    if not input_paths:
        raise CollectionError("replay directory contains no CSV files")
    now = datetime.now(JAKARTA_TIMEZONE)
    run_id = now.strftime("%Y%m%dT%H%M%S%f%z")
    outputs: list[Path] = []
    for input_path in input_paths:
        metadata = parse_raw_partition_path(input_path)
        # A single program has one source CSV per run, just like the crawler.
        staging_root = (
            repository_root / "tweets-data" / "replay" / run_id / metadata.program_id
        )
        staging_directory = staging_root / "tweets-data"
        staging_directory.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(input_path, staging_directory / input_path.name)
        destination = finalize_output(
            repository_root=repository_root,
            output_name=input_path.stem,
            program_id=metadata.program_id,
            run_id=run_id,
            collected_date=now.date(),
            staging_root=staging_root,
        )
        with destination.open(encoding="utf-8-sig", newline="") as handle:
            rows = sum(1 for _ in csv.DictReader(handle))
        (destination.parent / "ingestion_report.json").write_text(
            json.dumps(
                {
                    "source": "offline_replay",
                    "program_id": metadata.program_id,
                    "ingestion_run_id": run_id,
                    "rows": rows,
                    "replayed_from": input_path.relative_to(sample_root).as_posix(),
                    "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        outputs.append(destination)
        print(f"Replayed rows: {rows} | program={metadata.program_id}")
    return outputs


def main(argv: Sequence[str] | None = None) -> int:
    """Run finite collection cycles and preprocess each successful raw CSV."""
    parser = argparse.ArgumentParser(
        description="LK-04 X ingestion pipeline. Forwarded collector options:\n"
        "--from-date, --to-date, --lookback-days, --program, --limit, "
        "--non-interactive, --attempts, --retry-delay, --timeout, --dry-run.",
    )
    parser.add_argument("--preprocess", action="store_true")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=60)
    parser.add_argument(
        "--replay-dir",
        type=Path,
        help="Offline periodic simulation using saved CSVs; does not access X",
    )
    parser.add_argument("--processed-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    arguments, collector_arguments = parser.parse_known_args(argv)
    if arguments.cycles <= 0 or arguments.interval_seconds < 0:
        parser.error("cycles must be positive and interval-seconds non-negative")
    if arguments.replay_dir is not None and collector_arguments:
        parser.error("replay mode cannot be combined with live collector options")
    try:
        repository_root = find_repository_root([Path.cwd(), Path(__file__)])
        output_root = arguments.processed_root
        if not output_root.is_absolute():
            output_root = repository_root / output_root
        config_parser = argparse.ArgumentParser(add_help=False)
        config_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
        config_arguments, _ = config_parser.parse_known_args(collector_arguments)
        config_path = config_arguments.config
        if not config_path.is_absolute():
            config_path = repository_root / config_path
        for cycle in range(1, arguments.cycles + 1):
            print(f"Pipeline cycle: {cycle}/{arguments.cycles}")
            if arguments.replay_dir is not None:
                sample_root = arguments.replay_dir
                if not sample_root.is_absolute():
                    sample_root = repository_root / sample_root
                exit_code, raw_paths = 0, replay_samples(repository_root, sample_root)
            else:
                exit_code, raw_paths = run_collection(collector_arguments)
            # Successful programs can be processed even if a later one fails.
            if arguments.preprocess:
                for raw_path in raw_paths:
                    processing_status = preprocess_main(
                        [
                            "--input",
                            str(raw_path),
                            "--output-root",
                            str(output_root),
                            "--config",
                            str(config_path),
                        ]
                    )
                    if processing_status:
                        exit_code = processing_status
            if exit_code:
                return exit_code
            if cycle < arguments.cycles:
                time.sleep(arguments.interval_seconds)
    except (OSError, ValueError, CollectionError) as error:
        print(f"Pipeline error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Pipeline interrupted.", file=sys.stderr)
        return 130
    return 0
