"""Registry references must fail closed before loading model artifacts."""

from pathlib import Path

import pytest

pytest.importorskip("mlflow")
from kuping_negara.training.registry import NAME, artifact_digest, validate_reference


def reference():
    return {
        "model_name": NAME,
        "model_version": "1",
        "stage": "Production",
        "alias": "champion",
        "model_uri": f"models:/{NAME}/Production",
        "pinned_model_uri": f"models:/{NAME}/1",
        "simulation_only": True,
        "deployment_approved": False,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_uri", "models:/other/Production"),
        ("pinned_model_uri", "models:/other/1"),
        ("model_version", "../1"),
        ("stage", "Staging"),
        ("deployment_approved", True),
        ("simulation_only", False),
    ],
)
def test_rejects_changed_reference(field, value):
    data = reference()
    data[field] = value
    with pytest.raises(ValueError):
        validate_reference(data)


def test_accepts_simulation_reference():
    validate_reference(reference())


def test_digest_detects_modified_bytes_and_paths(tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    file = model / "weights"
    file.write_bytes(b"first")
    original = artifact_digest(model)
    file.write_bytes(b"second")
    assert artifact_digest(model) != original
    changed = artifact_digest(model)
    file.rename(model / "renamed")
    assert artifact_digest(model) != changed


def test_rejects_empty_artifacts(tmp_path: Path):
    with pytest.raises(ValueError):
        artifact_digest(tmp_path)
