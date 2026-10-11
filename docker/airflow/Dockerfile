FROM ghcr.io/astral-sh/uv:0.12.12 AS uv
FROM node:22-bookworm-slim AS collector
WORKDIR /opt/collector
COPY docker/collector/package*.json ./
RUN npm ci --ignore-scripts --omit=dev
COPY docker/collector/verify.cjs ./

FROM apache/airflow:3.3.2-python3.12
USER root
RUN apt-get update && apt-get install -y --no-install-recommends chromium \
    && rm -rf /var/lib/apt/lists/*
COPY --from=collector /usr/local/bin/node /usr/local/bin/node
COPY --from=collector /opt/collector /opt/collector
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/kuping-negara
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs
RUN UV_PROJECT_ENVIRONMENT=/opt/kuping-negara/.venv UV_PYTHON_DOWNLOADS=never \
    uv sync --locked --no-dev --no-editable --python /usr/local/bin/python \
    && chmod -R a+rX /opt/kuping-negara /opt/collector
COPY dags /opt/airflow/dags
COPY docker/airflow/init.py docker/airflow/verify_dags.py \
    docker/airflow/start.py docker/airflow/healthcheck.py /opt/airflow/
ENV KUPING_NEGARA_BROWSER_EXECUTABLE=/usr/bin/chromium \
    UV_CACHE_DIR=/home/airflow/.cache/uv \
    KUPING_NEGARA_COLLECTOR=/opt/collector/node_modules/tweet-harvest/dist/bin.js \
    KUPING_NEGARA_TOKEN_FILE=/run/secrets/x_auth_token
WORKDIR /opt/airflow
USER airflow
