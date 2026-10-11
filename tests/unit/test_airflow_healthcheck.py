"""An HTTP 200 response must not hide a failed component inside one container."""

import io
import json
import runpy

import pytest


def test_ui_available_with_dead_scheduler_is_unhealthy(monkeypatch):
    check = runpy.run_path("docker/airflow/healthcheck.py")["main"]
    payload = {
        "metadatabase": {"status": "healthy"},
        "scheduler": {"status": "unhealthy"},
        "dag_processor": {"status": "healthy"},
        "triggerer": {"status": "healthy"},
    }

    def available_ui(*args, **kwargs):
        return io.StringIO(json.dumps(payload))

    monkeypatch.setitem(check.__globals__, "urlopen", available_ui)
    with pytest.raises(SystemExit, match="scheduler"):
        check()
