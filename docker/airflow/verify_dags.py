"""Validate DAG imports, schedules, dependencies and timezone inside Airflow."""

import runpy
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from airflow.models import DagBag
from airflow.sdk.api.datamodels._generated import DagRun

bag = DagBag(dag_folder="/opt/airflow/dags")
assert not bag.import_errors, bag.import_errors
expected = {
    "mbg": "59 23 * * 1",
    "ckg": "59 23 * * 2",
    "kopdes_merah_putih": "59 23 * * 3",
    "sekolah_rakyat": "59 23 * * 4",
}
assert len(bag.dags) == 4
for program, cron in expected.items():
    dag = bag.dags[f"x_collect_preprocess_{program}"]
    assert dag.schedule == cron
    assert dag.timezone.name == "Asia/Jakarta"
    assert not dag.catchup
    assert dag.max_active_runs == 1
    assert dag.is_paused_upon_creation
    assert set(dag.task_ids) == {"collect", "preprocess"}
    assert dag.get_task("collect").downstream_task_ids == {"preprocess"}
    assert dag.get_task("collect").pool == "x_collection"
print(
    "Four DAGs verified: Jakarta 23:59 cron, collect -> preprocess, paused, no catchup."
)

# SDK enum stringification is not the literal 'scheduled'. Delayed workers
# must use the interval end, while manual runs use their trigger timestamp.
invoke = runpy.run_path("/opt/airflow/dags/x_collection.py")["_run_pipeline"]
run_type = DagRun.model_fields["run_type"].annotation
interval_end = datetime.fromisoformat("2026-10-12T23:59:00+07:00")
trigger_time = datetime.fromisoformat("2026-10-13T04:00:00+07:00")
for kind, expected_time in [
    (run_type.SCHEDULED, interval_end),
    (run_type.MANUAL, trigger_time),
]:
    context = {
        "dag": SimpleNamespace(dag_id="verify"),
        "dag_run": SimpleNamespace(
            run_type=kind, run_after=trigger_time, run_id="verify"
        ),
        "data_interval_end": interval_end,
    }
    with (
        patch.dict(
            invoke.__globals__, {"get_current_context": lambda context=context: context}
        ),
        patch("subprocess.run") as runner,
    ):
        runner.return_value.stdout = '{"raw_path": "example.csv"}'
        assert invoke("collect", "--program", "mbg") == {"raw_path": "example.csv"}
        command = runner.call_args.args[0]
        assert command[command.index("--scheduled-at") + 1] == expected_time.isoformat()
print(
    "SDK context verified: delayed tasks preserve dates; manual runs use trigger time."
)
