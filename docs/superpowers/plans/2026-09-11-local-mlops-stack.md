# Local MLOps Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reproducible, opt-in installation and lifecycle code for DVC,
MLflow, PostgreSQL, and Airflow without installing or starting infrastructure on
the user's local machine.

**Architecture:** Keep the application environment managed by `uv`, install DVC
as an isolated `uv` tool, and run server infrastructure through Docker Compose
profiles. MLflow and Airflow each use a dedicated PostgreSQL database; services
start only through an explicit lifecycle command.

**Tech Stack:** Python 3.12, uv 0.12.12, DVC 3.67.1, Docker Compose v2,
MLflow 3.15.1, PostgreSQL 16.14, Apache Airflow 3.3.1 with LocalExecutor,
Bash, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-09-11-local-mlops-stack-design.md`

## Global Constraints

- Do not install infrastructure tools, pull images, build images, or start
  services on the user's local machine while implementing this plan.
- Do not configure a DVC remote or add MinIO, RustFS, Redis, Celery, or Kubernetes.
- Do not start infrastructure from `postCreateCommand`.
- Never overwrite `.env` or commit credentials, datasets, DVC cache, database
  data, or runtime artifacts.
- Use exact versions from the approved spec and do not introduce em dash.
- Commit directly to `main`, then fast-forward `develop`; create no topic branch.

---

### Task 1: Define Executable Infrastructure Contracts

**Files:**
- Create: `tests/unit/test_infrastructure_contract.py`

**Interfaces:**
- Consumes: repository files through `pathlib.Path`
- Produces: standard-library tests runnable without infrastructure installation

- [ ] **Step 1: Write the failing contract tests**

Create a `unittest.TestCase` that verifies these exact contracts:

```python
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class InfrastructureContractTests(unittest.TestCase):
    def test_devcontainer_is_opt_in(self) -> None:
        config = json.loads(
            (ROOT / ".devcontainer" / "devcontainer.json").read_text("utf-8")
        )
        self.assertIn(
            "ghcr.io/devcontainers/features/docker-in-docker:4",
            config["features"],
        )
        self.assertEqual(config["containerEnv"]["UV_LINK_MODE"], "copy")
        self.assertEqual(set(config["forwardPorts"]), {5000, 8080})
        self.assertNotIn("docker compose up", config["postCreateCommand"])

    def test_dvc_has_no_remote(self) -> None:
        config = (ROOT / ".dvc" / "config").read_text("utf-8")
        installer = (ROOT / "scripts" / "install-mlops-tools.sh").read_text(
            "utf-8"
        )
        self.assertNotIn("[remote", config)
        self.assertIn("dvc==3.67.1", installer)
        self.assertNotIn("dvc remote add", installer)

    def test_compose_is_pinned_and_profile_based(self) -> None:
        compose = (ROOT / "compose.yaml").read_text("utf-8")
        for value in (
            "ghcr.io/mlflow/mlflow:v3.15.1-full",
            "postgres:16.14-bookworm",
            "apache/airflow:3.3.1-python3.12",
            "profiles: [tracking]",
            "profiles: [orchestration]",
            "LocalExecutor",
        ):
            self.assertIn(value, compose)
        for excluded in ("minio", "rustfs", "redis", "CeleryExecutor"):
            self.assertNotIn(excluded.lower(), compose.lower())

    def test_reset_requires_confirmation(self) -> None:
        script = (ROOT / "scripts" / "mlops-stack.sh").read_text("utf-8")
        self.assertIn('reset --confirm', script)
        self.assertIn('if [[ "${2:-}" != "--confirm" ]]', script)
```

- [ ] **Step 2: Run tests and confirm RED**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests/unit -p test_infrastructure_contract.py -v
```

Expected: FAIL because Compose, DVC metadata, and scripts do not exist.

- [ ] **Step 3: Commit the contract tests**

```bash
git add tests/unit/test_infrastructure_contract.py
git commit -m "test: define local MLOps infrastructure contract"
```

### Task 2: Prepare the Opt-In Dev Container

**Files:**
- Modify: `.devcontainer/devcontainer.json`

**Interfaces:**
- Consumes: existing Python Dev Container configuration
- Produces: Docker Compose runtime, private ports, and quiet uv copy behavior

- [ ] **Step 1: Add Dev Container properties**

Add the Docker-in-Docker feature, `UV_LINK_MODE=copy`, forwarded ports `5000`
and `8080`, private port labels, and the `Iterative.dvc` VS Code extension.
Preserve the existing Python image and `postCreateCommand` exactly. The new
properties are:

```json
"features": {
  "ghcr.io/devcontainers/features/docker-in-docker:4": {
    "version": "latest",
    "dockerDashComposeVersion": "v2"
  }
},
"containerEnv": {"UV_LINK_MODE": "copy"},
"forwardPorts": [5000, 8080]
```

