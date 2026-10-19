"""Validate LK-05 lineage and retain explicit annotation quality flags."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd
import yaml

from kuping_negara.preprocessing.history import PREPROCESSING_VERSION
from kuping_negara.preprocessing.text import prepare_model_text, text_fingerprint

LABELS = ("negative", "neutral", "positive")
COLUMNS = [
    "tweet_id",
    "conversation_id",
    "target_program",
    "model_text",
    "split_group_id",
    "sentiment_label",
    "annotation_source",
    "human_reviewed",
    "approved_for_training",
    "ai_training_candidate",
    "quality_status",
    "relevance_review",
]


def digest(path: Path, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, path.read_bytes()).hexdigest()


def read_frame(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def verify_raw(root: Path, raw: Path, revision: str) -> dict:
    relative = raw.resolve().relative_to(root.resolve()).as_posix()
    pointer = subprocess.check_output(
        ["git", "show", f"{revision}:{relative}.dvc"], cwd=root, text=True
    )
    record = yaml.safe_load(pointer)["outs"][0]
    if record.get("md5") != digest(raw, "md5"):
        raise ValueError("Raw CSV does not match the requested DVC revision")
    return {
        "raw_revision": revision,
        "raw_path": relative,
        "raw_md5": record["md5"],
        "raw_sha256": digest(raw),
    }


def validate_rows(frame: pd.DataFrame, allow_provisional: bool) -> None:
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing training columns: {sorted(missing)}")
    if frame.empty or set(frame.sentiment_label) != set(LABELS):
        raise ValueError("Training requires nonempty data containing all three labels")
    if frame.model_text.str.strip().eq("").any():
        raise ValueError("Training text cannot be empty")
    if frame[["tweet_id", "target_program", "split_group_id"]].eq("").any().any():
        raise ValueError("Training identity and grouping fields cannot be empty")
    if frame.duplicated(["target_program", "tweet_id"]).any():
        raise ValueError("Duplicate program/post keys in training data")
    if not frame.quality_status.eq("accepted").all():
        raise ValueError("Unresolved preprocessing flags cannot enter training")
    if not frame.relevance_review.eq("relevant").all():
        raise ValueError("Uncertain or irrelevant targets cannot enter training")
    approved = frame.human_reviewed.str.lower().eq(
        "true"
    ) & frame.approved_for_training.str.lower().eq("true")
    provisional = frame.annotation_source.eq(
        "ai"
    ) & frame.ai_training_candidate.str.lower().eq("true")
    if not (approved | (provisional & allow_provisional)).all():
        raise ValueError("Unapproved labels require explicit --allow-provisional")


def prepare_dataset(
    root: Path,
    labels: Path,
    raw: Path,
    output: Path,
    revision: str,
    allow_provisional: bool,
) -> dict:
    if not output.resolve().is_relative_to(root.resolve() / "data/training"):
        raise ValueError("Prepared data must stay inside data/training")
    lineage = verify_raw(root, raw, revision)
    manifest_path = labels.with_name("batch_manifest.json")
    batch = json.loads(manifest_path.read_text(encoding="utf-8"))
    if batch["combined_sha256"] != digest(labels):
        raise ValueError("Annotation CSV checksum does not match its batch manifest")
    frame = read_frame(labels)
    approved = frame.human_reviewed.str.lower().eq(
        "true"
    ) & frame.approved_for_training.str.lower().eq("true")
    selected = approved.copy()
    if allow_provisional:
        selected |= frame.ai_training_candidate.str.lower().eq(
            "true"
        ) & frame.annotation_source.eq("ai")
    selected &= frame.quality_status.eq("accepted") & frame.relevance_review.eq(
        "relevant"
    )
    frame = frame.loc[selected & frame.sentiment_label.isin(LABELS), COLUMNS].copy()
    validate_rows(frame, allow_provisional)
    raw_rows = read_frame(raw).set_index(["target_program", "id_str"])
    if raw_rows.index.has_duplicates:
        raise ValueError("Raw snapshot contains duplicate program/post keys")
    for row in frame.itertuples():
        key = (row.target_program, row.tweet_id)
        if key not in raw_rows.index:
            raise ValueError(
                "A labeled record is absent from the versioned raw snapshot"
            )
        source = raw_rows.loc[key]
        if row.model_text != prepare_model_text(source.full_text):
            raise ValueError("Model text differs from the versioned raw preprocessing")
        if row.conversation_id != source.conversation_id_str:
            raise ValueError("Conversation lineage differs from versioned raw")
    frame = frame.sort_values(["target_program", "tweet_id"]).reset_index(drop=True)
    content = frame.to_csv(index=False, lineterminator="\n")
    if output.exists() and output.read_text(encoding="utf-8") != content:
        raise ValueError("Existing training snapshot differs; choose a new output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="")
    provisional = not (
        frame.human_reviewed.str.lower().eq("true")
        & frame.approved_for_training.str.lower().eq("true")
    ).all()
    metadata = {
        **lineage,
        "dataset_sha256": digest(output),
        "labels_sha256": digest(labels),
        "rows": len(frame),
        "class_counts": frame.sentiment_label.value_counts().to_dict(),
        "program_counts": frame.target_program.value_counts().to_dict(),
        "preprocessing_version": PREPROCESSING_VERSION,
        "label_status": "provisional_ai" if provisional else "human_approved",
        "deployment_approved": False,
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def load_dataset(
    root: Path, dataset: Path, allow_provisional: bool
) -> tuple[pd.DataFrame, dict]:
    metadata = json.loads(
        dataset.with_suffix(".manifest.json").read_text(encoding="utf-8")
    )
    pointer = yaml.safe_load(
        dataset.with_suffix(dataset.suffix + ".dvc").read_text(encoding="utf-8")
    )
    if pointer["outs"][0].get("md5") != digest(dataset, "md5"):
        raise ValueError("Training CSV changed after dvc add")
    if metadata["dataset_sha256"] != digest(dataset):
        raise ValueError("Training CSV differs from its lineage manifest")
    expected = verify_raw(root, root / metadata["raw_path"], metadata["raw_revision"])
    if any(metadata[key] != value for key, value in expected.items()):
        raise ValueError("Raw lineage differs from the training manifest")
    frame = read_frame(dataset)
    validate_rows(frame, allow_provisional)
    provisional = not (
        frame.human_reviewed.str.lower().eq("true")
        & frame.approved_for_training.str.lower().eq("true")
    ).all()
    status = "provisional_ai" if provisional else "human_approved"
    if metadata["label_status"] != status or metadata["deployment_approved"]:
        raise ValueError("Manifest overstates label quality or deployment approval")
    if metadata["preprocessing_version"] != PREPROCESSING_VERSION:
        raise ValueError("Preprocessing version changed; rebuild the training snapshot")
    if len(frame) != metadata["rows"]:
        raise ValueError("Training row count differs from metadata")
    return frame, metadata


def leakage_groups(frame: pd.DataFrame) -> list[str]:
    """Union post, conversation, exact-text and preprocessing similarity groups."""
    parents = list(range(len(frame)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    seen = {}
    for i, row in enumerate(frame.itertuples()):
        values = [
            ("post", row.tweet_id),
            ("conversation", row.conversation_id),
            ("similarity", row.split_group_id),
            ("text", text_fingerprint(row.model_text)),
        ]
        for kind, value in values:
            if not value:
                continue
            key = (kind, value)
            if key in seen:
                parents[find(i)] = find(seen[key])
            else:
                seen[key] = i
    return [f"group-{find(i)}" for i in range(len(frame))]
