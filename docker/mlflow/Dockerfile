FROM ghcr.io/astral-sh/uv:0.12.12 AS uv
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/kuping-negara
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable --extra training \
    && mkdir -p /mlflow/artifacts \
    && chown -R 1000:1000 /mlflow /opt/kuping-negara
COPY --chown=1000:1000 . .
ENV PATH="/opt/kuping-negara/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MLFLOW_DISABLE_TELEMETRY=true \
    MLFLOW_DISABLE_AGENT_HINT=1 \
    MPLCONFIGDIR=/tmp/matplotlib
USER 1000:1000
CMD ["mlflow", "server", "--backend-store-uri", "sqlite:////mlflow/tracking.db", "--serve-artifacts", "--artifacts-destination", "/mlflow/artifacts", "--host", "0.0.0.0", "--port", "5000", "--allowed-hosts", "localhost:*,127.0.0.1:*,mlflow:5000"]
