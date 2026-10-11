"""Guard search precision at Jakarta midnight without contacting X."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_search_uses_exact_jakarta_window_and_rejects_invalid_bounds():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is covered by the Docker collector compatibility check")
    hook = Path("scripts/tweet_harvest_integrity_hook.cjs").resolve()
    script = r"""
const assert = require("node:assert/strict");
const adapter = require(process.argv[1]);
(async () => {
  let observed;
  await adapter.inputKeywordsInWindow(async (_page, params) => {
    await new Promise(resolve => setTimeout(resolve, 5));
    observed = params.MODIFIED_SEARCH_KEYWORDS;
  }, {}, {MODIFIED_SEARCH_KEYWORDS:'(mbg OR "makan bergizi gratis")'});
  // A date-only UTC search would also return October 11, 00:00-06:59 WIB.
  assert.equal(observed, '(mbg OR "makan bergizi gratis") since_time:1791046800 until_time:1791651600');
  process.env.KUPING_NEGARA_WINDOW_END = process.env.KUPING_NEGARA_WINDOW_START;
  assert.throws(() => adapter.exactWindowQuery("mbg"));
  delete process.env.KUPING_NEGARA_WINDOW_START;
  assert.throws(() => adapter.exactWindowQuery("mbg"));
  console.log(JSON.stringify({awaited:true, precise_midnight:true}));
})().catch(() => process.exit(1));
"""
    environment = {
        **os.environ,
        "NODE_OPTIONS": "",
        "KUPING_NEGARA_WINDOW_START": "2026-10-03T17:00:00Z",
        "KUPING_NEGARA_WINDOW_END": "2026-10-10T17:00:00Z",
    }
    result = subprocess.run(
        [node, "-e", script, str(hook)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert json.loads(result.stdout) == {"awaited": True, "precise_midnight": True}
