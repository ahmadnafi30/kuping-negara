"""LK-07 lifecycle simulation on versioned LK-06 data; never deployment approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import numpy as np
import pandas as pd
import yaml
from mlflow.models import infer_signature
from sklearn.base import clone

from kuping_negara.training.data import digest, load_dataset
from kuping_negara.training.evaluation import (
    FEATURES,
    make_pipeline,
    make_splits,
    metrics,
)

NAME = "kuping-negara-sentiment-lk07-simulation"
OUTPUT = Path("reports/registry/lk07")
SAMPLES = pd.DataFrame(
    {
        "model_text": [
            "program membantu warga",
            "layanan buruk dan mengecewakan",
            "pendaftaran program dibuka hari ini",
        ],
        "target_program": ["mbg", "ckg", "sekolah_rakyat"],
    }
)


def artifact_digest(directory: Path) -> str:
    """Hash names and bytes, rejecting symlinks, independently of download paths."""
    result = hashlib.sha256()
    files = sorted(p for p in directory.rglob("*") if p.is_file())
    if not files:
        raise ValueError("Empty model artifact")
    for path in files:
        if path.is_symlink():
            raise ValueError("Symlink in model artifact")
        result.update(path.relative_to(directory).as_posix().encode() + b"\0")
        result.update(bytes.fromhex(digest(path)))
    return result.hexdigest()


def save(record):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "workflow.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def register():
    if (OUTPUT / "workflow.json").exists():
        raise ValueError("Workflow already exists; do not create duplicate versions")
    root = Path.cwd()
    old = json.loads(
        (
            root / "reports/training/expanded_20261019_docker/experiment_summary.json"
        ).read_text(encoding="utf-8")
    )
    frame, lineage = load_dataset(
        root, root / "data/training/sentiment_expanded_20261019.csv", True
    )
    if lineage["dataset_sha256"] != old["lineage"]["dataset_sha256"]:
        raise ValueError("LK-06 dataset changed")
    development, test, folds = make_splits(frame, 42)
    if (
        development.tolist() != old["split"]["development_indices"]
        or test.tolist() != old["split"]["test_indices"]
    ):
        raise ValueError("Protected LK-06 split changed")
    client = mlflow.MlflowClient()
    if client.search_model_versions(f"name='{NAME}'"):
        raise ValueError("Registry name already has versions; preserve its history")
    original = next(row for row in old["runs"] if row["run_id"] == old["best_run_id"])
    version1 = mlflow.register_model(original["model_uri"], NAME)
    if str(version1.version) != "1":
        raise ValueError("Expected new registry version 1")
    parameters = {"C": 5.0, "ngram_max": 2, "feature_mode": "word_char"}
    pipeline = make_pipeline(parameters, 42)
    x, y = frame[FEATURES], frame.sentiment_label
    scores = []
    mlflow.set_experiment("kuping-negara-lk07-registry")
    with mlflow.start_run(
        run_name="lk07-c5-version2",
        tags={
            "simulation_only": "true",
            "deployment_approved": "false",
            "label_status": "provisional_ai",
        },
    ) as run:
        mlflow.log_params(
            {
                **parameters,
                "random_seed": 42,
                "dataset_sha256": lineage["dataset_sha256"],
                "development_rows": len(development),
                "test_reused_for_selection": False,
            }
        )
        for train, validation in folds:
            estimator = clone(pipeline).fit(
                x.iloc[development[train]], y.iloc[development[train]]
            )
            scores.append(
                metrics(
                    y.iloc[development[validation]],
                    estimator.predict(x.iloc[development[validation]]),
                    "cv",
                )["cv_macro_f1"]
            )
        score = float(np.mean(scores))
        mlflow.log_metric("cv_macro_f1", score)
        pipeline.fit(x.iloc[development], y.iloc[development])
        logged = mlflow.sklearn.log_model(
            pipeline,
            name="sentiment_model",
            signature=infer_signature(SAMPLES, pipeline.predict(SAMPLES)),
            input_example=SAMPLES,
        )
        mlflow.log_dict(lineage, "lineage.json")
        version2 = mlflow.register_model(logged.model_uri, NAME)
        new_run = run.info.run_id
    if str(version2.version) != "2":
        raise ValueError("Expected registry version 2")
    versions = [
        {
            "version": "1",
            "C": 10.0,
            "run_id": old["best_run_id"],
            "cv_macro_f1": original["metrics"]["cv_macro_f1"],
        },
        {"version": "2", "C": 5.0, "run_id": new_run, "cv_macro_f1": score},
    ]
    for version in versions:
        for key, value in {
            "simulation_only": "true",
            "deployment_approved": "false",
            "label_status": "provisional_ai",
            "dataset_sha256": lineage["dataset_sha256"],
            "C": str(version["C"]),
        }.items():
            client.set_model_version_tag(NAME, version["version"], key, value)
    winner = max(versions, key=lambda row: row["cv_macro_f1"])
    events = [
        {
            "version": row["version"],
            "stage": client.get_model_version(NAME, row["version"]).current_stage,
        }
        for row in versions
    ]
    client.transition_model_version_stage(NAME, winner["version"], "Staging")
    events.append(
        {
            "version": winner["version"],
            "stage": client.get_model_version(NAME, winner["version"]).current_stage,
        }
    )
    record = {
        "model_name": NAME,
        "versions": versions,
        "selected_version": winner["version"],
        "selection_metric": "development_cv_macro_f1",
        "lineage": lineage,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "test_rows_not_reused": len(test),
        "events": events,
        "simulation_only": True,
        "deployment_approved": False,
    }
    save(record)
    print(json.dumps(record, indent=2))


def promote():
    record = json.loads((OUTPUT / "workflow.json").read_text(encoding="utf-8"))
    if (
        record["model_name"] != NAME
        or record["simulation_only"] is not True
        or record["deployment_approved"] is not False
    ):
        raise ValueError("Only the named educational simulation can be promoted")
    client = mlflow.MlflowClient()
    selected = record["selected_version"]
    model = client.get_model_version(NAME, selected)
    if model.current_stage != "Staging":
        raise ValueError("Model must be in Staging before promotion")
    # Check the pinned artifact before changing the active stage.
    preflight = mlflow.pyfunc.load_model(f"models:/{NAME}/{selected}")
    predictions = preflight.predict(SAMPLES).tolist()
    if len(predictions) != len(SAMPLES) or not set(predictions).issubset(
        {"negative", "neutral", "positive"}
    ):
        raise ValueError("Staging model failed inference preflight")
    client.transition_model_version_stage(
        NAME, selected, "Production", archive_existing_versions=True
    )
    client.set_registered_model_alias(NAME, "champion", selected)
    if client.get_model_version(NAME, selected).current_stage != "Production":
        raise ValueError("Production transition failed")
    record["events"].append({"version": selected, "stage": "Production"})
    directory = Path(
        mlflow.artifacts.download_artifacts(artifact_uri=f"models:/{NAME}/{selected}")
    )
    reference = {
        "model_name": NAME,
        "model_version": selected,
        "stage": "Production",
        "alias": "champion",
        "model_uri": f"models:/{NAME}/Production",
        "pinned_model_uri": f"models:/{NAME}/{selected}",
        "run_id": model.run_id,
        "artifact_sha256": artifact_digest(directory),
        "dataset_sha256": record["lineage"]["dataset_sha256"],
        "raw_dvc_revision": record["lineage"]["raw_revision"],
        "raw_dvc_md5": record["lineage"]["raw_md5"],
        "source_commit": record["source_commit"],
        "simulation_only": True,
        "deployment_approved": False,
    }
    active = Path("registry/active_model.yaml")
    active.parent.mkdir(exist_ok=True)
    active.write_text(yaml.safe_dump(reference, sort_keys=False), encoding="utf-8")
    inference = verify(reference, client)
    (OUTPUT / "inference.json").write_text(
        json.dumps(inference, indent=2) + "\n", encoding="utf-8"
    )
    save(record)
    print(json.dumps(inference, indent=2))


def validate_reference(reference):
    version = str(reference.get("model_version", ""))
    expected = {
        "model_name": NAME,
        "stage": "Production",
        "alias": "champion",
        "model_uri": f"models:/{NAME}/Production",
        "pinned_model_uri": f"models:/{NAME}/{version}",
    }
    if (
        not version.isdecimal()
        or int(version) < 1
        or any(reference.get(key) != value for key, value in expected.items())
        or reference.get("simulation_only") is not True
        or reference.get("deployment_approved") is not False
    ):
        raise ValueError("Unexpected or unsafe model reference")


def verify(reference, client):
    validate_reference(reference)
    latest = client.get_latest_versions(NAME, stages=["Production"])
    if len(latest) != 1 or str(latest[0].version) != str(reference["model_version"]):
        raise ValueError("Production version differs from the published reference")
    directory = Path(
        mlflow.artifacts.download_artifacts(artifact_uri=reference["pinned_model_uri"])
    )
    if artifact_digest(directory) != reference["artifact_sha256"]:
        raise ValueError("Model artifact checksum differs from published metadata")
    model = mlflow.pyfunc.load_model(reference["model_uri"])
    predicted = model.predict(SAMPLES).tolist()
    if len(predicted) != len(SAMPLES) or not set(predicted).issubset(
        {"negative", "neutral", "positive"}
    ):
        raise ValueError("Invalid inference output")
    return {
        "model_uri": reference["model_uri"],
        "resolved_version": reference["model_version"],
        "production_verified": True,
        "artifact_checksum_verified": True,
        "container_runtime": Path("/.dockerenv").exists(),
        "synthetic_inputs": SAMPLES.to_dict(orient="records"),
        "predictions": predicted,
        "simulation_only": True,
        "deployment_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "promote", "infer"])
    args = parser.parse_args()
    uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    if args.action == "register":
        register()
    elif args.action == "promote":
        promote()
    else:
        reference = yaml.safe_load(
            Path("registry/active_model.yaml").read_text(encoding="utf-8")
        )
        if reference["model_name"] != NAME or reference["simulation_only"] is not True:
            raise ValueError("Unexpected model reference")
        print(json.dumps(verify(reference, mlflow.MlflowClient()), indent=2))


if __name__ == "__main__":
    main()
