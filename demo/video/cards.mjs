// Renders the demo video's cards (title, real-footage results, closing) to 1920x1080 PNGs. Numbers are read from
// committed files, never typed in: benchmark/real/POOLED.json.
// Usage: node cards.mjs <out_dir>
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const { chromium } = createRequire(new URL("../../frontend/package.json", import.meta.url))("@playwright/test");
const out = process.argv[2];
const root = new URL("../../", import.meta.url);
const pooled = JSON.parse(fs.readFileSync(new URL("benchmark/real/POOLED.json", root), "utf8"));
const figure = "data:image/png;base64," + fs.readFileSync(new URL("docs/media/real_traffic.png", root)).toString("base64");

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
  "card_1": `<div class="kicker">Rule QA for vision AI</div><h1>EventProof</h1>
    <div class="sub">Write a visual rule in plain English. EventProof finds where it is wrong,<br>repairs it, and checks the repair on real video.</div>
    <div class="models">Meta models: Muse Spark · Muse Wonder · SAM 3.1</div>
    <div class="note">Screen capture of the real studio replaying recorded runs (cached model outputs) · synthetic narration voice</div>`,
  "card_6a": `<div style="display:flex;flex-direction:column;align-items:center;gap:24px">
    <h2 style="margin:0;font-size:46px">Same SAM 3.1 tracks, two readings of “wait”: the synthetic-tuned repair passes a real rolling stop</h2>
    <img src="${figure}" style="width:1600px;border-radius:12px;background:white"></div>`,
  "card_6b": `<div class="kicker">Real traffic footage · labels frozen before any model ran</div>
    <h2>${c} clips, 2 cities, ${n} hand-labelled cars</h2>
    <table>
      <tr><td>Muse Spark’s rule → SAM 3.1 → deterministic engine</td>
          <td class="num good">${r.muse_spark_rule.objects_right}/${n} cars</td><td class="num muted">${r.muse_spark_rule.clips_right}/${c} clips</td></tr>
      <tr><td>Same rule + the repair that passed every synthetic test</td>
          <td class="num bad">${r.muse_spark_rule_plus_synthetic_repair.objects_right}/${n} cars</td><td class="num muted">${r.muse_spark_rule_plus_synthetic_repair.clips_right}/${c} clips</td></tr>
      <tr><td>Muse Spark alone, watching the video</td>
          <td class="num">${sa.counts_exact}/${sa.runs} runs<br><span class="muted">count cars right</span></td>
          <td class="num muted">${sa.overall_right}/${sa.runs} runs<br>verdict right</td></tr>
    </table>
    <div class="note">Pexels-licensed footage (Novi Sad, Wroclaw) · n is small; labels by one person · source: benchmark/real/POOLED.json</div>`,
  "card_7": `<div class="kicker">EventProof</div>
    <h2 style="font-size:84px">Build it. Break it. Repair it.<br>Prove it on real video.</h2>
    <div class="sub">Every number in this video is recomputed in CI from committed evidence.</div>
    <div class="models">Muse Spark · Muse Wonder · SAM 3.1 · MIT licensed</div>`,
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
