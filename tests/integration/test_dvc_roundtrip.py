"""Exercise real DVC hashes, remote storage and recovery without private data."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_two_git_versions_restore_from_local_dvc_remote(tmp_path):
    pytest.importorskip(
        "dvc", reason="Install the data-versioning extra for DVC integration"
    )
    if not shutil.which("git"):
        pytest.skip("Git executable required")
    repository = tmp_path / "repo"
    repository.mkdir()

    def run(*args):
        result = subprocess.run(
            args,
            cwd=repository,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return result.stdout

    def git(*args):
        return run(
            "git",
            "-c",
            "user.name=DVC Test",
            "-c",
            "user.email=dvc-test@example.invalid",
            *args,
        )

    def dvc(*args):
        return run(sys.executable, "-m", "dvc", *args)

    git("init")
    dvc("init")
    dvc("config", "core.analytics", "false")
    dvc("config", "cache.type", "copy")
    dvc("remote", "add", "--local", "--default", "test-store", str(tmp_path / "remote"))
    (repository / "data").mkdir()
    dataset = repository / "data/posts.csv"
    v1 = b"id,text\n1,initial\n"
    v2 = v1 + b"2,additional\n"
    dataset.write_bytes(v1)
    dvc("add", "data/posts.csv")
    dvc("push")
    git("add", ".dvc", ".dvcignore", "data/.gitignore", "data/posts.csv.dvc")
    git("commit", "-m", "data v1")
    git("tag", "v1")
    dataset.write_bytes(v2)
    dvc("add", "data/posts.csv")
    dvc("push")
    git("add", "data/posts.csv.dvc")
    git("commit", "-m", "data v2")
    git("tag", "v2")
    diff = json.loads(dvc("diff", "v1", "v2", "--json"))
    assert [Path(item["path"]).as_posix() for item in diff["modified"]] == [
        "data/posts.csv"
    ]
    assert json.loads(dvc("status", "--json")) == {}
    assert git("ls-files", "data/posts.csv").strip() == ""
    # Use a fresh empty cache so recovery must fetch objects from the remote.
    dvc("config", "--local", "cache.dir", str(tmp_path / "empty-cache"))
    dataset.unlink()
    for tag, expected in [("v1", v1), ("v2", v2)]:
        git("checkout", tag)
        dvc("pull")
        assert dataset.read_bytes() == expected
