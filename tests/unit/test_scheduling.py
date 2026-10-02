"""Check the weekly windows passed to the ingestion collector."""

from datetime import datetime, timezone

import pytest

from kuping_negara.scheduling import completed_week_window, weekly_cron


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        ("monday", "0 7 * * 1"),
        ("tuesday", "0 7 * * 2"),
        ("wednesday", "0 7 * * 3"),
        ("thursday", "0 7 * * 4"),
    ],
)
def test_weekly_cron_matches_collection_day(day, expected):
    assert weekly_cron(day) == expected


def test_window_covers_previous_seven_complete_jakarta_days():
    # 00:00 UTC is 07:00 WIB on Monday, 5 October 2026.
    trigger = datetime(2026, 10, 5, tzinfo=timezone.utc)
    assert completed_week_window(trigger) == (
        datetime(2026, 9, 28).date(),
        datetime(2026, 10, 4).date(),
    )


def test_window_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        completed_week_window(datetime(2026, 10, 5))

