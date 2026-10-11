# X Data Preprocessing

This guide defines the first reproducible preprocessing stage for Tweet Harvest
data. It turns one immutable raw CSV into canonical records plus a quality
report. The implementation is intended for LK-04, while its pilot findings can
support the technical decisions and evidence described in LK-03.

## Quick Start

Install the locked project environment:

```powershell
uv sync --locked --extra dev
uv pip check
```

Preprocess a CSV produced by the collector (replace this example path with your own file):

```powershell
uv run --locked preprocess-x-data `
  --input "data/raw/x/collected_date=2026-09-21/program=mbg/run_id=20260921T182524+0700/mbg_2026-09-14_2026-09-21.csv"
```

The input path must contain these partition segments:

```text
collected_date=YYYY-MM-DD/
program=<program_id>/
run_id=<Asia-Jakarta-timestamp>/
```

The CLI infers `target_program`, `ingestion_run_id`, and `collected_at` from
those segments. It rejects inconsistent dates and unknown programs.

## Processing Contract

The pipeline performs the following deterministic operations:

1. Read every CSV field as text so 19-digit X identifiers retain full precision.
2. Validate required columns, timestamps, non-empty text, and non-negative
   engagement counts.
3. Reject the Unicode replacement character because it indicates decoding loss.
4. Preserve the original post in `raw_text`.
5. Create `cleaned_text` using Unicode NFKC normalization and case folding.
6. Remove URLs and direct mentions from `cleaned_text`.
7. Keep hashtag words, punctuation, and emoji that may carry sentiment.
8. Map source names such as `favorite_count` to canonical names such as
   `like_count`.
9. Add language, relevance, duplicate, labeling-readiness, and lineage fields.
10. Exclude `username`, `user_id_str`, location, image URL, and reply-account
    identifiers from processed output.

Preprocessing never edits the source file. It calculates the input SHA-256
before transformation and confirms the same checksum after persistence.

## Output Layout

One run creates two local files:

```text
data/processed/x/
└── processed_date=YYYY-MM-DD/
    └── program=<program_id>/
        └── run_id=<ingestion_run_id>/
            ├── <raw-file-name>_processed.csv
            └── quality_report.json