- [ ] **Step 2: Validate without rebuilding or installing**

```powershell
Get-Content -Raw .devcontainer/devcontainer.json | ConvertFrom-Json | Out-Null
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest tests.unit.test_infrastructure_contract.InfrastructureContractTests.test_devcontainer_is_opt_in -v
```

Expected: JSON parse and focused test PASS. No container is rebuilt.

- [ ] **Step 3: Commit**

```bash
git add .devcontainer/devcontainer.json
git commit -m "feat: add opt-in Docker runtime for development"
```

### Task 3: Initialize DVC Without Installing It Locally

**Files:**
- Create: `.dvc/config`
- Create: `.dvc/.gitignore`
- Create: `.dvcignore`
- Create: `scripts/install-mlops-tools.sh`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: uv, Docker, Docker Compose when a user explicitly runs the script
- Produces: DVC repository metadata and an idempotent installation entry point

- [ ] **Step 1: Create DVC metadata manually**

Create an empty `.dvc/config`. Create `.dvc/.gitignore` with:

```gitignore
/config.local
/tmp
/cache
```

Create `.dvcignore` with explanatory comments only. Do not run `dvc init` on the
local machine and do not create a remote section.

- [ ] **Step 2: Extend root ignore rules**

Ignore `.dvc/cache/`, `.dvc/tmp/`, `.dvc/config.local`, `mlruns/`,
`mlartifacts/`, `airflow-logs/`, and `postgres-data/`.

- [ ] **Step 3: Create `install-mlops-tools.sh`**

The script must use `set -euo pipefail`, enter the repository root, and:

1. require `uv`, `docker`, and `docker compose`;
2. install `dvc==3.67.1` with `uv tool install` only when executed;
3. upgrade the existing DVC tool to the same pin when requested;
4. create `.env` only when absent;
5. generate Airflow Fernet and JWT secrets with Python standard library;
6. run `docker compose --env-file .env config --quiet`;
7. pull images only with the explicit `--pull` flag;
8. never build or start services;
9. print the next lifecycle commands.

Supported calls:

```bash
./scripts/install-mlops-tools.sh
./scripts/install-mlops-tools.sh --pull
```

- [ ] **Step 4: Validate without executing the installer**

```bash
bash -n scripts/install-mlops-tools.sh
```

Then run the focused DVC contract with `python -m unittest`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .dvc .dvcignore .gitignore scripts/install-mlops-tools.sh
git commit -m "feat: initialize local DVC workflow without remote"
```

### Task 4: Add the MLflow Tracking Profile

**Files:**
- Create: `compose.yaml`
- Create: `docker/mlflow/Dockerfile`
- Modify: `.env.example`

**Interfaces:**
- Consumes: Docker Compose and a user-created `.env`
- Produces: MLflow plus a dedicated PostgreSQL backend under `tracking`

- [ ] **Step 1: Add documented local defaults**

Add MLflow `3.15.1`, Airflow `3.3.1`, ports `5000` and `8080`, separate database
names/users/password placeholders, Airflow admin placeholders, UID `50000`,
Fernet placeholder, and JWT placeholder to `.env.example`.

- [ ] **Step 2: Create the MLflow image extension**

```dockerfile
FROM ghcr.io/mlflow/mlflow:v3.15.1-full

RUN python -m pip install --no-cache-dir "psycopg2-binary==2.9.10"
```

- [ ] **Step 3: Create tracking services in `compose.yaml`**

Define `mlflow-db` on `postgres:16.14-bookworm` with `pg_isready`. Define
`mlflow` from the Dockerfile with a health-aware database dependency, PostgreSQL
backend URI, named `/mlartifacts` volume, port `5000`, and `/health` check. Put
both services under `profiles: [tracking]`.

- [ ] **Step 4: Verify the intermediate contract**

Run the Compose contract test. Expected: FAIL only because the Airflow profile is
not present yet. Do not run any Docker command.

- [ ] **Step 5: Commit**

```bash
git add compose.yaml docker/mlflow/Dockerfile .env.example
git commit -m "feat: add containerized MLflow tracking profile"
```

### Task 5: Add Airflow and Safe Lifecycle Commands

**Files:**
- Modify: `compose.yaml`
- Create: `scripts/mlops-stack.sh`

**Interfaces:**
- Consumes: `.env`, Docker Compose, and repository `dags/`
- Produces: Airflow LocalExecutor profile and one lifecycle interface

- [ ] **Step 1: Add orchestration services**

Use `apache/airflow:3.3.1-python3.12` and `LocalExecutor`. Add `airflow-db`,
`airflow-init`, `airflow-apiserver`, `airflow-scheduler`, and
`airflow-dag-processor`. Use PostgreSQL, disable examples, pause new DAGs, use
`Asia/Jakarta`, mount `dags/`, persist logs in a named volume, add health-aware
dependencies, and assign `profiles: [orchestration]` to every service.

The API server health endpoint is `/api/v2/monitor/health` on port `8080`.

- [ ] **Step 2: Create `mlops-stack.sh`**

Support exactly:

```text
tracking-up
airflow-init
orchestration-up
all-up
status
logs tracking
logs orchestration
down
reset --confirm
```

Fail before Compose when `.env`, Docker, or Compose is missing. `reset` must
return non-zero unless argument two is exactly `--confirm`; only confirmed reset
may delete named volumes.

- [ ] **Step 3: Validate without running the stack**

```bash
bash -n scripts/mlops-stack.sh
```

Run all `test_infrastructure_contract.py` tests. Expected: PASS. Do not execute
the script.

- [ ] **Step 4: Commit**

```bash
git add compose.yaml scripts/mlops-stack.sh
git commit -m "feat: add Airflow orchestration and lifecycle commands"
```

### Task 6: Add Static Infrastructure Validation to CI

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: shell scripts, Compose file, `.env.example`
- Produces: GitHub-hosted validation without pulling infrastructure images

- [ ] **Step 1: Add validation steps**

```yaml
- name: Validate infrastructure scripts
  run: bash -n scripts/install-mlops-tools.sh scripts/mlops-stack.sh

