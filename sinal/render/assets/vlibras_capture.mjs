import path from "node:path";
import { pathToFileURL } from "node:url";

const stdin = [];
for await (const chunk of process.stdin) stdin.push(chunk);
const input = JSON.parse(Buffer.concat(stdin).toString("utf8"));
const playwrightModule = path.join(input.runtimeRoot, "node_modules", "@playwright", "test", "index.mjs");
const { chromium } = await import(pathToFileURL(playwrightModule).href);
const launchOptions = {
  headless: true,
  args: ["--enable-webgl", "--ignore-gpu-blocklist", "--use-angle=swiftshader-webgl"],
};
if (input.chromiumExecutable) launchOptions.executablePath = input.chromiumExecutable;

const browser = await chromium.launch(launchOptions);
const context = await browser.newContext({
  viewport: { width: input.width, height: input.height },
  recordVideo: { dir: input.captureDirectory, size: { width: input.width, height: input.height } },
});
const recordingStarted = performance.now();
const page = await context.newPage();
process.stderr.write("stage=page-created\n");
await page.goto(input.controlUrl, { waitUntil: "load", timeout: input.timeoutMs });

process.stderr.write("stage=page-content-loaded\n");
await page.waitForFunction(() => document.body.dataset.state === "loaded", null, { timeout: input.timeoutMs });
process.stderr.write("stage=unity-loaded\n");
await page.evaluate(
  config => window.configureVlibras(config.dictionaryUrl, config.avatar),
  { dictionaryUrl: input.dictionaryUrl, avatar: input.avatar },
);
await page.waitForTimeout(1500);
const trimOffsetSeconds = (performance.now() - recordingStarted) / 1000;
await page.evaluate(gloss => window.startGloss(gloss), input.gloss);
await page.waitForFunction(() => JSON.parse(document.body.dataset.playing || "[]")[0] === "True", null, { timeout: input.timeoutMs });
process.stderr.write("stage=animation-started\n");
const animationStarted = performance.now();
await page.waitForFunction(() => {
  const state=JSON.parse(document.body.dataset.playing || "[]");
  const counter=JSON.parse(document.body.dataset.counter || "[0,0]");
  return state[0]==="False"&&state[3]==="False"&&counter[1]>0&&counter[0]===counter[1];
}, null, { timeout: input.timeoutMs });
process.stderr.write("stage=animation-complete\n");
const animationSeconds = (performance.now() - animationStarted) / 1000;
const counter = await page.locator("body").evaluate(el => JSON.parse(el.dataset.counter || "[0,0]"));
await page.waitForTimeout(400);
const video = page.video();
await page.close();
await context.close();
const recording = await video.path();
await browser.close();
process.stdout.write(JSON.stringify({ recording, trimOffsetSeconds, animationSeconds, completedSigns: counter[0], totalSigns: counter[1] }) + "\n");
