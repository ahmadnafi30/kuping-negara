"""Aggregate-only EDA; never publish tweet text or account identifiers."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from kuping_negara.ingestion.tweet_harvest import JAKARTA_TIMEZONE, find_repository_root
from kuping_negara.training.candidates import load_verified_run

ENGAGEMENT_COLUMNS = ("reply_count", "retweet_count", "like_count", "quote_count")


def _counts(series: pd.Series) -> dict[str, int]:
    return {
        str(key if str(key).strip() else "unknown"): int(value)
        for key, value in series.value_counts(dropna=False).items()
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze_processed_runs(input_dir: Path) -> dict[str, Any]:
    """Summarize quality, coverage, and imbalance from verified CSV outputs."""
    files = sorted(input_dir.rglob("*_processed.csv"))
    if not files:
        raise ValueError(f"no processed CSV files in {input_dir}")
    frames = [load_verified_run(path) for path in files]
    frame = pd.concat(frames, ignore_index=True)
    missing_engagement = set(ENGAGEMENT_COLUMNS) - set(frame.columns)
    if missing_engagement:
        raise ValueError(f"missing engagement columns: {sorted(missing_engagement)}")

    eligible = frame.loc[frame["is_eligible_for_labeling"].eq("True")]
    unique_candidates = eligible.drop_duplicates(["target_program", "tweet_id"])
    published = pd.to_datetime(frame["published_at"], errors="coerce", utc=True)
    if published.isna().any():
        raise ValueError("processed rows contain invalid published_at values")
    published_local = published.dt.tz_convert(JAKARTA_TIMEZONE)
    lengths = frame["cleaned_text"].str.len()
    engagement: dict[str, dict[str, float | int]] = {}
    for column in ENGAGEMENT_COLUMNS:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or values.lt(0).any():
            raise ValueError(f"invalid {column} values")
        engagement[column] = {
            "median": float(values.median()),
            "p95": float(values.quantile(0.95)),
            "max": int(values.max()),
        }

    program_counts = _counts(frame["target_program"])
    candidate_counts = _counts(unique_candidates["target_program"])
    language_counts = _counts(frame["language"])
    program_quality = {
        str(program): _counts(group["quality_status"])
        for program, group in frame.groupby("target_program")
    }
    cross_program_tweets = int(
        unique_candidates.groupby("tweet_id")["target_program"].nunique().gt(1).sum()
    )
    source_hashes = {
        path.relative_to(input_dir).as_posix(): _sha256(path) for path in files
    }
    summary: dict[str, Any] = {
        "source_files": len(files),
        "processed_rows": int(len(frame)),
        "eligible_rows": int(len(eligible)),
        "unique_annotation_candidates": int(len(unique_candidates)),
        "duplicates_across_runs": int(len(eligible) - len(unique_candidates)),
        "tweet_ids_in_multiple_programs": cross_program_tweets,
        "program_counts": program_counts,
        "candidate_program_counts": candidate_counts,
        "program_quality_counts": program_quality,
        "quality_status_counts": _counts(frame["quality_status"]),
        "out_of_window_rows": int(
            frame["is_in_requested_window"].eq("False").sum()
        ),
        "source_language_counts": language_counts,
        "published_date_counts": _counts(published_local.dt.strftime("%Y-%m-%d")),
        "published_week_counts": _counts(published_local.dt.strftime("%G-W%V")),
        "published_at_min": published.min().isoformat(),
        "published_at_max": published.max().isoformat(),
        "cleaned_text_length": {
            "min": int(lengths.min()),
            "median": float(lengths.median()),
            "p95": float(lengths.quantile(0.95)),
            "max": int(lengths.max()),
            "empty": int(lengths.eq(0).sum()),
            "under_20_characters": int(lengths.lt(20).sum()),
        },
        "engagement": engagement,
        "missing_values": {
            column: int(frame[column].eq("").sum())
            for column in ("raw_text", "cleaned_text", "language", "published_at")
        },
        "input_sha256": source_hashes,
        "limitations": [
            "Language codes come from X/Tweet Harvest; no independent detection is run.",
            "Keywords indicate possible relevance, not semantic verification.",
            "Collection is capped per window and uses the Latest search tab.",
            "Sentiment labels are not present; this is not a labeled training set.",
        ],
    }
    return summary


def _bar_section(title: str, counts: dict[str, int]) -> str:
    largest = max(counts.values(), default=1)
    rows = []
    for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        width = max(1, round(count / largest * 100))
        rows.append(
            "<div class='bar-row'><span>"
            f"{html.escape(label)}</span><div class='track'><div class='fill' "
            f"style='width:{width}%'></div></div><strong>{count}</strong></div>"
        )
    return f"<section><h2>{html.escape(title)}</h2>{''.join(rows)}</section>"


def render_html(summary: dict[str, Any]) -> str:
    """Render a self-contained report with aggregate charts only."""
    cards = [
        ("Baris diproses", summary["processed_rows"]),
        ("Siap diperiksa", summary["eligible_rows"]),
        ("Kandidat unik", summary["unique_annotation_candidates"]),
        ("Di luar rentang tanggal", summary["out_of_window_rows"]),
        ("Duplikat antar-run", summary["duplicates_across_runs"]),
    ]
    card_html = "".join(
        f"<div class='card'><small>{html.escape(label)}</small><b>{value}</b></div>"
        for label, value in cards
    )
    text_stats = summary["cleaned_text_length"]
    engagement_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{values['median']:.1f}</td>"
        f"<td>{values['p95']:.1f}</td><td>{values['max']}</td></tr>"
        for name, values in summary["engagement"].items()
    )
    limitations = "".join(
        f"<li>{html.escape(item)}</li>" for item in summary["limitations"]
    )
    missing_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{count}</td></tr>"
        for name, count in summary["missing_values"].items()
    )
    return f"""<!doctype html>
