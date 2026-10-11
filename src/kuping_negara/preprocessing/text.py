"""Conservative text preparation that preserves sentiment-bearing content."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from collections.abc import Sequence

URL_PATTERN = re.compile(
    r"(?:https?://|www\.)[^\s\u2600-\u27ff\U0001f000-\U0001ffff]+", re.IGNORECASE
)
MENTION_PATTERN = re.compile(r"(?<!\w)@[\w_]+", re.UNICODE)
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([\w_]+)", re.UNICODE)
WHITESPACE_PATTERN = re.compile(r"\s+")
CAMEL_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
HASHTAG_PREFIXES = ("tolak", "dukung", "stop", "evaluasi", "anti", "pro", "kontra")
URL_END_PUNCTUATION = ".,!?;:)]}\"'\u201d\u2019"


def _preserve_character(character: str) -> str:
    # ZWJ/ZWNJ and emoji tag characters participate in visible graphemes.
    if character in ("\u200c", "\u200d") or 0xE0020 <= ord(character) <= 0xE007F:
        return character
    return " " if unicodedata.category(character).startswith("C") else character


def _remove_url(match: re.Match[str]) -> str:
    value = match.group()
    trimmed = value.rstrip(URL_END_PUNCTUATION)
    return " " + value[len(trimmed) :]


def prepare_model_text(text: str) -> str:
    """Remove account/link noise without changing case, hashtags or sentiment.

    No stemming, stopword/slang removal, repeated-letter collapse, or sentiment
    replacement is applied. A future tokenizer can adapt this model-neutral view.
    """
    normalized = unicodedata.normalize("NFKC", html.unescape(str(text)))
    normalized = "".join(_preserve_character(c) for c in normalized)
    normalized = URL_PATTERN.sub(_remove_url, normalized)
    normalized = MENTION_PATTERN.sub(" ", normalized)
    return WHITESPACE_PATTERN.sub(" ", normalized).strip()


def clean_text(text: str) -> str:
    """Provide the existing lowercase view while retaining hashtag words."""
    return HASHTAG_PATTERN.sub(r"\1", prepare_model_text(text)).casefold()


def duplicate_text_key(text: str) -> str:
    """Normalize identity noise/case, retaining negation, emoji and punctuation."""
    cleaned = clean_text(text)
    return re.sub(r"^rt\s+", "", cleaned).strip()


def text_fingerprint(text: str) -> str:
    return hashlib.sha256(duplicate_text_key(text).encode("utf-8")).hexdigest()


def _normalized_for_matching(text: str) -> str:
    return WHITESPACE_PATTERN.sub(
        " ", unicodedata.normalize("NFKC", str(text)).casefold()
    ).strip()


def match_keyword(text: str, keywords: Sequence[str]) -> str | None:
    """Match whole words and conservative program hashtags, never substrings."""
    sanitized = prepare_model_text(text)
    hashtags = HASHTAG_PATTERN.findall(sanitized)
    expanded = HASHTAG_PATTERN.sub(
        lambda m: " " + CAMEL_BOUNDARY.sub(" ", m.group(1)) + " ", sanitized
    )
    normalized_text = _normalized_for_matching(expanded)
    for keyword in keywords:
        normalized_keyword = _normalized_for_matching(keyword)
        if not normalized_keyword:
            continue
        pattern = re.compile(
            rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)", re.UNICODE
        )
        if pattern.search(normalized_text):
            return keyword
        compact = normalized_keyword.replace(" ", "")
        allowed = {compact, *(prefix + compact for prefix in HASHTAG_PREFIXES)}
        if any(hashtag.casefold() in allowed for hashtag in hashtags):
            return keyword
    return None
