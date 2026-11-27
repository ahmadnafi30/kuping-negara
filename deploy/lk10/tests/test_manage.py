"""Operational checks for Production selection and actual replica verification."""

import importlib.util
import itertools
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

spec = importlib.util.spec_from_file_location(
    "lk10_manage", Path(__file__).parents[1] / "manage.py"
)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


@pytest.fixture
def exported(tmp_path, monkeypatch):
    artifacts = tmp_path / ".artifacts"
    model = artifacts / "model"
    model.mkdir(parents=True)
    (model / "MLmodel").write_text("flavors: {python_function: {}}\n")
    (model / "weights.bin").write_bytes(b"test-model-weights")
    monkeypatch.setattr(manage, "ARTIFACTS", artifacts)
    monkeypatch.setattr(manage, "MODEL", model)
    monkeypatch.setattr(manage, "PRODUCTION", artifacts / "production.json")
    monkeypatch.setattr(manage, "IMAGE_RECEIPT", artifacts / "image.json")
    monkeypatch.setattr(manage, "EVIDENCE", tmp_path / ".evidence")
    receipt = {
        "stage": "Production",
        "model_name": manage.DEFAULT_NAME,
        "version": "1",
        "pinned_uri": f"models:/{manage.DEFAULT_NAME}/1",
        "artifact_sha256": manage.artifact_digest(model),
    }
    manage.write_json(manage.PRODUCTION, receipt)
    return receipt


def version(stage="Production", status="READY", name=manage.DEFAULT_NAME):
    return SimpleNamespace(
        name=name,
        current_stage=stage,
        status=status,
        version="1",
        run_id="source-run",
        source="models:/m-test",
        tags={"simulation_only": "true"},
    )


@pytest.mark.parametrize(
    "selected",
    [version("Staging"), version(status="FAILED_REGISTRATION"), version(name="other")],
)
def test_rejects_nonproduction_or_unready_model(selected):
    with pytest.raises(manage.CheckError):
        manage.validate_production(selected, manage.DEFAULT_NAME)


def test_production_model_is_accepted():
    manage.validate_production(version(), manage.DEFAULT_NAME)


def test_export_tampering_is_rejected(exported):
    (manage.MODEL / "weights.bin").write_bytes(b"changed")
    with pytest.raises(manage.CheckError, match="changed"):
        manage.validate_export()


def test_artifact_digest_uses_same_order_on_windows_and_linux(tmp_path):
    import hashlib

    (tmp_path / "MLmodel").write_bytes(b"metadata")
    (tmp_path / "conda.yaml").write_bytes(b"environment")
    expected = hashlib.sha256()
    for name in ["conda.yaml", "MLmodel"]:
        expected.update(name.encode() + b"\0")
        expected.update(hashlib.sha256((tmp_path / name).read_bytes()).digest())
    assert manage.artifact_digest(tmp_path) == expected.hexdigest()


def test_pinned_uri_must_match_version(exported):
    manage.write_json(manage.PRODUCTION, {**exported, "version": "2"})
    with pytest.raises(manage.CheckError, match="disagree"):
        manage.validate_export()


def test_native_serving_uses_export_and_mlflow_cli(exported):
    command = manage.serve_command(port=8001)
    assert command[:5] == [sys.executable, "-m", "mlflow", "models", "serve"]
    assert command[command.index("-m", 3) + 1] == str(manage.MODEL)
    assert command[command.index("-p") + 1] == "8001"


def test_build_uses_mlflow_models_build_docker_and_records_model(exported, monkeypatch):
    monkeypatch.setattr(manage.sys, "platform", "linux")
    commands = []

    def fake_run(command, **kwargs):
        commands.append([str(value) for value in command])
        return "sha256:verified-image" if command[0] == "docker" else ""

    monkeypatch.setattr(manage, "docker_ready", lambda: None)
    monkeypatch.setattr(manage, "run", fake_run)
    receipt = manage.build()
    assert commands[0][:5] == [sys.executable, "-m", "mlflow", "models", "build-docker"]
    assert receipt["artifact_sha256"] == exported["artifact_sha256"]
    assert receipt["image_id"] == "sha256:verified-image"


