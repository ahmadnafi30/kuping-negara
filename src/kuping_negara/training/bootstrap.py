"""Bounded historical collection for building an annotation candidate pool."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence

from kuping_negara.ingestion.tweet_harvest import (
    JAKARTA_TIMEZONE,
    find_repository_root,
    load_programs,
    run_collection,
    select_programs,
)
from kuping_negara.preprocessing.x_pipeline import (
    PreprocessingPipelineError,
    run_preprocessing,
)


@dataclass(frozen=True)
class CollectionJob:
    """One program and one complete, inclusive calendar window."""

    program_id: str
    from_date: date
    to_date: date


def build_collection_plan(
    program_ids: Sequence[str], start: date, end: date, window_days: int
) -> list[CollectionJob]:
    """Split the requested period into non-overlapping windows per program."""
    if start > end:
        raise ValueError("start date must not be after end date")
    if window_days <= 0:
        raise ValueError("window-days must be positive")
    if not program_ids:
        raise ValueError("at least one program is required")

    jobs = []
    for program_id in program_ids:
        current = start
        while current <= end:
            last = min(current + timedelta(days=window_days - 1), end)
            jobs.append(CollectionJob(program_id, current, last))
            current = last + timedelta(days=1)
    return jobs


def _date_range(arguments: argparse.Namespace, today: date) -> tuple[date, date]:
    if bool(arguments.start_date) != bool(arguments.end_date):
        raise ValueError("provide both --start-date and --end-date, or neither")
    if arguments.start_date:
        start = date.fromisoformat(arguments.start_date)
        end = date.fromisoformat(arguments.end_date)
    else:
        end = today - timedelta(days=1)
        start = end - timedelta(days=arguments.days - 1)
    if end >= today:
        raise ValueError("end date must be a completed day before today in WIB")
    if start > end:
        raise ValueError("start date must not be after end date")
    return start, end


def _save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an initial X post pool for annotation; preview by default."
    )
    parser.add_argument("--start-date", help="First complete day, YYYY-MM-DD")
    parser.add_argument("--end-date", help="Last complete day, YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--program", action="append", default=[])
    parser.add_argument(
        "--config", type=Path, default=Path("configs/keywords/programs.example.yaml")
    )
    parser.add_argument(
        "--manifest-dir", type=Path, default=Path("data/bootstrap/runs")
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data/processed/training_initial/x"),
        help="Keep initial training candidates separate from replay outputs",
    )
    parser.add_argument(
        "--execute", action="store_true", help="Actually contact X and save data"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Preview or run a finite historical collection without overwriting old runs."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.days <= 0 or arguments.limit <= 0:
            raise ValueError("days and limit must be positive")
        repository_root = find_repository_root([Path.cwd(), Path(__file__)])
        config_path = arguments.config
        if not config_path.is_absolute():
            config_path = repository_root / config_path
        programs = select_programs(load_programs(config_path), arguments.program)
        start, end = _date_range(
            arguments, datetime.now(JAKARTA_TIMEZONE).date()
        )
        jobs = build_collection_plan(list(programs), start, end, arguments.window_days)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(
        f"Programs: {len(programs)} | Windows: {len(jobs)} | "
        f"Limit per window: {arguments.limit}"
    )
    for job in jobs:
        print(f"{job.program_id}: {job.from_date} through {job.to_date}")
    if not arguments.execute:
        print("Preview only. Add --execute to collect posts and preprocess them.")
        return 0
    if not os.environ.get("X_AUTH_TOKEN", "").strip():
        print("X_AUTH_TOKEN is required for --execute.", file=sys.stderr)
        return 1

    manifest_dir = arguments.manifest_dir
    if not manifest_dir.is_absolute():
        manifest_dir = repository_root / manifest_dir
    processed_root = arguments.processed_root
    if not processed_root.is_absolute():
        processed_root = repository_root / processed_root
    run_id = datetime.now(JAKARTA_TIMEZONE).strftime("%Y%m%dT%H%M%S%f%z")
    manifest_path = manifest_dir / f"bootstrap_{run_id}.json"
    manifest: dict = {
        "created_at": datetime.now(JAKARTA_TIMEZONE).isoformat(),
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "window_days": arguments.window_days,
        "limit_per_program_window": arguments.limit,
        "jobs": [],
    }
    _save_manifest(manifest_path, manifest)

    for job in jobs:
        entry = {**asdict(job), "status": "running", "raw_files": [], "processed_files": []}
        entry["from_date"] = job.from_date.isoformat()
        entry["to_date"] = job.to_date.isoformat()
        manifest["jobs"].append(entry)
        _save_manifest(manifest_path, manifest)
        collector_args = [
            "--program", job.program_id,
            "--from-date", job.from_date.strftime("%d-%m-%Y"),
            "--to-date", job.to_date.strftime("%d-%m-%Y"),
            "--limit", str(arguments.limit),
            "--config", str(config_path),
            "--non-interactive",
        ]
        status, raw_paths = run_collection(collector_args)
        for raw_path in raw_paths:
            entry["raw_files"].append(raw_path.relative_to(repository_root).as_posix())
            try:
                artifacts = run_preprocessing(
                    input_path=raw_path,
                    output_root=processed_root,
                    config_path=config_path,
                )
            except (OSError, ValueError, PreprocessingPipelineError) as error:
                entry["status"] = "preprocessing_failed"
                entry["error_type"] = type(error).__name__
                _save_manifest(manifest_path, manifest)
                print(f"Preprocessing failed; inspect {manifest_path}", file=sys.stderr)
                return 1
            entry["processed_files"].append(
                artifacts.records_path.relative_to(repository_root).as_posix()
            )
        entry["status"] = "complete" if status == 0 else "collection_failed"
        _save_manifest(manifest_path, manifest)
        if status:
            print(f"Collection stopped; inspect {manifest_path}", file=sys.stderr)
            return status

    print(f"Completed {len(jobs)} jobs. Manifest: {manifest_path}")
    return 0
