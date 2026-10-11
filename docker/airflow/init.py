"""Prepare writable mounts and a local login file before database initialization."""

import json
import os
from pathlib import Path

for folder in [
    Path("/opt/airflow/logs"),
    Path("/opt/airflow/auth"),
    Path("/opt/kuping-negara/data"),
    Path("/opt/kuping-negara/data/raw"),
    Path("/opt/kuping-negara/data/processed"),
]:
    folder.mkdir(parents=True, exist_ok=True)
    os.chown(folder, 50000, 0)

passwords = Path("/opt/airflow/auth/passwords.json")
if not passwords.exists():
    passwords.write_text(
        json.dumps({"admin": Path("/run/secrets/admin_password").read_text().strip()}),
        encoding="utf-8",
    )
os.chmod(passwords, 0o600)
os.chown(passwords, 50000, 0)
