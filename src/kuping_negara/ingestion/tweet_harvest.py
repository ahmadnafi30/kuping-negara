"""Command-line orchestration for reproducible X data collection."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from kuping_negara.configuration import load_programs, select_programs
from kuping_negara.ingestion.browser import (
    build_tweet_harvest_environment,
    detect_browser_executable,
)
from kuping_negara.ingestion.queries import (
    TWEET_HARVEST_VERSION as TWEET_HARVEST_VERSION,
)
from kuping_negara.ingestion.queries import (
    build_output_name,
    build_search_query,
    build_tweet_harvest_command,
    parse_collection_window,
)
from kuping_negara.ingestion.storage import CollectionError, finalize_output
from kuping_negara.ingestion.validation import sha256_file, validate_collection
from kuping_negara.paths import (
    DEFAULT_CONFIG_PATH,
    JAKARTA_TIMEZONE,
    find_repository_root,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect X posts for Kuping Negara with Tweet Harvest."
    )
    parser.add_argument("--from-date", required=True, help="Start date: DD-MM-YYYY")
    parser.add_argument("--to-date", required=True, help="End date: DD-MM-YYYY")
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run Tweet Harvest sequentially for selected government programs."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)

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
    except (OSError, ValueError, yaml.YAMLError) as error:
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
        return 0

    npx_executable = shutil.which("npx")
    if not npx_executable:
        print("Error: npx is not available. Install Node.js LTS.", file=sys.stderr)
        return 1

    try:
        browser_executable = detect_browser_executable(
            explicit_path=arguments.browser_executable
        )
        execution_environment = build_tweet_harvest_environment(
            repository_root=repository_root,
            browser_executable=browser_executable,
            collection_start=start,
            collection_end=end,
        )
    except (ValueError, CollectionError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if browser_executable is not None:
        print(f"Browser runtime: {browser_executable}")
    else:
        print("Browser runtime: Playwright-managed Chromium")

    now = datetime.now(JAKARTA_TIMEZONE)
    run_id = now.strftime("%Y%m%dT%H%M%S%z")
    collected_paths: list[Path] = []

    print("Enter auth_token only in each hidden Tweet Harvest prompt.")
    for index, (program_id, display_name, output_name, command) in enumerate(
        plans, start=1
    ):
        print(f"\n[{index}/{len(plans)}] Collecting {display_name}")
        command[0] = npx_executable
        completed_process = subprocess.run(
            command,
            cwd=repository_root,
            env=execution_environment,
            check=False,
        )
        if completed_process.returncode != 0:
            print(
                f"Error: Tweet Harvest failed for {program_id} "
                f"with exit code {completed_process.returncode}.",
                file=sys.stderr,
            )
            return completed_process.returncode

        try:
            candidate = repository_root / "tweets-data" / f"{output_name}.csv"
            validation = validate_collection(
                candidate, start=start, end=end, limit=arguments.limit
            )
            destination = finalize_output(
                repository_root=repository_root,
                output_name=output_name,
                program_id=program_id,
                run_id=run_id,
                collected_date=now.date(),
            )
        except CollectionError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        (destination.parent / "collection.json").write_text(
            json.dumps(
                {
                    "query": build_search_query(
                        selected_programs[program_id]["keywords"]
                    ),
                    "from_date": start.isoformat(),
                    "to_date": end.isoformat(),
                    "limit": arguments.limit,
                    "config_sha256": sha256_file(config_path),
                    "input_sha256": sha256_file(destination),
                    "validation": validation,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        collected_paths.append(destination)
        print(f"Saved: {destination.relative_to(repository_root)}")

    print(f"\nCollection complete: {len(collected_paths)} dataset(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
