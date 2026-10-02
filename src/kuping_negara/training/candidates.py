"""Validate processed runs and deduplicate candidates across collection cycles."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

import pandas as pd

from kuping_negara.ingestion.tweet_harvest import JAKARTA_TIMEZONE, find_repository_root
from kuping_negara.preprocessing.x_pipeline import PREPROCESSING_VERSION

REQUIRED_COLUMNS = {
    "tweet_id",
    "target_program",
    "raw_text",
    "cleaned_text",
    "language",
    "published_at",
    "processed_at",
    "ingestion_run_id",
    "quality_status",
    "is_eligible_for_labeling",
}


class CandidatePoolError(ValueError):
    """A processed run cannot safely be used for annotation."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_run(path: Path) -> pd.DataFrame:
    """Check the preprocessing report before using the CSV it describes."""
    report_path = path.parent / "quality_report.json"
    if not report_path.is_file():
        raise CandidatePoolError(f"missing quality report beside {path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("preprocessing_version") != PREPROCESSING_VERSION:
        raise CandidatePoolError(f"outdated preprocessing version: {path}")
    if report.get("output_file") != path.name or report.get("output_sha256") != _sha256(path):
        raise CandidatePoolError(f"processed file does not match quality report: {path}")

    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise CandidatePoolError(f"missing processed columns in {path}: {sorted(missing)}")
    if len(frame) != report.get("processed_rows"):
        raise CandidatePoolError(f"row count does not match quality report: {path}")
    if not frame["is_eligible_for_labeling"].isin(["True", "False"]).all():
        raise CandidatePoolError(f"invalid eligibility values: {path}")
    inconsistent = frame["is_eligible_for_labeling"].eq("True") & frame[
        "quality_status"
    ].ne("accepted")
    if inconsistent.any():
        raise CandidatePoolError(f"non-accepted row marked eligible: {path}")
    if frame["tweet_id"].eq("").any() or frame["target_program"].eq("").any():
        raise CandidatePoolError(f"missing tweet identity or target program: {path}")
    if frame["cleaned_text"].eq("").any() and frame.loc[
        frame["cleaned_text"].eq(""), "is_eligible_for_labeling"
    ].eq("True").any():
        raise CandidatePoolError(f"empty cleaned text marked eligible: {path}")
    return frame


def build_annotation_pool(input_dir: Path, output_root: Path) -> tuple[Path, Path]:
    """Write one immutable candidate CSV and aggregate quality report."""
    files = sorted(input_dir.rglob("*_processed.csv"))
    if not files:
        raise CandidatePoolError(f"no processed CSV files in {input_dir}")
    frames = []
    for path in files:
        frame = load_verified_run(path)
        frame["source_file"] = path.relative_to(input_dir).as_posix()
        frames.append(frame)
    all_rows = pd.concat(frames, ignore_index=True)
    accepted = all_rows.loc[all_rows["is_eligible_for_labeling"].eq("True")].copy()
    accepted["_processed_utc"] = pd.to_datetime(
        accepted["processed_at"], errors="coerce", utc=True
    )
    if accepted["_processed_utc"].isna().any():
        raise CandidatePoolError("accepted rows contain invalid processed_at values")
    accepted = accepted.sort_values(
        ["target_program", "tweet_id", "_processed_utc", "ingestion_run_id"],
        ascending=[True, True, False, False],
        kind="stable",
    )
    candidates = accepted.drop_duplicates(
        ["target_program", "tweet_id"], keep="first"
    ).drop(columns="_processed_utc")
    candidates = candidates.sort_values(
        ["target_program", "published_at", "tweet_id"], kind="stable"
    )

    cross_program = (
        candidates.groupby("tweet_id")["target_program"].nunique().gt(1).sum()
        if not candidates.empty
        else 0
    )
    report = {
        "input_files": len(files),
        "processed_rows": int(len(all_rows)),
        "eligible_rows_before_deduplication": int(len(accepted)),
        "candidate_rows": int(len(candidates)),
        "duplicates_removed_across_runs": int(len(accepted) - len(candidates)),
        "tweet_ids_in_multiple_programs": int(cross_program),
        "quality_status_counts": {
            str(key): int(value)
            for key, value in all_rows["quality_status"].value_counts().items()
        },
        "candidate_program_counts": {
            str(key): int(value)
            for key, value in candidates["target_program"].value_counts().items()
        },
        "candidate_language_counts": {
            str(key): int(value)
            for key, value in candidates["language"].value_counts().items()
        },
        "source_files": [path.relative_to(input_dir).as_posix() for path in files],
        "note": "Unlabeled annotation candidates; sentiment labels are not inferred.",
    }

    build_id = datetime.now(JAKARTA_TIMEZONE).strftime("%Y%m%dT%H%M%S%f%z")
    destination = output_root / f"build_id={build_id}"
    destination.mkdir(parents=True, exist_ok=False)
    csv_path = destination / "candidate_pool.csv"
    report_path = destination / "candidate_report.json"
    candidates.to_csv(csv_path, index=False, encoding="utf-8-sig")
    report["candidate_sha256"] = _sha256(csv_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return csv_path, report_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an unlabeled annotation pool.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/x"))
    parser.add_argument(
        "--output-root", type=Path, default=Path("data/processed/annotation_pool")
    )
    arguments = parser.parse_args(argv)
    root = find_repository_root([Path.cwd(), Path(__file__)])
    input_dir = arguments.input_dir
    output_root = arguments.output_root
    if not input_dir.is_absolute():
        input_dir = root / input_dir
    if not output_root.is_absolute():
        output_root = root / output_root
    try:
        csv_path, report_path = build_annotation_pool(input_dir, output_root)
    except (OSError, ValueError) as error:
        print(f"Candidate pool error: {error}", file=sys.stderr)
        return 1
    print(f"Candidates: {csv_path}\nReport: {report_path}")
    return 0
