from __future__ import annotations

from pathlib import Path

import pytest

from kuping_negara.ingestion.tweet_harvest import (
    CollectionError,
    build_output_name,
    build_search_query,
    build_tweet_harvest_environment,
    build_tweet_harvest_command,
    detect_browser_executable,
    find_repository_root,
    finalize_output,
    load_programs,
    main,
    parse_collection_window,
    select_programs,
    validate_staging_window,
)


PROGRAMS = {
    "mbg": {
        "display_name": "Makan Bergizi Gratis",
        "keywords": ["mbg", "makan bergizi gratis"],
    },
    "ckg": {
        "display_name": "Cek Kesehatan Gratis",
        "keywords": ["ckg", "cek kesehatan gratis"],
    },
    "kopdes_merah_putih": {
        "display_name": "Koperasi Desa Merah Putih",
        "keywords": ["kopdes", "koperasi desa merah putih"],
    },
    "sekolah_rakyat": {
        "display_name": "Sekolah Rakyat",
        "keywords": ["sekolah rakyat"],
    },
}


def test_build_search_query_keeps_acronym_broad_and_quotes_phrase() -> None:
    query = build_search_query(["mbg", "makan bergizi gratis"])

    assert query == '(mbg OR "makan bergizi gratis")'


def test_build_search_query_does_not_filter_language_during_ingestion() -> None:
    query = build_search_query(["mbg"])

    assert "lang:" not in query


def test_parse_collection_window_rejects_decreasing_dates() -> None:
    with pytest.raises(ValueError, match="earlier"):
        parse_collection_window("22-09-2026", "21-09-2026")


def test_parse_collection_window_allows_single_inclusive_date() -> None:
    start, end = parse_collection_window("21-09-2026", "21-09-2026")

    assert start == end


def test_select_programs_defaults_to_all_configured_programs() -> None:
    selected = select_programs(PROGRAMS, [])

    assert list(selected) == [
        "mbg",
        "ckg",
        "kopdes_merah_putih",
        "sekolah_rakyat",
    ]


def test_select_programs_rejects_unknown_program() -> None:
    with pytest.raises(ValueError, match="unknown"):
        select_programs(PROGRAMS, ["unknown"])


def test_build_output_name_uses_program_and_iso_dates() -> None:
    start, end = parse_collection_window("14-09-2026", "21-09-2026")

    assert build_output_name("mbg", start, end) == "mbg_2026-09-14_2026-09-21"


def test_build_command_contains_collection_options_without_a_token() -> None:
    command = build_tweet_harvest_command(
        query='("sekolah rakyat")',
        from_date="14-09-2026",
        to_date="21-09-2026",
        limit=50,
        tab="LATEST",
        output_name="sekolah_rakyat_2026-09-14_2026-09-21",
    )

    assert command == [
        "npx",
        "-y",
        "tweet-harvest@2.7.1",
        "-s",
        '("sekolah rakyat")',
        "-f",
        "14-09-2026",
        "--to",
        "22-09-2026",
        "-l",
        "50",
        "--tab",
        "LATEST",
        "-o",
        "sekolah_rakyat_2026-09-14_2026-09-21",
        "-e",
        "csv",
    ]
    assert "-t" not in command
    assert "--token" not in command


def test_raw_destination_is_not_part_of_command_line() -> None:
    command = build_tweet_harvest_command(
        query='(ckg OR "cek kesehatan gratis")',
        from_date="14-09-2026",
        to_date="21-09-2026",
        limit=25,
        tab="TOP",
        output_name="ckg_2026-09-14_2026-09-21",
    )

    assert str(Path("data/raw")) not in " ".join(command)


def test_load_programs_reads_keyword_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / "programs.yaml"
    config_path.write_text(
        """
schema_version: 1
programs:
  mbg:
    display_name: Makan Bergizi Gratis
    keywords:
      - makan bergizi gratis
      - program mbg
""".strip(),
        encoding="utf-8",
    )

    programs = load_programs(config_path)

    assert programs["mbg"]["keywords"] == [
        "makan bergizi gratis",
        "program mbg",
    ]


def test_finalize_output_moves_csv_into_partitioned_raw_zone(tmp_path: Path) -> None:
    staging_directory = tmp_path / "tweets-data"
    staging_directory.mkdir()
    source = staging_directory / "mbg_2026-09-14_2026-09-21.csv"
    source.write_text("id_str,full_text\n1,contoh\n", encoding="utf-8")

    destination = finalize_output(
        repository_root=tmp_path,
        output_name="mbg_2026-09-14_2026-09-21",
        program_id="mbg",
        run_id="20260921T120000+0700",
        collected_date=parse_collection_window("21-09-2026", "22-09-2026")[0],
    )

    assert destination.relative_to(tmp_path).as_posix() == (
        "data/raw/x/collected_date=2026-09-21/program=mbg/"
        "run_id=20260921T120000+0700/mbg_2026-09-14_2026-09-21.csv"
    )
    assert destination.read_text(encoding="utf-8") == (
        "id_str,full_text\n1,contoh\n"
    )
    assert not source.exists()