def test_windows_build_corrects_generated_copy_paths(exported, monkeypatch):
    monkeypatch.setattr(manage.sys, "platform", "win32")
    monkeypatch.setattr(manage, "docker_ready", lambda: None)
    commands = []

    def fake_run(command, **kwargs):
        commands.append([str(value) for value in command])
        if "generate-dockerfile" in command:
            context = Path(command[-1])
            (context / "Dockerfile").write_text(
                "FROM python:3.12-slim\n"
                "COPY model_dir\\model /opt/ml/model\n"
                'RUN printf "\\n"\n'
            )
        elif command[:2] == ["docker", "build"]:
            dockerfile = (Path(command[-1]) / "Dockerfile").read_text()
            assert "COPY model_dir/model /opt/ml/model" in dockerfile
            assert 'RUN printf "\\n"' in dockerfile
        return "sha256:verified-image" if command[:3] == ["docker", "image", "inspect"] else ""

    monkeypatch.setattr(manage, "run", fake_run)
    receipt = manage.build()
    assert "generate-dockerfile" in commands[0]
    assert commands[1][:4] == ["docker", "build", "-t", manage.IMAGE]
    assert receipt["build_method"] == "generate-dockerfile+docker-build"
    assert receipt["artifact_sha256"] == exported["artifact_sha256"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"inputs": []},
        {"dataframe_split": {"columns": ["text"], "data": [["hello"]]}},
        {"dataframe_split": {"columns": ["model_text", "target_program"], "data": []}},
        {
            "dataframe_split": {
                "columns": ["model_text", "target_program"],
                "data": [["", "mbg"]],
            }
        },
        {
            "dataframe_split": {
                "columns": ["model_text", "target_program"],
                "data": [[1, "mbg"]],
            }
        },
    ],
)
def test_invalid_serving_inputs_are_rejected(payload):
    with pytest.raises(manage.CheckError):
        manage.validate_payload(payload)


def test_request_file_matches_the_real_model_signature():
    assert manage.validate_payload(manage.read_json(manage.ROOT / "request.json")) == 3


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"predictions": []},
        {"predictions": ["unknown"]},
        {"predictions": [["positive"]]},
        ["positive"],
    ],
)
def test_invalid_prediction_outputs_are_rejected(response):
    with pytest.raises(manage.CheckError):
        manage.validate_prediction(response, 1)


def rows(count=3):
    return [
        {
            "ID": f"container-{index}",
            "Name": f"api-service-{index}",
            "Service": "api-service",
            "State": "running",
            "Health": "healthy",
        }
        for index in range(1, count + 1)
    ]


@pytest.mark.parametrize("kind", ["missing", "unhealthy", "exited", "duplicate"])
def test_ps_requires_distinct_healthy_replicas(kind):
    values = rows()
    if kind == "missing":
        values.pop()
    elif kind == "unhealthy":
        values[0]["Health"] = "starting"
    elif kind == "exited":
        values[0]["State"] = "exited"
    else:
        values[0]["ID"] = values[1]["ID"]
    with pytest.raises(manage.CheckError):
        manage.require_healthy(values, 3)


def test_ps_supports_json_array_and_ndjson():
    values = rows()
    assert manage.parse_compose_rows(json.dumps(values)) == values
    assert (
        manage.parse_compose_rows("\n".join(json.dumps(value) for value in values))
        == values
    )


