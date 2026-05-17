import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { setTimeout as delay } from "node:timers/promises";

const baseUrl = process.env.CHINATRAVEL_SMOKE_URL || "http://127.0.0.1:5173/";
const chromePath =
  process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

async function waitFor(url, attempts = 40) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // keep polling
    }
    await delay(500);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function assertIncludes(text, expected) {
  if (!text.includes(expected)) {
    throw new Error(`Expected page HTML to include: ${expected}`);
  }
}

await waitFor(baseUrl);
const html = await (await fetch(baseUrl)).text();

assertIncludes(html, "ChinaTravel");
assertIncludes(html, "/src/main.ts");

if (existsSync(chromePath)) {
  const chrome = spawn(
    chromePath,
    [
      "--new-window",
      "--user-data-dir=%TEMP%\\chinatravel-smoke-chrome",
      "--disable-first-run-ui",
      "--no-first-run",
      baseUrl,
    ],
    { detached: true, stdio: "ignore" },
  );
  chrome.unref();
}

console.log(`Visual smoke ready: ${baseUrl}`);
