"use strict";

// Tweet Harvest 2.7.1 pins Playwright 1.41.1 and Chromium 121. On Windows,
// that bundled browser can fail with a Side-by-Side activation error. This
// preload hook keeps Tweet Harvest unchanged while directing Playwright to a
// current system Chrome or Edge executable selected by the Python collector.
const Module = require("module");

const browserExecutable = process.env.KUPING_NEGARA_BROWSER_EXECUTABLE;
const unattended = process.env.KUPING_NEGARA_NON_INTERACTIVE === "1";
const token = process.env.X_AUTH_TOKEN;

if (browserExecutable || unattended) {
  const originalLoad = Module._load;

  Module._load = function patchedModuleLoad(request, parent, isMain) {
    const loadedModule = originalLoad.apply(this, arguments);

    // Tweet Harvest 2.7.1 asks prompts for token and exportFormat. Supply
    // those answers in memory; the secret never enters OS command arguments.
    if (
      unattended && request === "prompts" &&
      /[\\/]tweet-harvest[\\/]dist[\\/]bin\.js$/.test(parent?.filename || "")
    ) {
      return async function answerCollectionPrompts(questions) {
        if (!token || token.trim().length < 30) {
          throw new Error("A valid X_AUTH_TOKEN is required");
        }
        const answers = {};
        for (const question of questions) {
          if (question.name === "token") answers.token = token.trim();
          else if (question.name === "exportFormat") answers.exportFormat = "csv";
          else throw new Error("Unexpected Tweet Harvest prompt; update adapter");
        }
        return answers;
      };
    }

    if (
      browserExecutable && request === "playwright-extra" &&
      loadedModule?.chromium &&
      !loadedModule.chromium.__kupingNegaraBrowserPatched
    ) {
      const chromium = loadedModule.chromium;
      const originalLaunch = chromium.launch.bind(chromium);

      chromium.launch = function launchWithSystemBrowser(options = {}) {
        return originalLaunch({ ...options, executablePath: browserExecutable });
      };
      Object.defineProperty(chromium, "__kupingNegaraBrowserPatched", {
        value: true,
      });
    }

    return loadedModule;
  };
}
