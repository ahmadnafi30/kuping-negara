"""Require fresh heartbeats from every component of the local standalone stack."""

import json
from urllib.request import urlopen


def main() -> None:
    with urlopen("http://localhost:8080/api/v2/monitor/health", timeout=5) as response:
        health = json.load(response)
    for component in ("metadatabase", "scheduler", "dag_processor", "triggerer"):
        if health.get(component, {}).get("status") != "healthy":
            raise SystemExit(f"Airflow component is not healthy: {component}")


if __name__ == "__main__":
    main()
