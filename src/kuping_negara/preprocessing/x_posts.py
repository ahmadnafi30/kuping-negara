"""Deterministic preprocessing for Tweet Harvest CSV records."""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

SCHEMA_VERSION = "1"
SOURCE_PLATFORM = "x"
REQUIRED_SOURCE_COLUMNS = {
    "conversation_id_str",
    "created_at",
    "favorite_count",
    "full_text",
    "id_str",
    "lang",
    "quote_count",
    "reply_count",
    "retweet_count",
    "tweet_url",
}
ENGAGEMENT_COLUMN_MAP = {
    "reply_count": "reply_count",
    "retweet_count": "retweet_count",
    "favorite_count": "like_count",
    "quote_count": "quote_count",
}
URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MENTION_PATTERN = re.compile(r"(?<!\w)@[\w_]+", re.UNICODE)
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([\w_]+)", re.UNICODE)
WHITESPACE_PATTERN = re.compile(r"\s+")


class PreprocessingError(ValueError):
    """Raised when source data cannot be transformed without data loss."""


@dataclass(frozen=True)
class PreprocessingResult:
    """Canonical records and aggregate quality evidence for one raw dataset."""

    records: pd.DataFrame
    report: dict[str, Any]


def clean_text(text: str) -> str:
    """Normalize text while removing URLs and direct user references.

    Emoji, including their joiners and tag characters, remain sentiment signals.
    Hashtag words remain, but the leading hash is removed.
    """

    normalized = unicodedata.normalize("NFKC", html.unescape(str(text)))
    normalized = "".join(
        " "
        if unicodedata.category(character).startswith("C")
        and character != "\u200d"
        and not "\U000e0020" <= character <= "\U000e007f"
        else character
        for character in normalized
    )
    normalized = URL_PATTERN.sub(" ", normalized)
    normalized = MENTION_PATTERN.sub(" ", normalized)
    normalized = HASHTAG_PATTERN.sub(r"\1", normalized)
    return WHITESPACE_PATTERN.sub(" ", normalized).strip().casefold()


def _normalized_for_matching(text: str) -> str:
    return WHITESPACE_PATTERN.sub(
        " ", unicodedata.normalize("NFKC", str(text)).casefold()
    ).strip()


def _match_keyword(text: str, keywords: Sequence[str]) -> str | None:
    normalized_text = _normalized_for_matching(text)
    for keyword in keywords:
        normalized_keyword = _normalized_for_matching(keyword)
        if not normalized_keyword:
            continue
        pattern = re.compile(
            rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)", re.UNICODE
        )
        if pattern.search(normalized_text):
            return keyword
    return None


