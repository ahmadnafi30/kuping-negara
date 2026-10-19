"""Weekly X collection followed by preprocessing, using Jakarta calendar days."""

from __future__ import annotations

import json
import subprocess
from datetime import timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task

# Keep parsing independent of data files, secrets, Node, and project dependencies.
PROGRAM_SCHEDULES = {
    "mbg": "59 23 * * 1",
    "ckg": "59 23 * * 2",
    "kopdes_merah_putih": "59 23 * * 3",
    "sekolah_rakyat": "59 23 * * 4",
}


COLLECTION_LIMIT = 200


def _run_pipeline(action: str, *arguments: str) -> dict[str, str]:
    context = get_current_context()
    # For scheduled cron runs this is the current scheduled firing time, rather
    # than the beginning of the preceding weekly data interval. Manual runs use
    # their actual trigger timestamp, avoiding the previous cron's window.
    run = context["dag_run"]
    timestamp = (
        context["data_interval_end"] if run.run_type == "scheduled" else run.run_after
    )
    result = subprocess.run(
        [
            "/opt/kuping-negara/.venv/bin/python",
            "-m",
            "kuping_negara.orchestration.runtime",
            action,
            "--scheduled-at",
            timestamp.isoformat(),
            "--execution-id",
            f"{context['dag'].dag_id}:{run.run_id}",
            *arguments,
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=1100,
    )
    if result.returncode:
        try:
            message = json.loads(result.stderr).get("error")
        except (ValueError, AttributeError):
            message = None
        raise RuntimeError(
            message
            if isinstance(message, str)
            else "Pipeline failed; inspect the local data-quality audit"
        )
    return json.loads(result.stdout)


def build_program_dag(program_id: str, schedule: str):
    @dag(
        dag_id=f"x_collect_preprocess_{program_id}",
        schedule=schedule,
        start_date=pendulum.datetime(2026, 10, 1, tz="Asia/Jakarta"),
        catchup=False,
        max_active_runs=1,
        max_active_tasks=1,
        dagrun_timeout=timedelta(minutes=45),
        is_paused_upon_creation=True,
        default_args={
            "owner": "kuping-negara",
            "retries": 1,
            "retry_delay": timedelta(minutes=5),
            "execution_timeout": timedelta(minutes=20),
        },
        tags=["x", "collection", "preprocessing"],
        doc_md=(
            f"Collect **{program_id}** at 23:59 Asia/Jakarta. "
            f"Uses the preceding 7 complete days, at most {COLLECTION_LIMIT} posts. "
            "Configure the Docker X secret before unpausing. "
            "Preprocessing runs only after successful collection."
        ),
    )
    def pipeline():
        @task(pool="x_collection", do_xcom_push=True)
        def collect() -> dict[str, str]:
            return _run_pipeline(
                "collect", "--program", program_id, "--limit", str(COLLECTION_LIMIT)
            )

        @task
        def preprocess(raw: dict[str, str]) -> dict[str, str]:
            return _run_pipeline("preprocess", "--input", raw["raw_path"])

        preprocess(collect())

    return pipeline()


for _program, _schedule in PROGRAM_SCHEDULES.items():
    globals()[f"x_{_program}"] = build_program_dag(_program, _schedule)
