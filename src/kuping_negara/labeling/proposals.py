"""Generate auditable AI proposals without granting human approval.

The optional teacher runs locally. Its confidence is uncalibrated and does not
establish target-specific sentiment correctness or replace annotation review.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pandas as pd

from kuping_negara.training.data import LABELS, digest, leakage_groups, read_frame

MODEL_ID = "taufiqdp/indonesian-sentiment"
MODEL_REVISION = "7b102f732bbce270807db57cde99c8c202bb2ad7"
MODEL_LABELS = {0: "negative", 1: "neutral", 2: "positive"}


def select_proposal(probabilities, *, eligible: bool, truncated: bool) -> dict:
    """Apply fixed conservative gates; never interpret scores as correctness."""
    if len(probabilities) != 3 or any(not 0 <= p <= 1 for p in probabilities):
        raise ValueError("Expected three finite probabilities")
    if abs(sum(probabilities) - 1) > 1e-4:
        raise ValueError("Probabilities must sum to one")
    order = sorted(range(3), key=lambda i: probabilities[i], reverse=True)
    confidence = probabilities[order[0]]
    margin = confidence - probabilities[order[1]]
    reasons = []
    if not eligible:
        reasons.append("preprocessing_requires_review")
    if truncated:
        reasons.append("teacher_input_truncated")
    if confidence < 0.8 or margin < 0.25:
        reasons.append("uncertain_teacher_prediction")
    return {
        "sentiment_label": MODEL_LABELS[order[0]] if not reasons else "uncertain",
        "teacher_proposed_label": MODEL_LABELS[order[0]],
        "teacher_score": confidence,
        "teacher_margin": margin,
        "teacher_confidence_candidate": not reasons,
        "candidate_exclusion_reason": ";".join(reasons),
        **{
            f"teacher_probability_{MODEL_LABELS[i]}": p
            for i, p in enumerate(probabilities)
        },
    }


def protect_benchmark(candidates: pd.DataFrame, protected: pd.DataFrame):
    """Exclude every connected post/conversation/text group from a known test set."""
    combined = pd.concat([candidates, protected], ignore_index=True).fillna("")
    groups = leakage_groups(combined)
    protected_groups = set(groups[len(candidates) :])
    keep = [group not in protected_groups for group in groups[: len(candidates)]]
    return candidates.loc[keep].copy(), len(candidates) - sum(keep)


def apply_ai_reviews(frame: pd.DataFrame, decisions: list[dict]) -> pd.DataFrame:
    """Apply explicit contextual AI decisions, retaining all human approval flags."""
    result = frame.copy()
    for decision in decisions:
        selected = result.target_program.eq(
            decision["target_program"]
        ) & result.tweet_id.eq(decision["tweet_id"])
        if selected.sum() != 1:
            raise ValueError("Review must identify exactly one source record")
        index = result.index[selected][0]
        row = result.loc[index]
        if (
            sha256(row.model_text.encode("utf-8")).hexdigest()
            != decision["text_sha256"]
        ):
            raise ValueError("Review text changed")
        label, relevance = decision["sentiment_label"], decision["relevance_review"]
        if label not in (*LABELS, "uncertain") or relevance not in {
            "relevant",
            "irrelevant",
            "uncertain",
        }:
            raise ValueError("Invalid contextual decision")
        if not decision["reason"].strip():
            raise ValueError("Review requires a concrete reason")
        eligible = (
            row.quality_status == "accepted"
            and str(row.is_eligible_for_labeling).lower() == "true"
        )
        candidate = eligible and relevance == "relevant" and label in LABELS
        result.loc[
            index, ["sentiment_label", "relevance_review", "ai_training_candidate"]
        ] = [label, relevance, str(candidate)]
        result.loc[index, "annotation_method"] = "local_teacher_with_ai_context_review"
        result.loc[index, "annotation_status"] = "ai_context_reviewed"
        result.loc[index, "review_reason"] = decision["reason"]
        result.loc[index, "label_reason"] = decision["reason"]
        result.loc[index, "context_reviewer"] = "codex_ai"
        result.loc[index, "guideline_version"] = "0.1.0"
        result.loc[index, "context_reviewed_at"] = datetime.now(UTC).isoformat()
        if decision.get("campaign_group_id"):
            result.loc[index, "campaign_group_id"] = decision["campaign_group_id"]
        result.loc[index, "candidate_exclusion_reason"] = (
            "" if candidate else "context_review_or_preprocessing_gate"
        )
        result.loc[index, ["human_reviewed", "approved_for_training"]] = "False"
    return result


def annotate_processed(root: Path, inputs: list[Path], model_path: Path, output: Path):
    if not output.resolve().is_relative_to(root.resolve() / "data/labeled"):
        raise ValueError("Annotation output must stay inside data/labeled")
    if output.exists():
        raise ValueError("Annotation batch exists; select a new output directory")
    # Optional dependencies are deliberately imported only for actual inference.
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    config = json.loads((model_path / "config.json").read_text(encoding="utf-8"))
    if config["id2label"] != {"0": "negatif", "1": "netral", "2": "positif"}:
        raise ValueError("Teacher label mapping changed")
    if model_path.name != MODEL_REVISION:
        raise ValueError("Teacher must use the pinned immutable model revision")
    tokenizer = AutoTokenizer.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False, use_safetensors=True
    )
    torch.set_num_threads(4)
    model.eval()
    sources, records = [], []
    stamp = datetime.now(UTC).isoformat()
    for path in inputs:
        path = path.resolve()
        if not path.is_relative_to(root.resolve() / "data/processed"):
            raise ValueError("Expected a completed preprocessing CSV")
        report_path = path.with_name("quality_report.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("preprocessing_version") != 3 or not report.get(
            "collection_validation"
        ):
            raise ValueError("Annotation requires validated current preprocessing")
        if report["output_sha256"] != digest(path):
            raise ValueError("Processed source checksum changed")
        frame = read_frame(path)
        sources.append(
            {"path": path.relative_to(root).as_posix(), "sha256": digest(path)}
        )
        for start in range(0, len(frame), 8):
            batch = frame.iloc[start : start + 8]
            texts = batch.model_text.tolist()
            lengths = [len(tokenizer.encode(text, truncation=False)) for text in texts]
            encoded = tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            with torch.inference_mode():
                probabilities = torch.softmax(model(**encoded).logits, dim=-1).tolist()
            for offset, (row, probs, length) in enumerate(
                zip(batch.to_dict("records"), probabilities, lengths, strict=True)
            ):
                eligible = (
                    row["quality_status"] == "accepted"
                    and row["is_eligible_for_labeling"].lower() == "true"
                )
                proposal = select_proposal(
                    probs, eligible=eligible, truncated=length > 256
                )
                records.append(
                    {
                        **row,
                        **proposal,
                        "ai_training_candidate": False,
                        "relevance_review": "relevant"
                        if row["is_relevant"].lower() == "true"
                        else "uncertain",
                        "language_review": "indonesian"
                        if row["is_indonesian"].lower() == "true"
                        else "uncertain",
                        "source_csv": sources[-1]["path"],
                        "source_csv_sha256": sources[-1]["sha256"],
                        "source_row_index": start + offset,
                        "annotation_source": "ai",
                        "annotator_id": MODEL_ID,
                        "annotation_method": "local_transformer_pseudo_label",
                        "annotation_status": "ai_model_proposed",
                        "human_reviewed": False,
                        "approved_for_training": False,
                        "annotated_at": stamp,
                        "teacher_revision": MODEL_REVISION,
                        "review_reason": "Automated relevance/language gates; no human review",
                        "label_reason": "Local teacher proposal; uncalibrated confidence, target sentiment unverified",
                    }
                )
    combined = pd.DataFrame(records)
    if combined.empty:
        raise ValueError("No completed records to annotate")
    combined = combined.drop_duplicates(["target_program", "tweet_id"], keep="first")
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False, encoding="utf-8", lineterminator="\n")
    manifest = {
        "combined_sha256": digest(output),
        "rows": len(combined),
        "sources": sources,
        "teacher": {
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "weights_sha256": digest(model_path / "model.safetensors"),
            "model_card": f"https://huggingface.co/{MODEL_ID}/tree/{MODEL_REVISION}",
            "confidence_min": 0.8,
            "margin_min": 0.25,
            "max_tokens": 256,
            "score_is_calibrated": False,
            "inference": "local_cpu",
        },
        "proposed_label_counts": combined.sentiment_label.value_counts().to_dict(),
        "human_reviewed": False,
        "deployment_approved": False,
    }
    output.with_name("batch_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, action="append", required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            annotate_processed(
                Path.cwd().resolve(), args.processed, args.model_path, args.output
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
