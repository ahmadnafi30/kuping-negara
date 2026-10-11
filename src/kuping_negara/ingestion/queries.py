"""Pure query and date-window construction for Tweet Harvest."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

TWEET_HARVEST_VERSION = "2.7.1"


def build_search_query(keywords: Sequence[str]) -> str:
    """Build an X search query from configured keywords without language filtering."""
    cleaned_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
    if not cleaned_keywords:
        raise ValueError("at least one keyword is required")

    query_terms = []
    for keyword in cleaned_keywords:
        escaped_keyword = keyword.replace(chr(34), chr(92) + chr(34))
        query_terms.append(
            f'"{escaped_keyword}"'
            if any(character.isspace() for character in keyword)
            else escaped_keyword
        )
    return f"({' OR '.join(query_terms)})"


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

    inclusive_end = datetime.strptime(to_date, "%d-%m-%Y").date()
    exclusive_until = (inclusive_end + timedelta(days=1)).strftime("%d-%m-%Y")

    return [
        "npx",
        "-y",
        f"tweet-harvest@{TWEET_HARVEST_VERSION}",
        "-s",
        query,
        "-f",
        from_date,
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
