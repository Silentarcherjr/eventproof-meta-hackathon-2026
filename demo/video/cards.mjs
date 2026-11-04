// Renders the demo video's cards (opening, real-footage evidence, closing) to 1920x1080 PNGs. Numbers are read from
// committed files, never typed in: benchmark/real/POOLED_v2.json, benchmark/tickets/report.json, benchmark/law/grid.json.
// Usage: node cards.mjs <out_dir> [durations.json]   (with durations: also an animated clip per card, timed to its narration)
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const { chromium } = createRequire(new URL("../../frontend/package.json", import.meta.url))("@playwright/test");
const out = process.argv[2];
const root = new URL("../../", import.meta.url);
const pooled = JSON.parse(fs.readFileSync(new URL("benchmark/real/POOLED_v2.json", root), "utf8"));
const tickets = JSON.parse(fs.readFileSync(new URL("benchmark/tickets/report.json", root), "utf8")).summary;
const grid = JSON.parse(fs.readFileSync(new URL("benchmark/law/grid.json", root), "utf8"));
const gt = grid.statutes[0].cells.map((x) => x.tickets);
const scale = JSON.parse(fs.readFileSync(new URL("benchmark/interaction/report.json", root), "utf8"));
const sp = scale.pooled.numeric_only_spread, pc = (x) => `${Math.round(x * 100)} %`;

const r = pooled.readings, sa = pooled.muse_spark_alone_from_video, n = pooled.labelled_cars, c = pooled.clips;
const STYLE = `
  * { box-sizing: border-box; } html, body { overflow: hidden; background: #09090b; } body { margin: 0; width: 1920px; height: 1080px; background: #09090b; color: #fafafa;
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif; display: flex; flex-direction: column;
    justify-content: center; padding: 0 160px; }
  .kicker { color: #2dd4bf; font-size: 30px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; }
  h1 { font-size: 132px; margin: 12px 0 8px; letter-spacing: -0.03em; } h2 { font-size: 58px; margin: 0 0 36px; line-height: 1.15; }
  .sub { font-size: 44px; color: #d4d4d8; } .note { position: absolute; bottom: 48px; left: 160px; right: 160px;
    font-size: 24px; color: #a1a1aa; }
  table { border-collapse: collapse; font-size: 36px; width: 100%; } td { padding: 18px 16px; border-bottom: 1px solid #27272a; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }
  .good { color: #4ade80; } .bad { color: #f87171; } .muted { color: #a1a1aa; font-size: 30px; }
  .models { margin-top: 40px; font-size: 34px; color: #a1a1aa; }
  body > * { opacity: 0; transform: translateY(18px); }
  [data-at] { opacity: 0; transform: translateY(14px); display: inline-block; }
  tr[data-at] { display: table-row; }
  .on { opacity: 1 !important; transform: none !important; transition: opacity .55s ease, transform .55s ease; }`;
// Reveals each element at its narration time; numbers in a revealed cell count up from 0 (still frames stay exact).
const PLAY = `window.play = () => {
  const t0 = performance.now();
  const show = (el) => { el.classList.add("on"); el.querySelectorAll(".num").forEach(countUp); };
  const countUp = (el) => { const final = el.textContent; const nums = final.match(/\\d+/g) || []; const t = performance.now();
    const step = () => { const k = Math.min(1, (performance.now() - t) / 700);
      let i = 0; el.textContent = final.replace(/\\d+/g, () => String(Math.round(Number(nums[i++]) * (1 - Math.pow(1 - k, 3)))));
      if (k < 1) requestAnimationFrame(step); else el.textContent = final; }; step(); };
  document.querySelectorAll("body > *:not(table):not(.note)").forEach((el, i) => { if (!el.hasAttribute("data-at")) setTimeout(() => show(el), 150 + i * 220); });
  document.querySelectorAll("body > table, body > .note").forEach((el) => setTimeout(() => el.classList.add("on"), 300));
  document.querySelectorAll("[data-at]").forEach((el) => setTimeout(() => show(el), 1000 * Number(el.dataset.at)));
};`;

