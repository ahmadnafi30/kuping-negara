FROM node:22-bookworm-slim AS node

FROM apache/airflow:3.3.1-python3.12

USER root
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update \
    && apt-get install -y --no-install-recommends chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/airflow/state /opt/airflow/node /opt/airflow/project \
    && chown -R airflow:0 /opt/airflow/state /opt/airflow/node /opt/airflow/project

USER airflow
RUN npm install --prefix /opt/airflow/node --no-audit --no-fund tweet-harvest@2.7.1

WORKDIR /opt/airflow/project
COPY --chown=airflow:0 pyproject.toml README.md ./
COPY --chown=airflow:0 src ./src
COPY --chown=airflow:0 scripts ./scripts
COPY --chown=airflow:0 configs ./configs
RUN pip install --no-cache-dir . && pip check

