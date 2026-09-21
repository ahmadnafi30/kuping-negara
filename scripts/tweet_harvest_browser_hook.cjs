"use strict";

// Tweet Harvest 2.7.1 pins Playwright 1.41.1 and Chromium 121. On Windows,
// that bundled browser can fail with a Side-by-Side activation error. This
// preload hook keeps Tweet Harvest unchanged while directing Playwright to a
// current system Chrome or Edge executable selected by the Python collector.
const Module = require("module");

const browserExecutable = process.env.KUPING_NEGARA_BROWSER_EXECUTABLE;

if (browserExecutable) {
  const originalLoad = Module._load;

  Module._load = function patchedModuleLoad(request, parent, isMain) {
    const loadedModule = originalLoad.apply(this, arguments);

    if (
      request === "playwright-extra" &&
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
