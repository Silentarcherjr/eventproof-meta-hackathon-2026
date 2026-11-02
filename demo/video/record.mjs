// Records the studio scenes of the demo video with Playwright (real app, recorded runs, cached model outputs).
// Usage: node record.mjs <out_dir> <durations.json>   (studio on :3000, API on :8000, both started beforehand)
// durations.json: {"2": seconds, "3": ..., "4": ..., "5": ...} = narration length of each studio scene.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const { chromium } = createRequire(new URL("../../frontend/package.json", import.meta.url))("@playwright/test");
const [out, durFile] = process.argv.slice(2);
const dur = JSON.parse(fs.readFileSync(durFile, "utf8"));
const STUDIO = "http://localhost:3000";
const NOVI_SAD = "20261102T040830Z-37064c4a";
const DEMO = "20261028T023754Z-a922b5bb";
const PAD = 1.2; // seconds of picture after the narration ends

const BASE_CSS = `
  nextjs-portal { display: none !important; }
  html { scroll-behavior: smooth; zoom: 1.3; }
  #ep-caption { position: fixed; right: 24px; top: 16px; max-width: 760px; z-index: 50; padding: 6px 12px; border-radius: 8px;
    background: rgba(9,9,11,.85); color: #e4e4e7; font: 600 18px/1.3 system-ui, sans-serif; border: 1px solid #3f3f46; }`;

async function caption(page, text) {
  await page.evaluate((t) => {
    let el = document.getElementById("ep-caption");
    if (!el) { el = document.createElement("div"); el.id = "ep-caption"; document.body.appendChild(el); }
    el.textContent = t;
  }, text);
}

const scrollTo = (page, sel, offset = 24) => page.evaluate(([s, o]) => {
  const el = document.querySelector(s);
  if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - o, behavior: "smooth" });
}, [sel, offset]);

const playAll = (page, sel) => page.evaluate((s) => document.querySelectorAll(s).forEach((v) => { v.muted = true; v.currentTime = 0; v.play(); }), sel);

// each scene: url, extra CSS, ready selector, and a script of [at_seconds, action]
const API = "http://localhost:8000";
const LIVE_RULE = "Every car must remain behind the stop line for at least 2 seconds before it crosses it.";
const LIVE_RUN = "20261102T080747Z-6b0ae7d4"; // recorded run of that rule (readings, Challenge, certificate)
const NOVI_CSS = `.lg\\:grid-cols-\\[minmax\\(0\\,3fr\\)_minmax\\(0\\,2fr\\)\\] { grid-template-columns: minmax(0,1.25fr) minmax(0,2fr) !important; }
          [data-testid=results] { display: flex; flex-direction: column; }
          [data-testid=overall] { order: -2; } [data-testid=assumptions] { order: -1; }
          [data-testid=challenge-panel] { display: none; }
          html { zoom: 1.12; }`;

// each scene: url, extra CSS, ready selector, optional pre-scroll target, and a script of [at_seconds, action]
const SCENES = {
  3: {
    url: `${STUDIO}/?run=${NOVI_SAD}`, ready: "[data-testid=overall]",
    css: NOVI_CSS + "[data-testid=objects] > li:has(.text-green-400), [data-testid=ambiguity-panel] { display: none; }",
    steps: [
      [0, (p) => caption(p, "Real drone footage (Pexels, Novi Sad) · recorded run: Muse Spark + SAM 3.1 outputs from cache")],
      [1.5, (p) => playAll(p, "[data-testid=video]")],
    ],
  },
  4: {
    url: `${STUDIO}/?run=${NOVI_SAD}`, ready: "[data-testid=overall]",
    css: NOVI_CSS + "[data-testid=objects] { display: none; } #ep-caption { top: auto !important; bottom: 16px; }",
    steps: [
      [0, (p) => caption(p, "A new rule on the same clip · Muse Spark + Muse Wonder responses recorded earlier today")],
      [0.3, (p) => scrollTo(p, "[data-testid=rule-input]", 160)],
      [1.0, async (p) => { await p.fill("[data-testid=rule-input]", ""); await p.type("[data-testid=rule-input]", LIVE_RULE, { delay: 18 }); }],
      [3.6, (p) => p.click("[data-testid=run]")],
      [5.0, (p) => scrollTo(p, "[data-testid=overall]", 160)],
      [7.0, (p) => scrollTo(p, "[data-testid=ambiguity-panel]", 16)],
      [8.0, (p) => p.click("[data-testid=ambiguity-ask]")],
      [9.5, (p) => scrollTo(p, "[data-testid=reading-0]", 110)],
    ],
  },
  5: {
    url: `${API}/runs/${LIVE_RUN}/certificate`, ready: "h1",
    css: "html { zoom: 1.0 !important; } body { max-width: 1100px !important; font-size: 19px !important; }",
    steps: [
      [0, (p) => caption(p, "Rule certificate · built from recorded results, no model call")],
      [7.5, (p) => p.evaluate(() => window.scrollTo({ top: document.body.scrollHeight * 0.55, behavior: "smooth" }))],
    ],
  },
  6: {
    url: `${STUDIO}/?run=${DEMO}`, ready: "[data-testid=ba-final]", pre: "[data-testid=challenge-panel]",
    css: "",
    steps: [
      [0.2, (p) => caption(p, "Warehouse version · Challenge Mode + Muse Spark repair (recorded run)")],
      [1.0, (p) => playAll(p, "[data-testid=side-by-side] video")],
      [6.5, (p) => scrollTo(p, "[data-testid=repair-headline]", 40)],
      [11, (p) => scrollTo(p, "[data-testid=before-after]", 16)],
      [11.5, (p) => playAll(p, "[data-testid=ba-video] video, video[data-testid=ba-video]")],
    ],
  },
};

const browser = await chromium.launch({ channel: "chrome", args: ["--window-size=1920,1080"] });
const meta = {};
for (const [id, sc] of Object.entries(SCENES)) {
  if (!(id in dur)) continue;
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, screen: { width: 1920, height: 1080 },
    recordVideo: { dir: path.join(out, `raw_${id}`), size: { width: 1920, height: 1080 } } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  await page.goto(sc.url);
  await page.waitForSelector(sc.ready, { timeout: 30000 });
  await page.addStyleTag({ content: BASE_CSS + sc.css });
  await page.waitForTimeout(800);
  if (sc.pre) await page.evaluate((s) => {  // jump (no animation) to the scene's start before the kept footage begins
    const el = document.querySelector(s);
    document.documentElement.style.scrollBehavior = "auto";
    window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 16);
    document.documentElement.style.scrollBehavior = "smooth";
  }, sc.pre);
  await page.waitForTimeout(1200); // layout settles, videos load
  const lead = (Date.now() - t0) / 1000;
  const start = Date.now();
  for (const [at, act] of sc.steps) {
    const wait = at * 1000 - (Date.now() - start);
    if (wait > 0) await page.waitForTimeout(wait);
    await act(page);
  }
  const end = (dur[id] + PAD) * 1000 - (Date.now() - start);
  if (end > 0) await page.waitForTimeout(end);
  const video = page.video();
  await ctx.close();
  meta[id] = { file: await video.path(), lead, length: dur[id] + PAD };
  console.log(`scene ${id}: lead ${lead.toFixed(2)} s, length ${(dur[id] + PAD).toFixed(2)} s`);
}
await browser.close();
fs.writeFileSync(path.join(out, "scenes.json"), JSON.stringify(meta, null, 2));