<html lang='id'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>EDA Data Awal Kuping Negara</title><style>
body{{font:16px/1.5 system-ui,sans-serif;color:#182436;background:#f5f7fb;max-width:1000px;margin:auto;padding:2rem}}
h1,h2{{line-height:1.2}}section{{background:white;padding:1.3rem;margin:1rem 0;border-radius:12px;box-shadow:0 2px 10px #18243610}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem}}.card{{background:#e8efff;padding:1rem;border-radius:10px}}
.card small,.card b{{display:block}}.card b{{font-size:1.9rem}}.bar-row{{display:grid;grid-template-columns:180px 1fr 55px;gap:.7rem;align-items:center;margin:.5rem 0}}
.track{{background:#e4e9f1;height:15px;border-radius:8px;overflow:hidden}}.fill{{background:#3759c8;height:100%}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:.5rem;text-align:left;border-bottom:1px solid #dde3ed}}
@media(max-width:600px){{.bar-row{{grid-template-columns:100px 1fr 40px}}}}
</style></head><body><h1>EDA data awal</h1>
<p>Ringkasan agregat hasil preprocessing. Laporan ini tidak memuat teks unggahan atau identitas akun.</p>
<div class='cards'>{card_html}</div>
{_bar_section('Program', summary['program_counts'])}
{_bar_section('Kandidat unik per program', summary['candidate_program_counts'])}
{_bar_section('Status kualitas', summary['quality_status_counts'])}
{_bar_section('Bahasa dari X', summary['source_language_counts'])}
{_bar_section('Minggu publikasi', summary['published_week_counts'])}
<section><h2>Panjang teks bersih</h2><p>Median {text_stats['median']:.1f} karakter; P95 {text_stats['p95']:.1f}; kosong {text_stats['empty']}; kurang dari 20 karakter {text_stats['under_20_characters']}.</p></section>
<section><h2>Interaksi</h2><table><thead><tr><th>Jenis</th><th>Median</th><th>P95</th><th>Maksimum</th></tr></thead><tbody>{engagement_rows}</tbody></table></section>
<section><h2>Nilai kosong</h2><table><thead><tr><th>Kolom</th><th>Jumlah</th></tr></thead><tbody>{missing_rows}</tbody></table></section>
<section><h2>Potensi kebocoran data</h2><p>{summary['tweet_ids_in_multiple_programs']} ID unggahan muncul di lebih dari satu program. Saat membagi data latih dan uji, kelompokkan berdasarkan ID unggahan.</p></section>
<section><h2>Batas pembacaan</h2><ul>{limitations}</ul></section>
</body></html>"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize processed X data safely.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/x"))
    parser.add_argument("--output-root", type=Path, default=Path("data/analysis/eda"))
    parser.add_argument("--run-id", help="Stable ID for reproducible DVC runs")
    arguments = parser.parse_args(argv)
    root = find_repository_root([Path.cwd(), Path(__file__)])
    input_dir = arguments.input_dir
    output_root = arguments.output_root
    if not input_dir.is_absolute():
        input_dir = root / input_dir
    if not output_root.is_absolute():
        output_root = root / output_root
    try:
        summary = analyze_processed_runs(input_dir)
        run_id = arguments.run_id or (
            datetime.now(JAKARTA_TIMEZONE).strftime("%Y%m%dT%H%M%S%f") + "WIB"
        )
        if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
            raise ValueError("run-id must contain only letters, digits, _ or -")
        destination = output_root / f"run_id={run_id}"
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (destination / "index.html").write_text(render_html(summary), encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"EDA error: {error}", file=sys.stderr)
        return 1
    print(f"EDA report: {destination / 'index.html'}")
    return 0
