"""Repository paths and defaults shared by command-line workflows."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_CONFIG_PATH = Path("configs/keywords/programs.example.yaml")
JAKARTA_TIMEZONE = ZoneInfo("Asia/Jakarta")


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
