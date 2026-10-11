"""Shared, validated program configuration for collection and preprocessing."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import yaml

PROGRAM_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


class ProgramConfig(TypedDict):
    """Validated fields used by the data pipeline."""

    display_name: str
    keywords: list[str]
    collection_day: NotRequired[str]


def load_programs(config_path: Path) -> dict[str, ProgramConfig]:
    """Load version 1 keyword YAML and reject invalid values before execution."""
    if not config_path.is_file():
        raise ValueError(f"keyword configuration not found: {config_path}")

    with config_path.open(encoding="utf-8") as config_file:
        document = yaml.safe_load(config_file)

    if (
        not isinstance(document, dict)
        or type(document.get("schema_version")) is not int
        or document["schema_version"] != 1
    ):
        raise ValueError("keyword configuration must use schema_version: 1")
    programs = document.get("programs")
    if not isinstance(programs, dict) or not programs:
        raise ValueError("keyword configuration must define non-empty programs")

    validated: dict[str, ProgramConfig] = {}
    for program_id, config in programs.items():
        if not isinstance(program_id, str) or not PROGRAM_ID_PATTERN.fullmatch(
            program_id
        ):
            raise ValueError("program IDs must use lower-case snake_case")
        if not isinstance(config, dict):
            raise ValueError(f"program {program_id} must define a mapping")
        display_name = config.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError(f"program {program_id} must define a display_name")
        keywords = config.get("keywords")
        if (
            not isinstance(keywords, list)
            or not keywords
            or any(
                not isinstance(value, str) or not value.strip() for value in keywords
            )
        ):
            raise ValueError(
                f"program {program_id} must define non-empty string keywords"
            )

        program: ProgramConfig = {
            "display_name": display_name.strip(),
            "keywords": [value.strip() for value in keywords],
        }
        if "collection_day" in config:
            day = config["collection_day"]
            if day not in (
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ):
                raise ValueError(f"program {program_id} has an invalid collection_day")
            program["collection_day"] = day
        validated[program_id] = program
    return validated


def select_programs(
    programs: Mapping[str, Mapping[str, Any]], requested: Sequence[str]
) -> dict[str, Mapping[str, Any]]:
    """Return selected programs in configuration order, or all when omitted."""
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
