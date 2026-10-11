"use strict";

// Local compatibility checks only: no X request and no real secret is read.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

async function main() {
  const help = spawnSync(process.execPath, [process.env.KUPING_NEGARA_COLLECTOR, "--help"], {
    encoding: "utf8",
  });
  assert.equal(help.status, 0, "Pinned collector must load with updated dependencies");
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "kuping-verify-"));
  try {
    const tokenFile = path.join(temporary, "synthetic-token");
    fs.writeFileSync(tokenFile, "a".repeat(40));
    const hook = "/opt/kuping-negara/scripts/tweet_harvest_secret_hook.cjs";
    const environment = { ...process.env, NODE_OPTIONS: "", KUPING_NEGARA_TOKEN_FILE: tokenFile };
    const prompt = spawnSync(process.execPath, ["--require", hook, "-e",
      "require('prompts')([{name:'token'}, {name:'exportFormat'}]).then(a => {if(a.token !== 'a'.repeat(40) || a.exportFormat !== 'csv') process.exit(1);})"],
      { env: environment });
    assert.equal(prompt.status, 0, "Secret prompt adapter failed");
    const failure = spawnSync(process.execPath, ["--require", hook, "-e", "console.error('synthetic failure')"],
      { env: environment });
    assert.equal(failure.status, 1, "Upstream logged errors must fail the collection task");
  } finally {
    fs.rmSync(temporary, { recursive: true });
  }
  const integrity = require("/opt/kuping-negara/scripts/tweet_harvest_integrity_hook.cjs");
  const collectorSource = fs.readFileSync(process.env.KUPING_NEGARA_COLLECTOR, "utf8");
  new (require("node:vm").Script)(integrity.patchCollectorSource(collectorSource));
  assert.throws(() => integrity.patchCollectorSource("unsupported"));
  const searchResponse = query => ({url: () => "https://x.com/i/api/graphql/id/SearchTimeline?variables=" + encodeURIComponent(JSON.stringify({rawQuery:query}))});
  assert.equal(integrity.matchesSearchResponse(searchResponse("ckg"), "03-10-2026", "11-10-2026"), false);
  assert.equal(integrity.matchesSearchResponse(searchResponse("ckg since:2026-10-03 until:2026-10-11"), "03-10-2026", "11-10-2026"), true);
  const lower = process.env.KUPING_NEGARA_WINDOW_START;
  const upper = process.env.KUPING_NEGARA_WINDOW_END;
  process.env.KUPING_NEGARA_WINDOW_START = "2026-10-03T17:00:00Z";
  process.env.KUPING_NEGARA_WINDOW_END = "2026-10-10T17:00:00Z";
  try {
    const exactQuery = integrity.exactWindowQuery('mbg OR "makan bergizi gratis"');
    assert.equal(exactQuery, 'mbg OR "makan bergizi gratis" since_time:1791046800 until_time:1791651600');
    let scopedQuery;
    await integrity.inputKeywordsInWindow(async (_page, parameters) => { scopedQuery = parameters.MODIFIED_SEARCH_KEYWORDS; }, {}, {MODIFIED_SEARCH_KEYWORDS:"mbg"});
    assert.equal(scopedQuery, integrity.exactWindowQuery("mbg"));
    const candidates = ["2026-10-03T16:59:59Z", "2026-10-03T17:00:00Z", "2026-10-10T16:59:59Z", "2026-10-10T17:00:00Z"]
      .map(created_at => ({tweet:{created_at}}));
    assert.equal(integrity.selectTweets(candidates, 50).length, 2);
    assert.equal(integrity.selectTweets(candidates, 1).length, 1);
    assert.throws(() => integrity.selectTweets([{tweet:{created_at:"invalid"}}], 1));
    const fixture = `async function checkRace() {
      let filled = false;
      const page = {};
      const inputKeywords = async () => { await new Promise(resolve => setTimeout(resolve, 5)); filled = true; };
      const matcher = (response2) => response2.url().includes("SearchTimeline") || response2.url().includes("TweetDetail");
      const allData = {tweets:[]}; const TARGET_TWEET_COUNT = 1;
      for (let pageNumber=0; pageNumber<1; pageNumber++) {
      inputKeywords(page, {});
      const tweetContents = [{tweet:{created_at:filled ? "2026-10-05T00:00:00Z" : "2026-10-11T00:00:00Z"}}];
          allData.tweets.push(...tweetContents);
          const comingTweets = tweetContents;
      return comingTweets.length;
      }
    }; checkRace();`;
    assert.equal(await require("node:vm").runInNewContext(integrity.patchCollectorSource(fixture), {require,setTimeout}), 1,
      "Collection must wait until its search query is ready");
    const emptyFirstBatch = `async function checkEmptyBatch() {
      const page = {}; const inputKeywords = async () => {};
      const matcher = (response2) => response2.url().includes("SearchTimeline") || response2.url().includes("TweetDetail");
      const cache = new Map(); const scrollDown = async () => {};
      const allData = {tweets:[]}; const TARGET_TWEET_COUNT = 1;
      let writes=0;
      for (const created_at of ["2026-10-11T00:00:00Z", "2026-10-05T00:00:00Z"]) {
      inputKeywords(page, {});
      const tweetContents = [{tweet:{created_at}}];
          allData.tweets.push(...tweetContents);
          const comingTweets = tweetContents;
      writes++; if(!comingTweets.length) throw new Error("Empty batch corrupted CSV header");
      }
      return writes;
    }; checkEmptyBatch();`;
    assert.equal(await require("node:vm").runInNewContext(integrity.patchCollectorSource(emptyFirstBatch), {require}), 1,
      "An empty first batch must not consume the CSV header");
  } finally {
    if (lower === undefined) delete process.env.KUPING_NEGARA_WINDOW_START; else process.env.KUPING_NEGARA_WINDOW_START = lower;
    if (upper === undefined) delete process.env.KUPING_NEGARA_WINDOW_END; else process.env.KUPING_NEGARA_WINDOW_END = upper;
  }
  const { chromium } = require("playwright-extra");
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.KUPING_NEGARA_BROWSER_EXECUTABLE,
  });
  try {
    const page = await browser.newPage();
    await page.goto("data:text/html,<title>Kuping</title>");
    assert.equal(await page.title(), "Kuping");
  } finally {
    await browser.close();
  }
  console.log("Collector race fix, response dates, exact Jakarta window, hard limit, secret adapter, and Chromium verified.");
}
main().catch(() => { console.error("Collector compatibility check failed"); process.exitCode = 1; });