def setup_replica_verification(monkeypatch, count=3, inconsistent=False):
    values = rows(count)
    monkeypatch.setattr(manage, "docker_ready", lambda: None)
    monkeypatch.setattr(
        manage, "validate_image", lambda: {"image_id": "sha256:verified"}
    )
    monkeypatch.setattr(
        manage,
        "compose",
        lambda *args, **kwargs: json.dumps(values) if kwargs.get("capture") else "",
    )
    monkeypatch.setattr(manage, "http_request", lambda *args, **kwargs: (200, {}, ""))

    def fake_run(command, **kwargs):
        if command[1] == "inspect":
            if command[3] == "{{.Image}}":
                return "sha256:verified"
            index = command[-1].split("-")[-1]
            return json.dumps({"network": {"IPAddress": f"172.25.0.{index}"}})
        index = command[3].split("-")[-1]
        predictions = ["positive", "negative", "neutral"]
        if inconsistent and index == "2":
            predictions[0] = "neutral"
        return json.dumps({"predictions": predictions})

    monkeypatch.setattr(manage, "run", fake_run)
    return values


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_every_replica_and_gateway_route_is_verified(exported, monkeypatch, count):
    setup_replica_verification(monkeypatch, count)
    backends = itertools.cycle(
        f"172.25.0.{index}:8080" for index in range(1, count + 1)
    )

    def fake_probe(url, payload, *, check_health=True):
        # Probing /ping before each prediction would skip half of an even pool.
        assert check_health is False
        return {
            "predictions": ["positive", "negative", "neutral"],
            "backend": next(backends),
        }

    monkeypatch.setattr(manage, "probe", fake_probe)
    result = manage.verify_replicas(count)
    assert len(result["healthy_replicas"]) == count
    assert len(result["observed_backends"]) == count
    assert (manage.EVIDENCE / f"replicas-{count}.json").is_file()


def test_inconsistent_replica_predictions_fail(exported, monkeypatch):
    setup_replica_verification(monkeypatch, inconsistent=True)
    with pytest.raises(manage.CheckError, match="inconsistent"):
        manage.verify_replicas(3)
    assert not (manage.EVIDENCE / "replicas-3.json").exists()


def test_gateway_must_reach_every_replica(exported, monkeypatch):
    setup_replica_verification(monkeypatch)
    clock = itertools.count()
    monkeypatch.setattr(manage.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        manage,
        "probe",
        lambda *args, **kwargs: {
            "predictions": ["positive", "negative", "neutral"],
            "backend": "172.25.0.1:8080",
        },
    )
    with pytest.raises(manage.CheckError, match="1/3"):
        manage.verify_replicas(3)
    assert not (manage.EVIDENCE / "replicas-3.json").exists()


def test_child_path_includes_interpreter_scripts_without_activation(
    monkeypatch, tmp_path
):
    scripts = tmp_path / "environment with spaces" / "Scripts"
    monkeypatch.setattr(manage.sys, "executable", str(scripts / "python.exe"))
    monkeypatch.setattr(manage.sys, "prefix", str(scripts.parent))
    monkeypatch.setattr(manage.sys, "base_prefix", str(tmp_path / "base-python"))
    source = {
        "Path": str(tmp_path / "system-bin"),
        "MLFLOW_TRACKING_TOKEN": "private-test-value",
    }
    actual = manage.subprocess_environment(source)
    assert actual["Path"].split(manage.os.pathsep)[0] == str(scripts)
    assert actual["VIRTUAL_ENV"] == str(scripts.parent)
    assert actual["MLFLOW_TRACKING_TOKEN"] == source["MLFLOW_TRACKING_TOKEN"]
    assert source["Path"] == str(tmp_path / "system-bin")
    assert "PATH" not in actual


def test_child_path_does_not_duplicate_interpreter_scripts(monkeypatch, tmp_path):
    scripts = str(tmp_path / "Scripts")
    monkeypatch.setattr(manage.sys, "executable", str(Path(scripts) / "python.exe"))
    actual = manage.subprocess_environment(
        {"PATH": manage.os.pathsep.join([scripts, "other", scripts])}
    )
    parts = actual["PATH"].split(manage.os.pathsep)
    assert parts[0] == scripts
    assert parts.count(scripts) == 1
    assert parts[-1] == "other"


