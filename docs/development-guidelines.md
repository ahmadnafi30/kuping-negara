# Development Guidelines

This document defines the minimum engineering standard for Kuping Negara.
Rules apply to application code, data pipelines, notebooks promoted to source
code, tests, configuration, and documentation.

## Language and Runtime

- Primary language: Python.
- Minimum supported version: Python 3.12.
- Source package: `src/kuping_negara`.
- Reusable code must be importable from the package; do not rely on notebook
  execution order or ad-hoc `sys.path` mutation.
- Use `uv` as the primary package and environment manager.
- Treat `pyproject.toml` and `uv.lock` as the dependency source of truth.
- Add runtime dependencies with `uv add <package>`.
- Add development dependencies to the `dev` extra with
  `uv add --optional dev <package>`.
- Regenerate the compatibility manifest with
  `uv export --frozen --extra dev --format requirements.txt --no-hashes
  --no-emit-project --output-file requirements.txt`.
- Never edit `uv.lock` or generated dependency pins manually. Explain every new
  runtime dependency in the Pull Request.

## Naming Conventions

| Element | Convention | Correct | Avoid |
| --- | --- | --- | --- |
| Python package/module | `snake_case` | `data_quality.py` | `DataQuality.py`, `data-quality.py` |
| Directory inside Python package | `snake_case` | `model_registry/` | `ModelRegistry/` |
| Function/method | `snake_case` | `validate_record()` | `ValidateRecord()` |
| Local variable/parameter | `snake_case` | `model_version` | `modelVersion` |
| Class/protocol/exception | `PascalCase` | `SchemaValidator` | `schema_validator` |
| Constant | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEZONE` | `defaultTimezone` |
| Internal/private name | leading underscore | `_load_manifest()` | `privateLoad()` |
| Test function | `test_<behavior>` | `test_rejects_empty_text()` | `checkEmptyText()` |
| Fixture | `snake_case` | `sample_tweet_record` | `SampleTweetRecord` |
| Environment variable | `UPPER_SNAKE_CASE` | `MLFLOW_TRACKING_URI` | `mlflowUri` |
| YAML/JSON config key | `snake_case` | `target_program` | `targetProgram` |
| DataFrame column | `snake_case` | `published_at` | `PublishedAt` |
| Branch | `<type>/<kebab-case>` | `feat/schema-validation` | `feature_schemaValidation` |
| Markdown file | `kebab-case.md` | `git-workflow.md` | `Git_Workflow.md` |

Python code uses `snake_case`, not camelCase. `PascalCase` is reserved for
classes and exception types. External API fields may follow an upstream
contract, but conversion to the internal canonical naming must happen at the
adapter boundary.

## Python Code Style

- Follow PEP 8 and target a maximum line length of 88 characters.
- Use four spaces; never use tab indentation.
- Use explicit, descriptive names. Avoid unexplained abbreviations.
- Public functions and methods require type hints for parameters and return
  values.
- Prefer small functions with one responsibility and explicit input/output.
- Avoid mutable global state and hidden I/O inside transformation functions.
- Use `pathlib.Path` instead of manual path concatenation.
- Keep imports ordered: standard library, third-party packages, local package.
- Never use wildcard imports.
- Use timezone-aware datetimes; operational scheduling uses `Asia/Jakarta`.

## Docstrings and Comments

- Public modules, classes, and non-obvious public functions require docstrings.
- A docstring explains contract, parameters, return value, side effects, and
  raised exceptions when these are not self-evident.
- Comments explain *why* a decision exists, not a literal translation of code.
- Do not leave stale commented-out code; Git preserves history.
- `TODO` must include context and a tracked issue reference when issue tracking
  is available.

## Component Boundaries

- Source adapters belong in `ingestion`; they must not contain modeling logic.
- Deterministic text transformations belong in `preprocessing`.
- Schema and quality gates belong in `validation`.
- Training code may consume validated/labeled data but must not call source APIs.
- `inference` owns model loading and prediction interfaces.
- `api` handles transport concerns and delegates prediction to `inference`.
- `dashboard` handles presentation concerns and must not retrain models.
- `monitoring` consumes emitted metrics/events; it must not silently mutate data.
- Airflow DAG files orchestrate package functions; business logic does not live
  inside DAG definitions.

Cross-component imports must follow these boundaries and must not create cyclic
dependencies. Shared primitives should live in a narrowly scoped module only
after at least two real consumers exist.

## Configuration and Secrets

- Non-secret configuration is versioned under `configs/`.
- Secrets are loaded from environment variables or a runtime secret manager.
- Never place real credentials in `.env.example`, notebooks, test fixtures,
  logs, screenshots, commits, or Pull Request descriptions.
- Validate configuration at application startup and fail with actionable error
  messages.
- Avoid hard-coded program keywords, storage locations, thresholds, or model
  versions inside business logic.

## Data Engineering Rules

- Raw data is append-only and immutable.
- Every ingestion run receives a unique `ingestion_run_id`.
- Transformations must be deterministic for the same input and configuration.
- Validate schema before moving data into the processed zone.
- Quarantine invalid records rather than silently dropping them.
- Preserve lineage fields through every transformation.
- Never commit raw, processed, labeled, or model artifact contents to Git.
- Data-contract breaking changes require a version bump and migration note.

## Logging and Error Handling

- Use structured logging fields such as `run_id`, `program`, `data_version`,
  `model_version`, and `record_count`.
- Never log credentials, cookies, authorization headers, or raw personal data.
- Raise domain-specific exceptions at package boundaries.
- Do not catch `Exception` merely to ignore a failure.
- If a failure is recoverable, log context and use a bounded retry policy.
- If a failure compromises correctness, fail the stage explicitly and prevent
  downstream promotion.

## Testing Standard

- Place fast isolated tests in `tests/unit/`.
- Place cross-component, storage, API, or pipeline tests in
  `tests/integration/`.
- Name tests after observable behavior, not implementation detail.
- Every bug fix must include a regression test when the behavior can be tested.
- Use small synthetic fixtures; never require production credentials or raw
  personal data.
- Tests must be deterministic and safe to run repeatedly.
- A model-quality test must record the fixture/data version and expected metric
  threshold.

Minimum local verification:

```bash
uv sync --frozen --extra dev
uv pip check
uv run --frozen --extra dev python -m kuping_negara.healthcheck
uv run --frozen --extra dev pytest
```

## Notebook Standard

- Use notebooks for EDA, visualization, and experiment narrative only.
- File names use a numeric prefix and kebab-case, for example
  `01-data-profile.ipynb`.
- A notebook must run top-to-bottom from a clean kernel.
- Do not store credentials, large embedded outputs, or private data.
- Production transformations and model logic must be extracted into `src/` and
  covered by tests.

## Documentation Standard

- Keep technical nouns in their established form: `Quick Start`, `Pull Request`,
  `data contract`, `quality gate`, `model registry`, and `rollback`.
- Document current behavior separately from planned architecture.
- Code examples must be executable or clearly labeled as proposed contracts.
- Update README and relevant `docs/` files in the same Pull Request as a
  contract or workflow change.

## Definition of Done

A change is complete only when:

- implementation matches the approved scope;
- tests cover the important behavior and pass locally;
- CI passes;
- data/security/privacy impact has been reviewed;
- configuration and schema changes are versioned;
- documentation is updated;
- no secret, dataset, cache, or model binary is staged;
- commit messages follow Conventional Commits;
- Pull Request has enough context for an independent reviewer;
- topic branch is deleted after merge.
