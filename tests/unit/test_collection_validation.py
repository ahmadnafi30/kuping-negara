"""Regressions for actual collection dates, hard limits, and corrupt input."""

from datetime import date

import pandas as pd
import pytest

from kuping_negara.ingestion.storage import CollectionError
from kuping_negara.ingestion.validation import validate_collection


def write_csv(tmp_path, timestamps):
    path = tmp_path / "posts.csv"
    pd.DataFrame(
        [
            {
                "id_str": str(1000000000000000000 + i),
                "full_text": "CKG membantu",
                "created_at": timestamp,
            }
            for i, timestamp in enumerate(timestamps)
        ]
    ).to_csv(path, index=False)
    return path


def test_exact_jakarta_midnight_boundaries(tmp_path):
    path = write_csv(tmp_path, ["2026-10-03T17:00:00Z", "2026-10-10T16:59:59Z"])
    report = validate_collection(
        path, start=date(2026, 10, 4), end=date(2026, 10, 10), limit=2
    )
    assert report["rows"] == 2
    assert report["outside_window_rows"] == 0


@pytest.mark.parametrize(
    "timestamp",
    ["2026-10-03T16:59:59Z", "2026-10-10T17:00:00Z", "2026-10-11T06:00:00Z"],
)
def test_outside_jakarta_dates_rejected(tmp_path, timestamp):
    with pytest.raises(CollectionError, match="outside requested Jakarta window"):
        validate_collection(
            write_csv(tmp_path, [timestamp]),
            start=date(2026, 10, 4),
            end=date(2026, 10, 10),
            limit=50,
        )


def test_limit_is_enforced_even_when_collector_exits_zero(tmp_path):
    path = write_csv(tmp_path, ["2026-10-10T12:00:00Z"] * 60)
    with pytest.raises(CollectionError, match="60 rows exceeds requested limit 50"):
        validate_collection(
            path, start=date(2026, 10, 4), end=date(2026, 10, 10), limit=50
        )


def test_invalid_publication_time_is_rejected(tmp_path):
    with pytest.raises(CollectionError, match="invalid publication timestamps"):
        validate_collection(
            write_csv(tmp_path, ["invalid"]),
            start=date(2026, 10, 4),
            end=date(2026, 10, 10),
            limit=50,
        )
