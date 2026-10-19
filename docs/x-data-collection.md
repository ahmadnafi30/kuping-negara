# X Data Collection

This guide covers local pilot-data collection for all Kuping Negara programs
with Tweet Harvest 2.7.1. The collector reads versioned keywords from
`configs/keywords/programs.example.yaml` and stores raw CSV files outside Git.

## Prerequisites

- Python 3.12 managed by `uv`.
- Node.js LTS with `npx` available on `PATH`.
- Google Chrome or Microsoft Edge installed locally on Windows.
- A valid X account used in accordance with applicable platform rules,
  institutional policy, and research ethics.
- A newly generated `auth_token` that has never been shared or committed.

Install the locked Python environment:

```powershell
uv sync --locked --extra dev
uv pip check
```

Confirm Node.js tooling:

```powershell
node --version
npx --version
```

## Security Rules

The interactive collector never reads a token from source code or `.env` and
never adds a token to the generated command. Tweet Harvest asks for the token
through its hidden prompt for every selected program.

For unattended collection, use the [Airflow Docker guide](airflow-docker.md).
That adapter reads a local Docker secret into the prompt in memory and runs
headlessly; the interactive CLI behavior described here is unchanged.

- Paste the token only into `What's your Twitter auth token?`.
- Never send the token through chat, email, an issue, or a Pull Request.
- Never place it in a notebook, script, command argument, screenshot, or Git.
- If a token is exposed, revoke the affected X session before collecting data.
- Do not publish raw usernames or post text without an approved privacy review.

## Validate the Collection Plan

Run this before using a real token:

```powershell
uv run --locked --no-sync collect-x-data `
  --from-date 14-09-2026 `
  --to-date 20-09-2026 `
  --limit 50 `
  --dry-run
```

The command prints four program IDs and their queries. It does not execute
`npx`, open X, request a token, or create raw data.

## Collect All Programs

```powershell
uv run --locked --no-sync collect-x-data `
  --from-date 14-09-2026 `
  --to-date 20-09-2026 `
  --limit 50 `
  --tab LATEST
```

The default program order follows the YAML configuration:

1. `mbg`
2. `ckg`
3. `kopdes_merah_putih`
4. `sekolah_rakyat`

For each program, paste the valid token into the hidden prompt and choose CSV
if Tweet Harvest displays an export-format prompt. Do not start a second
collector while the first one is running.

## Collect Selected Programs

Repeat `--program` to select more than one program:

```powershell
uv run --locked --no-sync collect-x-data `
  --program mbg `
  --program sekolah_rakyat `
  --from-date 14-09-2026 `
  --to-date 20-09-2026 `
  --limit 25
```

`--from-date` and `--to-date` are inclusive. The example covers 14 September
through 20 September 2026 in Asia/Jakarta. X searches use UTC calendar dates,
so the adapter passes 13 September as the broad `since` boundary and
21 September as exclusive `until`. It then filters each timestamp against the
exact Jakarta interval (13 September 17:00 UTC through 20 September 17:00 UTC,
end exclusive) before counting toward the limit. A checked in-memory fix also
awaits the search form before consuming responses; unknown collector source
versions fail instead of collecting unfiltered initial results.

Current queries use `lang:id` to reduce unrelated foreign-language acronym
matches. CKG also requires health context (for example kesehatan, puskesmas or
skrining); full program names are quoted. Both options are versioned per program
and can be omitted in a separate configuration for a broader recall audit.
Search filters can miss useful code-switched posts and are not a language or
relevance ground truth. Preprocessing still checks both signals independently.

## Raw Output Layout

Tweet Harvest first writes a staging CSV under `tweets-data/`. After a
successful run, the collector validates a non-empty CSV, every publication
timestamp in the requested Jakarta period, and a hard row limit, then moves it to:

```text
data/raw/x/
└── collected_date=YYYY-MM-DD/
    └── program=<program_id>/
        └── run_id=<Asia-Jakarta-timestamp>/
            ├── <program_id>_<from-date>_<to-date>.csv
            ├── collection.json
            └── collection_config.yaml
