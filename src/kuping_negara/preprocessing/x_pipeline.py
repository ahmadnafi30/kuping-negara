"""File pipeline and CLI for preprocessing Tweet Harvest datasets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from kuping_negara.preprocessing.x_posts import (
    PreprocessingError,
    preprocess_tweet_harvest_frame,
)


JAKARTA_TIMEZONE = ZoneInfo("Asia/Jakarta")
DEFAULT_CONFIG_PATH = Path("configs/keywords/programs.example.yaml")
DEFAULT_OUTPUT_ROOT = Path("data/processed/x")


class PreprocessingPipelineError(RuntimeError):
    """Raised when preprocessing file lineage or persistence is invalid."""


@dataclass(frozen=True)
class RawPartitionMetadata:
    """Lineage values encoded in a raw dataset partition path."""

    program_id: str
    ingestion_run_id: str
    collected_at: datetime


@dataclass(frozen=True)
class PreprocessingArtifacts:
    """Paths created by one successful preprocessing execution."""

    records_path: Path
    report_path: Path


def _extract_partition_value(path: Path, prefix: str) -> str:
    values = [
        part.removeprefix(prefix) for part in path.parts if part.startswith(prefix)
    ]
    if len(values) != 1 or not values[0]:
        raise PreprocessingPipelineError(
            f"raw path must contain exactly one {prefix}<value> partition"
        )
    return values[0]


def parse_raw_partition_path(input_path: Path) -> RawPartitionMetadata:
    """Extract program and ingestion lineage from a partitioned raw path."""

    resolved_path = input_path.resolve()
    program_id = _extract_partition_value(resolved_path, "program=")
    ingestion_run_id = _extract_partition_value(resolved_path, "run_id=")
    collected_date_text = _extract_partition_value(resolved_path, "collected_date=")
    try:
        collected_at = datetime.strptime(
            ingestion_run_id, "%Y%m%dT%H%M%S%z"
        )
        collected_date = date.fromisoformat(collected_date_text)
    except ValueError as error:
        raise PreprocessingPipelineError(
            "raw path contains invalid collected_date or run_id"
        ) from error
    if collected_at.date() != collected_date:
        raise PreprocessingPipelineError(
            "collected_date partition does not match the run_id date"
        )
    return RawPartitionMetadata(
        program_id=program_id,
        ingestion_run_id=ingestion_run_id,
        collected_at=collected_at,
    )


def _load_program_keywords(
    config_path: Path, program_id: str
) -> tuple[str, ...]:
    if not config_path.is_file():
        raise PreprocessingPipelineError(
            f"keyword configuration not found: {config_path}"
        )
    with config_path.open(encoding="utf-8") as config_file:
        document = yaml.safe_load(config_file)
    programs = document.get("programs") if isinstance(document, Mapping) else None
    program = programs.get(program_id) if isinstance(programs, Mapping) else None
    keywords = program.get("keywords") if isinstance(program, Mapping) else None
    if not isinstance(keywords, list) or not keywords:
        raise PreprocessingPipelineError(
            f"keyword configuration does not define program: {program_id}"
        )
    normalized_keywords = tuple(
        keyword.strip()
        for keyword in keywords
        if isinstance(keyword, str) and keyword.strip()
    )
    if not normalized_keywords:
        raise PreprocessingPipelineError(
            f"program {program_id} does not contain usable keywords"
        )
    return normalized_keywords


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_processed_at(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PreprocessingPipelineError("processed_at must be timezone-aware")
    return value


def run_preprocessing(
    *,
    input_path: Path,
    output_root: Path,
    config_path: Path,
    processed_at: datetime | None = None,
) -> PreprocessingArtifacts:
    """Preprocess one immutable raw CSV and persist records plus a report."""

    resolved_input = input_path.resolve()
    if not resolved_input.is_file():
        raise PreprocessingPipelineError(f"raw CSV not found: {resolved_input}")
    metadata = parse_raw_partition_path(resolved_input)
    keywords = _load_program_keywords(config_path.resolve(), metadata.program_id)
    execution_time = _validate_processed_at(
        processed_at or datetime.now(JAKARTA_TIMEZONE)
    )
    input_sha256 = _sha256(resolved_input)

    source = pd.read_csv(
        resolved_input,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )
    result = preprocess_tweet_harvest_frame(
        source,
        program_id=metadata.program_id,
        ingestion_run_id=metadata.ingestion_run_id,
        collected_at=metadata.collected_at,
        keywords=keywords,
    )
    records = result.records.copy()
    records["data_version"] = f"sha256:{input_sha256}"
    records["processed_at"] = execution_time.isoformat()

    destination_directory = (
        output_root.resolve()
        / f"processed_date={execution_time.date().isoformat()}"
        / f"program={metadata.program_id}"
        / f"run_id={metadata.ingestion_run_id}"
    )
    try:
        destination_directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise PreprocessingPipelineError(
            f"processed run already exists: {destination_directory}"
        ) from error

    records_path = destination_directory / f"{resolved_input.stem}_processed.csv"
    report_path = destination_directory / "quality_report.json"
    records.to_csv(
        records_path,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_ALL,
        lineterminator="\n",
    )
    output_sha256 = _sha256(records_path)

    report: dict[str, Any] = {
        **result.report,
        "program_id": metadata.program_id,
        "ingestion_run_id": metadata.ingestion_run_id,
        "processed_at": execution_time.isoformat(),
        "input_file": resolved_input.name,
        "input_sha256": input_sha256,
        "output_file": records_path.name,
        "output_sha256": output_sha256,
        "data_version": f"sha256:{input_sha256}",
        "output_columns": list(records.columns),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if _sha256(resolved_input) != input_sha256:
        raise PreprocessingPipelineError("raw CSV changed during preprocessing")
    return PreprocessingArtifacts(
        records_path=records_path,
        report_path=report_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preprocess one partitioned Tweet Harvest CSV."
    )
    parser.add_argument("--input", type=Path, required=True, help="Raw CSV path")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Processed X data root",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Program keyword configuration",
    )
    parser.add_argument(
        "--processed-at",
        help="Optional timezone-aware ISO timestamp for reproducible execution",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the X preprocessing CLI and print non-sensitive artifact metadata."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        processed_at = (
            datetime.fromisoformat(arguments.processed_at)
            if arguments.processed_at
            else None
        )
        artifacts = run_preprocessing(
            input_path=arguments.input,
            output_root=arguments.output_root,
            config_path=arguments.config,
            processed_at=processed_at,
        )
        report = json.loads(artifacts.report_path.read_text(encoding="utf-8"))
    except (
        OSError,
        PreprocessingError,
        PreprocessingPipelineError,
        ValueError,
        yaml.YAMLError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Processed rows: {report['processed_rows']}")
    print(f"Eligible for labeling: {report['eligible_for_labeling']}")
    print(f"Processed CSV: {artifacts.records_path}")
    print(f"Quality report: {artifacts.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
