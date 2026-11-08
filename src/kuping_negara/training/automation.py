"""Evaluate an unregistered training batch and stage only an eligible candidate."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

MIN_HOLDOUT_MACRO_F1 = 0.75


def evaluate(summary: dict) -> dict:
    if summary["registry"] is not None or summary["deployment_approved"] is not False:
        raise ValueError(
            "Expected an unregistered candidate without deployment approval"
        )
    split = summary["split"]
    if split["group_overlap"] != 0 or split["test_rows"] <= 0:
        raise ValueError("Holdout is empty or has group leakage")
    score = summary["test_metrics"]["test_macro_f1"]
    if (
        type(score) not in (int, float)
        or not math.isfinite(score)
        or not 0 <= score <= 1
    ):
        raise ValueError("Invalid holdout Macro-F1")
    return {
        "metric": "test_macro_f1",
        "minimum": MIN_HOLDOUT_MACRO_F1,
        "observed": score,
        "passed": score >= MIN_HOLDOUT_MACRO_F1,
        "test_rows": split["test_rows"],
        "source_commit": summary["source_commit"],
        "dataset_sha256": summary["lineage"]["dataset_sha256"],
        "run_id": summary["best_run_id"],
    }


def stage(summary: dict, evaluation: dict, name: str, tracking_uri: str) -> dict:
    import mlflow
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException

    if evaluation != evaluate(summary) or not evaluation["passed"]:
        raise ValueError("Cannot stage a candidate without a passing quality gate")
    if not name.endswith("-pilot"):
        raise ValueError("Use a dedicated pilot registry")
    run_id = evaluation["run_id"]
    winner = next(row for row in summary["runs"] if row["run_id"] == run_id)
    model_uri = winner["model_uri"]
    if not model_uri.startswith("models:/m-") or "/" in model_uri[len("models:/") :]:
        raise ValueError("Expected a tracked MLflow model ID")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    client = MlflowClient()
    run = client.get_run(run_id)
    if (
        run.info.status != "FINISHED"
        or run.data.metrics.get("test_macro_f1") != evaluation["observed"]
        or run.data.tags.get("source_commit") != evaluation["source_commit"]
        or run.data.params.get("dataset_sha256") != evaluation["dataset_sha256"]
        or client.get_logged_model(model_uri.removeprefix("models:/")).source_run_id
        != run_id
    ):
        raise ValueError(
            "Tracked model, metrics, or lineage differ from the evaluation"
        )

    try:
        matches = [
            version
            for version in client.search_model_versions(f"name = '{name}'")
            if version.run_id == run_id
        ]
    except MlflowException as error:
        if error.error_code != "RESOURCE_DOES_NOT_EXIST":
            raise
        matches = []
    if len(matches) > 1 or (matches and matches[0].source != model_uri):
        raise ValueError("Ambiguous existing model version for this run")
    version = matches[0] if matches else mlflow.register_model(model_uri, name)
    if version.current_stage not in {"None", "Staging"}:
        raise ValueError("Refusing to change an already promoted or archived candidate")
    tags = {
        "deployment_approved": "false",
        "label_status": summary["lineage"]["label_status"],
        "source_commit": evaluation["source_commit"],
        "dataset_sha256": evaluation["dataset_sha256"],
        "test_macro_f1": str(evaluation["observed"]),
        "minimum_test_macro_f1": str(evaluation["minimum"]),
        "quality_gate": "passed",
    }
    for key, value in tags.items():
        client.set_model_version_tag(name, version.version, key, value)
    if version.current_stage == "None":
        client.transition_model_version_stage(name, version.version, "Staging")
    if client.get_model_version(name, version.version).current_stage != "Staging":
        raise ValueError("Registry did not confirm Staging")
    return {"name": name, "version": version.version, "stage": "Staging", **evaluation}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["evaluate", "stage"])
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument(
        "--registry", default="kuping-negara-sentiment-automation-pilot"
    )
    parser.add_argument("--tracking-uri", default=os.environ.get("MLFLOW_TRACKING_URI"))
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    if args.action == "evaluate":
        result = evaluate(summary)
        args.evaluation.write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit("Holdout Macro-F1 below threshold; Staging blocked")
    else:
        if not args.tracking_uri:
            parser.error("Staging requires an explicit tracking URI")
        evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
        result = stage(summary, evaluation, args.registry, args.tracking_uri)
        receipt = args.evaluation.with_name("registry_receipt.json")
        receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
