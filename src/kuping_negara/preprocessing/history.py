"""Serialize publications and find labeling IDs in verified completed runs."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from kuping_negara.ingestion.validation import sha256_file

PREPROCESSING_VERSION = 2


@contextmanager
def preprocessing_lock(root: Path, timeout: float = 120):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".preprocessing.lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Timed out waiting for preprocessing publication lock"
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_UN)


def eligible_tweet_ids(root: Path) -> set[str]:
    seen: set[str] = set()
    for report_path in sorted(root.rglob("quality_report.json")):
        if any(part.startswith(".") for part in report_path.relative_to(root).parts):
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("preprocessing_version") != PREPROCESSING_VERSION:
            raise ValueError(
                "Legacy processed output must be audited and quarantined before reuse"
            )
        name = report["output_file"]
        if Path(name).name != name:
            raise ValueError("Processed report contains an invalid output filename")
        records = report_path.parent / name
        if sha256_file(records) != report["output_sha256"]:
            raise ValueError("Processed history hash has changed")
        frame = pd.read_csv(
            records, dtype=str, keep_default_na=False, encoding="utf-8-sig"
        )
        eligible = frame["is_eligible_for_labeling"].str.casefold().eq("true")
        eligible &= frame["quality_status"].eq("accepted") & frame[
            "cleaned_text"
        ].str.strip().ne("")
        seen.update(frame.loc[eligible, "tweet_id"])
    return seen
