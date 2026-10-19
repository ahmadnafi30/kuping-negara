"""Annotation opt-in, raw lineage and transitive leakage grouping checks."""

import json

import pandas as pd
import pytest
import yaml

from kuping_negara.preprocessing.text import prepare_model_text
from kuping_negara.training.data import (
    digest,
    leakage_groups,
    load_dataset,
    prepare_dataset,
    validate_rows,
)
from kuping_negara.training.evaluation import make_splits
from tests.fixtures.training import sample_frame


def test_provisional_opt_in_does_not_change_approval_flags():
    frame = sample_frame()
    with pytest.raises(ValueError, match="allow-provisional"):
        validate_rows(frame, False)
    validate_rows(frame, True)
    assert frame.approved_for_training.eq("False").all()
    frame.loc[0, "sentiment_label"] = "uncertain"
    with pytest.raises(ValueError, match="three labels"):
        validate_rows(frame, True)


def test_prepare_checks_source_and_dvc_integrity(training_dataset):
    root, raw, labels = training_dataset
    output = root / "data/training/sentiment.csv"
    meta = prepare_dataset(root, labels, raw, output, "lk05-data-v2", True)
    output.with_suffix(".csv.dvc").write_text(
        yaml.safe_dump({"outs": [{"md5": digest(output, "md5")}]})
    )
    loaded, actual = load_dataset(root, output, True)
    assert len(loaded) == meta["rows"] == 30
    assert actual["label_status"] == "provisional_ai"
    with pytest.raises(ValueError, match="allow-provisional"):
        load_dataset(root, output, False)
    raw.write_text(raw.read_text() + "tampered")
    with pytest.raises(ValueError, match="DVC revision"):
        load_dataset(root, output, True)


def test_preparation_rejects_unversioned_text(training_dataset):
    root, raw, labels = training_dataset
    frame = pd.read_csv(labels, dtype=str, keep_default_na=False)
    frame.loc[0, "model_text"] = prepare_model_text("A different post")
    frame.to_csv(labels, index=False)
    labels.with_name("batch_manifest.json").write_text(
        json.dumps({"combined_sha256": digest(labels)})
    )
    with pytest.raises(ValueError, match="versioned raw preprocessing"):
        prepare_dataset(
            root,
            labels,
            raw,
            root / "data/training/sentiment.csv",
            "lk05-data-v2",
            True,
        )


def test_leakage_groups_union_shared_conversations_and_text():
    frame = sample_frame()
    frame.loc[0, "conversation_id"] = frame.loc[1, "conversation_id"]
    frame.loc[1, "model_text"] = frame.loc[2, "model_text"]
    groups = leakage_groups(frame)
    assert groups[0] == groups[1] == groups[2]
    assert groups[3] != groups[0]


def test_splits_keep_related_posts_together_and_cover_classes():
    frame = sample_frame(15)
    frame.loc[0, "conversation_id"] = frame.loc[1, "conversation_id"]
    dev, test, folds = make_splits(frame, 42)
    groups = leakage_groups(frame)
    assert not {groups[i] for i in dev} & {groups[i] for i in test}
    assert set(dev) | set(test) == set(range(len(frame)))
    for train, validation in folds:
        assert not {groups[dev[i]] for i in train} & {
            groups[dev[i]] for i in validation
        }
        assert frame.iloc[dev[validation]].sentiment_label.nunique() == 3


def test_word_character_features_preserve_emoji_negation_and_slang():
    from kuping_negara.training.evaluation import make_pipeline

    frame = sample_frame()
    frame.loc[0, "model_text"] = "Program nggak bagus 😡 #TolakMBG"
    model = make_pipeline({"C": 1, "ngram_max": 2, "feature_mode": "word_char"}, 42)
    model.fit(frame[["model_text", "target_program"]], frame.sentiment_label)
    features = model.named_steps["features"].named_transformers_
    assert {"nggak", "nggak bagus", "😡"} <= set(features["text"].vocabulary_)
    assert "gak" in features["characters"].vocabulary_
    assert "program" not in features
