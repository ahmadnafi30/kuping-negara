# GitHub Codespaces Setup

This guide defines the reproducible development environment for Kuping Negara.
The repository uses Python 3.12, `uv`, a committed `uv.lock`, and a Dev
Container so a new Codespace can install and verify the project automatically.

## Acceptance Criteria

A Codespace is ready when all of the following are true:

- the container starts without a Dev Container error;
- Python reports version `3.12.x`;
- `uv sync --frozen --extra dev` succeeds without changing `uv.lock`;
- `uv pip check` reports no incompatible or missing dependencies;
- the environment health check reports pandas, scikit-learn, JupyterLab, and
  pytest as installed;
- the complete test suite passes.

## Prerequisites

- A GitHub account with access to this repository.
- GitHub Codespaces access and available quota.
- Permission to create a Codespace from the `main` branch.

No local Python installation is required when using Codespaces.

## Create the Codespace

1. Open the repository on GitHub.
2. Select **Code**.
3. Open the **Codespaces** tab.
4. Select **Create codespace on main**.
5. Wait until the terminal finishes the `postCreateCommand` process.

During creation, GitHub clones the repository and builds the container defined
in `.devcontainer/devcontainer.json`. The post-create process then installs the
pinned `uv` release, creates `.venv`, installs the locked runtime and `dev`
dependencies, validates dependency consistency, and runs the health check.

## Verify the Environment

Run these commands from the repository root:

```bash
python --version
uv --version
uv sync --frozen --extra dev
uv pip check
uv run --frozen --extra dev python -m kuping_negara.healthcheck
uv run --frozen --extra dev pytest
git status --short
```

Expected evidence:

- `python --version` returns Python `3.12.x`;
- `uv --version` returns `uv 0.12.12`;
- dependency sync and consistency checks exit successfully;
- the health check displays `[OK]` for `pandas`, `scikit-learn`, `jupyterlab`,
  and `pytest`;
- all tests pass;
- `git status --short` has no output after setup.

The empty Git status is important. It proves that installation used the
committed lockfile without silently rewriting repository files.

## Dependency Files

| File | Role |
| --- | --- |
| `pyproject.toml` | Direct runtime and development dependency declarations |
| `uv.lock` | Exact, reproducible resolution used by Codespaces and CI |
| `requirements.txt` | Generated compatibility export for pip-based tools |
| `.python-version` | Python 3.12 selection for local uv and automation |

Do not install planned components such as Airflow, MLflow, FastAPI, Streamlit,
DVC, or transformers until repository code actually imports or operates them.
Premature installation makes the Codespace slower and introduces avoidable
dependency conflicts.

## Daily uv Workflow

Synchronize after pulling dependency changes:

```bash
uv sync --frozen --extra dev
```

Run project commands inside the managed environment:

```bash
uv run --frozen --extra dev python -m kuping_negara
uv run --frozen --extra dev pytest
uv run --frozen --extra dev jupyter lab
```

Add a runtime dependency:

```bash
uv add <package>
```

Add a development-only dependency:

```bash
uv add --optional dev <package>
```

After an approved dependency change, refresh the compatibility manifest:

```bash
uv lock
uv export --frozen --extra dev --format requirements.txt --no-hashes \
  --no-emit-project --output-file requirements.txt
```

Commit `pyproject.toml`, `uv.lock`, and `requirements.txt` together. CI uses
`--frozen`, so it fails when the lockfile does not match the project metadata.

## Rebuild After Container Changes

When `.devcontainer/devcontainer.json` changes:

1. Open the Command Palette with `Ctrl+Shift+P`.
2. Run **Codespaces: Rebuild Container**.
3. Wait for the post-create process to finish.
4. Repeat all commands in [Verify the Environment](#verify-the-environment).

## Troubleshooting

### Frozen lockfile error

Cause: `pyproject.toml` changed without a matching `uv.lock` update.

Resolution on the dependency-authoring branch:

```bash
uv lock
uv sync --frozen --extra dev
```

Commit the updated lockfile. Do not remove `--frozen` from Codespaces or CI to
hide a stale lockfile.

### VS Code uses the wrong Python interpreter

Open the Command Palette, run **Python: Select Interpreter**, and select:

```text
${containerWorkspaceFolder}/.venv/bin/python
```

Then reload the VS Code window.

### A dependency is missing or inconsistent

Run:

```bash
uv sync --frozen --extra dev
uv pip check
uv run --frozen --extra dev python -m kuping_negara.healthcheck
```

If the issue remains, review the Codespace creation log and rebuild the
container. Do not manually install an undeclared package as the permanent fix.

### Post-create process fails

1. Open the creation log shown by Codespaces.
2. Find the first command that returned a non-zero status.
3. Confirm the Codespace has network access to PyPI.
4. Confirm `pyproject.toml` and `uv.lock` were committed together.
5. Run **Codespaces: Rebuild Container** after correcting the cause.

## Secrets

Use GitHub Codespaces secrets or environment variables for credentials. Never
place access tokens, cookies, `.env` contents, or private source data in Git,
terminal screenshots, notebooks, or assessment documents.

## Assessment Evidence Checklist

Capture evidence only after a clean rebuild:

- Codespace running from the `main` branch;
- successful `postCreateCommand` completion;
- Python and uv versions;
- successful locked dependency sync;
- `uv pip check` output;
- environment health check output;
- passing test output;
- clean Git status.

These artifacts demonstrate that the environment runs without errors and that
all declared dependencies install reproducibly.

## Official References

- [Creating a codespace for a repository](https://docs.github.com/en/codespaces/developing-in-a-codespace/creating-a-codespace-for-a-repository?tool=vscode)
- [Setting up a Python project for GitHub Codespaces](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/setting-up-your-python-project-for-codespaces?apiVersion=2022-11-28)
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Using uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/)
