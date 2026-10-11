"""Validate staging CSVs and move them into the immutable raw zone."""

from __future__ import annotations

import csv
import shutil
from datetime import date
from pathlib import Path


class CollectionError(RuntimeError):
    """Raised when collection cannot produce a valid raw dataset."""


def finalize_output(
    *,
    repository_root: Path,
    output_name: str,
    program_id: str,
    run_id: str,
    collected_date: date,
) -> Path:
    """Move a completed staging CSV into the immutable raw data zone."""
    source = repository_root / "tweets-data" / f"{output_name}.csv"
    if not source.is_file() or source.stat().st_size == 0:
        raise CollectionError(
            f"Tweet Harvest did not produce a non-empty file: {source}"
        )

    with source.open(encoding="utf-8-sig", newline="") as source_file:
        populated_rows = (
            row for row in csv.reader(source_file) if any(cell.strip() for cell in row)
        )
        header = next(populated_rows, None)
        first_data_row = next(populated_rows, None)

    if header is None or first_data_row is None:
        raise CollectionError(
            f"Tweet Harvest produced a CSV with no tweet rows: {source}"
        )

    destination_directory = (
        repository_root
        / "data"
        / "raw"
        / "x"
        / f"collected_date={collected_date.isoformat()}"
        / f"program={program_id}"
        / f"run_id={run_id}"
    )
    destination_directory.mkdir(parents=True, exist_ok=False)
    destination = destination_directory / source.name
    shutil.move(str(source), destination)
    return destination
