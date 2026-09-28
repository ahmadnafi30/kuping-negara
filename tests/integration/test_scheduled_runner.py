from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell") if os.name == "nt" else None
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="Windows runner")


def _run_wrapper(root: Path, *options: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.pop("X_AUTH_TOKEN", None)
    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PROJECT_ROOT / "scripts/run_ingestion.ps1"),
            "-RepositoryRoot",
            str(root),
            "-PythonExecutable",
            sys.executable,
            *options,
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )


@pytest.mark.parametrize("child_exit_code", [0, 7])
def test_windows_runner_loads_secret_privately_and_returns_child_status(
    tmp_path: Path, child_exit_code: int
) -> None:
    if shutil.which("node") is None:
        pytest.skip("Runner requires Node.js")
    (tmp_path / "src").mkdir()
    token = "private_test_token"
    (tmp_path / ".env").write_text(f'X_AUTH_TOKEN="{token}"\n', encoding="utf-8")
    (tmp_path / "src/ingest_data.py").write_text(
        "import json, os, sys\n"
        f"assert os.environ['X_AUTH_TOKEN'] == {token!r}\n"
        "print(json.dumps(sys.argv[1:]))\n"
        f"sys.exit({child_exit_code})\n",
        encoding="utf-8",
    )
    result = _run_wrapper(tmp_path, "-Program", "mbg")
    assert result.returncode == child_exit_code, result.stderr
    logs = list((tmp_path / "logs").glob("*.log"))
    assert len(logs) == 1
    log = logs[0].read_text(encoding="utf-8-sig")
    assert token not in result.stdout + result.stderr + log
    assert '"--non-interactive"' in log
    assert '"--preprocess"' in log
    assert '"--program", "mbg"' in log
    assert f"exit_code={child_exit_code}" in log


def test_windows_runner_dry_run_needs_no_token(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/ingest_data.py").write_text(
        "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    result = _run_wrapper(tmp_path, "-DryRun")
    assert result.returncode == 0, result.stderr
    arguments = json.loads(
        next(line for line in result.stdout.splitlines() if line.startswith("["))
    )
    assert "--dry-run" in arguments
    assert "--non-interactive" not in arguments