```

The unique `run_id` prevents a later ingestion run from overwriting an earlier
raw dataset. Both `tweets-data/` and raw dataset contents are ignored by Git.
The manifest records requested dates/limit, input/configuration hashes, and
validation evidence. New runs retain the exact keyword YAML beside their CSV.
Historical runs without this copy resolve their original configuration by SHA-256
from `configs/keywords/history/`; a later keyword edit does not invalidate a
valid historical collection. [DVC versioning](dvc.md) tracks a validated combined raw
snapshot while retaining the original per-run files.

## CLI Options

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `--from-date` | Yes | None | Start date in `DD-MM-YYYY` |
| `--to-date` | Yes | None | Inclusive end date in `DD-MM-YYYY` |
| `--limit` | No | `50` | Maximum posts requested per program |
| `--program` | No | All programs | Repeatable program ID selector |
| `--tab` | No | `LATEST` | X search tab: `LATEST` or `TOP` |
| `--config` | No | Keyword example YAML | Alternative keyword configuration |
| `--browser-executable` | No | Auto-detected | Chrome or Edge executable override |
| `--dry-run` | No | Disabled | Validate and display the plan only |

## Troubleshooting

### `program not found: collect-x-data`

The local environment does not contain the current project entry point:

```powershell
uv sync --locked --extra dev
uv run --locked --no-sync collect-x-data --help
```

### Hardlink warning from `uv`

The warning is non-fatal and occurs when the cache and environment use
different filesystems. Suppress it for the current PowerShell session with:

```powershell
$env:UV_LINK_MODE = "copy"
```

### `npx is not available`

Install Node.js LTS, reopen PowerShell, and verify `node --version` plus
`npx --version`.

### Playwright says `Executable doesn't exist`

Tweet Harvest 2.7.1 pins an older Playwright browser. The project collector
automatically uses an installed Google Chrome or Microsoft Edge on Windows and
prints the selected `Browser runtime` before collection starts. This avoids
editing the global npm cache and does not expose the X token.

If automatic detection cannot find a browser, provide its executable path:

```powershell
uv run --locked --no-sync collect-x-data `
  --from-date 14-09-2026 `
  --to-date 20-09-2026 `
  --limit 50 `
  --browser-executable "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

Do not run `npx playwright install` for this error. Tweet Harvest 2.7.1 pins
Chromium 121, whose Windows binary can fail even after it is fully downloaded.

### Invalid token or login page

Revoke the invalid X session, log in again, retrieve a new `auth_token`, and
enter it only in the hidden prompt. Never reuse a token that was shared.

### No output CSV or `no tweet rows`

Tweet Harvest can create a two-byte CSV containing only a line break when its
search returns zero posts. The collector treats that file as a failed run and
does not move it into `data/raw/`. Check the date window, test the same query in
the X web interface, verify the login session, and review the browser output.
Do not create an empty placeholder dataset.

## Next Stage

After a raw CSV passes ingestion checks, run the preprocessing workflow in
[`x-data-preprocessing.md`](x-data-preprocessing.md). Preprocessing reads the
partition metadata, preserves the raw file, removes user identifiers from the
processed contract, and creates a quality report for labeling readiness.

## Exact Jakarta search bounds

The pinned collector adapter adds `since_time` and `until_time` Unix timestamp
constraints for the requested Jakarta midnight boundaries, alongside the CLI's
outer UTC date search. A date-only search can otherwise page through thousands
of posts from the following day's first seven WIB hours before finding valid
records. The exact timestamp constraints reduce that unnecessary pagination;
the independent publication-time validation and hard row limit remain required.

A `429` response means X has temporarily limited the session. Respect the
reported reset time rather than issuing repeated manual triggers. A failed
collection must remain failed and must not be published as an empty dataset.

## Pagination and larger batches

The checked Tweet Harvest adapter reads entries across all SearchTimeline
instructions, including pages that begin with a cursor replacement. It removes
repeated post IDs before applying the hard limit and recognizes an explicit
end-of-timeline response. Source changes outside the pinned version fail closed.
Upstream timeouts or network failures still fail the collection; partial staging
CSVs are not silently accepted.

Weekly Airflow collection requests at most 200 posts per program. Schedules
remain Monday through Thursday at 23:59 WIB. The interactive CLI retains its
50-post default; use `--limit 125` or another explicit cap for research batches.
Actual results can be fewer than the cap, especially for CKG.

For a historical week inside the Docker environment, use the runtime CLI's
`--window-end YYYY-MM-DD` together with `--lookback-days 7`. This selects the
publication interval while retaining the real current `--scheduled-at` timestamp
for provenance. The window must end before the collection day. Collect serially,
retain successful checkpoints, and stop on an authentication or rate-limit
response. Do not replay a completed week merely to increase row counts.
