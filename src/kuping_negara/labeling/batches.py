"""Assemble explicit AI reviews and protect the original experimental holdout."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from kuping_negara.labeling.proposals import apply_ai_reviews, protect_benchmark
from kuping_negara.preprocessing.text import text_fingerprint
from kuping_negara.training.data import digest, read_frame


def assemble_reviewed_batch(
    *,
    proposals: list[Path],
    decisions_path: Path,
    original_labels: Path,
    original_dataset: Path,
    original_summary: Path,
    output: Path,
) -> dict:
    if output.exists():
        raise ValueError("Reviewed batch already exists")
    frames, sources = [], []
    teachers = []
    for path in proposals:
        manifest = json.loads(
            path.with_name("batch_manifest.json").read_text(encoding="utf-8")
        )
        if manifest["combined_sha256"] != digest(path):
            raise ValueError("Teacher proposal checksum changed")
        frame = read_frame(path)
        # Raw teacher confidence never authorizes training without context review.
        frame["ai_training_candidate"] = "False"
        frames.append(frame)
        sources.append({"sha256": digest(path), "rows": len(frame)})
        teachers.append(manifest["teacher"])
    combined = pd.concat(frames, ignore_index=True).fillna("")
    # First eligible occurrence wins; duplicate copies remain in source batches.
    combined["_priority"] = combined.quality_status.ne("accepted").astype(int)
    combined = (
        combined.sort_values("_priority", kind="stable")
        .drop_duplicates(["target_program", "tweet_id"])
        .drop(columns="_priority")
        .reset_index(drop=True)
    )
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    keys = [(d["target_program"], d["tweet_id"]) for d in decisions]
    if len(set(keys)) != len(keys):
        raise ValueError("Context review contains duplicate decisions")
    combined = apply_ai_reviews(combined, decisions)
    summary = json.loads(original_summary.read_text(encoding="utf-8"))
    if summary["lineage"]["dataset_sha256"] != digest(original_dataset):
        raise ValueError("Original benchmark dataset changed")
    original = read_frame(original_dataset)
    development, test = (
        summary["split"]["development_indices"],
        summary["split"]["test_indices"],
    )
    if set(development) & set(test) or sorted(development + test) != list(
        range(len(original))
    ):
        raise ValueError("Original benchmark split is invalid")
    old_manifest = json.loads(
        original_labels.with_name("batch_manifest.json").read_text(encoding="utf-8")
    )
    if old_manifest["combined_sha256"] != digest(original_labels):
        raise ValueError("Original contextual labels changed")
    old_labels = read_frame(original_labels).set_index(["target_program", "tweet_id"])
    old_dev = original.iloc[development]
    selected = old_labels.loc[
        list(zip(old_dev.target_program, old_dev.tweet_id, strict=True))
    ].reset_index()
    combined = pd.concat([selected, combined], ignore_index=True).fillna("")
    if combined.duplicated(["target_program", "tweet_id"]).any():
        raise ValueError("New candidates duplicate original development records")
    combined, removed = protect_benchmark(combined, original.iloc[test])
    # A text-only classifier cannot learn opposing target labels for one text.
    candidates_mask = combined.ai_training_candidate.str.lower().eq("true")
    text_keys = combined.model_text.map(text_fingerprint)
    conflicts = (
        combined.loc[candidates_mask]
        .groupby(text_keys[candidates_mask])
        .sentiment_label.nunique()
    )
    conflicting_texts = set(conflicts.index[conflicts > 1])
    conflict_mask = candidates_mask & text_keys.isin(conflicting_texts)
    combined.loc[conflict_mask, "ai_training_candidate"] = "False"
    combined.loc[conflict_mask, "candidate_exclusion_reason"] = (
        "mixed_target_text_requires_target_conditioned_model"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False, encoding="utf-8", lineterminator="\n")
    candidates = combined[
        combined.ai_training_candidate.str.lower().eq("true")
        & combined.quality_status.eq("accepted")
        & combined.relevance_review.eq("relevant")
    ]
    provenance = {
        "teachers": teachers,
        "proposal_sources": sources,
        "context_decisions_sha256": digest(decisions_path),
        "context_decisions": len(decisions),
        "reviewer_type": "ai_contextual_review",
        "original_dataset_sha256": digest(original_dataset),
        "original_development_rows_reused": len(selected),
        "original_test_rows_protected": len(test),
        "rows_excluded_for_original_benchmark_overlap": removed,
        "unreviewed_teacher_proposals_enter_training": False,
        "mixed_target_text_conflicts_excluded": int(conflict_mask.sum()),
        "human_reviewed": False,
        "deployment_approved": False,
    }
    manifest = {
        "combined_sha256": digest(output),
        "rows": len(combined),
        "annotation_provenance": provenance,
        "training_candidate_rows": len(candidates),
        "candidate_program_counts": candidates.target_program.value_counts().to_dict(),
        "candidate_class_counts": candidates.sentiment_label.value_counts().to_dict(),
        "candidate_program_classes": candidates.groupby(
            ["target_program", "sentiment_label"]
        )
        .size()
        .unstack(fill_value=0)
        .to_dict(orient="index"),
    }
    output.with_name("batch_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
