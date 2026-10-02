"""Weekly X ingestion and preprocessing, one program per Jakarta weekday."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import CronTriggerTimetable, dag, get_current_context, task

from kuping_negara.ingestion.tweet_harvest import load_programs
from kuping_negara.scheduling import completed_week_window, weekly_cron

PROJECT_ROOT = Path("/opt/airflow/project")
CONFIG_PATH = PROJECT_ROOT / "configs/keywords/programs.example.yaml"
TWEET_HARVEST_BIN = Path(
    "/opt/airflow/node/node_modules/tweet-harvest/dist/bin.js"
)


def create_program_dag(program_id: str, collection_day: str):
    """Keep the program choice fixed in each generated DAG."""

    @dag(
        dag_id=f"weekly_x_{program_id}",
        schedule=CronTriggerTimetable(
            weekly_cron(collection_day), timezone="Asia/Jakarta"
        ),
        start_date=pendulum.datetime(2026, 10, 1, tz="Asia/Jakarta"),
        catchup=False,
        is_paused_upon_creation=True,
        max_active_runs=1,
        tags=["kuping-negara", "ingestion", "weekly"],
    )
    def weekly_program():
        @task(execution_timeout=timedelta(minutes=45))
        def collect_and_preprocess():
            if not os.environ.get("X_AUTH_TOKEN", "").strip():
                raise RuntimeError("X_AUTH_TOKEN is missing from the Airflow container")

            context = get_current_context()
            trigger_time = context.get("data_interval_end") or pendulum.now(
                "Asia/Jakarta"
            )
            first_day, last_day = completed_week_window(trigger_time)
            command = [
                sys.executable,
                "src/ingest_data.py",
                "--preprocess",
                "--program",
                program_id,
                "--from-date",
                first_day.strftime("%d-%m-%Y"),
                "--to-date",
                last_day.strftime("%d-%m-%Y"),
                "--limit",
                "50",
                "--non-interactive",
                "--tweet-harvest-bin",
                str(TWEET_HARVEST_BIN),
            ]
            subprocess.run(command, cwd=PROJECT_ROOT, check=True)

        collect_and_preprocess()

    return weekly_program()


for _program_id, _settings in load_programs(CONFIG_PATH).items():
    globals()[f"weekly_x_{_program_id}"] = create_program_dag(
        _program_id, _settings["collection_day"]
    )

