"""Actual MLflow logging, Registry and model reload on synthetic data."""

import json

import pandas as pd
import pytest

from kuping_negara.training.data import digest, prepare_dataset
from kuping_negara.training.evaluation import FEATURES


def test_three_runs_register_cv_winner_and_reload(training_dataset):
    import yaml

    mlflow = pytest.importorskip("mlflow")
    pytest.importorskip("matplotlib")
    from kuping_negara.training.experiments import run_experiments

    root, raw, labels = training_dataset
    dataset = root / "data/training/sentiment.csv"
    prepare_dataset(root, labels, raw, dataset, "lk05-data-v2", True)
    dataset.with_suffix(".csv.dvc").write_text(
        yaml.safe_dump({"outs": [{"md5": digest(dataset, "md5")}]})
    )
    config = root / "config.json"
    config.write_text(
        json.dumps(
            {
                "experiment_name": "synthetic-integration",
                "random_seed": 42,
                "trials": [
                    {"name": str(c), "C": c, "ngram_max": 1} for c in (0.1, 1, 10)
                ],
            }
        )
    )
    summary = run_experiments(
        root=root,
        dataset=dataset,
        config=config,
        output=root / "reports/training/test",
        allow_provisional=True,
    )
    assert len(summary["runs"]) == 3
    client = mlflow.MlflowClient()
    runs = [client.get_run(row["run_id"]) for row in summary["runs"]]
    assert all(run.info.status == "FINISHED" for run in runs)
    assert len({run.data.params["C"] for run in runs}) == 3
    assert all("cv_macro_f1" in run.data.metrics for run in runs)
    assert sum("test_macro_f1" in run.data.metrics for run in runs) == 1
    assert summary["split"]["group_overlap"] == 0
    assert summary["registry"]["name"].endswith("pilot")
    assert summary["deployment_approved"] is False
    registered = client.get_model_version(
        summary["registry"]["name"], summary["registry"]["version"]
    )
    assert registered.run_id == summary["best_run_id"]
    assert registered.tags["deployment_approved"] == "false"
    model = mlflow.sklearn.load_model(f"models:/{registered.name}/{registered.version}")
    sample = pd.DataFrame(
        {"model_text": ["bagus program membantu"], "target_program": ["mbg"]}
    )
    assert model.predict(sample[FEATURES]).shape == (1,)