def test_staging_window_uses_jakarta_local_date(tmp_path: Path) -> None:
    source = tmp_path / "posts.csv"
    source.write_text(
        "created_at,id_str\n"
        "Mon Sep 21 17:30:00 +0000 2026,1\n",
        encoding="utf-8",
    )
    start, end = parse_collection_window("22-09-2026", "22-09-2026")
    assert validate_staging_window(source, start=start, end=end) == 1


def test_staging_window_rejects_dates_outside_search(tmp_path: Path) -> None:
    source = tmp_path / "posts.csv"
    source.write_text(
        "created_at,id_str\n"
        "Fri Oct 02 12:00:00 +0000 2026,1\n",
        encoding="utf-8",
    )
    start, end = parse_collection_window("25-09-2026", "01-10-2026")
    with pytest.raises(CollectionError, match="outside"):
        validate_staging_window(source, start=start, end=end)


def test_finalize_output_rejects_csv_without_header_or_data_rows(
    tmp_path: Path,
) -> None:
    staging_directory = tmp_path / "tweets-data"
    staging_directory.mkdir()
    source = staging_directory / "mbg_2026-09-14_2026-09-21.csv"
    source.write_bytes(b"\r\n")

    with pytest.raises(CollectionError, match="no tweet rows"):
        finalize_output(
            repository_root=tmp_path,
            output_name="mbg_2026-09-14_2026-09-21",
            program_id="mbg",
            run_id="20260921T120000+0700",
            collected_date=parse_collection_window("21-09-2026", "22-09-2026")[
                0
            ],
        )

    assert source.exists()
    assert not (tmp_path / "data" / "raw" / "x").exists()


def test_dry_run_lists_every_program_without_creating_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config_directory = tmp_path / "configs" / "keywords"
    config_directory.mkdir(parents=True)
    config_path = config_directory / "programs.example.yaml"
    lines = ["schema_version: 1", "programs:"]
    for program_id, config in PROGRAMS.items():
        lines.extend(
            [
                f"  {program_id}:",
                f"    display_name: {config['display_name']}",
                "    keywords:",
                *[f"      - {keyword}" for keyword in config["keywords"]],
            ]
        )
    config_path.write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "--from-date",
            "14-09-2026",
            "--to-date",
            "21-09-2026",
            "--limit",
            "50",
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert all(program_id in output for program_id in PROGRAMS)
    assert "Requested window: 14-09-2026 through 21-09-2026 inclusive" in output
    assert "Tweet Harvest until: 22-09-2026" in output
    assert "Dry run complete" in output
    assert not (tmp_path / "tweets-data").exists()


def test_find_repository_root_from_nested_working_directory(tmp_path: Path) -> None:
    repository_root = tmp_path / "kuping-negara"
    config_directory = repository_root / "configs" / "keywords"
    nested_directory = repository_root / "src" / "kuping_negara" / "ingestion"
    config_directory.mkdir(parents=True)
    nested_directory.mkdir(parents=True)
    (repository_root / "pyproject.toml").write_text(
        "[project]\nname = 'kuping-negara'\n",
        encoding="utf-8",
    )
    (config_directory / "programs.example.yaml").write_text(
        "schema_version: 1\nprograms: {}\n",
        encoding="utf-8",
    )

    detected_root = find_repository_root([nested_directory])

    assert detected_root == repository_root


def test_detect_browser_executable_prefers_explicit_path(tmp_path: Path) -> None:
    browser = tmp_path / "browser.exe"
    browser.touch()

    detected = detect_browser_executable(
        explicit_path=browser,
        environment={},
        platform="win32",
    )

    assert detected == browser.resolve()


def test_detect_browser_executable_finds_windows_chrome(tmp_path: Path) -> None:
    program_files = tmp_path / "Program Files"
    chrome = program_files / "Google" / "Chrome" / "Application" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.touch()

    detected = detect_browser_executable(
        explicit_path=None,
        environment={"PROGRAMFILES": str(program_files)},
        platform="win32",
    )

    assert detected == chrome.resolve()


def test_build_environment_preloads_browser_hook_without_losing_node_options(
    tmp_path: Path,
) -> None:
    scripts_directory = tmp_path / "scripts"
    scripts_directory.mkdir()
    hook = scripts_directory / "tweet_harvest_browser_hook.cjs"
    hook.touch()
    browser = tmp_path / "chrome.exe"
    browser.touch()
    base_environment = {"NODE_OPTIONS": "--trace-warnings", "KEEP_ME": "yes"}

    environment = build_tweet_harvest_environment(
        repository_root=tmp_path,
        browser_executable=browser,
        base_environment=base_environment,
    )

    assert environment["KUPING_NEGARA_BROWSER_EXECUTABLE"] == str(browser.resolve())
    assert "--trace-warnings" in environment["NODE_OPTIONS"]
    assert f'--require="{hook.resolve().as_posix()}"' in environment["NODE_OPTIONS"]
    assert environment["KEEP_ME"] == "yes"
    assert environment is not base_environment
