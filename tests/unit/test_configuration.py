from pathlib import Path

import pytest
import yaml

from kuping_negara.configuration import load_programs


@pytest.mark.parametrize(
    ("program_id", "config", "message"),
    [
        ("../mbg", {"display_name": "MBG", "keywords": ["mbg"]}, "snake_case"),
        ("mbg", {"keywords": ["mbg"]}, "display_name"),
        ("mbg", {"display_name": "MBG", "keywords": [42]}, "string keywords"),
        ("mbg", {"display_name": "MBG", "keywords": [" "]}, "string keywords"),
        ("mbg", {"display_name": "MBG", "keywords": []}, "string keywords"),
        ("mbg", "not a mapping", "mapping"),
        (
            "mbg",
            {"display_name": "MBG", "keywords": ["mbg"], "collection_day": "today"},
            "collection_day",
        ),
    ],
)
def test_config_rejects_invalid_program_values(
    tmp_path: Path, program_id: str, config: object, message: str
) -> None:
    path = tmp_path / "programs.yaml"
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "programs": {program_id: config}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        load_programs(path)


@pytest.mark.parametrize("version", [None, 2, "1", True, 1.0])
def test_config_rejects_unsupported_schema_version(
    tmp_path: Path, version: object
) -> None:
    path = tmp_path / "programs.yaml"
    path.write_text(
        yaml.safe_dump({"schema_version": version, "programs": {}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="schema_version"):
        load_programs(path)


def test_config_normalizes_values_and_preserves_program_order(tmp_path: Path) -> None:
    path = tmp_path / "programs.yaml"
    path.write_text(
        "schema_version: 1\nprograms:\n"
        "  mbg:\n    display_name: ' MBG '\n    keywords: [' mbg ']\n"
        "  ckg:\n    display_name: CKG\n    keywords: [ckg]\n",
        encoding="utf-8",
    )
    programs = load_programs(path)
    assert list(programs) == ["mbg", "ckg"]
    assert programs["mbg"] == {"display_name": "MBG", "keywords": ["mbg"]}