const CARDS = {
  "card_1": `<div class="kicker">EventProof</div>
    <h2 style="font-size:84px;line-height:1.08">Before an AI camera fines anyone,<br>put the rule, and every ticket, on trial.</h2>
    <table style="margin-top:24px">
      <tr data-at="6.0"><td>Takoma Park, Maryland: AI stop-sign camera citations since January 2026</td><td class="num">$40</td></tr>
      <tr data-at="9.4"><td>Virginia: AI cameras may cite stop-sign violations (April 2026)</td><td class="num">SB84</td></tr>
    </table>
    <div class="models" data-at="12.5">Meta models: Muse Spark · Muse Wonder · SAM 3.1</div>
    <div class="note">Screen capture of the real studio replaying recorded runs (cached Meta outputs) · sources in the README</div>`,
  "card_7": `<div class="kicker">Real footage · labels frozen and pre-registered before any model call</div>
    <h2>The numbers, all recomputed in CI</h2>
    <table>
      <tr data-at="1.0"><td>Real tickets (all correct under the rule) unchanged under every challenge</td><td class="num good">${tickets.tickets - tickets.tickets_beatable_by_menu} of ${tickets.tickets}</td></tr>
      <tr data-at="2.2"><td>Tickets the same law issues on the same ${grid.cars.length} cars, depending on two unwritten numbers</td><td class="num">${Math.min(...gt)} to ${Math.max(...gt)}</td></tr>
      <tr data-at="3.4"><td>California statute on ${scale.vehicle_ids.length.toLocaleString("en-US")} real STOP approaches (drone trajectories, no labels): drivers ticketed</td><td class="num">${pc(sp.min_share)} to ${pc(sp.max_share)}</td></tr>
      <tr data-at="10.5"><td>Cars right: Muse Spark's rule → SAM 3.1 → engine</td><td class="num good">${r.muse_spark_rule.objects_right}/${n}</td></tr>
      <tr data-at="16.7"><td>Cars right: the repair that passed every synthetic test</td><td class="num bad">${r.muse_spark_rule_plus_synthetic_repair.objects_right}/${n}</td></tr>
      <tr data-at="21.9"><td>Muse Spark alone, watching the video: runs that count the cars right</td><td class="num">${sa.counts_exact}/${sa.runs}</td></tr>
    </table>
    <div class="note">Pexels-licensed footage (Novi Sad, Wroclaw, Santos); INTERACTION trajectories (CC BY 4.0) · statutes copied verbatim · labelled sets are small · sources: benchmark/</div>`,
  "card_8": `<div class="kicker">EventProof</div>
    <h2 style="font-size:84px"><span data-at="0.3">Compile the rule.</span><br><span data-at="1.8">Attack it, and every ticket.</span><br><span data-at="4.4">Issue only what survives.</span></h2>
    <div class="models" data-at="6.5">Built with Muse Spark · Muse Wonder · SAM 3.1 · MIT licensed</div>`,
};

const durFile = process.argv[3];
const dur = durFile ? JSON.parse(fs.readFileSync(durFile, "utf8")) : null;
const NARR = { card_1: "1", card_7: "7", card_8: "8" };
const html = (body) => `<!doctype html><html><head><meta charset="utf-8"><style>${STYLE}</style><script>${PLAY}</script></head><body>${body}</body></html>`;
const browser = await chromium.launch({ channel: "chrome", args: ["--window-size=1920,1080"] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
for (const [name, body] of Object.entries(CARDS)) {
  await page.setContent(html(body).replace("<style>", "<style>* { transition: none !important; } "));
  await page.evaluate(() => { document.querySelectorAll("body > *, [data-at]").forEach((el) => el.classList.add("on")); });
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(name);
}
await page.close();
const meta = {};
if (dur) for (const [name, body] of Object.entries(CARDS)) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, screen: { width: 1920, height: 1080 }, recordVideo: { dir: path.join(out, `raw_${name}`), size: { width: 1920, height: 1080 } } });
  const p = await ctx.newPage();
  const t0 = Date.now();
  await p.setContent(html(body));
  await p.waitForTimeout(600);
  const lead = (Date.now() - t0) / 1000;
  await p.evaluate(() => window.play());
  await p.waitForTimeout((dur[NARR[name]] + 1.0) * 1000);
  const v = p.video();
  await ctx.close();
  meta[name] = { file: await v.path(), lead };
}
await browser.close();
if (dur) fs.writeFileSync(path.join(out, "cards.json"), JSON.stringify(meta, null, 2));
