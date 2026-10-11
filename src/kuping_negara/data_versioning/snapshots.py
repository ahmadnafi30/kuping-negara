"""Append unique program/post records from validated immutable raw runs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from kuping_negara.ingestion.validation import validate_collection_manifest
from kuping_negara.paths import DEFAULT_CONFIG_PATH


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_snapshot(
    *,
    repository_root: Path,
    inputs: list[Path],
    output: Path,
    metrics_path: Path,
    append: bool = False,
) -> dict:
    root = repository_root.resolve()
    output = output.resolve()
    metrics_path = metrics_path.resolve()
    if not metrics_path.is_relative_to(root / "reports"):
        raise ValueError("Metrics output must stay inside reports")
    if not output.is_relative_to(root / "data/raw"):
        raise ValueError("Snapshot output must stay inside data/raw")
    if output.exists() and not append:
        raise ValueError("Existing snapshot requires explicit append mode")
    if append and not output.is_file():
        raise ValueError("Append mode requires an existing snapshot")
    if not inputs:
        raise ValueError("At least one completed raw collection is required")
    rows: list[dict[str, str]] = []
    fields: list[str] | None = None
    previous_sha256 = sha256(output) if output.exists() else None
    if append:
        with output.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = list(reader)
        if not fields or "target_program" not in fields or "id_str" not in fields:
            raise ValueError("Existing snapshot has an incompatible raw schema")
    original_rows = len(rows)
    seen = {(r["target_program"], r["id_str"]) for r in rows}
    if len(seen) != len(rows):
        raise ValueError("Existing snapshot contains duplicate program/post keys")
    sources = []
    for candidate in inputs:
        source = candidate.resolve()
        if not source.is_relative_to(root / "data/raw") or source == output:
            raise ValueError("Inputs must be distinct raw collection files")
        program_parts = [p[8:] for p in source.parts if p.startswith("program=")]
        if len(program_parts) != 1:
            raise ValueError("Input must have one program partition")
        program = program_parts[0]
        validate_collection_manifest(source, config_path=root / DEFAULT_CONFIG_PATH)
        source_hash = sha256(source)
        added = skipped = count = 0
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            source_fields = reader.fieldnames
            if not source_fields or "id_str" not in source_fields:
                raise ValueError("Raw input requires id_str")
            if "target_program" in source_fields:
                raise ValueError("Input must be a collector CSV, not another snapshot")
            expected = ["target_program", *source_fields]
            if fields is None:
                fields = expected
            if fields != expected:
                raise ValueError("Raw input columns differ from the snapshot schema")
            for record in reader:
                count += 1
                if not record["id_str"]:
                    raise ValueError("Raw post ID must not be empty")
                key = (program, record["id_str"])
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                rows.append({"target_program": program, **record})
                added += 1
        if sha256(source) != source_hash:
            raise ValueError("Raw input changed during snapshot creation")
        sources.append(
            {
                "path": source.relative_to(root).as_posix(),
                "sha256": source_hash,
                "rows_read": count,
                "rows_added": added,
                "duplicate_keys_skipped": skipped,
            }
        )
    if append and len(rows) == original_rows:
        raise ValueError("No new unique rows; refusing to fabricate a data update")
    if not rows:
        raise ValueError("Snapshot must contain real ingested records")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="", dir=output.parent, delete=False
        ) as stream:
            temporary_name = stream.name
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, output)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    metrics = {
        "dataset": output.relative_to(root).as_posix(),
        "rows": len(rows),
        "previous_rows": original_rows,
        "new_unique_rows": len(rows) - original_rows,
        "program_counts": dict(Counter(r["target_program"] for r in rows)),
        "previous_sha256": previous_sha256,
        "sha256": sha256(output),
        "append": append,
        "sources": sources,
        "created_at": datetime.now(UTC).isoformat(),
        "training_performed": False,
        "note": "Data versioning simulation using real completed ingestions; no labels or model weights are changed.",
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("data/raw/lk05_dataset.csv")
    )
    parser.add_argument(
        "--metrics", type=Path, default=Path("reports/lk05/dataset_metrics.json")
    )
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()
    result = build_snapshot(
        repository_root=Path.cwd(),
        inputs=args.input,
        output=args.output,
        metrics_path=args.metrics,
        append=args.append,
    )
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
