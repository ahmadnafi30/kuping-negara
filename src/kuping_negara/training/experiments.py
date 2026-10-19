"""Log tuning trials and register the CV winner without tuning on test data."""

from __future__ import annotations

import json
import subprocess
import uuid
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.metrics import ConfusionMatrixDisplay, classification_report

from kuping_negara.training.data import LABELS, digest, leakage_groups, load_dataset
from kuping_negara.training.evaluation import (
    FEATURES,
    make_pipeline,
    make_splits,
    metrics,
)


def tracking_store(root: Path) -> str:
    path = root.resolve() / "mlruns/tracking.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + path.as_posix()


def run_experiments(
    *,
    root: Path,
    dataset: Path,
    config: Path,
    output: Path,
    allow_provisional: bool,
    tracking_uri: str | None = None,
) -> dict:
    if not output.resolve().is_relative_to(root.resolve() / "reports/training"):
        raise ValueError("Experiment reports must stay inside reports/training")
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            "Experiment output already exists; choose a new report directory"
        )
    frame, lineage = load_dataset(root, dataset, allow_provisional)
    settings = json.loads(config.read_text(encoding="utf-8"))
    trials = settings["trials"]
    if (
        len(trials) < 3
        or len(
            {
                (t["C"], t["ngram_max"], t.get("feature_mode", "word_program"))
                for t in trials
            }
        )
        < 3
    ):
        raise ValueError("Configure at least three distinct hyperparameter trials")
    if any(
        not np.isfinite(t["C"]) or t["C"] <= 0 or t["ngram_max"] not in (1, 2)
        for t in trials
    ):
        raise ValueError("C must be positive and ngram_max must be 1 or 2")
    provisional = lineage["label_status"] == "provisional_ai"
    name = (
        "kuping-negara-sentiment-pilot"
        if provisional
        else "kuping-negara-sentiment-candidate"
    )
    name = settings.get("registered_model_name", name)
    if provisional and not name.endswith("-pilot"):
        raise ValueError("Provisional data requires a registry name ending in -pilot")
    development, test, folds = make_splits(frame, settings["random_seed"])
    x = frame[FEATURES]
    y = frame.sentiment_label
    groups = np.asarray(leakage_groups(frame))
    split = {
        "strategy": "5-fold grouped holdout; 3-fold grouped CV on development only",
        "seed": settings["random_seed"],
        "development_rows": len(development),
        "test_rows": len(test),
        "group_overlap": len(set(groups[development]) & set(groups[test])),
        "independent_groups_by_class": frame.assign(group=groups)
        .groupby("sentiment_label")
        .group.nunique()
        .to_dict(),
        "class_counts": {
            "development": y.iloc[development].value_counts().to_dict(),
            "test": y.iloc[test].value_counts().to_dict(),
        },
        "development_indices": development.tolist(),
        "test_indices": test.tolist(),
        "cv_indices_relative_to_development": [
            {"train": a.tolist(), "validation": b.tolist()} for a, b in folds
        ],
    }
    if split["group_overlap"]:
        raise ValueError("A leakage group crossed the holdout boundary")
    # Validate feature modes before creating any experiment runs.
    for trial in trials:
        make_pipeline(trial, settings["random_seed"])
    mlflow.set_tracking_uri(tracking_uri or tracking_store(root))
    mlflow.set_registry_uri(mlflow.get_tracking_uri())
    experiment = mlflow.get_experiment_by_name(settings["experiment_name"])
    if experiment is None:
        # HTTP servers own artifact storage; local file URIs are not portable
        # between trainer and server containers.
        artifact_options = {}
        if urlparse(mlflow.get_tracking_uri()).scheme not in {"http", "https"}:
            artifact_options["artifact_location"] = (
                root.resolve() / "mlruns/artifacts"
            ).as_uri()
        experiment_id = mlflow.create_experiment(
            settings["experiment_name"], **artifact_options
        )
    else:
        experiment_id = experiment.experiment_id
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    source_dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, text=True
        ).strip()
    )
    batch_id = uuid.uuid4().hex[:12]
    results = []
    fitted = {}
    for trial in trials:
        pipeline = make_pipeline(trial, settings["random_seed"])
        scores = []
        with mlflow.start_run(
            experiment_id=experiment_id,
            run_name=trial["name"],
            tags={
                "batch_id": batch_id,
                "label_status": lineage["label_status"],
                "deployment_approved": "false",
                "source_commit": source_commit,
                "source_dirty": str(source_dirty).lower(),
                "evaluation": "grouped_cv_then_single_holdout",
            },
        ) as run:
            for key, value in {
                "feature_mode": trial.get("feature_mode", "word_program"),
                "C": trial["C"],
                "ngram_max": trial["ngram_max"],
                "class_weight": "balanced",
                "max_features": 10000,
                "char_ngram_range": "3-5"
                if "char" in trial.get("feature_mode", "")
                else "none",
                "char_max_features": 20000
                if "char" in trial.get("feature_mode", "")
                else 0,
                "program_feature": trial.get("feature_mode", "word_program")
                != "word_char",
                "random_seed": settings["random_seed"],
                "cv_folds": 3,
                "dataset_sha256": lineage["dataset_sha256"],
                "raw_dvc_revision": lineage["raw_revision"],
                "raw_dvc_md5": lineage["raw_md5"],
                "preprocessing_version": lineage["preprocessing_version"],
            }.items():
                mlflow.log_param(key, value)
            for step, (train, validation) in enumerate(folds):
                estimator = clone(pipeline)
                estimator.fit(x.iloc[development[train]], y.iloc[development[train]])
                values = metrics(
                    y.iloc[development[validation]],
                    estimator.predict(x.iloc[development[validation]]),
                    "cv",
                )
                scores.append(values)
                mlflow.log_metrics(
                    {k.replace("cv_", "fold_"): v for k, v in values.items()}, step=step
                )
            aggregate = {
                key: float(np.mean([s[key] for s in scores])) for key in scores[0]
            }
            aggregate["cv_macro_f1_std"] = float(
                np.std([s["cv_macro_f1"] for s in scores])
            )
            for key, value in aggregate.items():
                mlflow.log_metric(key, value)
            pipeline.fit(x.iloc[development], y.iloc[development])
            # Synthetic input avoids storing examples of real posts in model metadata.
            example = pd.DataFrame(
                {"model_text": ["Program membantu warga"], "target_program": ["mbg"]}
            )
            model = mlflow.sklearn.log_model(
                pipeline,
                name="sentiment_model",
                signature=infer_signature(example, pipeline.predict(example)),
                input_example=example,
                pip_requirements=[
                    f"scikit-learn=={version('scikit-learn')}",
                    f"pandas=={version('pandas')}",
                    f"numpy=={version('numpy')}",
                    f"cloudpickle=={version('cloudpickle')}",
                ],
            )
            mlflow.log_dict(lineage, "lineage.json")
            mlflow.log_dict(split, "split.json")
            mlflow.log_artifact(str(config), "configuration")
            row = {
                "run_id": run.info.run_id,
                "name": trial["name"],
                "parameters": trial,
                "model_uri": model.model_uri,
                "metrics": aggregate,
            }
            results.append(row)
            fitted[run.info.run_id] = pipeline
    best = max(results, key=lambda r: r["metrics"]["cv_macro_f1"])
    estimator = fitted[best["run_id"]]
    predicted = estimator.predict(x.iloc[test])
    test_metrics = metrics(y.iloc[test], predicted, "test")
    dummy = DummyClassifier(strategy="most_frequent").fit(
        x.iloc[development], y.iloc[development]
    )
    dummy_metrics = metrics(y.iloc[test], dummy.predict(x.iloc[test]), "dummy_test")
    output.mkdir(parents=True, exist_ok=True)
    figure, ax = plt.subplots(figsize=(6, 5))
    ConfusionMatrixDisplay.from_predictions(
        y.iloc[test], predicted, labels=LABELS, ax=ax, colorbar=False
    )
    ax.set_title("Pilot AI labels: held-out test (CV winner only)")
    figure.tight_layout()
    matrix_path = output / "confusion_matrix.png"
    figure.savefig(matrix_path, dpi=160)
    plt.close(figure)
    figure, ax = plt.subplots(figsize=(8, 4))
    ax.bar(
        [r["name"] for r in results],
        [r["metrics"]["cv_macro_f1"] for r in results],
        yerr=[r["metrics"]["cv_macro_f1_std"] for r in results],
        capsize=4,
    )
    ax.set(
        ylabel="Grouped CV Macro-F1 (mean +/- std)",
        ylim=(0, 1),
        title="Three parameter trials; provisional AI labels",
    )
    figure.tight_layout()
    comparison_path = output / "comparison.png"
    figure.savefig(comparison_path, dpi=160)
    plt.close(figure)
    with mlflow.start_run(run_id=best["run_id"]):
        mlflow.log_metrics({**test_metrics, **dummy_metrics})
        mlflow.set_tag("selection", "best_cv_macro_f1")
        mlflow.log_dict(
            classification_report(
                y.iloc[test],
                predicted,
                labels=LABELS,
                output_dict=True,
                zero_division=0,
            ),
            "test_classification_report.json",
        )
        mlflow.log_artifact(str(matrix_path))
        mlflow.log_artifact(str(comparison_path))
    registered = mlflow.register_model(best["model_uri"], name)
    client = MlflowClient()
    for key, value in {
        "label_status": lineage["label_status"],
        "deployment_approved": "false",
        "selection_metric": "cv_macro_f1",
        "dataset_sha256": lineage["dataset_sha256"],
    }.items():
        client.set_model_version_tag(name, registered.version, key, value)
    client.set_registered_model_alias(name, "experimental", registered.version)
    slice_metrics = {}
    for program in sorted(frame.target_program.unique()):
        positions = np.flatnonzero(
            frame.iloc[test].target_program.to_numpy() == program
        )
        if len(positions):
            slice_metrics[program] = {
                "rows": len(positions),
                "class_counts": y.iloc[test[positions]].value_counts().to_dict(),
                **metrics(y.iloc[test[positions]], predicted[positions], "test"),
            }
    summary = {
        "experiment_name": settings["experiment_name"],
        "batch_id": batch_id,
        "source_commit": source_commit,
        "source_dirty": source_dirty,
        "config_sha256": digest(config),
        "lineage": lineage,
        "split": split,
        "runs": results,
        "best_run_id": best["run_id"],
        "best_parameters": best["parameters"],
        "selection_metric": "cv_macro_f1",
        "test_metrics": test_metrics,
        "test_program_slices": slice_metrics,
        "dummy_metrics": dummy_metrics,
        "registry": {
            "name": name,
            "version": registered.version,
            "alias": "experimental",
        },
        "deployment_approved": False,
        "limitations": [
            "AI labels are provisional; metrics measure agreement with AI labels, not human ground truth."
            if provisional
            else "Human-approved labels still require independent deployment review.",
            "Grouped holdout is not a future-time benchmark; no temporal generalization claim.",
            "Limited, imbalanced AI-labeled sample; retain grouped-fold uncertainty and class-level recall.",
            "Selection is affected by search coverage and teacher label bias; require independent human and program-slice evaluation.",
        ],
    }
    summary_path = output / "experiment_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with mlflow.start_run(run_id=best["run_id"]):
        mlflow.log_artifact(str(summary_path))
    return summary
