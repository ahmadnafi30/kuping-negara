"""Synthetic, versioned training data for unit and MLflow integration checks."""

import json
import subprocess

import pandas as pd
import yaml

from kuping_negara.training.data import COLUMNS, digest


def sample_frame(count=10):
    return pd.DataFrame(
        [
            {
                "tweet_id": f"{k}-{i}",
                "conversation_id": f"{k}-{i}",
                "target_program": "mbg",
                "model_text": f"{word} program sekolah contoh {k} nomor {i}",
                "split_group_id": f"{k}-{i}",
                "sentiment_label": label,
                "annotation_source": "ai",
                "human_reviewed": "False",
                "approved_for_training": "False",
                "ai_training_candidate": "True",
                "quality_status": "accepted",
                "relevance_review": "relevant",
            }
            for k, (label, word) in enumerate(
                [("negative", "buruk"), ("neutral", "berita"), ("positive", "bagus")]
            )
            for i in range(count)
        ],
        columns=COLUMNS,
    )


def create_training_repository(tmp_path):
    root = tmp_path
    raw = root / "data/raw/lk05_dataset.csv"
    raw.parent.mkdir(parents=True)
    frame = sample_frame()
    records = pd.DataFrame(
        {
            "target_program": frame.target_program,
            "id_str": frame.tweet_id,
            "conversation_id_str": frame.conversation_id,
            "full_text": frame.model_text,
        }
    )
    records.to_csv(raw, index=False)
    pointer = {"outs": [{"md5": digest(raw, "md5"), "path": raw.name}]}
    raw.with_suffix(".csv.dvc").write_text(yaml.safe_dump(pointer))
    for args in (
        ["init", "-q"],
        ["add", "data/raw/lk05_dataset.csv.dvc"],
        [
            "-c",
            "user.name=Tests",
            "-c",
            "user.email=tests@example.invalid",
            "commit",
            "-qm",
            "data snapshot",
        ],
        ["tag", "lk05-data-v2"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True)
    labels = root / "data/labeled/batch/all.csv"
    labels.parent.mkdir(parents=True)
    frame.to_csv(labels, index=False)
    labels.with_name("batch_manifest.json").write_text(
        json.dumps({"combined_sha256": digest(labels)})
    )
    return root, raw, labels