def test_user_installed_cli_tools_are_available_without_shell_profile(monkeypatch):
    monkeypatch.setattr(manage.sys, "prefix", "/usr/local")
    monkeypatch.setattr(manage.sys, "base_prefix", "/usr/local")
    monkeypatch.setattr(
        manage.sysconfig, "get_path", lambda name, scheme: "/home/vscode/.local/bin"
    )
    actual = manage.subprocess_environment({"PATH": "/usr/bin"})
    assert "/home/vscode/.local/bin" in actual["PATH"].split(manage.os.pathsep)


def test_run_passes_runtime_path_to_mlflow_child(monkeypatch):
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(manage.subprocess, "run", fake_run)
    manage.run([manage.sys.executable, "-m", "mlflow", "models", "serve"])
    path_key = next(key for key in observed["env"] if key.upper() == "PATH")
    assert observed["env"][path_key].split(manage.os.pathsep)[0] == str(
        Path(manage.sys.executable).parent
    )


def fake_mlflow(
    monkeypatch, model_directory, *, archive_during_export=False, empty=False
):
    calls = {"versions": 0}
    chosen = version()

    class Client:
        def get_latest_versions(self, name, stages):
            assert stages == ["Production"]
            return [] if empty else [chosen]

        def get_model_version(self, name, selected):
            calls["versions"] += 1
            if archive_during_export and calls["versions"] == 2:
                return version("Archived")
            return chosen

        def get_run(self, run_id):
            return SimpleNamespace(info=SimpleNamespace(status="FINISHED"))

    def download(**kwargs):
        import shutil

        target = Path(kwargs["dst_path"]) / "downloaded"
        shutil.copytree(model_directory, target)
        return str(target)

    fake = SimpleNamespace(
        __version__="3.17.1",
        MlflowClient=lambda **kwargs: Client(),
        set_tracking_uri=lambda uri: None,
        set_registry_uri=lambda uri: None,
        artifacts=SimpleNamespace(download_artifacts=download),
    )
    monkeypatch.setitem(sys.modules, "mlflow", fake)


def test_prepare_exports_only_verified_production(exported, monkeypatch):
    fake_mlflow(monkeypatch, manage.MODEL)
    record = manage.prepare("http://127.0.0.1:5000", manage.DEFAULT_NAME)
    assert record["stage"] == "Production"
    assert record["artifact_sha256"] == exported["artifact_sha256"]
    assert record["pinned_uri"].endswith("/1")
    assert record["run_id"] == "source-run"


def test_prepare_rechecks_production_after_download(exported, monkeypatch):
    fake_mlflow(monkeypatch, manage.MODEL, archive_during_export=True)
    before = manage.PRODUCTION.read_bytes()
    with pytest.raises(manage.CheckError, match="Production"):
        manage.prepare("http://127.0.0.1:5000", manage.DEFAULT_NAME)
    assert manage.PRODUCTION.read_bytes() == before


def test_empty_registry_cannot_fall_back_to_demo(exported, monkeypatch):
    fake_mlflow(monkeypatch, manage.MODEL, empty=True)
    with pytest.raises(manage.CheckError, match="exactly one Production"):
        manage.prepare("http://127.0.0.1:5000", manage.DEFAULT_NAME)


def test_retagged_serving_image_is_rejected(exported, monkeypatch):
    manage.write_json(
        manage.IMAGE_RECEIPT,
        {
            "artifact_sha256": exported["artifact_sha256"],
            "image_id": "sha256:original",
        },
    )
    monkeypatch.setattr(manage, "run", lambda *args, **kwargs: "sha256:replaced")
    with pytest.raises(manage.CheckError, match="tag changed"):
        manage.validate_image()


def test_compose_scales_model_images_without_host_port_conflicts():
    config = yaml.safe_load(manage.COMPOSE.read_text())
    model = config["services"]["api-service"]
    assert model["deploy"]["replicas"] == 3
    assert "ports" not in model and "container_name" not in model
    assert "command" not in model and "entrypoint" not in model
    assert model["environment"]["MLFLOW_MODELS_WORKERS"] == "1"
    assert (
        config["services"]["gateway"]["depends_on"]["api-service"]["condition"]
        == "service_healthy"
    )