- name: Validate Compose configuration
  run: docker compose --env-file .env.example config --quiet
```

Do not add `pull`, `build`, or `up` to CI. Preserve uv sync, dependency check,
health check, and pytest.

- [ ] **Step 2: Validate diff and commit**

```bash
git diff --check
git add .github/workflows/ci.yml
git commit -m "ci: validate MLOps infrastructure configuration"
```

### Task 7: Write Complete Step-by-Step Guides

**Files:**
- Create: `docs/local-mlops-stack.md`
- Create: `docs/dvc-workflow.md`
- Modify: `docs/codespaces-setup.md`
- Modify: `docs/development-guidelines.md`
- Modify: `docs/project-structure.md`
- Modify: `docs/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: all actual commands and limitations from Tasks 2 through 6
- Produces: operator documentation for Codespaces, WSL, and Ubuntu VM

- [ ] **Step 1: Write `local-mlops-stack.md`**

Include prerequisites, minimum resources, architecture, Codespaces Rebuild
Container steps, WSL preparation, Ubuntu VM preparation using official Docker
and uv links, tool installation, optional image pulling, profile startup, URLs,
health verification, status, logs, shutdown, confirmed reset, persistence,
security, troubleshooting, and uninstall boundaries.

Every user action must be a numbered step followed by its exact command and
expected result. State that repository creation itself installs nothing locally.

- [ ] **Step 2: Write `dvc-workflow.md`**

Document `dvc doctor`, `dvc status`, `dvc add data/raw`, Git staging and commit,
`dvc checkout`, cache behavior, and the absence of `dvc push`/`dvc pull` until a
remote is configured. Explain how future remote configuration uses
`.dvc/config.local` or secret environment settings for credentials.

- [ ] **Step 3: Update all documentation indexes and rules**

Link both guides, extend the repository tree, document opt-in infrastructure,
and change DVC, MLflow, Airflow, and PostgreSQL status to `Infrastructure
scaffold available; feature integration planned`. Keep the default Codespaces
Quick Start lightweight.

- [ ] **Step 4: Validate style and commit**

```powershell
$emdash = [char]0x2014
rg -n $emdash README.md docs
git diff --check
```

Expected: no em dash match and no whitespace errors.

```bash
git add README.md docs
git commit -m "docs: add step-by-step MLOps environment setup"
```

### Task 8: Verify, Push, and Synchronize

**Files:**
- Verify: all changed files

**Interfaces:**
- Consumes: completed implementation
- Produces: clean synchronized branches and successful GitHub CI

- [ ] **Step 1: Run only non-installing local checks**

```powershell
Get-Content -Raw .devcontainer/devcontainer.json | ConvertFrom-Json | Out-Null
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests/unit -p test_infrastructure_contract.py -v
bash -n scripts/install-mlops-tools.sh scripts/mlops-stack.sh
git diff --check
uv lock --check
```

Do not execute either script and do not run Docker Compose locally.

- [ ] **Step 2: Audit files and secrets**

Inspect `git status --short --untracked-files=all` and credential-like matches.
Confirm no `.env`, data, cache, database, artifact, or log file is staged.

- [ ] **Step 3: Push and verify CI**

Push `main`, monitor GitHub Actions through completion, and use the first CI
parsing error as the source of truth if Compose validation fails.

- [ ] **Step 4: Synchronize `develop`**

```bash
git switch develop
git merge --ff-only main
git push origin develop
git switch main
```

- [ ] **Step 5: Confirm final state**

Confirm `main`, `develop`, `origin/main`, and `origin/develop` resolve to the same
commit and the `main` working tree is clean.