```

The pipeline refuses to overwrite an existing processed run. Both files are
ignored by Git. DVC can version this directory after a remote-storage strategy
has been selected.

## Canonical Fields

| Field | Purpose |
| --- | --- |
| `tweet_id` | X post identifier stored as text |
| `conversation_id` | Conversation identifier stored as text |
| `tweet_url` | Source permalink |
| `target_program` | Program ID from the raw partition |
| `matched_keyword` | First configured keyword found in cleaned text |
| `raw_text` | Original text retained for traceability |
| `cleaned_text` | Normalized text for labeling and model preparation |
| `language` | Language label supplied by X |
| `published_at` | UTC ISO 8601 timestamp |
| `collected_at` | Time encoded by the ingestion run ID |
| `year_week` | ISO year and week in Asia/Jakarta |
| `year_month` | Calendar month in Asia/Jakarta |
| `reply_count` | Non-negative reply count |
| `retweet_count` | Non-negative repost count |
| `like_count` | Canonical form of `favorite_count` |
| `quote_count` | Non-negative quote count |
| `ingestion_run_id` | Link to the source collection execution |
| `data_version` | SHA-256 identity of the raw CSV |
| `schema_version` | Canonical data-contract version |
| `source_platform` | Source identifier, currently `x` |
| `is_duplicate` | Repeated ID within this CSV or previously eligible ID across runs |
| `is_duplicate_across_runs` | ID already eligible in a completed run, across programs |
| `is_empty_cleaned_text` | No text remains after removing URLs and mentions |
| `is_indonesian` | True when the source language label is `in` |
| `is_relevant` | True when a configured program keyword is present |
| `is_eligible_for_labeling` | True only when status is `accepted` |
| `quality_status` | Review decision described below |
| `processed_at` | Timezone-aware processing timestamp |

## Quality Statuses

| Status | Meaning | Action |
| --- | --- | --- |
| `accepted` | Indonesian, relevant, non-empty cleaned text, and not a repeated ID | Ready for annotation |
| `duplicate` | Repeated ID within this CSV or a previous eligible run | Exclude from labeling sample |
| `empty_cleaned_text` | Only links/mentions or whitespace remain | Exclude from labeling and training |
| `review_language` | Relevant keyword found, but language is not `in` | Review text manually |
| `review_relevance` | Language is `in`, but no configured keyword was found | Review query relevance |
| `review_language_and_relevance` | Both checks need review | Review before use |

Rows that need review remain visible. The pipeline does not silently drop them.
This preserves evidence for later rule improvements and prevents loss caused by
imperfect platform language labels.

## Integrity Gates and Cross-Run History

The current processed contract is schema version `2` and preprocessing version
`2`. Keyword relevance uses cleaned text: a program acronym occurring only in
a URL or account mention cannot make a record eligible. Empty cleaned text
receives an explicit flag, even if another quality status takes precedence.

New collector runs write `collection.json` beside the CSV. Preprocessing
rechecks the raw/configuration hashes, exact inclusive Jakarta date range, and
hard requested row limit. Airflow requires this manifest; the standalone CLI
can read legacy CSVs without one, with `collection_validation: null` in its
report. Such legacy output has no verified collection window or limit.

All publishers share one file lock under `data/processed/x`. While holding it,
the pipeline verifies completed report/CSV hashes, loads previously eligible
IDs, transforms the new run, and publishes its CSV/report atomically. IDs are
global across programs to prevent the same post entering multiple labeling
samples. Previous review/empty records do not block a later eligible record.
Duplicate rows remain in the output but are ineligible. An Airflow retry reuses
its unchanged output without counting itself as a new duplicate.

Keep the complete processed history and lock in one output root. Separate
output roots have separate histories. This local file lock is intended for one
Docker host; distributed workers need shared transactional coordination.

Before reusing outputs generated under older rules, stop Airflow and audit:

```powershell
docker compose stop airflow
.\.venv\Scripts\python.exe -m kuping_negara.orchestration.audit --repository-root .
docker compose up -d --build --wait
```

The audit moves legacy/invalid processed run folders to
`data/quarantine/x/processed/` and adds `quarantine.json`. It does not edit or
remove raw CSVs. Quarantined outputs must be excluded from labeling/training.
A raw CSV that passes the current manifest checks can be regenerated through
preprocessing; out-of-window or over-limit inputs must be recollected.

## Historical MBG Pilot Audit

These figures are historical notes from a local pilot. The dataset is not
tracked in this repository and the figures are not a reproducible test fixture.

The 21 September 2026 pilot contains 20 records and 15 source columns. The raw
CSV decoded as UTF-8 with no replacement character, mojibake marker, control
character, empty text, duplicate row, or duplicate tweet ID.

| Check | Result |
| --- | ---: |
| Source records | 20 |
| Processed records | 20 |
| Ready for labeling | 17 |
| Review language | 1 |
| Review relevance | 1 |
| Review language and relevance | 1 |
| Duplicate tweet IDs | 0 |
| Replacement characters | 0 |
| Source language `in` | 18 |
| Source language `ar` | 1 |
| Source language `en` | 1 |

Five source rows contain emoji or other valid symbols. Those characters are
not evidence of corruption. The pipeline keeps them because they may express
sentiment. URLs and mentions are removed only from `cleaned_text`; `raw_text`
retains the source content for traceability.

## Privacy and Repository Rules

- Never commit files under `data/raw/`, `data/processed/`, or `data/quarantine/`.
- Processed records still contain `raw_text` and source permalinks. They are
  not fully anonymized even though explicit account columns are removed.
- Never publish raw usernames or post text without an approved privacy review.
- Use only the aggregate quality report as submission evidence when raw content
  is not required.
- Do not paste X tokens into commands, source files, logs, or screenshots.
- Treat `data_version` as lineage metadata, not as proof that publication is
  permitted.

## Verification

Run all automated checks:

```powershell
uv run --locked --extra dev pytest
uv run --locked --extra dev python -m compileall -q src tests
```

Inspect only aggregate quality evidence:

```powershell
Get-Content `
  "data/processed/x/processed_date=2026-09-21/program=mbg/run_id=20260921T182524+0700/quality_report.json"
```

## Troubleshooting

### `raw path must contain exactly one ... partition`

Use a CSV produced by `collect-x-data`. Do not move it outside the partitioned
raw directory before preprocessing.

### `processed run already exists`

The overwrite guard is working. Inspect the existing quality report. Use a new
ingestion run for newly collected data instead of replacing earlier output.

### `full_text contains a Unicode replacement character`

The input has already lost one or more decoded characters. Keep it in the raw
zone, investigate the source encoding, and collect it again. Do not replace the
character silently.

### A valid post is marked for review

The platform language label and simple keyword match are conservative quality
signals. Review the post manually. Improve the versioned keyword configuration
or a later language-identification stage only after collecting representative
examples and adding regression tests.
