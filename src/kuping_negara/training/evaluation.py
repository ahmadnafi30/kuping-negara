"""Fixed grouped splits, training-only vocabulary and aggregate evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from kuping_negara.training.data import LABELS, leakage_groups

FEATURES = ["model_text", "target_program"]


def make_pipeline(parameters: dict, seed: int) -> Pipeline:
    features = ColumnTransformer(
        [
            (
                "text",
                TfidfVectorizer(
                    ngram_range=(1, parameters["ngram_max"]),
                    sublinear_tf=True,
                    max_features=10000,
                ),
                "model_text",
            ),
            ("program", OneHotEncoder(handle_unknown="ignore"), ["target_program"]),
        ]
    )
    return Pipeline(
        [
            ("features", features),
            (
                "classifier",
                LogisticRegression(
                    C=parameters["C"],
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=seed,
                ),
            ),
        ]
    )


def make_splits(frame: pd.DataFrame, seed: int) -> tuple[np.ndarray, np.ndarray, list]:
    labels = frame.sentiment_label.to_numpy()
    groups = np.asarray(leakage_groups(frame))
    counts = frame.assign(group=groups).groupby("sentiment_label").group.nunique()
    if counts.min() < 5:
        raise ValueError(
            "Need at least five independent groups per class for holdout/CV"
        )
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    for development, test in outer.split(frame, labels, groups):
        if set(labels[test]) != set(LABELS):
            continue
        inner = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=seed)
        folds = list(
            inner.split(
                frame.iloc[development], labels[development], groups[development]
            )
        )
        if all(
            set(labels[development][a]) == set(LABELS)
            and set(labels[development][b]) == set(LABELS)
            for a, b in folds
        ):
            return development, test, folds
    raise ValueError("Cannot create grouped splits with every class in each fold")


def metrics(truth, predicted, prefix: str) -> dict:
    values = {
        f"{prefix}_accuracy": accuracy_score(truth, predicted),
        f"{prefix}_macro_f1": f1_score(
            truth, predicted, labels=LABELS, average="macro", zero_division=0
        ),
        f"{prefix}_weighted_f1": f1_score(
            truth, predicted, labels=LABELS, average="weighted", zero_division=0
        ),
    }
    recall = recall_score(
        truth, predicted, labels=LABELS, average=None, zero_division=0
    )
    values.update(
        {
            f"{prefix}_recall_{label}": float(value)
            for label, value in zip(LABELS, recall, strict=True)
        }
    )
    return {key: float(value) for key, value in values.items()}
