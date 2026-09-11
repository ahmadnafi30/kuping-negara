# Project Structure and Code Placement

Kuping Negara uses the `src` layout with a single top-level Python namespace:
`kuping_negara`. This avoids accidental imports from the repository root and
keeps package boundaries explicit.

## Directory Ownership

| Path | Responsibility | Typical Contents | Must Not Contain |
| --- | --- | --- | --- |
| `.devcontainer/` | Reproducible developer environment | `devcontainer.json` | Application logic or secrets |
| `.github/workflows/` | CI/CD automation | YAML workflows | Business logic |
| `configs/keywords/` | Program collection configuration | Versioned YAML | Access tokens |
| `configs/schemas/` | Data contracts | JSON Schema and migration notes | Raw datasets |
| `dags/` | Workflow orchestration | Thin Airflow DAG definitions | Transformation/model implementation |
| `data/raw/` | Immutable source-aligned records | Local/DVC-managed artifacts | Git-tracked dataset content |
| `data/processed/` | Validated transformed records | Local/DVC-managed artifacts | Raw credentials or identifiers |
| `data/labeled/` | Annotation output | Versioned external artifacts | Unreviewed secrets/PII |
| `docs/` | Engineering and operational documentation | Markdown and architecture references | Executable production logic |
| `models/` | Local model artifacts | Serialized models and metadata | Git-tracked binaries |
| `notebooks/` | EDA and experiment narratives | Numbered notebooks | Only copy of reusable logic |
| `src/kuping_negara/` | Installable application package | Domain modules | Large data/model artifacts |
| `tests/unit/` | Isolated deterministic tests | Function/class behavior | Live external calls |
| `tests/integration/` | Cross-boundary tests | Pipeline/API/storage tests | Production secrets |

## Python Package Boundaries

### `ingestion/`

Source adapters, collection request construction, response normalization,
idempotency keys, raw persistence, and ingestion metadata. A source-specific
adapter converts upstream field names into the canonical internal contract.

### `validation/`

JSON Schema checks, required-field validation, range checks, duplicate checks,
quality reports, and quarantine decisions. Validation produces explicit results
and never silently repairs unknown corruption.

### `preprocessing/`

Text cleaning, URL/mention handling, normalization, language-related transforms,
anonymization, and deduplication. Prefer pure functions so outputs are
reproducible and easy to test.

### `labeling/`

Annotation sample preparation, guideline-version metadata, annotator agreement,
adjudication input/output, and label quality checks. UI-specific tools may call
this layer but must not redefine label semantics.

### `training/`

Feature construction, split strategy, training, evaluation, experiment logging,
model-card creation, and registry submission. Training consumes versioned data
and never calls the source platform directly.

### `inference/`

Model loading, input validation at the model boundary, batch prediction, online
prediction, probability/confidence formatting, and model-version reporting.

### `api/`

FastAPI routes, request/response schema, authentication hooks, and HTTP error
mapping. Routes delegate business behavior to package services.

### `dashboard/`

Streamlit views, filters, charts, and presentation formatting. It consumes a
documented API or query interface rather than importing training internals.

### `monitoring/`

Metric calculation, drift analysis, service/pipeline health checks, and alert
payload construction. Alert policy and thresholds are configuration-driven.

## Code Placement Decision Guide

| Change | Place It Here |
| --- | --- |
| New X/Tweet Harvest field mapping | `src/kuping_negara/ingestion/` |
| New required data field or enum | `configs/schemas/` plus `validation/` |
| Text normalization rule | `preprocessing/` with unit tests |
| Annotation decision rule | `docs/annotation-guidelines.md` and `labeling/` if automated |
| Train/test split or estimator code | `training/` |
| Model prediction formatting | `inference/` |
| HTTP endpoint | `api/`; prediction logic remains in `inference/` |
| Dashboard chart | `dashboard/` |
| Drift metric or alert payload | `monitoring/` |
| Pipeline schedule/dependency | `dags/`; called logic stays in `src/` |
| Exploratory analysis | `notebooks/`; promote reusable logic into `src/` |
| Small deterministic behavior test | `tests/unit/` |
| Multi-component/storage/API test | `tests/integration/` |

## Dependency Direction

Recommended dependency flow:

```text
ingestion → validation → preprocessing
labeling → validation
training → validation/preprocessing
inference → trained model contract
api → inference
dashboard → API/query contract
monitoring ← events/metrics from all runtime stages
dags → public functions from package modules
```

Avoid reverse dependencies such as `inference` importing `api`, or
`preprocessing` importing `training`. Avoid cyclic imports and catch-all
`utils.py` modules. Create a shared abstraction only after its ownership and
multiple real consumers are clear.

## Adding a New Module

Before adding a module:

1. identify one owning package from the responsibility table;
2. choose a `snake_case.py` name that describes one concern;
3. define its public input/output contract and side effects;
4. add type hints and a module docstring;
5. add unit tests mirroring its package path;
6. add integration tests when it crosses I/O or component boundaries;
7. update data contract/configuration/documentation if behavior changes;
8. verify the module does not introduce a cyclic dependency.

Example mapping:

```text
src/kuping_negara/preprocessing/text_normalization.py
tests/unit/preprocessing/test_text_normalization.py
```

## Repository Hygiene

- Keep generated files, caches, virtual environments, datasets, and model
  artifacts out of Git.
- Preserve empty required directories using `.gitkeep` only.
- Do not add placeholder directories for technologies that have no approved
  implementation plan.
- Remove merged topic branches; do not keep them artificially synchronized with
  `main` merely to remove a `behind` indicator.
