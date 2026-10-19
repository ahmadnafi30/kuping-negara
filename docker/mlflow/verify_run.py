"""Reload a completed expanded experiment and verify its data/model contract."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd

from kuping_negara.labeling.proposals import protect_benchmark
from kuping_negara.training.data import LABELS, digest, leakage_groups, read_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tracking-uri", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    summary = json.loads(
        (args.output / "experiment_summary.json").read_text(encoding="utf-8")
    )
    frame = read_frame(root / "data/training/sentiment_expanded_20261019.csv")
    assert len(frame) == 396
    assert (
        digest(root / "data/training/sentiment_expanded_20261019.csv")
        == summary["lineage"]["dataset_sha256"]
    )
    assert not frame.human_reviewed.str.lower().eq("true").any()
    assert not frame.approved_for_training.str.lower().eq("true").any()
    original = read_frame(root / "data/training/sentiment_dataset.csv")
    initial = json.loads(
        (root / "reports/training/initial/experiment_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        digest(root / "data/training/sentiment_dataset.csv")
        == initial["lineage"]["dataset_sha256"]
    )
    protected = original.iloc[initial["split"]["test_indices"]]
    _, overlap = protect_benchmark(frame, protected)
    assert overlap == 0
    groups = np.asarray(leakage_groups(frame))
    split = summary["split"]
    assert not set(groups[split["development_indices"]]) & set(
        groups[split["test_indices"]]
    )
    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_registry_uri(args.tracking_uri)
    client = mlflow.MlflowClient()
    runs = [client.get_run(row["run_id"]) for row in summary["runs"]]
    assert len(runs) == 3 and all(run.info.status == "FINISHED" for run in runs)
    assert sum("test_macro_f1" in run.data.metrics for run in runs) == 1
    assert all(
        run.data.tags["source_commit"] == summary["source_commit"] for run in runs
    )
    assert all(run.data.tags["source_dirty"] == "false" for run in runs)
    registry = summary["registry"]
    registered = client.get_model_version(registry["name"], registry["version"])
    assert registered.run_id == summary["best_run_id"]
    assert registered.tags["deployment_approved"] == "false"
    model = mlflow.sklearn.load_model(f"models:/{registered.name}/{registered.version}")
    transformers = model.named_steps["features"].named_transformers_
    assert {"text", "characters"}.issubset(transformers)
    assert "program" not in transformers
    sample = pd.DataFrame(
        {
            "model_text": [
                "program membantu warga",
                "tidak setuju layanan buruk",
                "pendaftaran dibuka hari ini",
            ],
            "target_program": ["mbg", "ckg", "sekolah_rakyat"],
        }
    )
    predictions = model.predict(sample)
    assert len(predictions) == 3 and set(predictions).issubset(LABELS)
    test = np.asarray(split["test_indices"])
    actual_accuracy = float(
        np.mean(
            model.predict(frame.iloc[test][["model_text", "target_program"]])
            == frame.iloc[test].sentiment_label
        )
    )
    assert abs(actual_accuracy - summary["test_metrics"]["test_accuracy"]) < 1e-12
    evidence = {
        "platform": platform.system(),
        "python": platform.python_version(),
        "container_runtime": Path("/.dockerenv").exists(),
        "tracking_transport": "http"
        if args.tracking_uri.startswith("http")
        else "local_sqlite",
        "run_ids": [run.info.run_id for run in runs],
        "all_three_runs_finished": True,
        "model_reloaded_from_registry": True,
        "predictions_match_reported_test_accuracy": True,
        "source_commit": summary["source_commit"],
        "source_dirty_at_training": False,
        "original_test_rows_protected": len(protected),
        "original_test_group_overlap": overlap,
        "new_development_test_group_overlap": 0,
        "human_reviewed": False,
        "deployment_approved": False,
        "model_features": ["text", "characters"],
        "program_one_hot": False,
        "dataset_sha256": summary["lineage"]["dataset_sha256"],
    }
    (args.output / "runtime_verification.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
