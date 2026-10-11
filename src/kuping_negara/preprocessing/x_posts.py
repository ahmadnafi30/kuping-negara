"""Deterministic preprocessing for Tweet Harvest CSV records."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from kuping_negara.paths import JAKARTA_TIMEZONE
from kuping_negara.preprocessing.duplicates import TextReference, compare_text
from kuping_negara.preprocessing.text import (
    clean_text,
    match_keyword,
    prepare_model_text,
    text_fingerprint,
)

SCHEMA_VERSION = "3"
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


class PreprocessingError(ValueError):
    """Raised when source data cannot be transformed without data loss."""


@dataclass(frozen=True)
class PreprocessingResult:
    """Canonical records and aggregate quality evidence for one raw dataset."""

    records: pd.DataFrame
    report: dict[str, Any]


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
    *,
    is_duplicate: bool,
    is_indonesian: bool,
    is_relevant: bool,
    is_empty: bool,
    duplicate_text: bool = False,
    near_duplicate: bool = False,
) -> str:
    if is_duplicate:
        return "duplicate"
    if is_empty:
        return "empty_cleaned_text"
    if duplicate_text:
        return "duplicate_text"
    if near_duplicate:
        return "review_similar_text"
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
    previous_tweet_ids: Collection[str] = (),
    history: Collection[TextReference] = (),
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

    if frame.empty:
        raise PreprocessingError("source dataset must contain at least one row")

    source = frame.copy()
    raw_text = source["full_text"].fillna("").astype(str)
    if raw_text.str.strip().eq("").any():
        raise PreprocessingError("full_text must not be empty")
    if raw_text.str.contains("\ufffd", regex=False).any():
        raise PreprocessingError("full_text contains a Unicode replacement character")

    tweet_ids = source["id_str"].fillna("").astype(str).str.strip()
    if tweet_ids.eq("").any():
        raise PreprocessingError("id_str must not be empty")

    published_at = pd.to_datetime(
        source["created_at"], errors="coerce", utc=True, format="mixed"
    )
    if published_at.isna().any():
        rows = ", ".join(
            str(index) for index in source.index[published_at.isna()].tolist()
        )
        raise PreprocessingError(f"created_at is invalid at rows: {rows}")

    engagement = {
        output_column: _to_nonnegative_integer(source[input_column], input_column)
        for input_column, output_column in ENGAGEMENT_COLUMN_MAP.items()
    }
    model_text = raw_text.map(prepare_model_text)
    cleaned_text = raw_text.map(clean_text)
    matched_keywords = pd.Series(
        [match_keyword(value, keywords) for value in model_text],
        index=source.index,
        dtype=object,
    )
    languages = _to_optional_string(source["lang"])
    language_normalized = languages.fillna("").str.casefold().replace({"in": "id"})
    indonesian_flags = language_normalized.eq("id")
    relevance_flags = matched_keywords.notna()
    empty_cleaned_flags = cleaned_text.str.strip().eq("")
    references = list(history)
    past_ids = {
        r.tweet_id for r in references if r.program_id == program_id and r.eligible
    }
    past_ids.update(previous_tweet_ids)
    duplicate_flags, across_run_flags, text_flags, near_flags = [], [], [], []
    group_ids, similar_ids, quality_statuses = [], [], []
    repeated_ids = tweet_ids.duplicated(keep="first")
    for position, (tweet_id, text) in enumerate(
        zip(tweet_ids, model_text, strict=True)
    ):
        decision = compare_text(
            tweet_id=tweet_id, program_id=program_id, text=text, references=references
        )
        across = tweet_id in past_ids
        duplicate = bool(repeated_ids.iloc[position]) or across or decision.duplicate_id
        status = _quality_status(
            is_duplicate=duplicate,
            is_indonesian=bool(indonesian_flags.iloc[position]),
            is_relevant=bool(relevance_flags.iloc[position]),
            is_empty=bool(empty_cleaned_flags.iloc[position]),
            duplicate_text=decision.duplicate_text,
            near_duplicate=decision.near_duplicate,
        )
        duplicate_flags.append(duplicate)
        across_run_flags.append(across)
        text_flags.append(decision.duplicate_text)
        near_flags.append(decision.near_duplicate)
        group_ids.append(decision.split_group_id)
        similar_ids.append(decision.similar_to)
        quality_statuses.append(status)
        if not empty_cleaned_flags.iloc[position]:
            references.append(
                TextReference(
                    tweet_id,
                    program_id,
                    text,
                    status == "accepted",
                    decision.split_group_id,
                )
            )
    eligible_flags = [status == "accepted" for status in quality_statuses]
    local_published = published_at.dt.tz_convert(JAKARTA_TIMEZONE)
    iso_calendar = local_published.dt.isocalendar()

    records = pd.DataFrame(
        {
            "tweet_id": tweet_ids,
            "conversation_id": _to_optional_string(source["conversation_id_str"]),
            "tweet_url": _to_optional_string(source["tweet_url"]),
            "target_program": program_id,
            "matched_keyword": matched_keywords,
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "model_text": model_text,
            "text_fingerprint": model_text.map(text_fingerprint),
            "split_group_id": group_ids,
            "similar_to_tweet_id": similar_ids,
            "language_normalized": language_normalized,
            "language_needs_review": ~indonesian_flags,
            "language": languages,
            "published_at": published_at.map(_isoformat_utc),
            "collected_at": collected_at.isoformat(),
            "year_week": [
                f"{year}-W{week:02d}"
                for year, week in zip(
                    iso_calendar["year"], iso_calendar["week"], strict=True
                )
            ],
            "year_month": local_published.dt.strftime("%Y-%m"),
            **engagement,
            "ingestion_run_id": ingestion_run_id,
            "schema_version": SCHEMA_VERSION,
            "source_platform": SOURCE_PLATFORM,
            "is_duplicate": duplicate_flags,
            "is_duplicate_across_runs": across_run_flags,
            "is_duplicate_text": text_flags,
            "is_near_duplicate": near_flags,
            "is_empty_cleaned_text": empty_cleaned_flags,
            "is_indonesian": indonesian_flags,
            "is_relevant": relevance_flags,
            "is_eligible_for_labeling": eligible_flags,
            "quality_status": quality_statuses,
        }
    )

    status_counts = records["quality_status"].value_counts().to_dict()
    report: dict[str, Any] = {
        "source_rows": int(len(source)),
        "processed_rows": int(len(records)),
        "duplicate_tweet_ids": int(sum(duplicate_flags)),
        "duplicate_tweet_ids_across_runs": int(sum(across_run_flags)),
        "empty_cleaned_text_rows": int(empty_cleaned_flags.sum()),
        "deduplication_scope": "tweet_or_text_per_program",
        "duplicate_text_rows": int(sum(text_flags)),
        "near_duplicate_rows": int(sum(near_flags)),
        "language_review_rows": int((~indonesian_flags).sum()),
        "language_validation": "source_label_only",
        "text_preparation": "conservative_case_preserving_v3",
        "eligible_for_labeling": int(sum(eligible_flags)),
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
