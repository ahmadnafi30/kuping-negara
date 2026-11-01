"""LK-07 lifecycle simulation on versioned LK-06 data; never deployment approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from time import perf_counter

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


def annotate():
    """Enrich the existing educational registry without creating new versions."""
    record = json.loads((OUTPUT / "workflow.json").read_text(encoding="utf-8"))
    if record["model_name"] != NAME or record["simulation_only"] is not True:
        raise ValueError("Unexpected registry workflow")
    client = mlflow.MlflowClient()
    description = (
        "Klasifikasi sentimen teks Indonesia untuk MBG, CKG, Kopdes Merah Putih "
        "dan Sekolah Rakyat. Logistic Regression balanced, max_iter=2000, seed=42; "
        "TF-IDF kata 1-2 gram dan karakter 3-5 gram. "
        "Dataset DVC 396 contoh berlabel AI: 316 development, 80 test. "
        "Pemilihan versi memakai 3-fold grouped CV Macro-F1 pada development; "
        "test LK-6 tidak digunakan ulang untuk memilih versi. "
        "Versi 1 C=10 (CV Macro-F1=0.790114) dipilih dibanding versi 2 C=5 "
        "(0.783011). Alur simulasi None -> Staging -> Production; alias champion. "
        "Label belum divalidasi manusia, prediksi contoh masih dapat keliru. "
        "Production hanya simulasi LK-7, bukan persetujuan deployment. "
        "Referensi dan checksum: registry/active_model.yaml, dilacak DVC. "
        "Artefak disimpan pada volume MLflow, terpisah dari metadata DVC."
    )
    client.update_registered_model(NAME, description=description)
    audit = {"model_name": NAME, "versions": []}
    for version in record["versions"]:
        number = version["version"]
        current = client.get_model_version(NAME, number)
        if current.run_id != version["run_id"]:
            raise ValueError("Version source differs from workflow")
        selected = number == record["selected_version"]
        detail = (
            f"Versi {number}: C={version['C']}; "
            f"development CV Macro-F1={version['cv_macro_f1']:.6f}. "
            f"Source run: {version['run_id']}. "
            + (
                "Artefak terbaik LK-6 digunakan kembali; dipilih karena skor CV "
                "tertinggi. None -> Staging -> Production; alias champion. "
                if selected
                else "Pembaruan parameter dari C=10 ke C=5; dilatih pada development "
                "yang sama. Skor CV lebih rendah, sehingga tidak dipromosikan. "
            )
            + f"Dataset SHA-256: {record['lineage']['dataset_sha256']}. "
            f"Raw DVC revision: {record['lineage']['raw_revision']}. "
            "Representasi TF-IDF kata 1-2 dan karakter 3-5 gram; class_weight=balanced; "
            "max_iter=2000; random_seed=42. Label provisional_ai; "
            "simulation_only=true; deployment_approved=false. "
            "Kesiapan pemanggilan tidak menjamin ketepatan sentimen."
        )
        client.update_model_version(NAME, number, description=detail)
        for key, value in {
            "cv_macro_f1": str(version["cv_macro_f1"]),
            "selection_metric": "development_cv_macro_f1",
            "algorithm": "LogisticRegression",
            "feature_mode": "word_char",
            "class_weight": "balanced",
            "max_iter": "2000",
            "random_seed": "42",
            "development_rows": "316",
            "test_rows_not_reused": "80",
            "raw_dvc_revision": record["lineage"]["raw_revision"],
            "selected_for_simulation": str(selected).lower(),
        }.items():
            client.set_model_version_tag(NAME, number, key, value)
        saved = client.get_model_version(NAME, number)
        if saved.description != detail:
            raise ValueError("Version description was not persisted")
        audit["versions"].append(
            {
                "version": number,
                "description": saved.description,
                "stage": saved.current_stage,
                "tags": saved.tags,
            }
        )
    saved_model = client.get_registered_model(NAME)
    if saved_model.description != description:
        raise ValueError("Registry description was not persisted")
    audit["description"] = saved_model.description
    (OUTPUT / "metadata_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


def predict_inputs(model, inputs):
    """Validate the public model contract before requesting predictions."""
    if not isinstance(inputs, pd.DataFrame) or inputs.empty:
        raise ValueError("Provide at least one input row")
    if not set(FEATURES).issubset(inputs.columns):
        raise ValueError(f"Input requires columns {FEATURES}")
    for column in FEATURES:
        if (
            not inputs[column]
            .map(lambda value: isinstance(value, str) and bool(value.strip()))
            .all()
        ):
            raise ValueError(f"Column {column} must contain non-empty strings")
    predictions = model.predict(inputs[FEATURES]).tolist()
    if len(predictions) != len(inputs) or not set(predictions).issubset(
        {"negative", "neutral", "positive"}
    ):
        raise ValueError("Invalid inference output")
    return predictions


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
    started = perf_counter()
    model = mlflow.pyfunc.load_model(reference["model_uri"])
    load_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    predicted = predict_inputs(model, SAMPLES)
    first_prediction_ms = (perf_counter() - started) * 1000
    durations = []
    for _ in range(30):
        started = perf_counter()
        if predict_inputs(model, SAMPLES) != predicted:
            raise ValueError("Repeated predictions are inconsistent")
        durations.append((perf_counter() - started) * 1000)
    rejected = 0
    for invalid in [
        pd.DataFrame(),
        SAMPLES.drop(columns=["model_text"]),
        SAMPLES.assign(model_text=""),
        SAMPLES.assign(model_text=None),
    ]:
        try:
            predict_inputs(model, invalid)
        except ValueError:
            rejected += 1
    if rejected != 4:
        raise ValueError("Invalid inputs were not rejected")
    return {
        "model_uri": reference["model_uri"],
        "resolved_version": reference["model_version"],
        "production_verified": True,
        "model_load_ms": load_ms,
        "first_batch_prediction_ms": first_prediction_ms,
        "warm_batch_rows": len(SAMPLES),
        "warm_repetitions": len(durations),
        "warm_batch_median_ms": float(np.median(durations)),
        "warm_batch_p95_ms": float(np.percentile(durations, 95)),
        "warm_batch_max_ms": max(durations),
        "invalid_input_cases_rejected": rejected,
        "timing_scope": "local container; 3 synthetic rows; no concurrency or network SLA",
        "benchmark_source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "artifact_checksum_verified": True,
        "container_runtime": Path("/.dockerenv").exists(),
        "synthetic_inputs": SAMPLES.to_dict(orient="records"),
        "predictions": predicted,
        "simulation_only": True,
        "deployment_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "promote", "infer", "annotate"])
    args = parser.parse_args()
    uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    if args.action == "register":
        register()
    elif args.action == "promote":
        promote()
    elif args.action == "annotate":
        annotate()
    else:
        reference = yaml.safe_load(
            Path("registry/active_model.yaml").read_text(encoding="utf-8")
        )
        if reference["model_name"] != NAME or reference["simulation_only"] is not True:
            raise ValueError("Unexpected model reference")
        result = verify(reference, mlflow.MlflowClient())
        (OUTPUT / "inference_benchmark.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
