"""Verified proposal batches cannot silently authorize unreviewed teacher labels."""

import json
from hashlib import sha256

import pandas as pd
import pytest

from kuping_negara.labeling.batches import assemble_reviewed_batch
from kuping_negara.training.data import digest, prepare_dataset, read_frame
from tests.fixtures.training import sample_frame


def test_assembly_requires_explicit_context_decisions_and_valid_sources(
    training_dataset,
):
    root, raw, labels = training_dataset
    original = root / "data/training/original.csv"
    prepare_dataset(root, labels, raw, original, "lk05-data-v2", True)
    summary = root / "original_summary.json"
    test = [0, 10, 20]
    summary.write_text(
        json.dumps(
            {
                "lineage": {"dataset_sha256": digest(original)},
                "split": {
                    "test_indices": test,
                    "development_indices": [i for i in range(30) if i not in test],
                },
            }
        )
    )
    frame = sample_frame().iloc[:2].copy()
    frame["tweet_id"] = ["new-1", "new-2"]
    frame["conversation_id"] = frame.tweet_id
    frame["split_group_id"] = frame.tweet_id
    frame["model_text"] = ["contoh baru pertama bagus", "contoh baru kedua bagus"]
    frame["sentiment_label"] = "positive"
    frame["annotation_method"] = "local_transformer_pseudo_label"
    frame["is_eligible_for_labeling"] = "True"
    proposals = root / "proposals/proposals.csv"
    proposals.parent.mkdir()
    frame.to_csv(proposals, index=False)
    manifest = proposals.with_name("batch_manifest.json")
    manifest.write_text(
        json.dumps(
            {"combined_sha256": digest(proposals), "teacher": {"revision": "synthetic"}}
        )
    )
    decisions = root / "decisions.json"
    row = frame.iloc[0]
    decisions.write_text(
        json.dumps(
            [
                dict(
                    target_program=row.target_program,
                    tweet_id=row.tweet_id,
                    text_sha256=sha256(row.model_text.encode()).hexdigest(),
                    sentiment_label="positive",
                    relevance_review="relevant",
                    reason="Explicit favorable evaluation of the target",
                )
            ]
        )
    )
    options = dict(
        proposals=[proposals],
        decisions_path=decisions,
        original_labels=labels,
        original_dataset=original,
        original_summary=summary,
    )
    output = root / "data/labeled/reviewed.csv"
    result = assemble_reviewed_batch(**options, output=output)
    assert (
        result["training_candidate_rows"] == 28
    )  # 27 old development + one actual review
    assert result["annotation_provenance"]["original_test_rows_protected"] == 3
    loaded = read_frame(output)
    assert (
        loaded.loc[loaded.tweet_id.eq("new-2"), "ai_training_candidate"].iloc[0]
        == "False"
    )
    assert not loaded.human_reviewed.str.lower().eq("true").any()
    assert len(pd.read_csv(output)) == 29
    manifest.write_text(json.dumps({"combined_sha256": "tampered", "teacher": {}}))
    with pytest.raises(ValueError, match="checksum"):
        assemble_reviewed_batch(**options, output=output.with_name("tampered.csv"))
