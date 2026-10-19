"""Exercise HTTP tracking, artifact storage and Registry on synthetic CI data."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import mlflow
import mlflow.sklearn
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from kuping_negara.training.data import digest, prepare_dataset
from kuping_negara.training.experiments import run_experiments
from tests.fixtures.training import create_training_repository


def main():
    with TemporaryDirectory(prefix="mlflow-smoke-") as directory:
        root, raw, labels = create_training_repository(Path(directory))
        dataset = root / "data/training/synthetic.csv"
        prepare_dataset(root, labels, raw, dataset, "lk05-data-v2", True)
        dataset.with_suffix(".csv.dvc").write_text(
            yaml.safe_dump({"outs": [{"md5": digest(dataset, "md5")}]}),
            encoding="utf-8",
        )
        config = root / "config.json"
        config.write_text(
            json.dumps(
                {
                    "experiment_name": "container-synthetic-smoke",
                    "registered_model_name": "container-synthetic-pilot",
                    "random_seed": 42,
                    "trials": [
                        {
                            "name": str(c),
                            "C": c,
                            "ngram_max": 2,
                            "feature_mode": "word_char",
                        }
                        for c in (0.5, 2, 10)
                    ],
                }
            ),
            encoding="utf-8",
        )
        summary = run_experiments(
            root=root,
            dataset=dataset,
            config=config,
            output=root / "reports/training/smoke",
            allow_provisional=True,
            tracking_uri=os.environ["MLFLOW_TRACKING_URI"],
        )
        client = mlflow.MlflowClient()
        runs = [client.get_run(row["run_id"]) for row in summary["runs"]]
        assert len(runs) == 3
        assert all(run.info.status == "FINISHED" for run in runs)
        assert all(
            run.info.artifact_uri.startswith("mlflow-artifacts:/") for run in runs
        )
        assert len({run.data.params["C"] for run in runs}) == 3
        assert sum("test_macro_f1" in run.data.metrics for run in runs) == 1
        assert summary["split"]["group_overlap"] == 0
        registered = client.get_model_version_by_alias(
            summary["registry"]["name"], "experimental"
        )
        assert registered.run_id == summary["best_run_id"]
        assert registered.tags["deployment_approved"] == "false"
        model = mlflow.sklearn.load_model(f"models:/{registered.name}@experimental")
        sample = pd.DataFrame(
            {"model_text": ["bagus program membantu"], "target_program": ["mbg"]}
        )
        assert model.predict(sample).shape == (1,)
        transformers = model.named_steps["features"].named_transformers_
        assert {"text", "characters"}.issubset(transformers)
        assert "program" not in transformers
        print(
            "HTTP training verified: three finished runs, proxied artifacts and Registry model reload"
        )


if __name__ == "__main__":
    main()
