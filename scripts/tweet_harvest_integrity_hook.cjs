"use strict";
// Apply checked, in-memory fixes to the pinned CLI; never edit the npm cache.
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");

function once(source, needle, replacement) {
  if (source.split(needle).length !== 2) throw new Error("Unsupported collector source; refusing unsafe collection");
  return source.replace(needle, replacement);
}

function patchCollectorSource(source) {
  const helper = JSON.stringify(__filename);
  source = once(source, "      inputKeywords(page, {", `      await require(${helper}).inputKeywordsInWindow(inputKeywords, page, {`);
  source = once(source,
    '(response2) => response2.url().includes("SearchTimeline") || response2.url().includes("TweetDetail")',
    `(response2) => IS_SEARCH_MODE ? require(${helper}).matchesSearchResponse(response2, SEARCH_FROM_DATE, SEARCH_TO_DATE) : response2.url().includes("TweetDetail")`);
  return once(source,
    "          allData.tweets.push(...tweetContents);\n          const comingTweets = tweetContents;",
    `          const comingTweets = require(${helper}).selectTweets(tweetContents, TARGET_TWEET_COUNT - allData.tweets.length);\n          if (!comingTweets.length) { cache.set("got_tweets", false); await scrollDown(page); continue; }\n          allData.tweets.push(...comingTweets);`);
}

function exactWindowQuery(query) {
  const lower = Date.parse(process.env.KUPING_NEGARA_WINDOW_START);
  const upper = Date.parse(process.env.KUPING_NEGARA_WINDOW_END);
  if (typeof query !== "string" || !Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper || lower % 1000 || upper % 1000) {
    throw new Error("A valid whole-second collection window and query are required");
  }
  return `${query} since_time:${lower / 1000} until_time:${upper / 1000}`;
}

async function inputKeywordsInWindow(inputKeywords, page, parameters) {
  // Keep the pinned CLI's outer date search and add exact Jakarta boundaries.
  // This avoids paging through the following day's first seven WIB hours.
  const keywords = parameters.MODIFIED_SEARCH_KEYWORDS;
  const scoped = typeof keywords === "string"
    ? { ...parameters, MODIFIED_SEARCH_KEYWORDS: exactWindowQuery(keywords) }
    : parameters;
  return await inputKeywords(page, scoped);
}

function isoDate(value) {
  const [day, month, year] = value.split(" ")[0].split("-");
  return `${year}-${month}-${day}`;
}

function matchesSearchResponse(response, from, to) {
  try {
    if (!from || !to || !response.url().includes("SearchTimeline")) return false;
    const url = new URL(response.url());
    const variables = url.searchParams.get("variables");
    const request = variables ? JSON.parse(variables) : response.request().postDataJSON()?.variables;
    const query = request?.rawQuery;
    return typeof query === "string" && query.includes(`since:${isoDate(from)}`) && query.includes(`until:${isoDate(to)}`);
  } catch { return false; }
}

function selectTweets(tweets, remaining) {
  const lower = Date.parse(process.env.KUPING_NEGARA_WINDOW_START);
  const upper = Date.parse(process.env.KUPING_NEGARA_WINDOW_END);
  if (!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper || !Number.isInteger(remaining) || remaining < 0) {
    throw new Error("Valid collection window and remaining limit are required");
  }
  return tweets.filter(item => {
    const published = Date.parse(item.tweet.created_at);
    if (!Number.isFinite(published)) throw new Error("Collector returned an invalid publication timestamp");
    return published >= lower && published < upper;
  }).slice(0, remaining);
}

function install() {
  const original = Module._extensions[".js"];
  Module._extensions[".js"] = function loadCheckedCollector(module, filename) {
    if (!filename.replace(/\\/g, "/").endsWith("/tweet-harvest/dist/bin.js")) return original(module, filename);
    const packageFile = path.join(path.dirname(filename), "..", "package.json");
    if (JSON.parse(fs.readFileSync(packageFile, "utf8")).version !== "2.7.1") throw new Error("Unsupported collector version");
    module._compile(patchCollectorSource(fs.readFileSync(filename, "utf8")), filename);
  };
}
module.exports = { install, patchCollectorSource, exactWindowQuery, inputKeywordsInWindow, matchesSearchResponse, selectTweets };
