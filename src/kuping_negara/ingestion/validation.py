"""Validate the actual CSV against its requested Jakarta collection contract."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

from kuping_negara.ingestion.storage import CollectionError
from kuping_negara.paths import JAKARTA_TIMEZONE


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collection_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    if start > end:
        raise CollectionError("Collection dates must be increasing")
    return (
        datetime.combine(start, time.min, JAKARTA_TIMEZONE).astimezone(UTC),
        datetime.combine(
            end + timedelta(days=1), time.min, JAKARTA_TIMEZONE
        ).astimezone(UTC),
    )


def validate_collection(path: Path, *, start: date, end: date, limit: int) -> dict:
    if type(limit) is not int or limit < 1:
        raise CollectionError("Collection limit must be a positive integer")
    try:
        frame = pd.read_csv(
            path, dtype=str, keep_default_na=False, encoding="utf-8-sig"
        )
    except (OSError, ValueError) as error:
        raise CollectionError("Collection CSV cannot be decoded or parsed") from error
    if frame.empty:
        raise CollectionError("Collection CSV has no tweet rows")
    required = {"id_str", "full_text", "created_at"}
    if not required.issubset(frame.columns):
        raise CollectionError("Collection CSV is missing required columns")
    if (
        frame["id_str"].str.strip().eq("").any()
        or frame["full_text"].str.strip().eq("").any()
    ):
        raise CollectionError("Collection CSV contains empty tweet IDs or text")
    published = pd.to_datetime(
        frame["created_at"], utc=True, format="mixed", errors="coerce"
    )
    if published.isna().any():
        raise CollectionError("Collection CSV contains invalid publication timestamps")
    lower, upper = collection_bounds(start, end)
    outside = ~((published >= lower) & (published < upper))
    if outside.any():
        raise CollectionError(
            f"Collection rejected: {int(outside.sum())} rows outside requested Jakarta window {start} through {end}"
        )
    if len(frame) > limit:
        raise CollectionError(
            f"Collection rejected: {len(frame)} rows exceeds requested limit {limit}"
        )
    return {
        "status": "passed",
        "validation_version": 1,
        "timezone": "Asia/Jakarta",
        "rows": len(frame),
        "outside_window_rows": 0,
        "requested_limit": limit,
        "start_inclusive_utc": lower.isoformat(),
        "end_exclusive_utc": upper.isoformat(),
        "published_at_min": published.min().isoformat(),
        "published_at_max": published.max().isoformat(),
    }


def validate_collection_manifest(
    path: Path, *, required: bool = True, config_path: Path | None = None
) -> dict | None:
    manifest_path = path.parent / "collection.json"
    if not manifest_path.is_file():
        if required:
            raise CollectionError(
                "Collection manifest is required before scheduled preprocessing"
            )
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        start = date.fromisoformat(manifest["from_date"])
        end = date.fromisoformat(manifest["to_date"])
        limit = manifest["limit"]
        if manifest["input_sha256"] != sha256_file(path):
            raise CollectionError("Raw collection hash has changed")
        if config_path and manifest["config_sha256"] != sha256_file(config_path):
            raise CollectionError("Collection keyword configuration has changed")
    except (KeyError, ValueError, TypeError) as error:
        raise CollectionError("Collection manifest is invalid") from error
    return validate_collection(path, start=start, end=end, limit=limit)
