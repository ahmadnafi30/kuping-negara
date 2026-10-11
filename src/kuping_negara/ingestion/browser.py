"""System-browser detection and the Tweet Harvest child environment."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

from kuping_negara.ingestion.storage import CollectionError

BROWSER_EXECUTABLE_ENV = "KUPING_NEGARA_BROWSER_EXECUTABLE"
BROWSER_HOOK_PATH = Path("scripts/tweet_harvest_browser_hook.cjs")


def detect_browser_executable(
    *,
    explicit_path: Path | None,
    environment: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> Path | None:
    """Find a supported system browser for Tweet Harvest's Playwright runtime."""
    current_environment = os.environ if environment is None else environment

    configured_path = explicit_path
    if configured_path is None and current_environment.get(BROWSER_EXECUTABLE_ENV):
        configured_path = Path(current_environment[BROWSER_EXECUTABLE_ENV])

    if configured_path is not None:
        resolved_path = configured_path.expanduser().resolve()
        if not resolved_path.is_file():
            raise ValueError(f"browser executable not found: {resolved_path}")
        return resolved_path

    current_platform = sys.platform if platform is None else platform
    candidates: list[Path] = []
    if current_platform == "win32":
        locations = [
            ("PROGRAMFILES", Path("Google/Chrome/Application/chrome.exe")),
            ("PROGRAMFILES(X86)", Path("Google/Chrome/Application/chrome.exe")),
            ("LOCALAPPDATA", Path("Google/Chrome/Application/chrome.exe")),
            ("PROGRAMFILES", Path("Microsoft/Edge/Application/msedge.exe")),
            ("PROGRAMFILES(X86)", Path("Microsoft/Edge/Application/msedge.exe")),
        ]
        for variable, relative_path in locations:
            base_directory = current_environment.get(variable)
            if base_directory:
                candidates.append(Path(base_directory) / relative_path)
    else:
        for executable_name in ("google-chrome", "chromium", "chromium-browser"):
            executable = shutil.which(executable_name)
            if executable:
                candidates.append(Path(executable))

    return next(
        (candidate.resolve() for candidate in candidates if candidate.is_file()),
        None,
    )


def build_tweet_harvest_environment(
    *,
    repository_root: Path,
    browser_executable: Path | None,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an isolated child environment with an optional browser fallback."""
    environment = dict(os.environ if base_environment is None else base_environment)
    if browser_executable is None:
        return environment

    hook_path = (repository_root / BROWSER_HOOK_PATH).resolve()
    if not hook_path.is_file():
        raise CollectionError(f"Tweet Harvest browser hook not found: {hook_path}")

    require_option = f'--require="{hook_path.as_posix()}"'
    existing_options = environment.get("NODE_OPTIONS", "").strip()
    environment["NODE_OPTIONS"] = " ".join(
        option for option in (existing_options, require_option) if option
    )
    environment[BROWSER_EXECUTABLE_ENV] = str(browser_executable.resolve())
    return environment
