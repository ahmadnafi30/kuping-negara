"""Quality gate acceptance cases at the actual holdout boundary."""

import pytest

from kuping_negara.training.automation import evaluate, stage


def candidate(score, overlap=0):
    return {
        "registry": None,
        "deployment_approved": False,
        "split": {"group_overlap": overlap, "test_rows": 80},
        "test_metrics": {"test_macro_f1": score},
        "source_commit": "test-commit",
        "lineage": {"dataset_sha256": "test-snapshot"},
        "best_run_id": "test-run",
    }


@pytest.mark.parametrize(
    ("score", "passed"), [(0.7476383, False), (0.75, True), (0.8, True)]
)
def test_holdout_acceptance_boundary(score, passed):
    decision = evaluate(candidate(score))
    assert decision["passed"] is passed
    assert decision["minimum"] == 0.75


def test_leakage_cannot_pass_even_with_perfect_score():
    with pytest.raises(ValueError, match="leakage"):
        evaluate(candidate(1.0, overlap=1))


def test_cannot_stage_by_editing_a_rejected_decision():
    pytest.importorskip("mlflow")
    summary = candidate(0.7476383)
    forged = {**evaluate(summary), "passed": True}
    with pytest.raises(ValueError, match="passing quality gate"):
        stage(summary, forged, "sentiment-pilot", "invalid")
