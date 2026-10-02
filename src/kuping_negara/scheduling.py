"""Small scheduling helpers shared by Airflow and unit tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

JAKARTA = ZoneInfo("Asia/Jakarta")
WEEKDAY_NUMBERS = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
}


def weekly_cron(collection_day: str, hour: int = 7) -> str:
    """Schedule one program per week at the configured Jakarta weekday."""
    if collection_day not in WEEKDAY_NUMBERS:
        raise ValueError(f"unsupported collection_day: {collection_day}")
    if not 0 <= hour <= 23:
        raise ValueError("hour must be between 0 and 23")
    return f"0 {hour} * * {WEEKDAY_NUMBERS[collection_day]}"


def completed_week_window(trigger_time: datetime) -> tuple[date, date]:
    """Collect the seven complete local calendar days before a run."""
    if trigger_time.tzinfo is None:
        raise ValueError("trigger_time must be timezone-aware")
    last_day = trigger_time.astimezone(JAKARTA).date() - timedelta(days=1)
    return last_day - timedelta(days=6), last_day

