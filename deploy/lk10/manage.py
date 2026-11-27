"""Prepare a Production model, use MLflow native serving, and verify replicas."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import sysconfig
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / ".artifacts"
MODEL = ARTIFACTS / "model"
PRODUCTION = ARTIFACTS / "production.json"
IMAGE_RECEIPT = ARTIFACTS / "image.json"
EVIDENCE = ROOT / ".evidence"
COMPOSE = ROOT / "docker-compose.yaml"
IMAGE = "kuping-negara-serving:lk10"
DEFAULT_NAME = "kuping-negara-sentiment-lk07-simulation"
LABELS = {"negative", "neutral", "positive"}
DIRECT_PROBE = """
import json, sys, urllib.request
payload = sys.stdin.buffer.read()
with urllib.request.urlopen('http://127.0.0.1:8080/ping', timeout=10) as response:
    assert response.status == 200
request = urllib.request.Request(
    'http://127.0.0.1:8080/invocations', data=payload,
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=30) as response:
    print(json.dumps(json.load(response)))
"""


class CheckError(RuntimeError):
    """An operational precondition or verification failed."""


def now():
    return datetime.now(UTC).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def subprocess_environment(environment=None):
    """Expose this interpreter's CLI tools to subprocesses such as uvicorn."""
    result = dict(os.environ if environment is None else environment)
    path_key = next((key for key in result if key.upper() == "PATH"), "PATH")
    scripts = str(Path(sys.executable).parent)
    candidates = [scripts]
    if sys.prefix == sys.base_prefix:
        candidates.append(
            sysconfig.get_path("scripts", scheme=sysconfig.get_preferred_scheme("user"))
        )
    normalized = {os.path.normcase(os.path.normpath(path)) for path in candidates}
    remaining = [
        part
        for part in result.get(path_key, "").split(os.pathsep)
        if part and os.path.normcase(os.path.normpath(part)) not in normalized
    ]
    result[path_key] = os.pathsep.join(dict.fromkeys([*candidates, *remaining]))
    if sys.prefix != sys.base_prefix:
        result["VIRTUAL_ENV"] = sys.prefix
    result.setdefault("PYTHONUNBUFFERED", "1")
    return result


