from kuping_negara import PROJECT_NAME, __version__
from kuping_negara.healthcheck import dependency_versions, project_summary


def test_project_summary_matches_package_metadata() -> None:
    assert project_summary() == {"name": PROJECT_NAME, "version": __version__}


def test_healthcheck_reports_all_required_dependencies() -> None:
    versions = dependency_versions()
    assert set(versions) == {"pandas", "scikit-learn", "jupyterlab"}

