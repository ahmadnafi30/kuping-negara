"""Small environment check used locally, in Codespaces, and in CI."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from kuping_negara import PROJECT_NAME, __version__

REQUIRED_DISTRIBUTIONS = ("pandas", "scikit-learn", "jupyterlab")


def dependency_versions() -> dict[str, str | None]:
    """Return installed versions for the minimum development dependencies."""
    result: dict[str, str | None] = {}
    for distribution in REQUIRED_DISTRIBUTIONS:
        try:
            result[distribution] = version(distribution)
        except PackageNotFoundError:
            result[distribution] = None
    return result


def project_summary() -> dict[str, str]:
    """Return stable project metadata for smoke tests and diagnostics."""
    return {"name": PROJECT_NAME, "version": __version__}


def main() -> int:
    """Print a readable environment report and return a process status code."""
    summary = project_summary()
    print(f"{summary['name']} v{summary['version']}")

    missing: list[str] = []
    for distribution, installed_version in dependency_versions().items():
        if installed_version is None:
            missing.append(distribution)
            print(f"[MISSING] {distribution}")
        else:
            print(f"[OK] {distribution}=={installed_version}")

    if missing:
        print("Install dependencies with: python -m pip install -r requirements.txt")
        return 1

    print("Environment is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
