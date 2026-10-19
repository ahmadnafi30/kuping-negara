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
uv run --locked --no-sync preprocess-x-data `
  --input "<path-raw-run.csv>"
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
| `matched_keyword` | First configured keyword found in sanitized model text or a program hashtag |
| `raw_text` | Original text retained for traceability |
| `cleaned_text` | Normalized text for labeling and model preparation |
| `model_text` | Case-preserving text; keeps hashtags, negation, emoji and punctuation |
| `text_fingerprint` | SHA-256 of normalized text for duplicate checks |
| `split_group_id` | Global hint for grouping copies/similar text before dataset splitting |
| `similar_to_tweet_id` | Previous eligible ID that triggered a text duplicate/review flag |
| `language` | Original language label supplied by X |
| `language_normalized` | Source label casefolded; `in` maps to `id` |
| `language_needs_review` | Source language does not confirm Indonesian |
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
| `is_duplicate` | Repeated ID within this CSV or previously eligible ID for this program |
| `is_duplicate_across_runs` | ID already eligible in a completed run for this program |
| `is_duplicate_text` | Normalized text already eligible for this program, even with another ID |
| `is_near_duplicate` | Long text similar to a previously eligible text; requires review |
| `is_empty_cleaned_text` | No text remains after removing URLs and mentions |
| `is_indonesian` | True when the source language label is `in` or `id` (case-insensitive) |
| `is_relevant` | True when a configured program keyword is present |
| `is_eligible_for_labeling` | True only when status is `accepted` |
| `quality_status` | Review decision described below |
| `processed_at` | Timezone-aware processing timestamp |

## Quality Statuses

| Status | Meaning | Action |
| --- | --- | --- |
| `accepted` | Indonesian, relevant, non-empty cleaned text, and not a repeated ID | Ready for annotation |
| `duplicate` | Repeated ID within this CSV or a previous eligible run for this program | Exclude from labeling sample |
| `duplicate_text` | Identical normalized text already eligible for this program | Exclude from repeated labeling |
| `review_similar_text` | Text similarity needs a human decision | Review; no automatic sentiment label |
| `empty_cleaned_text` | Only links/mentions or whitespace remain | Exclude from labeling and training |
| `review_language` | Relevant keyword found, but language is not `in`/`id` | Review text manually |
| `review_relevance` | Language is `in`/`id`, but no configured keyword was found | Review query relevance |
| `review_language_and_relevance` | Both checks need review | Review before use |

Rows that need review remain visible. The pipeline does not silently drop them.
This preserves evidence for later rule improvements and prevents loss caused by
imperfect platform language labels.

## Integrity Gates and Cross-Run History

The current processed contract is schema version `3` and preprocessing version
`3`. Keyword relevance uses sanitized, case-preserving model text and hashtags: a program acronym occurring only in
a URL or account mention cannot make a record eligible. Empty cleaned text
receives an explicit flag, even if another quality status takes precedence.

New collector runs write `collection.json` beside the CSV. Preprocessing
rechecks the raw/configuration hashes (using the frozen collection YAML), exact inclusive Jakarta date range, and
hard requested row limit. Airflow requires this manifest; the standalone CLI
can read legacy CSVs without one, with `collection_validation: null` in its
report. Such legacy output has no verified collection window or limit.

All publishers share one file lock under `data/processed/x`. While holding it,
the pipeline verifies completed report/CSV hashes, loads previously eligible
IDs, transforms the new run, and publishes its CSV/report atomically. Duplicate decisions are
scoped to the target program: one post can have a different sentiment toward
MBG and CKG. Such copies keep a shared global group hint and must stay in the
same dataset split. Previous review/empty records do not block a later eligible
record.
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
`data/quarantine/x/processed/preprocessing_version=<old>/` and adds `quarantine.json`. It does not edit or
remove raw CSVs. Quarantined outputs must be excluded from labeling/training.
A raw CSV that passes the current manifest checks can be regenerated through
preprocessing; out-of-window or over-limit inputs must be recollected.

## Sentiment Preparation (Version 3)

`raw_text` remains unchanged. `model_text` removes direct account mentions and
URL values, normalizes HTML/Unicode/whitespace, and retains capitalization,
hashtags, negation, informal spelling, repeated letters, emoji sequences, and
punctuation. `cleaned_text` remains the lowercase view without hashtag markers.
Neither view is a sentiment label or a guarantee of readiness for training.

ZWJ/ZWNJ and emoji tag sequences are preserved; unrelated control characters
are removed. URL removal preserves attached terminal punctuation and emoji.
Hashtag relevance recognizes CamelCase words, compact program phrases and a
limited set of stance prefixes (`tolak`, `dukung`, `stop`, `evaluasi`, `anti`,
`pro`, `kontra`). For example, `#TolakMBG` matches `mbg`, but `#mbgossip` does not.
A hashtag match never assigns positive/negative sentiment.

Duplicate fingerprints remove identity noise, lowercase text and strip a
leading retweet marker; they retain negation, emoji and punctuation. Different
IDs with the same normalized text cannot create repeated eligible examples
for one program. Similarity uses character SequenceMatcher with threshold
`0.92`, at least 40 characters per text and length ratio at least `0.85`. These
heuristics flag `review_similar_text`; they do not equate sentiments, delete
rows, or automatically accept a label. Small negation edits can require review.

`split_group_id` is a grouping hint, not a finished train/test split. Before
training, reconcile connected similarity groups and conversation IDs across
the entire labeled dataset, then keep related examples together. Never split
per target program independently when the same post occurs in multiple targets.
Similarity scanning currently compares against local history; large datasets
will need an indexed candidate search.

`language_validation: source_label_only` explicitly records the limitation of
X language labels. `in`, `id` and uppercase equivalents map to Indonesian;
other/unknown labels require review and remain visible. This stage does not
claim to identify code-switching or fix incorrectly labeled Indonesian posts.
Those cases need manual review or a separately evaluated language detector.

Downstream tokenization must follow the selected model's requirements. Do not
automatically remove negation/stopwords or apply stemming/slang replacement.
Keep human-approved labels separate from quality flags and suggested labels.

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
uv run --locked --no-sync pytest
uv run --locked --no-sync python -m compileall -q src tests
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
