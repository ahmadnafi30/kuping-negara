"""Target-aware duplicate decisions and conservative text-similarity flags."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from kuping_negara.preprocessing.text import duplicate_text_key, text_fingerprint

SIMILARITY_THRESHOLD = 0.92
MIN_SIMILARITY_CHARACTERS = 40


@dataclass(frozen=True)
class TextReference:
    tweet_id: str
    program_id: str
    text: str
    eligible: bool
    split_group_id: str


@dataclass(frozen=True)
class DuplicateDecision:
    duplicate_id: bool
    duplicate_text: bool
    near_duplicate: bool
    similar_to: str | None
    split_group_id: str


def compare_text(
    *, tweet_id: str, program_id: str, text: str, references: list[TextReference]
) -> DuplicateDecision:
    """Do not infer sentiment or delete similar posts; request human review.

    Exact duplicates block repeated labeling only within one target program.
    Group hints remain global so cross-target copies can stay in the same split.
    """
    key = duplicate_text_key(text)
    fingerprint = text_fingerprint(text)
    group = "text:" + fingerprint
    duplicate_id = duplicate_text = near = False
    similar_to = None
    best_score = 0.0
    same_tweet_group = None
    for reference in references:
        other = duplicate_text_key(reference.text)
        same_target = reference.program_id == program_id
        if reference.tweet_id == tweet_id:
            same_tweet_group = reference.split_group_id
            duplicate_id |= same_target and reference.eligible
        exact = bool(key) and key == other
        score = 1.0 if exact else 0.0
        if (
            not exact
            and min(len(key), len(other)) >= MIN_SIMILARITY_CHARACTERS
            and min(len(key), len(other)) / max(len(key), len(other)) >= 0.85
        ):
            score = SequenceMatcher(None, key, other, autojunk=False).ratio()
        if score >= SIMILARITY_THRESHOLD:
            if score > best_score:
                best_score = score
                group = reference.split_group_id
            if same_target and reference.eligible:
                duplicate_text |= exact
                near |= not exact
                similar_to = reference.tweet_id
    return DuplicateDecision(
        duplicate_id, duplicate_text, near, similar_to, same_tweet_group or group
    )
