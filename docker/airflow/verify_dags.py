"""Validate DAG imports, schedules, dependencies and timezone inside Airflow."""

from airflow.models import DagBag

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
