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
  console.log("Collector imports, secret adapter, error status, and headless Chromium verified.");
}
main().catch(() => { console.error("Collector compatibility check failed"); process.exitCode = 1; });