def _to_nonnegative_integer(series: pd.Series, column_name: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    invalid = numeric.isna() | numeric.lt(0) | numeric.mod(1).ne(0)
    if invalid.any():
        rows = ", ".join(str(index) for index in series.index[invalid].tolist())
        raise PreprocessingError(
            f"{column_name} must contain non-negative integers; invalid rows: {rows}"
        )
    return numeric.astype("int64")


def _to_optional_string(series: pd.Series) -> pd.Series:
    values = series.fillna("").astype(str).str.strip()
    return values.where(values.ne(""), None)


def _isoformat_utc(timestamp: pd.Timestamp) -> str:
    return timestamp.isoformat().replace("+00:00", "Z")


def _quality_status(
    *, is_duplicate: bool, is_indonesian: bool, is_relevant: bool,
    is_in_requested_window: bool,
) -> str:
    if not is_in_requested_window:
        return "review_out_of_window"
    if is_duplicate:
        return "duplicate"
    if not is_indonesian and not is_relevant:
        return "review_language_and_relevance"
    if not is_indonesian:
        return "review_language"
    if not is_relevant:
        return "review_relevance"
    return "accepted"


def preprocess_tweet_harvest_frame(
    frame: pd.DataFrame,
    *,
    program_id: str,
    ingestion_run_id: str,
    collected_at: datetime,
    keywords: Sequence[str],
    requested_start: date | None = None,
    requested_end: date | None = None,
) -> PreprocessingResult:
    """Map Tweet Harvest fields to the canonical processed-data contract.

    The function preserves every source row. Potential duplicates, language
    mismatches, and relevance mismatches receive review flags instead of being
    silently removed.
    """

    missing_columns = sorted(REQUIRED_SOURCE_COLUMNS - set(frame.columns))
    if missing_columns:
        raise PreprocessingError(
            f"missing required columns: {', '.join(missing_columns)}"
        )
    if not program_id.strip():
        raise PreprocessingError("program_id must not be empty")
    if not ingestion_run_id.strip():
        raise PreprocessingError("ingestion_run_id must not be empty")
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise PreprocessingError("collected_at must be timezone-aware")
    if (requested_start is None) != (requested_end is None):
        raise PreprocessingError(
            "requested_start and requested_end must be provided together"
        )
    if requested_start is not None and requested_start > requested_end:
        raise PreprocessingError("requested_start must not exceed requested_end")

    source = frame.copy()
    if source.empty:
        raise PreprocessingError("source dataset must contain at least one row")
    raw_text = source["full_text"].fillna("").astype(str)
    if raw_text.str.strip().eq("").any():
        raise PreprocessingError("full_text must not be empty")
    if raw_text.str.contains("\ufffd", regex=False).any():
        raise PreprocessingError("full_text contains a Unicode replacement character")

    tweet_ids = source["id_str"].fillna("").astype(str).str.strip()
    if tweet_ids.eq("").any():
        raise PreprocessingError("id_str must not be empty")
    duplicate_flags = tweet_ids.duplicated(keep="first")

    published_at = pd.to_datetime(
        source["created_at"], errors="coerce", utc=True, format="mixed"
    )
    if published_at.isna().any():
        rows = ", ".join(
            str(index) for index in source.index[published_at.isna()].tolist()
        )
        raise PreprocessingError(f"created_at is invalid at rows: {rows}")
    published_local = published_at.dt.tz_convert("Asia/Jakarta")
    local_dates = published_local.dt.date
    in_window_flags = (
        local_dates.between(requested_start, requested_end)
        if requested_start is not None
        else pd.Series(True, index=source.index)
    )

    engagement = {
        output_column: _to_nonnegative_integer(source[input_column], input_column)
        for input_column, output_column in ENGAGEMENT_COLUMN_MAP.items()
    }
    cleaned_text = raw_text.map(clean_text)
    empty_cleaned_flags = cleaned_text.str.strip().eq("")
    matched_keywords = pd.Series(
        [_match_keyword(value, keywords) for value in cleaned_text],
        index=source.index,
        dtype=object,
    )
    languages = _to_optional_string(source["lang"])
    indonesian_flags = languages.eq("in")
    relevance_flags = matched_keywords.notna()
    quality_statuses = [
        _quality_status(
            is_duplicate=bool(is_duplicate),
            is_indonesian=bool(is_indonesian),
            is_relevant=bool(is_relevant),
            is_in_requested_window=bool(is_in_window),
        )
        for is_duplicate, is_indonesian, is_relevant, is_in_window in zip(
            duplicate_flags,
            indonesian_flags,
            relevance_flags,
            in_window_flags,
            strict=True,
        )
    ]
    quality_statuses = [
        "review_empty_cleaned_text" if empty else status
        for empty, status in zip(empty_cleaned_flags, quality_statuses, strict=True)
    ]
    eligible_flags = [status == "accepted" for status in quality_statuses]
    iso_calendar = published_local.dt.isocalendar()

    records = pd.DataFrame(
        {
            "tweet_id": tweet_ids,
            "conversation_id": _to_optional_string(source["conversation_id_str"]),
            "tweet_url": _to_optional_string(source["tweet_url"]),
            "target_program": program_id,
            "matched_keyword": matched_keywords,
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "language": languages,
            "published_at": published_at.map(_isoformat_utc),
            "collected_at": collected_at.isoformat(),
            "year_week": [
                f"{year}-W{week:02d}"
                for year, week in zip(
                    iso_calendar["year"], iso_calendar["week"], strict=True
                )
            ],
            "year_month": published_local.dt.strftime("%Y-%m"),
            **engagement,
            "ingestion_run_id": ingestion_run_id,
            "schema_version": SCHEMA_VERSION,
            "source_platform": SOURCE_PLATFORM,
            "is_duplicate": duplicate_flags,
            "is_indonesian": indonesian_flags,
            "is_relevant": relevance_flags,
            "is_in_requested_window": in_window_flags,
            "is_eligible_for_labeling": eligible_flags,
            "quality_status": quality_statuses,
        }
    )

    status_counts = records["quality_status"].value_counts().to_dict()
    report: dict[str, Any] = {
        "source_rows": int(len(source)),
        "processed_rows": int(len(records)),
        "duplicate_tweet_ids": int(duplicate_flags.sum()),
        "eligible_for_labeling": int(sum(eligible_flags)),
        "out_of_window_rows": int((~in_window_flags).sum()),
        "requested_start": requested_start.isoformat() if requested_start else None,
        "requested_end": requested_end.isoformat() if requested_end else None,
        "quality_status_counts": {
            str(status): int(count) for status, count in status_counts.items()
        },
        "language_counts": {
            str(language): int(count)
            for language, count in languages.fillna("unknown").value_counts().items()
        },
        "published_at_min": _isoformat_utc(published_at.min()),
        "published_at_max": _isoformat_utc(published_at.max()),
        "replacement_characters": 0,
    }
    return PreprocessingResult(records=records, report=report)
