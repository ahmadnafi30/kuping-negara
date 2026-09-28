# X Data Collection

This guide covers local pilot-data collection for all Kuping Negara programs
with Tweet Harvest 2.7.1. The collector reads versioned keywords from
`configs/keywords/programs.example.yaml` and stores raw CSV files outside Git.

For the LK-04 wrapper, unattended mode, retry policy, and periodic simulation,
see [LK-04 Implementation](lk04-implementation.md). Runtime CSVs remain outside
Git; the small deidentified course subset under `data/raw/samples/` is explicitly
versioned with provenance.

## Prerequisites

- Python 3.12 managed by `uv`.
- Node.js LTS with `npx` available on `PATH`.
- Google Chrome or Microsoft Edge installed locally on Windows.
- A valid X account used in accordance with applicable platform rules,
  institutional policy, and research ethics.
- A newly generated `auth_token` that has never been shared or committed.

Install the locked Python environment:

```powershell
uv sync --frozen --extra dev
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

- Paste the token only into `What's your Twitter auth token?`.
- Never send the token through chat, email, an issue, or a Pull Request.
- Never place it in a notebook, script, command argument, screenshot, or Git.
- If a token is exposed, revoke the affected X session before collecting data.
- Do not publish raw usernames or post text without an approved privacy review.

## Validate the Collection Plan

Run this before using a real token:

```powershell
uv run --frozen collect-x-data `
  --from-date 14-09-2026 `
  --to-date 21-09-2026 `
  --limit 50 `
  --dry-run
```

The command prints four program IDs and their queries. It does not execute
`npx`, open X, request a token, or create raw data.

## Collect All Programs

```powershell
uv run --frozen collect-x-data `
  --from-date 14-09-2026 `
  --to-date 21-09-2026 `
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
uv run --frozen collect-x-data `
  --program mbg `
  --program sekolah_rakyat `
  --from-date 14-09-2026 `
  --to-date 21-09-2026 `
  --limit 25
```

`--from-date` and `--to-date` are inclusive. The example covers 14 September
through 21 September 2026. Internally, the collector passes 22 September to
Tweet Harvest because X treats `until` as an exclusive boundary.

Keyword queries prioritize recall. Acronyms remain unquoted, multi-word names
use exact-phrase quotes, and ingestion does not apply `lang:id`. Language and
program relevance belong in preprocessing so potentially useful posts are not
discarded before the raw zone.

## Raw Output Layout

Tweet Harvest first writes a staging CSV under `tweets-data/`. After a
successful run, the collector requires a non-empty file and moves it to:

```text
data/raw/x/
└── collected_date=YYYY-MM-DD/
    └── program=<program_id>/
        └── run_id=<Asia-Jakarta-timestamp>/
            └── <program_id>_<from-date>_<to-date>.csv
```

The unique `run_id` prevents a later ingestion run from overwriting an earlier
raw dataset. Both `tweets-data/` and raw dataset contents are ignored by Git.
DVC versioning can track the raw zone in a later implementation phase.

## CLI Options

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `--from-date` | With `--to-date` | Rolling 7-day window |  Start date in `DD-MM-YYYY` |
| `--to-date` | With `--from-date` | Today in Asia/Jakarta |  Inclusive end date in `DD-MM-YYYY` |
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
uv sync --frozen --extra dev
uv run --frozen collect-x-data --help
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
uv run --frozen collect-x-data `
  --from-date 14-09-2026 `
  --to-date 21-09-2026 `
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
