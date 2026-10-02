"""Ensure historical collection windows are complete and do not overlap."""

from datetime import date

import pytest

from kuping_negara.training.bootstrap import build_collection_plan


def test_plan_covers_partial_final_window_for_each_program():
    jobs = build_collection_plan(
        ["mbg", "ckg"], date(2026, 9, 1), date(2026, 9, 16), 7
    )
    assert [(job.program_id, job.from_date, job.to_date) for job in jobs] == [
        ("mbg", date(2026, 9, 1), date(2026, 9, 7)),
        ("mbg", date(2026, 9, 8), date(2026, 9, 14)),
        ("mbg", date(2026, 9, 15), date(2026, 9, 16)),
        ("ckg", date(2026, 9, 1), date(2026, 9, 7)),
        ("ckg", date(2026, 9, 8), date(2026, 9, 14)),
        ("ckg", date(2026, 9, 15), date(2026, 9, 16)),
    ]


@pytest.mark.parametrize("window_days", [0, -1])
def test_plan_rejects_nonpositive_window(window_days):
    with pytest.raises(ValueError, match="window-days"):
        build_collection_plan(["mbg"], date(2026, 9, 1), date(2026, 9, 2), window_days)