def run(command, *, capture=False, stdin=None, env=None):
    result = subprocess.run(
        [str(part) for part in command],
        cwd=ROOT,
        env=subprocess_environment(env),
        input=stdin,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip() if capture else ""
        raise CheckError(
            f"Command failed ({result.returncode}): {command[0]}\n{detail}"
        )
    return result.stdout.strip() if capture else ""


def docker_ready():
    run(["docker", "info", "--format", "{{.ServerVersion}}"], capture=True)


def compose(*arguments, capture=False):
    return run(["docker", "compose", "-f", COMPOSE, *arguments], capture=capture)


def artifact_digest(directory):
    directory = Path(directory).resolve()
    if not (directory / "MLmodel").is_file():
        raise CheckError("Model export has no MLmodel file")
    result = hashlib.sha256()
    # pathlib's default ordering differs between Windows and Linux. Preserve
    # the Windows export order explicitly so the receipt survives transfer.
    for path in sorted(
        directory.rglob("*"),
        key=lambda path: tuple(part.casefold() for part in path.relative_to(directory).parts),
    ):
        if path.is_symlink():
            raise CheckError("Model export must not contain symlinks")
        if path.is_file():
            result.update(path.relative_to(directory).as_posix().encode() + b"\0")
            result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def validate_production(version, name):
    if version.name != name or version.current_stage != "Production":
        raise CheckError("Selected version is not the requested Production model")
    if version.status != "READY" or not str(version.version).isdecimal():
        raise CheckError("Production version is not READY")
    if not version.run_id:
        raise CheckError("Production model has no source run")


def prepare(tracking_uri, name):
    try:
        import mlflow
        from mlflow import MlflowClient
    except ImportError as error:
        raise CheckError(
            "Install requirements-tools.txt in Python 3.12 first"
        ) from error
    parsed = urllib.parse.urlsplit(tracking_uri)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CheckError("Use an HTTP(S) MLflow tracking URI")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CheckError(
            "Use a plain tracking URL; credentials belong in MLflow environment variables"
        )
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    versions = client.get_latest_versions(name, stages=["Production"])
    if len(versions) != 1:
        raise CheckError(
            "Expected exactly one Production version; restore the LK-07 registry first"
        )
    selected = client.get_model_version(name, str(versions[0].version))
    validate_production(selected, name)
    source_run = client.get_run(selected.run_id)
    if source_run.info.status != "FINISHED":
        raise CheckError("The Production source run is not FINISHED")
    pinned_uri = f"models:/{name}/{selected.version}"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="download-", dir=ARTIFACTS) as temporary:
        temporary_path = Path(temporary).resolve()
        if not temporary_path.is_relative_to(ARTIFACTS.resolve()):
            raise CheckError("Temporary export escaped its destination")
        downloaded = Path(
            mlflow.artifacts.download_artifacts(
                artifact_uri=pinned_uri,
                dst_path=str(temporary_path),
                tracking_uri=tracking_uri,
            )
        ).resolve()
        if not downloaded.is_relative_to(temporary_path):
            raise CheckError("Downloaded model escaped the temporary export")
        digest = artifact_digest(downloaded)
        current = client.get_model_version(name, str(selected.version))
        validate_production(current, name)
        if current.source != selected.source or current.run_id != selected.run_id:
            raise CheckError("Production reference changed during export")
        if MODEL.exists():
            if artifact_digest(MODEL) != digest:
                raise CheckError(
                    "A different model export already exists; use a fresh LK-10 folder"
                )
        else:
            shutil.copytree(downloaded, MODEL)
    record = {
        "model_name": name,
        "version": str(selected.version),
        "stage": "Production",
        "production_uri": f"models:/{name}/Production",
        "pinned_uri": pinned_uri,
        "run_id": selected.run_id,
        "artifact_sha256": digest,
        "tracking_uri": tracking_uri,
        "mlflow_version": mlflow.__version__,
        "exported_at": now(),
        "simulation_only": (selected.tags or {}).get("simulation_only"),
        "deployment_approved": (selected.tags or {}).get(
            "deployment_approved", "false"
        ),
    }
    write_json(PRODUCTION, record)
    print(json.dumps(record, indent=2))
    return record


def validate_export():
    if not PRODUCTION.is_file() or not MODEL.is_dir():
        raise CheckError(
            "Run 'python manage.py prepare' against the Production registry first"
        )
    record = read_json(PRODUCTION)
    if (
        record.get("stage") != "Production"
        or not str(record.get("version", "")).isdecimal()
    ):
        raise CheckError("Export receipt does not identify a Production version")
    expected_uri = f"models:/{record['model_name']}/{record['version']}"
    if record.get("pinned_uri") != expected_uri:
        raise CheckError("Export model URI and version disagree")
    if artifact_digest(MODEL) != record.get("artifact_sha256"):
        raise CheckError("Exported model changed after Production verification")
    return record


def serve_command(port=8001, host="127.0.0.1", env_manager="local"):
    validate_export()
    return [
        sys.executable,
        "-m",
        "mlflow",
        "models",
        "serve",
        "-m",
        str(MODEL),
        "--env-manager",
        env_manager,
        "--host",
        host,
        "-p",
        str(port),
        "--workers",
        "1",
    ]


