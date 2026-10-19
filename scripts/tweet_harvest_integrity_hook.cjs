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

function searchTimelineEntries(response) {
  const instructions = response?.data?.search_by_raw_query?.search_timeline?.timeline?.instructions;
  if (!Array.isArray(instructions)) throw new Error("SearchTimeline instructions are unavailable");
  return instructions.flatMap(instruction => Array.isArray(instruction.entries)
    ? instruction.entries : instruction.entry ? [instruction.entry] : []);
}

function searchTimelineTerminated(response) {
  const instructions = response?.data?.search_by_raw_query?.search_timeline?.timeline?.instructions;
  return Array.isArray(instructions) && instructions.some(instruction =>
    instruction.type === "TimelineTerminateTimeline" && instruction.direction === "Bottom");
}

const searchQueues = new WeakMap();
function installSearchResponseQueue(page, from, to) {
  if (searchQueues.has(page)) throw new Error("Search response queue already installed");
  const state = {responses: [], waiter: null};
  searchQueues.set(page, state);
  page.on("response", response => {
    if (!matchesSearchResponse(response, from, to)) return;
    if (state.waiter) {
      const deliver = state.waiter;
      state.waiter = null;
      deliver(response);
    } else {
      if (state.responses.length >= 128) throw new Error("Search response queue overflow");
      state.responses.push(response);
    }
  });
}
async function waitForCollectionResponse(page, searchMode, timeout = 1500) {
  if (!searchMode) return await page.waitForResponse(response => response.url().includes("TweetDetail"), {timeout});
  const state = searchQueues.get(page);
  if (!state) throw new Error("Search response queue is missing");
  const response = state.responses.length ? state.responses.shift() : await new Promise(resolve => {
    const timer = setTimeout(() => { state.waiter = null; resolve(undefined); }, timeout);
    state.waiter = result => { clearTimeout(timer); resolve(result); };
  });
  if (response && typeof response.status === "function" && response.status() >= 400) {
    throw new Error(`Search HTTP ${response.status()}; collection stopped`);
  }
  return response;
}

function patchPaginationSource(source) {
  const helper = JSON.stringify(__filename);
  source = once(source, `      await require(${helper}).inputKeywordsInWindow(inputKeywords, page, {`,
    `      require(${helper}).installSearchResponseQueue(page, SEARCH_FROM_DATE, SEARCH_TO_DATE);\n      await require(${helper}).inputKeywordsInWindow(inputKeywords, page, {`);
  const waitStart = source.indexOf("        const response = await Promise.race([");
  const waitEnd = source.indexOf("        if (response) {", waitStart);
  if (waitStart < 0 || waitEnd < 0) throw new Error("Unsupported response loop");
  source = once(source, source.slice(waitStart, waitEnd),
    `        const response = await require(${helper}).waitForCollectionResponse(page, IS_SEARCH_MODE);\n`);
  source = once(source, "            tweets = _optionalChain([responseJson, 'access', _7 => _7.data, 'optionalAccess', _8 => _8.search_by_raw_query, 'access', _9 => _9.search_timeline, 'access', _10 => _10.timeline, 'optionalAccess', _11 => _11.instructions, 'optionalAccess', _12 => _12[0], 'optionalAccess', _13 => _13.entries]);",
    `            tweets = require(${helper}).searchTimelineEntries(responseJson);
            if (require(${helper}).searchTimelineTerminated(responseJson) && !tweets.some(entry => entry.content?.itemContent?.tweet_results?.result)) break;`);
  return once(source,
    "selectTweets(tweetContents, TARGET_TWEET_COUNT - allData.tweets.length)",
    "selectTweets(tweetContents, TARGET_TWEET_COUNT - allData.tweets.length, new Set(allData.tweets.map(item => item.tweet.id_str)))");
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

function selectTweets(tweets, remaining, seen = new Set()) {
  const lower = Date.parse(process.env.KUPING_NEGARA_WINDOW_START);
  const upper = Date.parse(process.env.KUPING_NEGARA_WINDOW_END);
  if (!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper || !Number.isInteger(remaining) || remaining < 0) {
    throw new Error("Valid collection window and remaining limit are required");
  }
  return tweets.filter(item => {
    const published = Date.parse(item.tweet.created_at);
    if (!Number.isFinite(published)) throw new Error("Collector returned an invalid publication timestamp");
    if (!(published >= lower && published < upper)) return false;
    const id = item.tweet.id_str;
    if (id && seen.has(id)) return false;
    if (id) seen.add(id);
    return true;
  }).slice(0, remaining);
}

function install() {
  const original = Module._extensions[".js"];
  Module._extensions[".js"] = function loadCheckedCollector(module, filename) {
    if (!filename.replace(/\\/g, "/").endsWith("/tweet-harvest/dist/bin.js")) return original(module, filename);
    const packageFile = path.join(path.dirname(filename), "..", "package.json");
    if (JSON.parse(fs.readFileSync(packageFile, "utf8")).version !== "2.7.1") throw new Error("Unsupported collector version");
    module._compile(patchPaginationSource(patchCollectorSource(fs.readFileSync(filename, "utf8"))), filename);
  };
}
module.exports = { install, patchCollectorSource, patchPaginationSource, searchTimelineEntries, searchTimelineTerminated, installSearchResponseQueue, waitForCollectionResponse, exactWindowQuery, inputKeywordsInWindow, matchesSearchResponse, selectTweets };
