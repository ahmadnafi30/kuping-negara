"""Prepare mounts once, then run the official Airflow standalone as non-root."""

import os
import runpy


def main() -> None:
    runpy.run_path("/opt/airflow/init.py")
    os.setgroups([])
    os.setgid(0)
    os.setuid(50000)
    os.environ.update(HOME="/home/airflow", USER="airflow", LOGNAME="airflow")
    os.umask(0o002)
    os.execv(
        "/entrypoint",
        [
            "/entrypoint",
            "bash",
            "-c",
            "airflow db migrate && "
            'airflow pools set x_collection 1 "One X collection at a time" && '
            "exec airflow standalone",
        ],
    )


if __name__ == "__main__":
    main()
