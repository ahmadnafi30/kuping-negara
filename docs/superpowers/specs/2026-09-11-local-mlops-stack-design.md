# Local MLOps Stack Design

## Status

Approved direction: installation-first infrastructure scaffold for local Linux,
WSL, GitHub Codespaces, or a future Linux VM. Services remain opt-in and do not
start during Codespace creation.

## Context

Kuping Negara currently has a reproducible Python 3.12 application environment
managed by `uv`. The repository declares Airflow, MLflow, and DVC as planned
MLOps capabilities, but it does not yet provide installation or lifecycle code
for them.

The stack must be easy to install later without forcing every contributor to
run resource-heavy services. MinIO and other S3-compatible object stores are
explicitly excluded from this phase. DVC is initialized without a remote.

## Goals

- Provide repeatable installation and lifecycle commands for Docker, Airflow,
  MLflow, PostgreSQL, and DVC.
- Keep the main application `.venv` isolated from Airflow and DVC dependency
  graphs.
- Allow tracking and orchestration services to start independently.
- Make the same files usable in Codespaces, WSL, and a Linux VM.
- Pin tool and container versions for reproducibility.
- Add health checks, port definitions, safe defaults, and operational docs.

## Non-Goals

- Production deployment, high availability, TLS termination, or public access.
- CeleryExecutor, Redis, Kubernetes, or distributed Airflow workers.
- Permanent DVC remote storage.
- Shared MLflow artifact storage.
- Automatic service startup when a Codespace is created.
- Implementation of ingestion, training, inference, or monitoring pipelines.

## Options Considered

### Selected: Profile-Based Compose with Isolated Tooling

Use Docker Compose profiles named `tracking` and `orchestration`. Run MLflow and
Airflow in their official containers, each with a dedicated PostgreSQL service.
Install DVC as an isolated `uv` tool and commit only its repository metadata.

This option has clear component boundaries, avoids dependency conflicts in the
application environment, and works on both Codespaces and a future Linux VM.

### Rejected: Install Everything in the Application Environment

Adding Airflow, MLflow, and DVC to the main project `.venv` would make dependency
resolution slower and couple unrelated runtime concerns. Airflow in particular
has a large constrained dependency graph. This approach also does not model the
server processes used by a realistic MLOps environment.

### Deferred: Distributed Compose Stack

The official Airflow CeleryExecutor stack adds Redis, workers, a triggerer, and
additional operational overhead. It is appropriate when distributed execution
is required, but unnecessary for the current single-developer foundation.

## Component Architecture

### Application Environment

- Python `3.12` selected by `.python-version`.
- `uv 0.12.12` manages `.venv`, `pyproject.toml`, and `uv.lock`.
- Application dependencies remain pandas, scikit-learn, JupyterLab, and pytest.
- `UV_LINK_MODE=copy` is set in the Dev Container to avoid cross-filesystem
  hardlink warnings in Codespaces.

### Docker Runtime

- Dev Container Feature: `ghcr.io/devcontainers/features/docker-in-docker:4`.
- Docker Compose v2 is the only supported Compose interface.
- Ports are declared for MLflow `5000` and Airflow `8080`.
- Infrastructure services never start from `postCreateCommand`.

### DVC

- Version: `3.67.1`.
- Installed as an isolated tool with `uv tool install dvc==3.67.1`.
- Repository initialized with `dvc init`.
- No default remote is configured.
- `.dvc/config` contains no credentials or remote URL.
- `.dvc/cache`, temporary state, and data contents remain Git-ignored.

Until a remote is configured, `dvc add` can version data locally but `dvc push`
cannot create a durable or shared copy. Deleting a Codespace may therefore remove
both the working dataset and its local DVC cache.

### MLflow Tracking Profile

- Image: `ghcr.io/mlflow/mlflow:v3.15.1-full`.
- Backend database: dedicated `postgres:16.14-bookworm` service.
- Artifact destination: named Docker volume mounted at `/mlartifacts`.
- Server port: `5000`.
- Health endpoint: `/health`.

The database stores experiment and run metadata. The artifact volume stores
model files, plots, and other run outputs. The volume is suitable for local
development but is not shared storage and must not be described as production
durability.

### Airflow Orchestration Profile

- Image: `apache/airflow:3.3.1-python3.12`.
- Executor: `LocalExecutor`.
- Backend database: dedicated `postgres:16.14-bookworm` service.
- Services: database initialization, API server, scheduler, and DAG processor.
- API/UI port: `8080`.
- Health endpoint: `/api/v2/monitor/health`.
- Repository `dags/` is mounted read-only where practical.
- Logs and Airflow state use named Docker volumes.

