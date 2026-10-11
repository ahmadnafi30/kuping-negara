"""Unicode-aware text normalization and keyword matching."""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Sequence

URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MENTION_PATTERN = re.compile(r"(?<!\w)@[\w_]+", re.UNICODE)
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([\w_]+)", re.UNICODE)
WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Normalize text while removing URLs and direct user references.

    Emoji and ordinary punctuation remain available as sentiment signals.
    Hashtag words remain, but the leading hash is removed.
    """

    normalized = unicodedata.normalize("NFKC", html.unescape(str(text)))
    normalized = "".join(
        " " if unicodedata.category(character).startswith("C") else character
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


def match_keyword(text: str, keywords: Sequence[str]) -> str | None:
    """Return the first configured keyword matching normalized word boundaries."""
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
