"""Pure query and date-window construction for Tweet Harvest."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

TWEET_HARVEST_VERSION = "2.7.1"


def build_search_query(
    keywords: Sequence[str],
    *,
    language: str | None = None,
    context_keywords: Sequence[str] = (),
) -> str:
    """Build a scoped query while retaining the broad legacy call contract."""

    def terms(values):
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("at least one keyword is required")
        quoted = []
        for value in cleaned:
            escaped = value.replace(chr(34), chr(92) + chr(34))
            quoted.append(
                f'"{escaped}"' if any(c.isspace() for c in value) else escaped
            )
        return "(" + " OR ".join(quoted) + ")"

    query = terms(keywords)
    if context_keywords:
        query += " " + terms(context_keywords)
    if language is not None:
        import re

        if not re.fullmatch(r"[a-z]{2}", language):
            raise ValueError("language must be a two-letter lower-case code")
        query += " lang:" + language
    return query


def parse_collection_window(from_date: str, to_date: str) -> tuple[date, date]:
    """Parse Tweet Harvest dates and require an increasing date window."""
    try:
        start = datetime.strptime(from_date, "%d-%m-%Y").date()
        end = datetime.strptime(to_date, "%d-%m-%Y").date()
    except ValueError as error:
        raise ValueError("dates must use DD-MM-YYYY format") from error

    if start > end:
        raise ValueError("from-date must be earlier than or equal to to-date")
    return start, end


def build_output_name(program_id: str, start: date, end: date) -> str:
    """Create a deterministic Tweet Harvest staging filename."""
    return f"{program_id}_{start.isoformat()}_{end.isoformat()}"


def build_tweet_harvest_command(
    *,
    query: str,
    from_date: str,
    to_date: str,
    limit: int,
    tab: str,
    output_name: str,
) -> list[str]:
    """Build a token-free Tweet Harvest command for interactive execution."""
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    normalized_tab = tab.upper()
    if normalized_tab not in {"LATEST", "TOP"}:
        raise ValueError("tab must be LATEST or TOP")

    start, inclusive_end = parse_collection_window(from_date, to_date)
    # UTC date search is an outer window; the adapter keeps exact Jakarta bounds.
    outer_from = (start - timedelta(days=1)).strftime("%d-%m-%Y")
    exclusive_until = (inclusive_end + timedelta(days=1)).strftime("%d-%m-%Y")

    return [
        "npx",
        "-y",
        f"tweet-harvest@{TWEET_HARVEST_VERSION}",
        "-s",
        query,
        "-f",
        outer_from,
        "--to",
        exclusive_until,
        "-l",
        str(limit),
        "--tab",
        normalized_tab,
        "-o",
        output_name,
        "-e",
        "csv",
    ]
