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
const setRange = (p, sel, v) => p.evaluate(([s, val]) => {
  const el = document.querySelector(s);
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  setter.call(el, String(val)); el.dispatchEvent(new Event("input", { bubbles: true }));
}, [sel, v]);
const sweep = (sel, from, to, at, every) => Array.from({ length: Math.abs(to - from) + 1 }, (_, i) =>
  [at + i * every, (p) => setRange(p, sel, from + Math.sign(to - from) * i)]);
const SCENES = {
  2: {
    url: `${STUDIO}/law`, ready: "[data-testid=statute]",
    css: "html { zoom: 1.15 !important; } a[href='/'] { display: none; }",
    steps: [
      [0, (p) => caption(p, "Verbatim Maryland statute · Muse Spark's compiled rule · 30 labelled real cars · no model call on this page")],
      // stillness speed from Spark's 0.05 down to 0.01 (more tickets), then up to "any motion" (none)
      ...sweep("[data-testid=speed]", 4, 0, 18.5, 0.35),
      ...sweep("[data-testid=speed]", 0, 20, 20.1, 0.18),
      [23.9, (p) => setRange(p, "[data-testid=time]", 12)],
      ...sweep("[data-testid=speed]", 20, 7, 24.1, 0.15),
    ],
  },
  3: {
    url: `${STUDIO}/?run=${NOVI_SAD}`, ready: "[data-testid=overall]",
    css: NOVI_CSS + "[data-testid=objects] > li:has(.text-green-400), [data-testid=ambiguity-panel], [data-testid=ticket-panel], [data-testid=gallery], [data-testid=hosted-banner] { display: none; }",
    steps: [
      [0, (p) => caption(p, "Real drone footage (Pexels, Novi Sad) · recorded run: Muse Spark + SAM 3.1 outputs from cache")],
      [1.5, (p) => playAll(p, "[data-testid=video]")],
    ],
  },
  4: {
    url: `${STUDIO}/court`, ready: "[data-testid=case]", pre: "[data-testid=case]",
    css: "html { zoom: 1.05 !important; } a[href='/'] { display: none; } #ep-caption { top: auto !important; bottom: 16px; }",
    steps: [
      [0, (p) => caption(p, "Ticket court · a real ticket (Wroclaw) · Muse Spark's defense recorded earlier, the ruling is deterministic")],
    ],
  },
  5: {
    url: `${STUDIO}/court`, ready: "[data-testid=scoreboard]",
    css: "html { zoom: 1.05 !important; } a[href='/'] { display: none; } #ep-caption { top: auto !important; bottom: 16px; }",
    steps: [
      [0, (p) => caption(p, "All 20 real tickets from labelled footage")],
      [18.8, (p) => scrollTo(p, "[data-testid=contract]", 60)],
    ],
  },
  6: {
    url: `${STUDIO}/?run=${LIVE_RUN}`, ready: "[data-testid=overall]",
    css: NOVI_CSS + "[data-testid=objects], [data-testid=ticket-panel], [data-testid=gallery], [data-testid=hosted-banner] { display: none; } #ep-caption { top: auto !important; bottom: 16px; }",
    steps: [
      [0, (p) => caption(p, "A new rule on the same clip · Muse Spark + Muse Wonder responses recorded earlier")],
      [0.3, (p) => scrollTo(p, "[data-testid=rule-input]", 160)],
      [1.0, async (p) => { await p.fill("[data-testid=rule-input]", ""); await p.type("[data-testid=rule-input]", LIVE_RULE, { delay: 16 }); }],
      [4.8, (p) => scrollTo(p, "[data-testid=overall]", 160)],
      [6.5, (p) => scrollTo(p, "[data-testid=ambiguity-panel]", 16)],
      [7.2, (p) => p.click("[data-testid=ambiguity-ask]")],
      [8.6, (p) => scrollTo(p, "[data-testid=reading-0]", 110)],
      [17.6, async (p) => { await p.goto(`${API}/runs/${LIVE_RUN}/certificate`); await p.addStyleTag({ content: BASE_CSS + "html { zoom: 1.0 !important; } body { max-width: 1100px !important; font-size: 19px !important; }" }); await caption(p, "Rule certificate · built from recorded results, no model call"); }],
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
