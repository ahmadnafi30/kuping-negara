"""Quarantine legacy or invalid processed output without modifying raw CSVs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from kuping_negara.ingestion.storage import CollectionError
from kuping_negara.ingestion.validation import sha256_file, validate_collection_manifest
from kuping_negara.preprocessing.history import (
    PREPROCESSING_VERSION,
    preprocessing_lock,
)


def audit_existing_outputs(root: Path) -> dict:
    root = root.resolve()
    processed = root / "data/processed/x"
    quarantine = root / "data/quarantine/x/processed"
    raw_by_hash = {}
    for raw in (root / "data/raw/x").rglob("*.csv"):
        raw_by_hash.setdefault(sha256_file(raw), []).append(raw)
    moved = []
    with preprocessing_lock(processed):
        for path in sorted(processed.rglob("quality_report.json")):
            report = json.loads(path.read_text(encoding="utf-8"))
            reasons = []
            if report.get("preprocessing_version") != PREPROCESSING_VERSION:
                reasons.append("Legacy preprocessing rules require regeneration")
            candidates = raw_by_hash.get(report["input_sha256"], [])
            if not candidates:
                reasons.append("Matching immutable raw input was not found")
            else:
                try:
                    validate_collection_manifest(candidates[0])
                except CollectionError as error:
                    reasons.append(str(error))
            if not reasons:
                continue
            source = path.parent.resolve()
            target = (quarantine / source.relative_to(processed)).resolve()
            if not source.is_relative_to(processed) or not target.is_relative_to(
                quarantine
            ):
                raise ValueError("Quarantine path escaped the dataset directories")
            if target.exists():
                raise ValueError("Quarantine destination already exists")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            (target / "quarantine.json").write_text(
                json.dumps(
                    {
                        "status": "quarantined",
                        "eligible_for_labeling": False,
                        "eligible_for_training": False,
                        "reasons": reasons,
                        "original_path": str(source.relative_to(root)),
                        "raw_input_sha256": report["input_sha256"],
                        "audited_at": datetime.now(UTC).isoformat(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            moved.append({"path": str(target.relative_to(root)), "reasons": reasons})
    return {"quarantined_runs": len(moved), "runs": moved}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(audit_existing_outputs(args.repository_root), indent=2))
