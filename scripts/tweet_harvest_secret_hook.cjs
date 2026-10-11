"use strict";

// Adapter for the pinned 2.7.1 CLI: supply its password prompt in memory.
// No credential is passed through argv, environment values, stdout, or XCom.
const fs = require("node:fs");
const Module = require("node:module");
const originalLoad = Module._load;

Module._load = function secretPromptAdapter(request, parent, isMain) {
  if (request === "prompts") {
    return async function answerTokenPrompt(questions) {
      if (questions.some((question) => !["token", "exportFormat"].includes(question.name))) {
        throw new Error("Unexpected interactive collector prompt");
      }
      const token = fs.readFileSync(process.env.KUPING_NEGARA_TOKEN_FILE, "utf8").trim();
      if (!/^[a-fA-F0-9]{40}$/.test(token)) {
        throw new Error("Configure a valid X auth_token secret file");
      }
      return { token, exportFormat: "csv" };
    };
  }
  return originalLoad.apply(this, arguments);
};

// Upstream catches crawl failures, logs an error, and otherwise exits zero.
// Treat any such failure as unsuccessful, including a partial CSV result.
const originalError = console.error.bind(console);
console.error = (...args) => {
  process.exitCode = 1;
  originalError(...args);
};