def normalize_dockerfile_paths(path):
    """Docker COPY sources use POSIX paths even when MLflow runs on Windows."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text(
        "".join(
            line.replace("\\", "/") if line.startswith("COPY ") else line
            for line in lines
        ),
        encoding="utf-8",
    )


def build():
    record = validate_export()
    docker_ready()
    # MLflow owns the image creation and serving entrypoint.
    command = [
        sys.executable,
        "-m",
        "mlflow",
        "models",
        "build-docker",
        "-m",
        str(MODEL),
        "-n",
        IMAGE,
        "--env-manager",
        "local",
    ]
    if sys.platform == "win32":
        print("Running: mlflow models generate-dockerfile + docker build", flush=True)
        # MLflow's build-docker uses os.path.relpath in COPY instructions.
        # Keep its generated model installation and native serving entrypoint,
        # correcting only the host-specific source separators before building.
        with tempfile.TemporaryDirectory(prefix="docker-", dir=ARTIFACTS) as context:
            run([
                sys.executable, "-m", "mlflow", "models", "generate-dockerfile",
                "-m", str(MODEL), "--env-manager", "local",
                "--output-directory", context,
            ])
            normalize_dockerfile_paths(Path(context) / "Dockerfile")
            run(["docker", "build", "-t", IMAGE, context])
    else:
        print("Running: mlflow models build-docker", flush=True)
        run(command)
    image_id = run(
        ["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], capture=True
    )
    receipt = {
        "image": IMAGE,
        "image_id": image_id,
        "artifact_sha256": record["artifact_sha256"],
        "pinned_uri": record["pinned_uri"],
        "built_at": now(),
        "command": [
            "mlflow",
            "models",
            "build-docker",
            "-m",
            ".artifacts/model",
            "-n",
            IMAGE,
            "--env-manager",
            "local",
        ],
        "build_method": "generate-dockerfile+docker-build"
        if sys.platform == "win32" else "build-docker",
    }
    write_json(IMAGE_RECEIPT, receipt)
    print(json.dumps(receipt, indent=2))
    return receipt


def validate_image():
    record = validate_export()
    if not IMAGE_RECEIPT.is_file():
        raise CheckError(
            "Run 'python manage.py build' to create the MLflow serving image"
        )
    receipt = read_json(IMAGE_RECEIPT)
    if receipt.get("artifact_sha256") != record["artifact_sha256"]:
        raise CheckError("Serving image was built for a different exported model")
    actual = run(
        ["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], capture=True
    )
    if actual != receipt.get("image_id"):
        raise CheckError("Serving image tag changed after the recorded build")
    return receipt


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {"dataframe_split"}:
        raise CheckError("Use a dataframe_split payload")
    split = payload["dataframe_split"]
    if not isinstance(split, dict):
        raise CheckError("dataframe_split must be an object")
    if split.get("columns") != ["model_text", "target_program"]:
        raise CheckError(
            "Input columns must be model_text and target_program in that order"
        )
    rows = split.get("data")
    if not isinstance(rows, list) or not rows:
        raise CheckError("Provide at least one input row")
    if any(
        not isinstance(row, list)
        or len(row) != 2
        or any(not isinstance(value, str) or not value.strip() for value in row)
        for row in rows
    ):
        raise CheckError("Each row requires two nonempty strings")
    return len(rows)


def validate_prediction(response, expected_rows):
    if not isinstance(response, dict):
        raise CheckError("MLflow response must be an object")
    labels = response.get("predictions")
    if not isinstance(labels, list) or len(labels) != expected_rows:
        raise CheckError("Prediction count differs from the input row count")
    if any(not isinstance(label, str) or label not in LABELS for label in labels):
        raise CheckError("Unexpected sentiment output")
    return labels


def http_request(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Connection": "close"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return response.status, dict(response.headers.items()), body


def probe(url, payload, *, check_health=True):
    rows = validate_payload(payload)
    base = url.rstrip("/")
    if check_health:
        status, _, _ = http_request(base + "/ping")
        if status != 200:
            raise CheckError("MLflow /ping did not return HTTP 200")
    status, headers, body = http_request(base + "/invocations", payload)
    if status != 200:
        raise CheckError("MLflow /invocations did not return HTTP 200")
    result = json.loads(body)
    labels = validate_prediction(result, rows)
    backend = next(
        (value for key, value in headers.items() if key.lower() == "x-model-replica"),
        "",
    )
    return {
        "status": status,
        "response": result,
        "predictions": labels,
        "backend": backend,
    }


def test_api(url, request_path=ROOT / "request.json"):
    payload = read_json(request_path)
    record = validate_export()
    result = probe(url, payload)
    evidence = {
        "checked_at": now(),
        "url": url,
        "model": record,
        "input": payload,
        "output": result,
        "environment": "codespaces"
        if os.environ.get("CODESPACES") == "true"
        else "local",
    }
    write_json(EVIDENCE / "api.json", evidence)
    print("INPUT:\n" + json.dumps(payload, indent=2, ensure_ascii=False))
    print("OUTPUT:\n" + json.dumps(result["response"], indent=2))
    print("PASS: native MLflow /ping and /invocations")
    return evidence


def parse_compose_rows(output):
    output = output.strip()
    if not output:
        return []
    if output.startswith("["):
        rows = json.loads(output)
    else:
        rows = [json.loads(line) for line in output.splitlines() if line.strip()]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise CheckError("Unexpected docker compose ps JSON")
    return rows


def require_healthy(rows, expected):
    if len(rows) != expected:
        raise CheckError(f"Expected {expected} model replicas, found {len(rows)}")
    if len({row.get("ID") for row in rows}) != expected:
        raise CheckError("Replica identities are missing or repeated")
    for row in rows:
        if not row.get("ID") or row.get("Service") != "api-service":
            raise CheckError("Unexpected service in model replica list")
        if row.get("State") != "running" or row.get("Health") != "healthy":
            raise CheckError(f"Replica is not running and healthy: {row.get('Name')}")


def up(replicas):
    docker_ready()
    validate_image()
    compose(
        "up",
        "-d",
        "--scale",
        f"api-service={replicas}",
        "--wait",
        "--wait-timeout",
        "300",
    )
    compose("ps")


def verify_replicas(replicas, url="http://127.0.0.1:8002"):
    docker_ready()
    image = validate_image()
    payload = read_json(ROOT / "request.json")
    expected_rows = validate_payload(payload)
    rows = parse_compose_rows(
        compose("ps", "--all", "--format", "json", "api-service", capture=True)
    )
    require_healthy(rows, replicas)
    baseline = None
    direct = []
    expected_backends = set()
    for row in rows:
        container = row["ID"]
        actual_image = run(
            ["docker", "inspect", "--format", "{{.Image}}", container], capture=True
        )
        if actual_image != image["image_id"]:
            raise CheckError("A replica is not running the verified serving image")
        networks = json.loads(
            run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .NetworkSettings.Networks}}",
                    container,
                ],
                capture=True,
            )
        )
        addresses = {
            network.get("IPAddress")
            for network in networks.values()
            if network.get("IPAddress")
        }
        expected_backends.update(f"{address}:8080" for address in addresses)
        output = run(
            ["docker", "exec", "-i", container, "python", "-c", DIRECT_PROBE],
            stdin=json.dumps(payload),
            capture=True,
        )
        labels = validate_prediction(json.loads(output), expected_rows)
        if baseline is None:
            baseline = labels
        if labels != baseline:
            raise CheckError("Model replicas returned inconsistent predictions")
        direct.append(
            {
                "container": row["Name"],
                "id": container,
                "image_id": actual_image,
                "predictions": labels,
            }
        )
        print(f"PASS replica: {row['Name']} -> {labels}", flush=True)

    observed = set()
    routed_requests = []
    # Check health once; alternating ping/predict could skip even-numbered replicas.
    http_request(url.rstrip("/") + "/ping")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            result = probe(url, payload, check_health=False)
            if result["predictions"] != baseline:
                raise CheckError("Gateway returned predictions from a different model")
            # With retries Nginx can return multiple addresses; the final one served the response.
            backend = result["backend"].split(",")[-1].strip()
            if backend not in expected_backends:
                raise CheckError(
                    f"Gateway returned an unexpected or missing backend: {backend}"
                )
            observed.add(backend)
            routed_requests.append(
                {"backend": backend, "predictions": result["predictions"]}
            )
            if len(observed) >= replicas:
                break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    if len(observed) != replicas:
        raise CheckError(f"Gateway reached {len(observed)}/{replicas} backends")
    evidence = {
        "checked_at": now(),
        "expected_replicas": replicas,
        "healthy_replicas": direct,
        "gateway": url,
        "observed_backends": sorted(observed),
        "routed_requests": routed_requests,
        "input": payload,
        "production": read_json(PRODUCTION),
        "image": image,
    }
    write_json(EVIDENCE / f"replicas-{replicas}.json", evidence)
    compose("ps")
    print("INPUT:\n" + json.dumps(payload, indent=2, ensure_ascii=False))
    print("OUTPUT:\n" + json.dumps({"predictions": baseline}, indent=2))
    print(
        f"PASS: {replicas} healthy model replicas, identical predictions, all reached through gateway"
    )
    return evidence


def local_check(port=8001):
    """Launch the real native server, test it, and stop only its own process."""
    command = serve_command(port=port)
    with socket.socket() as reserved:
        try:
            reserved.bind(("127.0.0.1", port))
        except OSError as error:
            raise CheckError(f"Local serving port {port} is unavailable") from error
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    log_path = EVIDENCE / "native-serve.log"
    options = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=subprocess_environment(),
            stdout=log,
            stderr=subprocess.STDOUT,
            **options,
        )
        try:
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise CheckError(f"Native MLflow server exited; read {log_path}")
                try:
                    status, _, _ = http_request(f"http://127.0.0.1:{port}/ping")
                    if status == 200:
                        result = test_api(f"http://127.0.0.1:{port}")
                        result["native_serve_command"] = [
                            "mlflow",
                            "models",
                            "serve",
                            "-m",
                            ".artifacts/model",
                            "--env-manager",
                            "local",
                            "-p",
                            str(port),
                        ]
                        write_json(EVIDENCE / "api.json", result)
                        return result
                except (urllib.error.URLError, TimeoutError):
                    pass
                time.sleep(1)
            raise CheckError(
                f"Native MLflow server did not become ready; read {log_path}"
            )
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                else:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    preparing = sub.add_parser("prepare")
    preparing.add_argument(
        "--tracking-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"),
    )
    preparing.add_argument("--model-name", default=DEFAULT_NAME)
    serving = sub.add_parser("serve")
    serving.add_argument("--port", type=int, default=8001)
    serving.add_argument("--host", default="127.0.0.1")
    serving.add_argument(
        "--env-manager", choices=["local", "virtualenv", "uv", "conda"], default="local"
    )
    local = sub.add_parser("local-check")
    local.add_argument("--port", type=int, default=8001)
    sub.add_parser("build")
    sub.add_parser("check-model")
    starting = sub.add_parser("up")
    starting.add_argument("--replicas", type=int, default=3)
    api = sub.add_parser("test-api")
    api.add_argument("--url", default="http://127.0.0.1:8001")
    api.add_argument("--request", type=Path, default=ROOT / "request.json")
    checking = sub.add_parser("verify")
    checking.add_argument("--replicas", type=int, default=3)
    checking.add_argument("--url", default="http://127.0.0.1:8002")
    sub.add_parser("status")
    args = parser.parse_args()
    if hasattr(args, "replicas") and not 1 <= args.replicas <= 12:
        parser.error("replicas must be between 1 and 12")
    try:
        if args.action == "prepare":
            prepare(args.tracking_uri, args.model_name)
        elif args.action == "serve":
            run(serve_command(args.port, args.host, args.env_manager))
        elif args.action == "local-check":
            local_check(args.port)
        elif args.action == "build":
            build()
        elif args.action == "check-model":
            print(json.dumps(validate_export(), indent=2))
        elif args.action == "up":
            up(args.replicas)
        elif args.action == "test-api":
            test_api(args.url, args.request)
        elif args.action == "verify":
            verify_replicas(args.replicas, args.url)
        else:
            compose("ps")
    except (CheckError, OSError, ValueError, urllib.error.URLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
