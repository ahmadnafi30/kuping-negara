from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from kuping_negara.preprocessing.x_posts import (
    PreprocessingError,
    clean_text,
    preprocess_tweet_harvest_frame,
)

JAKARTA_TIMEZONE = ZoneInfo("Asia/Jakarta")


def _source_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "conversation_id_str": "1000000000000000001",
                "created_at": "Mon Sep 21 11:15:29 +0000 2026",
                "favorite_count": "3",
                "full_text": "@warga MBG bagus! 😊 https://t.co/example #Sehat",
                "id_str": "2000000000000000001",
                "image_url": "https://example.test/image.jpg",
                "in_reply_to_screen_name": "warga",
                "lang": "in",
                "location": "Malang",
                "quote_count": "0",
                "reply_count": "1",
                "retweet_count": "2",
                "tweet_url": "https://x.com/example/status/1",
                "user_id_str": "3000000000000000001",
                "username": "example_user",
            },
            {
                "conversation_id_str": "1000000000000000002",
                "created_at": "Mon Sep 21 11:16:29 +0000 2026",
                "favorite_count": "0",
                "full_text": "School lunch policy discussion",
                "id_str": "2000000000000000002",
                "image_url": "",
                "in_reply_to_screen_name": "",
                "lang": "en",
                "location": "",
                "quote_count": "0",
                "reply_count": "0",
                "retweet_count": "0",
                "tweet_url": "https://x.com/example/status/2",
                "user_id_str": "3000000000000000002",
                "username": "another_user",
            },
        ]
    )


def test_clean_text_removes_identity_noise_and_preserves_sentiment_symbols() -> None:
    cleaned = clean_text("  @Warga MBG bagus! 😊 https://t.co/example #Sehat\n")

    assert cleaned == "mbg bagus! 😊 sehat"


def test_preprocess_maps_source_fields_without_user_identifiers() -> None:
    result = preprocess_tweet_harvest_frame(
        _source_frame(),
        program_id="mbg",
        ingestion_run_id="20260921T182524+0700",
        collected_at=datetime(2026, 9, 21, 18, 25, 24, tzinfo=JAKARTA_TIMEZONE),
        keywords=["mbg", "makan bergizi gratis"],
    )

    assert result.records["tweet_id"].tolist() == [
        "2000000000000000001",
        "2000000000000000002",
    ]
    assert result.records["like_count"].tolist() == [3, 0]
    assert result.records["matched_keyword"].tolist() == ["mbg", None]
    assert result.records["quality_status"].tolist() == [
        "accepted",
        "review_language_and_relevance",
    ]
    assert result.records["is_eligible_for_labeling"].tolist() == [True, False]
    assert "username" not in result.records.columns
    assert "user_id_str" not in result.records.columns


def test_preprocess_preserves_every_row_and_flags_duplicate_tweet_ids() -> None:
    source = pd.concat([_source_frame(), _source_frame().iloc[[0]]], ignore_index=True)

    result = preprocess_tweet_harvest_frame(
        source,
        program_id="mbg",
        ingestion_run_id="20260921T182524+0700",
        collected_at=datetime(2026, 9, 21, 18, 25, 24, tzinfo=JAKARTA_TIMEZONE),
        keywords=["mbg", "makan bergizi gratis"],
    )

    assert len(result.records) == 3
    assert result.records["is_duplicate"].tolist() == [False, False, True]
    assert result.records["quality_status"].tolist()[-1] == "duplicate"
    assert result.report["duplicate_tweet_ids"] == 1


def test_preprocess_rejects_missing_required_source_columns() -> None:
    source = _source_frame().drop(columns=["full_text"])

    with pytest.raises(PreprocessingError, match="missing required columns: full_text"):
        preprocess_tweet_harvest_frame(
            source,
            program_id="mbg",
            ingestion_run_id="20260921T182524+0700",
            collected_at=datetime(2026, 9, 21, 18, 25, 24, tzinfo=JAKARTA_TIMEZONE),
            keywords=["mbg"],
        )


def test_preprocess_rejects_negative_engagement_counts() -> None:
    source = _source_frame()
    source.loc[0, "reply_count"] = "-1"

    with pytest.raises(PreprocessingError, match="reply_count"):
        preprocess_tweet_harvest_frame(
            source,
            program_id="mbg",
            ingestion_run_id="20260921T182524+0700",
            collected_at=datetime(2026, 9, 21, 18, 25, 24, tzinfo=JAKARTA_TIMEZONE),
            keywords=["mbg"],
        )


def test_preprocess_rejects_unicode_replacement_characters() -> None:
    source = _source_frame()
    source.loc[0, "full_text"] = "teks rusak \ufffd"

    with pytest.raises(PreprocessingError, match="replacement character"):
        preprocess_tweet_harvest_frame(
            source,
            program_id="mbg",
            ingestion_run_id="20260921T182524+0700",
            collected_at=datetime(2026, 9, 21, 18, 25, 24, tzinfo=JAKARTA_TIMEZONE),
            keywords=["mbg"],
        )


def test_preprocess_rejects_header_only_dataset() -> None:
    with pytest.raises(PreprocessingError, match="at least one row"):
        preprocess_tweet_harvest_frame(
            _source_frame().iloc[:0],
            program_id="mbg",
            ingestion_run_id="20260921T182524+0700",
            collected_at=datetime(2026, 9, 21, 18, 25, 24, tzinfo=JAKARTA_TIMEZONE),
            keywords=["mbg"],
        )


@pytest.mark.parametrize(
    "text", ["@mbg https://example.test", "https://example.test/mbg", "@mbg"]
)
def test_empty_cleaned_text_is_never_eligible(text):
    source = _source_frame().iloc[[0]].copy()
    source.loc[0, "full_text"] = text
    result = preprocess_tweet_harvest_frame(
        source,
        program_id="mbg",
        ingestion_run_id="run",
        collected_at=datetime(2026, 9, 21, tzinfo=JAKARTA_TIMEZONE),
        keywords=["mbg"],
    )
    assert result.records.iloc[0]["cleaned_text"] == ""
    assert result.records.iloc[0]["quality_status"] == "empty_cleaned_text"
    assert not result.records.iloc[0]["is_eligible_for_labeling"]
    assert result.report["empty_cleaned_text_rows"] == 1


def test_mentions_and_links_are_not_keyword_evidence():
    source = _source_frame().iloc[[0]].copy()
    source.loc[0, "full_text"] = "@mbg berita https://example.test/mbg"
    result = preprocess_tweet_harvest_frame(
        source,
        program_id="mbg",
        ingestion_run_id="run",
        collected_at=datetime(2026, 9, 21, tzinfo=JAKARTA_TIMEZONE),
        keywords=["mbg"],
    )
    assert result.records.iloc[0]["quality_status"] == "review_relevance"
    assert not result.records.iloc[0]["is_relevant"]


@pytest.mark.parametrize("collection_timezone", [JAKARTA_TIMEZONE, UTC])
def test_temporal_groups_follow_jakarta_calendar(collection_timezone):
    source = _source_frame().iloc[[0]].copy()
    source.loc[0, "created_at"] = "2026-09-30T18:00:00Z"
    result = preprocess_tweet_harvest_frame(
        source,
        program_id="mbg",
        ingestion_run_id="run",
        collected_at=datetime(2026, 10, 1, tzinfo=collection_timezone),
        keywords=["mbg"],
    )
    assert result.records.iloc[0]["year_month"] == "2026-10"
    assert result.records.iloc[0]["published_at"] == "2026-09-30T18:00:00Z"