LocalExecutor provides realistic scheduling and parallel task execution on one
machine without Redis or separate Celery workers. This stack is for development
and assessment only.

## Repository Changes

```text
kuping-negara/
├── .devcontainer/devcontainer.json
├── .dvc/
│   ├── .gitignore
│   └── config
├── compose.yaml
├── docs/
│   ├── dvc-workflow.md
│   ├── local-mlops-stack.md
│   └── superpowers/
│       ├── plans/
│       └── specs/
├── scripts/
│   ├── install-mlops-tools.sh
│   └── mlops-stack.sh
├── .env.example
├── .gitignore
└── README.md
```

`install-mlops-tools.sh` installs or verifies DVC and validates Docker Compose.
`mlops-stack.sh` exposes explicit commands for initialization, startup, status,
logs, shutdown, and destructive reset. Destructive reset requires a confirmation
flag and is never called automatically.

## Configuration and Secrets

`.env.example` documents local defaults for:

- MLflow database name, username, password, and port;
- Airflow database name, username, password, admin username, and port;
- Airflow Fernet key and API JWT secret placeholders;
- timezone `Asia/Jakarta`.

The installation script creates `.env` only when it does not exist and generates
random local secrets. Existing `.env` files are never overwritten. `.env` stays
Git-ignored. Compose fails with an actionable message when a required secret is
missing.

## Lifecycle Interface

```bash
./scripts/install-mlops-tools.sh
./scripts/mlops-stack.sh tracking-up
./scripts/mlops-stack.sh airflow-init
./scripts/mlops-stack.sh orchestration-up
./scripts/mlops-stack.sh all-up
./scripts/mlops-stack.sh status
./scripts/mlops-stack.sh logs tracking
./scripts/mlops-stack.sh down
./scripts/mlops-stack.sh reset --confirm
```

All commands are idempotent except `reset --confirm`, which deletes containers
and named volumes.

## Data and Artifact Flow

1. Source and processing code remains in Git.
2. Large datasets are added with `dvc add` when real data becomes available.
3. Git stores the resulting `.dvc` pointer or `dvc.lock`, not dataset contents.
4. DVC stores objects in its local cache until a remote is configured.
5. Training code sends parameters, metrics, and run artifacts to MLflow.
6. MLflow stores metadata in PostgreSQL and files in its local artifact volume.
7. Airflow schedules package entry points and does not contain business logic.

## Validation Strategy

- Parse `devcontainer.json` as JSON.
- Run `bash -n` against every shell script.
- Run `docker compose config` and verify both profiles are present.
- Verify DVC repository metadata with `dvc doctor` and `dvc status`.
- Start each profile separately and wait for declared health checks.
- Verify MLflow `/health` and Airflow `/api/v2/monitor/health`.
- Run the existing application health check and pytest suite.
- Confirm Git status remains clean after non-destructive setup.

CI validates static configuration and scripts but does not pull and start the
full infrastructure stack on every push. Full service smoke tests are documented
for Codespaces or a Linux VM because Airflow images and startup time are large.

## Resource Expectations

- Application and MLflow only: minimum 2 cores and 8 GB RAM.
- Application, MLflow, and Airflow together: recommended 4 cores and 16 GB RAM.
- At least 15 GB free storage is recommended for container images and volumes.

## Security Boundaries

- Local credentials are development-only and never committed.
- Ports opened by Codespaces remain private by default.
- No production dataset or personal data is included in images or Git history.
- The Compose stack is not exposed directly to the public internet.
- Production deployment requires external secret management, TLS, backups,
  access control, and a supported durable artifact store.

## Future Extension Points

- Add Google Drive, GCS, S3, Azure, or SSH as the DVC remote.
- Replace the MLflow artifact volume with durable object storage.
- Add an extended Airflow image only when DAGs require project-specific packages.
- Move the same Compose contract to a dedicated Linux VM for persistent services.
- Replace Compose with managed services or Kubernetes when operational needs
  justify the additional complexity.

## References

- [DVC command workflow](https://dvc.org/doc/command-reference/)
- [Docker Compose profiles](https://docs.docker.com/compose/how-tos/profiles/)
- [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
- [Apache Airflow Docker images](https://airflow.apache.org/docs/docker-stack/index.html)
- [Apache Airflow architecture](https://airflow.apache.org/docs/apache-airflow/stable/concepts/overview.html)
- [MLflow tracking server](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/)
