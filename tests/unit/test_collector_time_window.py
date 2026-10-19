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
  const response = {data:{search_by_raw_query:{search_timeline:{timeline:{instructions:[
    {type:"TimelineReplaceEntry",entry:{entryId:"cursor"}},
    {type:"TimelineAddEntries",entries:[{entryId:"tweet-1"}]},
    {type:"TimelineTerminateTimeline",direction:"Bottom"}
  ]}}}}};
  assert.equal(adapter.searchTimelineEntries(response).length, 2);
  assert.equal(adapter.searchTimelineTerminated(response), true);
  assert.throws(() => adapter.searchTimelineEntries({}));
  process.env.KUPING_NEGARA_WINDOW_START = "2026-10-03T17:00:00Z";
  process.env.KUPING_NEGARA_WINDOW_END = "2026-10-10T17:00:00Z";
  const seen = new Set(["old"]);
  const tweets = ["old", "new", "new"].map(id_str => ({tweet:{id_str,created_at:"2026-10-05T00:00:00Z"}}));
  assert.equal(adapter.selectTweets(tweets, 100, seen).length, 1);
  const page = new (require("node:events").EventEmitter)();
  adapter.installSearchResponseQueue(page, "03-10-2026", "11-10-2026");
  const queued = {url: () => "https://x.com/SearchTimeline?variables=" + encodeURIComponent(JSON.stringify({rawQuery:"mbg since:2026-10-03 until:2026-10-11"})), status: () => 200};
  page.emit("response", queued); // Arrives while the search form is still awaiting Enter.
  assert.equal(await adapter.waitForCollectionResponse(page, true, 10), queued);
  assert.equal(await adapter.waitForCollectionResponse(page, true, 10), undefined);
  page.emit("response", queued); // Timed-out waiter must not swallow the next page.
  assert.equal(await adapter.waitForCollectionResponse(page, true, 10), queued);
  page.emit("response", {...queued, status: () => 429});
  await assert.rejects(adapter.waitForCollectionResponse(page, true, 10), /HTTP 429/);
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
