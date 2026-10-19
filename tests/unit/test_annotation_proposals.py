"""Proposal gates do not equate model confidence with human approval."""

import pandas as pd
import pytest

from kuping_negara.labeling.proposals import protect_benchmark, select_proposal
from tests.fixtures.training import sample_frame


def test_uncertain_truncated_or_unresolved_records_are_excluded():
    assert (
        select_proposal([0.1, 0.05, 0.85], eligible=True, truncated=False)[
            "sentiment_label"
        ]
        == "positive"
    )
    for probabilities, eligible, truncated in [
        ([0.45, 0.4, 0.15], True, False),
        ([0.9, 0.05, 0.05], False, False),
        ([0.9, 0.05, 0.05], True, True),
    ]:
        result = select_proposal(probabilities, eligible=eligible, truncated=truncated)
        assert result["sentiment_label"] == "uncertain"
        assert not result["teacher_confidence_candidate"]
    for values in [[float("nan"), 0, 1], [0.9, 0.9, 0], [-1, 1, 1]]:
        with pytest.raises(ValueError):
            select_proposal(values, eligible=True, truncated=False)


def test_old_benchmark_blocks_transitive_conversation_and_text_matches():
    frame = sample_frame()
    protected = frame.iloc[[0]].copy()
    candidates = frame.iloc[1:].copy().reset_index(drop=True)
    candidates.loc[0, "conversation_id"] = protected.iloc[0].conversation_id
    candidates.loc[1, "model_text"] = candidates.loc[0, "model_text"]
    kept, removed = protect_benchmark(candidates, protected)
    assert removed == 2
    assert len(kept) == len(candidates) - 2
    assert not set(kept.tweet_id) & set(protected.tweet_id)
    assert len(pd.concat([kept, protected])) == len(frame) - 2


def test_context_review_never_overrides_preprocessing_or_human_flags():
    from hashlib import sha256

    from kuping_negara.labeling.proposals import apply_ai_reviews

    frame = sample_frame().iloc[:2].copy()
    frame["is_eligible_for_labeling"] = "True"
    frame.loc[0, "quality_status"] = "review_relevance"
    row = frame.iloc[0]
    decision = dict(
        target_program=row.target_program,
        tweet_id=row.tweet_id,
        text_sha256=sha256(row.model_text.encode()).hexdigest(),
        sentiment_label="positive",
        relevance_review="relevant",
        reason="Explicit support for the target",
    )
    reviewed = apply_ai_reviews(frame, [decision])
    assert reviewed.iloc[0].ai_training_candidate == "False"
    assert reviewed.iloc[0].approved_for_training == "False"
    decision["text_sha256"] = "wrong"
    with pytest.raises(ValueError, match="text changed"):
        apply_ai_reviews(frame, [decision])
