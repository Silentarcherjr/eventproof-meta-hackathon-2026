// Renders the demo video's cards (opening, real-footage evidence, closing) to 1920x1080 PNGs. Numbers are read from
// committed files, never typed in: benchmark/real/POOLED_v2.json, benchmark/tickets/report.json, benchmark/law/grid.json.
// Usage: node cards.mjs <out_dir>
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

const r = pooled.readings, sa = pooled.muse_spark_alone_from_video, n = pooled.labelled_cars, c = pooled.clips;
const STYLE = `
  * { box-sizing: border-box; } body { margin: 0; width: 1920px; height: 1080px; background: #09090b; color: #fafafa;
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif; display: flex; flex-direction: column;
    justify-content: center; padding: 0 160px; }
  .kicker { color: #2dd4bf; font-size: 30px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; }
  h1 { font-size: 132px; margin: 12px 0 8px; letter-spacing: -0.03em; } h2 { font-size: 58px; margin: 0 0 36px; line-height: 1.15; }
  .sub { font-size: 44px; color: #d4d4d8; } .note { position: absolute; bottom: 48px; left: 160px; right: 160px;
    font-size: 24px; color: #a1a1aa; }
  table { border-collapse: collapse; font-size: 40px; width: 100%; } td { padding: 22px 16px; border-bottom: 1px solid #27272a; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }
  .good { color: #4ade80; } .bad { color: #f87171; } .muted { color: #a1a1aa; font-size: 30px; }
  .models { margin-top: 40px; font-size: 34px; color: #a1a1aa; }`;

const CARDS = {
  "card_1": `<div class="kicker">EventProof</div>
    <h2 style="font-size:84px;line-height:1.08">Before an AI camera fines anyone,<br>put the rule, and every ticket, on trial.</h2>
    <table style="margin-top:24px">
      <tr><td>Takoma Park, Maryland: AI stop-sign camera citations since January 2026</td><td class="num">$40</td></tr>
      <tr><td>Virginia: AI cameras may cite stop-sign violations (April 2026)</td><td class="num">SB84</td></tr>
    </table>
    <div class="models">Meta models: Muse Spark · Muse Wonder · SAM 3.1</div>
    <div class="note">Screen capture of the real studio replaying recorded runs (cached Meta outputs) · sources in the README</div>`,
  "card_7": `<div class="kicker">Real footage · labels frozen and pre-registered before any model call</div>
    <h2>The numbers, all recomputed in CI</h2>
    <table>
      <tr><td>Real tickets (all correct under the rule) unchanged under every challenge</td><td class="num good">${tickets.tickets - tickets.tickets_beatable_by_menu} of ${tickets.tickets}</td></tr>
      <tr><td>Tickets the same law issues on the same ${grid.cars.length} cars, depending on two unwritten numbers</td><td class="num">${Math.min(...gt)} to ${Math.max(...gt)}</td></tr>
      <tr><td>Cars right: Muse Spark's rule → SAM 3.1 → engine</td><td class="num good">${r.muse_spark_rule.objects_right}/${n}</td></tr>
      <tr><td>Cars right: the repair that passed every synthetic test</td><td class="num bad">${r.muse_spark_rule_plus_synthetic_repair.objects_right}/${n}</td></tr>
      <tr><td>Muse Spark alone, watching the video: runs that count the cars right</td><td class="num">${sa.counts_exact}/${sa.runs}</td></tr>
    </table>
    <div class="note">Pexels-licensed footage (Novi Sad, Wroclaw, Santos); statutes copied verbatim · labelled sets are small · sources: benchmark/</div>`,
  "card_8": `<div class="kicker">EventProof</div>
    <h2 style="font-size:84px">Compile the rule.<br>Attack it, and every ticket.<br>Issue only what survives.</h2>
    <div class="models">Built with Muse Spark · Muse Wonder · SAM 3.1 · MIT licensed</div>`,
};

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
for (const [name, body] of Object.entries(CARDS)) {
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${STYLE}</style></head><body>${body}</body></html>`);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(name);
}
await browser.close();
