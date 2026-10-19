"""Commands for dataset preparation and three-run MLflow experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kuping_negara.paths import find_repository_root
from kuping_negara.training.data import prepare_dataset


def main() -> None:
    root = find_repository_root([Path.cwd(), Path(__file__)])
    parser = argparse.ArgumentParser(
        description="Versioned sentiment training with MLflow"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser(
        "prepare", help="Join reviewed labels to an LK-05 raw snapshot"
    )
    prepare.add_argument("--labels", type=Path, required=True)
    prepare.add_argument("--raw", type=Path, default=root / "data/raw/lk05_dataset.csv")
    prepare.add_argument("--raw-revision", default="lk05-data-v2")
    prepare.add_argument(
        "--output", type=Path, default=root / "data/training/sentiment_dataset.csv"
    )
    prepare.add_argument("--allow-provisional", action="store_true")
    train = commands.add_parser(
        "run", help="Run CV trials, evaluate once, register experimental winner"
    )
    train.add_argument(
        "--dataset", type=Path, default=root / "data/training/sentiment_dataset.csv"
    )
    train.add_argument(
        "--config", type=Path, default=root / "configs/training/sentiment.json"
    )
    train.add_argument("--output", type=Path, default=root / "reports/training/initial")
    train.add_argument(
        "--tracking-uri", help="Defaults to the repository's local SQLite store"
    )
    train.add_argument("--allow-provisional", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_dataset(
            root,
            args.labels,
            args.raw,
            args.output,
            args.raw_revision,
            args.allow_provisional,
        )
    else:
        from kuping_negara.training.experiments import run_experiments

        result = run_experiments(
            root=root,
            dataset=args.dataset,
            config=args.config,
            output=args.output,
            allow_provisional=args.allow_provisional,
            tracking_uri=args.tracking_uri,
        )
        result = {
            key: result[key]
            for key in (
                "best_run_id",
                "best_parameters",
                "test_metrics",
                "registry",
                "deployment_approved",
            )
        }
    print(json.dumps(result, indent=2))
