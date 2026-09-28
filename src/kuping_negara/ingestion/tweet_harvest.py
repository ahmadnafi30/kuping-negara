"""Orchestrate reproducible X data collection with Tweet Harvest."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

TWEET_HARVEST_VERSION = "2.7.1"
DEFAULT_CONFIG_PATH = Path("configs/keywords/programs.example.yaml")
JAKARTA_TIMEZONE = ZoneInfo("Asia/Jakarta")
BROWSER_EXECUTABLE_ENV = "KUPING_NEGARA_BROWSER_EXECUTABLE"
BROWSER_HOOK_PATH = Path("scripts/tweet_harvest_browser_hook.cjs")


def execute_collection(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
    non_interactive: bool,
) -> None:
    """Run a bounded crawler and stop its browser process tree on timeout.

    Unattended upstream output is discarded because it is not under our
    control. Only token-free status messages are emitted by the wrapper.
    """
    options: dict[str, Any] = {}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL if non_interactive else None,
        stdout=subprocess.DEVNULL if non_interactive else None,
        stderr=subprocess.DEVNULL if non_interactive else None,
        **options,
    )
    try:
        return_code = process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        # Sandboxed Windows environments can reject taskkill. Always stop
        # the direct child too, so cleanup cannot wait indefinitely.
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        if isinstance(error, KeyboardInterrupt):
            raise
        raise CollectionError("crawler timed out") from error
    if return_code != 0:
        raise CollectionError(f"crawler exited with status {return_code}")


class CollectionError(RuntimeError):
    """Raised when Tweet Harvest cannot produce a valid raw dataset."""


def find_cached_tweet_harvest(
    *,
    explicit_path: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    """Find a locally installed bin.js with the exact pinned package version.

    Running Node directly avoids npm startup/network checks and Windows batch
    argument forwarding when an appropriate cached package is already present.
    """
    current_environment = os.environ if environment is None else environment
    if explicit_path is not None:
        candidates = [explicit_path.expanduser().resolve()]
    else:
        cache_roots: list[Path] = []
        configured_cache = current_environment.get("NPM_CONFIG_CACHE")
        if configured_cache:
            cache_roots.append(Path(configured_cache))
        local_appdata = current_environment.get("LOCALAPPDATA")
        if local_appdata:
            cache_roots.append(Path(local_appdata) / "npm-cache")
        cache_roots.append(Path.home() / ".npm")
        candidates = []
        for cache_root in cache_roots:
            candidates.extend(
                sorted(cache_root.glob("_npx/*/node_modules/tweet-harvest/dist/bin.js"))
            )
    for candidate in candidates:
        try:
            package = json.loads(
                (candidate.parent.parent / "package.json").read_text(encoding="utf-8")
            )
            if candidate.is_file() and package.get("version") == TWEET_HARVEST_VERSION:
                return candidate.resolve()
        except (OSError, ValueError):
            continue
    if explicit_path is not None:
        raise ValueError("tweet-harvest-bin must belong to Tweet Harvest 2.7.1")
    return None


def build_search_query(keywords: Sequence[str]) -> str:
    """Build an X search query for Indonesian posts from configured keywords."""
    cleaned_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
    if not cleaned_keywords:
        raise ValueError("at least one keyword is required")

    query_terms = []
    for keyword in cleaned_keywords:
        escaped_keyword = keyword.replace(chr(34), chr(92) + chr(34))
        query_terms.append(
            f'"{escaped_keyword}"'
            if any(character.isspace() for character in keyword)
            else escaped_keyword
        )
    return f"({' OR '.join(query_terms)})"


def parse_collection_window(from_date: str, to_date: str) -> tuple[date, date]:
    """Parse Tweet Harvest dates and require an increasing date window."""
    try:
        start = datetime.strptime(from_date, "%d-%m-%Y").date()
        end = datetime.strptime(to_date, "%d-%m-%Y").date()
    except ValueError as error:
        raise ValueError("dates must use DD-MM-YYYY format") from error

    if start > end:
        raise ValueError("from-date must be earlier than or equal to to-date")
    return start, end


def select_programs(
    programs: Mapping[str, Mapping[str, Any]], requested: Sequence[str]
) -> dict[str, Mapping[str, Any]]:
    """Return requested programs while preserving configuration order."""
    if not requested:
        return dict(programs)

    unknown_programs = sorted(set(requested) - set(programs))
    if unknown_programs:
        choices = ", ".join(programs)
        unknown = ", ".join(unknown_programs)
        raise ValueError(f"unknown program: {unknown}. Available programs: {choices}")

    requested_set = set(requested)
    return {
        program_id: config
        for program_id, config in programs.items()
        if program_id in requested_set
    }


def build_output_name(program_id: str, start: date, end: date) -> str:
    """Create a deterministic Tweet Harvest staging filename."""
    return f"{program_id}_{start.isoformat()}_{end.isoformat()}"


def build_tweet_harvest_command(
    *,
    query: str,
    from_date: str,
    to_date: str,
    limit: int,
    tab: str,
    output_name: str,
) -> list[str]:
    """Build a token-free Tweet Harvest command for interactive execution."""
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    normalized_tab = tab.upper()
    if normalized_tab not in {"LATEST", "TOP"}:
        raise ValueError("tab must be LATEST or TOP")

    inclusive_end = datetime.strptime(to_date, "%d-%m-%Y").date()
    exclusive_until = (inclusive_end + timedelta(days=1)).strftime("%d-%m-%Y")

    return [
        "npx",
        "-y",
        f"tweet-harvest@{TWEET_HARVEST_VERSION}",
        "-s",
        query,
        "-f",
        from_date,
        "--to",
        exclusive_until,
        "-l",
        str(limit),
        "--tab",
        normalized_tab,
        "-o",
        output_name,
        "-e",
        "csv",
    ]


def find_repository_root(starting_points: Sequence[Path]) -> Path:
    """Find the project root by walking upward from candidate paths."""
    for starting_point in starting_points:
        resolved_path = starting_point.resolve()
        current_directory = (
            resolved_path if resolved_path.is_dir() else resolved_path.parent
        )
        for candidate in (current_directory, *current_directory.parents):
            if (candidate / "pyproject.toml").is_file() and (
                candidate / "src" / "kuping_negara"
            ).is_dir():
                return candidate

    raise ValueError("Kuping Negara repository root could not be located")


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
    hook_path = (repository_root / BROWSER_HOOK_PATH).resolve()
    if not hook_path.is_file():
        raise CollectionError(f"Tweet Harvest browser hook not found: {hook_path}")

    require_option = f'--require="{hook_path.as_posix()}"'
    existing_options = environment.get("NODE_OPTIONS", "").strip()
    environment["NODE_OPTIONS"] = " ".join(
        option for option in (existing_options, require_option) if option
    )
    if browser_executable is not None:
        environment[BROWSER_EXECUTABLE_ENV] = str(browser_executable.resolve())
    return environment


def load_programs(config_path: Path) -> dict[str, Mapping[str, Any]]:
    """Load and validate program keyword configuration from YAML."""
    if not config_path.is_file():
        raise ValueError(f"keyword configuration not found: {config_path}")

    with config_path.open(encoding="utf-8") as config_file:
        document = yaml.safe_load(config_file)

    programs = document.get("programs") if isinstance(document, dict) else None
    if not isinstance(programs, dict) or not programs:
        raise ValueError("keyword configuration must define non-empty programs")

    for program_id, config in programs.items():
        keywords = config.get("keywords") if isinstance(config, dict) else None
        if not isinstance(keywords, list) or not keywords:
            raise ValueError(f"program {program_id} must define keywords")
    return programs


def finalize_output(
    *,
    repository_root: Path,
    output_name: str,
    program_id: str,
    run_id: str,
    collected_date: date,
    staging_root: Path | None = None,
) -> Path:
    """Move a completed staging CSV into the immutable raw data zone."""
    source = (staging_root or repository_root) / "tweets-data" / f"{output_name}.csv"
    if not source.is_file() or source.stat().st_size == 0:
        raise CollectionError(
            f"Tweet Harvest did not produce a non-empty file: {source}"
        )

    with source.open(encoding="utf-8-sig", newline="") as source_file:
        populated_rows = (
            row for row in csv.reader(source_file) if any(cell.strip() for cell in row)
        )
        header = next(populated_rows, None)
        first_data_row = next(populated_rows, None)

    if header is None or first_data_row is None:
        raise CollectionError(
            f"Tweet Harvest produced a CSV with no tweet rows: {source}"
        )

    destination_directory = (
        repository_root
        / "data"
        / "raw"
        / "x"
        / f"collected_date={collected_date.isoformat()}"
        / f"program={program_id}"
        / f"run_id={run_id}"
    )
    destination_directory.mkdir(parents=True, exist_ok=False)
    destination = destination_directory / source.name
    shutil.move(str(source), destination)
    return destination


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect X posts for Kuping Negara with Tweet Harvest."
    )
    parser.add_argument("--from-date", help="Start date: DD-MM-YYYY")
    parser.add_argument("--to-date", help="End date: DD-MM-YYYY")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--tweet-harvest-bin",
        type=Path,
        help="Installed Tweet Harvest 2.7.1 dist/bin.js; npm cache auto-detected",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Use X_AUTH_TOKEN from the environment, without terminal prompts",
    )
    parser.add_argument("--limit", type=int, default=50, help="Posts per program")
    parser.add_argument(
        "--program",
        action="append",
        default=[],
        help="Program ID. Repeat the option to select multiple programs.",
    )
    parser.add_argument(
        "--tab", choices=["LATEST", "TOP"], default="LATEST", help="X search tab"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Program keyword YAML relative to the repository root",
    )
    parser.add_argument(
        "--browser-executable",
        type=Path,
        help="Chrome or Edge executable. Auto-detected on Windows when omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the collection plan without opening X or requesting a token",
    )
    return parser


def run_collection(argv: Sequence[str] | None = None) -> tuple[int, list[Path]]:
    """Run Tweet Harvest sequentially for selected government programs."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)

    if bool(arguments.from_date) != bool(arguments.to_date):
        parser.error("provide both --from-date and --to-date, or neither")
    if arguments.lookback_days <= 0 or arguments.attempts <= 0:
        parser.error("lookback-days and attempts must be greater than zero")
    if arguments.retry_delay < 0 or arguments.timeout <= 0:
        parser.error("retry-delay must be non-negative and timeout positive")
    if not arguments.from_date:
        today = datetime.now(JAKARTA_TIMEZONE).date()
        arguments.from_date = (
            today - timedelta(days=arguments.lookback_days - 1)
        ).strftime("%d-%m-%Y")
        arguments.to_date = today.strftime("%d-%m-%Y")

    try:
        repository_root = find_repository_root([Path.cwd(), Path(__file__).resolve()])
        start, end = parse_collection_window(arguments.from_date, arguments.to_date)
        config_path = (
            arguments.config
            if arguments.config.is_absolute()
            else repository_root / arguments.config
        )
        programs = load_programs(config_path)
        selected_programs = select_programs(programs, arguments.program)
        if arguments.limit <= 0:
            raise ValueError("limit must be greater than zero")
    except ValueError as error:
        parser.error(str(error))

    plans: list[tuple[str, str, str, list[str]]] = []
    for program_id, config in selected_programs.items():
        query = build_search_query(config["keywords"])
        output_name = build_output_name(program_id, start, end)
        command = build_tweet_harvest_command(
            query=query,
            from_date=arguments.from_date,
            to_date=arguments.to_date,
            limit=arguments.limit,
            tab=arguments.tab,
            output_name=output_name,
        )
        plans.append((program_id, config["display_name"], output_name, command))

    exclusive_until = (end + timedelta(days=1)).strftime("%d-%m-%Y")
    print(f"Programs: {len(plans)} | Limit per program: {arguments.limit}")
    print(
        f"Requested window: {arguments.from_date} through {arguments.to_date} inclusive"
    )
    print(f"Tweet Harvest until: {exclusive_until} (exclusive)")
    for program_id, display_name, _, command in plans:
        query = command[command.index("-s") + 1]
        print(f"- {program_id}: {display_name} | {query}")

    if arguments.dry_run:
        print("Dry run complete. No token requested and no data collected.")
        return 0, []

    if arguments.non_interactive and not os.environ.get("X_AUTH_TOKEN", "").strip():
        print("Error: --non-interactive requires X_AUTH_TOKEN.", file=sys.stderr)
        return 1, []

    try:
        cached_bin = find_cached_tweet_harvest(
            explicit_path=arguments.tweet_harvest_bin
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1, []
    node_executable = shutil.which("node")
    npx_executable = shutil.which("npx")
    if not node_executable or (cached_bin is None and not npx_executable):
        print("Error: Node.js LTS with node/npx is required.", file=sys.stderr)
        return 1, []

    try:
        browser_executable = detect_browser_executable(
            explicit_path=arguments.browser_executable
        )
        execution_environment = build_tweet_harvest_environment(
            repository_root=repository_root,
            browser_executable=browser_executable,
        )
    except (ValueError, CollectionError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1, []

    if browser_executable is not None:
        print(f"Browser runtime: {browser_executable}")
    else:
        print("Browser runtime: Playwright-managed Chromium")

    now = datetime.now(JAKARTA_TIMEZONE)
    run_id = now.strftime("%Y%m%dT%H%M%S%f%z")
    collected_paths: list[Path] = []

    if arguments.non_interactive:
        execution_environment["KUPING_NEGARA_NON_INTERACTIVE"] = "1"
        print("Unattended collection: token loaded from the environment.")
    else:
        execution_environment.pop("X_AUTH_TOKEN", None)
        execution_environment.pop("KUPING_NEGARA_NON_INTERACTIVE", None)
        print("Enter auth_token only in each hidden Tweet Harvest prompt.")
    for index, (program_id, display_name, output_name, command) in enumerate(
        plans, start=1
    ):
        print(f"\n[{index}/{len(plans)}] Collecting {display_name}")
        if cached_bin is not None:
            command = [node_executable, str(cached_bin), *command[3:]]
        else:
            command[0] = npx_executable
        destination = None
        for attempt in range(1, arguments.attempts + 1):
            # Each attempt has a fresh cwd, so a failed run cannot reuse a
            # previous CSV or collide with another running collection.
            staging_root = (
                repository_root
                / "tweets-data"
                / "runs"
                / run_id
                / program_id
                / f"attempt={attempt}"
            )
            staging_root.mkdir(parents=True, exist_ok=False)
            try:
                execute_collection(
                    command,
                    cwd=staging_root,
                    environment=execution_environment,
                    timeout=arguments.timeout,
                    non_interactive=arguments.non_interactive,
                )
                destination = finalize_output(
                    repository_root=repository_root,
                    output_name=output_name,
                    program_id=program_id,
                    run_id=run_id,
                    collected_date=now.date(),
                    staging_root=staging_root,
                )
                break
            except (CollectionError, OSError, UnicodeError, csv.Error):
                # Do not expose upstream exception text that may contain
                # credentials or personal source data.
                print(
                    f"Collection failed: program={program_id} "
                    f"attempt={attempt}/{arguments.attempts}",
                    file=sys.stderr,
                )
                if attempt < arguments.attempts:
                    time.sleep(min(arguments.retry_delay * 2 ** (attempt - 1), 60))
        if destination is None:
            return 1, collected_paths
        with destination.open(encoding="utf-8-sig", newline="") as raw_file:
            record_count = sum(1 for _ in csv.DictReader(raw_file))
        (destination.parent / "ingestion_report.json").write_text(
            json.dumps(
                {
                    "source": "live_x",
                    "program_id": program_id,
                    "ingestion_run_id": run_id,
                    "rows": record_count,
                    "attempts_used": attempt,
                    "from_date": start.isoformat(),
                    "to_date": end.isoformat(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        collected_paths.append(destination)
        print(f"Saved: {destination.relative_to(repository_root)}")

    print(f"\nCollection complete: {len(collected_paths)} dataset(s).")
    return 0, collected_paths


def main(argv: Sequence[str] | None = None) -> int:
    """Run the standalone collector and propagate its exit status."""
    return run_collection(argv)[0]


if __name__ == "__main__":
    raise SystemExit(main())
