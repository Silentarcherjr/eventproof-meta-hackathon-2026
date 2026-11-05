import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const fx = (f: string) => path.join(__dirname, "fixtures", f);
const evidence = JSON.parse(readFileSync(fx("evidence.json"), "utf8"));

test("upload -> run -> verdict, overlay and timeline visible", async ({ page }) => {
  let posted: { rule?: string; layout?: string; hasVideo?: boolean } = {};
  await page.route("http://api.test/runs", async (route) => {
    const body = route.request().postDataBuffer()?.toString("latin1") ?? "";
    posted = { hasVideo: body.includes('name="video"'), rule: body.includes("inspection zone") ? "ok" : undefined,
               layout: body.includes("packing_entry") ? "ok" : undefined };
    await route.fulfill({ json: evidence });
  });
  await page.route(`http://api.test/runs/${evidence.run_id}/tracks`, (r) => r.fulfill({ path: fx("tracks.json") }));
  await page.route(`http://api.test/runs/${evidence.run_id}/video`,
    (r) => r.fulfill({ path: fx("tailgate-7.mp4"), contentType: "video/mp4" }));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "EventProof Studio" })).toBeVisible();
  await expect(page.getByTestId("run")).toBeDisabled();

  await page.getByTestId("video-input").setInputFiles(fx("tailgate-7.mp4"));
  await page.getByTestId("run").click();

  await expect(page.getByTestId("overall")).toContainText("FAIL");
  expect(posted).toEqual({ hasVideo: true, rule: "ok", layout: "ok" });
  const objects = page.getByTestId("objects");
  await expect(objects).toContainText("VIOLATION");
  await expect(objects).toContainText("never 1500 ms in inspection");
  await expect(page.getByTestId("assumptions")).toBeVisible();
  await expect(page.getByTestId("provenance")).toContainText("sam-3.1");
  await expect(page.getByTestId("timeline")).toBeVisible();

  // seek to the violating crossing (frame 88): both perceived boxes are drawn on the video
  await objects.getByRole("button", { name: "f88" }).click();
  await expect(page.getByTestId("frame-counter")).toContainText("f88");
  await expect(page.getByTestId("track-box-1")).toBeVisible();
  await expect(page.getByTestId("track-box-0")).toBeVisible();

  // editing the rule marks the shown result as stale
  await page.getByTestId("rule-input").fill("No blue box should ever reach packing.");
  await expect(page.getByTestId("stale")).toBeVisible();
});

test("challenge -> side by side -> SAM confirm -> Muse repair verified on holdout", async ({ page }) => {
  const id = evidence.run_id;
  await page.route("http://api.test/runs", (r) => r.fulfill({ json: evidence }));
  await page.route(`http://api.test/runs/${id}/tracks`, (r) => r.fulfill({ path: fx("tracks.json") }));
  await page.route(`http://api.test/runs/${id}/video`, (r) => r.fulfill({ path: fx("tailgate-7.mp4"), contentType: "video/mp4" }));
  await page.route(`http://api.test/runs/${id}/challenge`, (r) => r.fulfill({ path: fx("challenge.json") }));
  await page.route(`http://api.test/runs/${id}/challenge/files/side_by_side.mp4`,
    (r) => r.fulfill({ path: fx("side_by_side.mp4"), contentType: "video/mp4" }));
  await page.route(`http://api.test/runs/${id}/challenge/sam-confirm`, (r) => r.fulfill({ path: fx("sam_confirm.json") }));
  await page.route(`http://api.test/runs/${id}/stored/*`, (r) => r.fulfill({ status: 404, json: { detail: "not computed yet" } }));
  await page.route("http://api.test/final-report", (r) => r.fulfill({ path: fx("final_report.json") }));
  await page.route(`http://api.test/runs/${id}/before-after`, (r) => r.fulfill({ path: fx("before_after_muse.json") }));
  await page.route(`http://api.test/runs/${id}/challenge/files/counterexample.mp4`,
    (r) => r.fulfill({ path: fx("counterexample.mp4"), contentType: "video/mp4" }));
  let proposer = "";
  await page.route(`http://api.test/runs/${id}/repair`, async (r) => {
    proposer = JSON.parse(r.request().postData() ?? "{}").proposer;
    await r.fulfill({ path: fx("repair_muse.json") });
  });

  await page.goto("/");
  await page.getByTestId("video-input").setInputFiles(fx("tailgate-7.mp4"));
  await page.getByTestId("run").click();
  await page.getByTestId("challenge").click();

  const cx = page.getByTestId("counterexample");
  await expect(cx).toContainText("DRIVE_THROUGH", { ignoreCase: true });
  await expect(cx).toContainText("specification error");
  await expect(page.getByTestId("suite")).toContainText("drive_through");
  await expect(page.getByTestId("side-by-side")).toBeVisible();

  await page.getByTestId("sam-confirm").click();
  await expect(page.getByTestId("sam-result")).toContainText("real SAM 3.1");

  await page.getByTestId("repair-muse").click();
  expect(proposer).toBe("muse");
  // the headline is the first accepted proposal in Muse's order (not the best holdout score)
  await expect(page.getByTestId("repair-headline")).toContainText("Repair verified on unseen cases: 144/200 → 164/200");
  await expect(page.getByTestId("repair-headline")).toContainText("2 of 8 proposals accepted");
  await expect(page.getByTestId("decision-accepted")).toHaveCount(2);
  await expect(page.getByTestId("decision-rejected").first()).toContainText("holdout regression");

  // before / after: the same failing case judged by both rules, the counter chart, unseen and final results
  const ba = page.getByTestId("before-after");
  await expect(page.getByTestId("ba-before")).toContainText("Says PASS — wrong");
  await expect(page.getByTestId("ba-after")).toContainText("Says FAIL — right");
  await expect(page.getByTestId("counter-chart")).toBeVisible();
  await expect(page.getByTestId("ba-story")).toContainText("1.53 s");
  await expect(page.getByTestId("ba-holdout")).toContainText("144/200");
  await expect(page.getByTestId("ba-holdout")).toContainText("164/200");
  await expect(page.getByTestId("ba-final")).toContainText("158/200");
  await expect(page.getByTestId("ba-final")).toContainText("117/120");
  await expect(ba).toContainText("2 of 8 accepted");

  // editing the rule hides the challenge panel and the comparison (they belonged to the previous inputs)
  await page.getByTestId("rule-input").fill("No blue box should ever reach packing.");
  await expect(page.getByTestId("challenge-panel")).toHaveCount(0);
  await expect(page.getByTestId("before-after")).toHaveCount(0);
});

test("API errors are shown, not swallowed", async ({ page }) => {
  await page.route("http://api.test/runs", (r) => r.fulfill({ status: 503, json: { detail: "live-call allowance 0 is used up" } }));
  await page.goto("/");
  await page.getByTestId("video-input").setInputFiles(fx("tailgate-7.mp4"));
  await page.getByTestId("run").click();
  await expect(page.getByTestId("error")).toContainText("allowance");
});

test("?run= reopens a recorded run with its stored results, without calling any model", async ({ page }) => {
  const id = evidence.run_id;
  const posts: string[] = [];
  page.on("request", (r) => { if (r.method() === "POST") posts.push(r.url()); });
  await page.route(`http://api.test/runs/${id}`, (r) => r.fulfill({ json: evidence }));
  await page.route(`http://api.test/runs/${id}/tracks`, (r) => r.fulfill({ path: fx("tracks.json") }));
  await page.route(`http://api.test/runs/${id}/video`, (r) => r.fulfill({ path: fx("tailgate-7.mp4"), contentType: "video/mp4" }));
  const stored: Record<string, string> = { challenge: "challenge.json", "sam-confirm": "sam_confirm.json",
                                           "repair-muse": "repair_muse.json", "before-after-muse": "before_after_muse.json" };
  await page.route(`http://api.test/runs/${id}/stored/*`, (r) => {
    const key = r.request().url().split("/").pop()!;
    return stored[key] ? r.fulfill({ path: fx(stored[key]) }) : r.fulfill({ status: 404, json: { detail: "not computed yet" } });
  });
  await page.route("http://api.test/final-report", (r) => r.fulfill({ path: fx("final_report.json") }));
  await page.route(`http://api.test/runs/${id}/challenge/files/*`, (r) => r.fulfill({ path: fx("side_by_side.mp4"), contentType: "video/mp4" }));

  await page.goto(`/?run=${id}`);
  await expect(page.getByTestId("overall")).toContainText("FAIL");
  await expect(page.getByTestId("rule-input")).toHaveValue(evidence.rule.text);
  await expect(page.getByTestId("counterexample")).toBeVisible();
  await expect(page.getByTestId("sam-result")).toContainText("real SAM 3.1");
  await expect(page.getByTestId("repair-headline")).toContainText("2 of 8 proposals accepted");
  await expect(page.getByTestId("ba-after")).toContainText("Says FAIL — right");
  // the stepper summarises where the rule stands (certificate unavailable here: step 4 stays a link)
  await expect(page.getByTestId("step-2")).toContainText("test scenes fool it");
  await expect(page.getByTestId("step-3")).toContainText("2/8 repairs hold on hidden scenes");
  await expect(page.getByTestId("certificate-link")).toHaveAttribute("href", `http://api.test/runs/${id}/certificate`);
  expect(posts).toEqual([]);
});

test("a new rule on the open run's video posts to /runs/{id}/rule", async ({ page }) => {
  const id = evidence.run_id;
  let body: { rule_text?: string } = {};
  await page.route(`http://api.test/runs/${id}`, (r) => r.fulfill({ json: evidence }));
  await page.route(`http://api.test/runs/${id}/tracks`, (r) => r.fulfill({ path: fx("tracks.json") }));
  await page.route(`http://api.test/runs/${id}/video`, (r) => r.fulfill({ path: fx("tailgate-7.mp4"), contentType: "video/mp4" }));
  await page.route(`http://api.test/runs/${id}/rule`, async (r) => {
    body = JSON.parse(r.request().postData() ?? "{}");
    await r.fulfill({ json: { ...evidence, run_id: "20261102T000000Z-0000beef", rule: { ...evidence.rule, text: body.rule_text } } });
  });
  await page.route("http://api.test/runs/20261102T000000Z-0000beef/tracks", (r) => r.fulfill({ path: fx("tracks.json") }));
  await page.goto(`/?run=${id}`);
  await expect(page.getByTestId("overall")).toContainText("FAIL");
  await expect(page.getByTestId("run")).toBeDisabled();  // nothing changed yet
  await page.getByTestId("rule-input").fill("Every blue box must stand still 2 s at inspection.");
  await page.getByTestId("run").click();
  await expect(page.getByTestId("stale")).toHaveCount(0);
  expect(body.rule_text).toBe("Every blue box must stand still 2 s at inspection.");
});

test("hosted server: gallery of real clips, first clip opened, live caps shown", async ({ page }) => {
  const id = evidence.run_id;
  await page.route("http://api.test/health", (r) => r.fulfill({ json: {
    status: "ok", mode: "hosted", meta_api_key_configured: true, muse_model: "muse-spark-1.3", sam_model: "sam-3.1",
    live_calls_remaining: { muse: 40, sam: 6 }, rate_limit: "20/600s", demo_runs: [id, "20261102T040830Z-37064c4a"],
    demo_clips: [{ run_id: id, clip: "tailgate-7.mp4", rule: evidence.rule.text, overall: "FAIL" },
                 { run_id: "20261102T040830Z-37064c4a", clip: "novisad_approach_a.mp4", rule: "Every car must wait", overall: "FAIL" }] } }));
  await page.route(`http://api.test/runs/${id}`, (r) => r.fulfill({ json: evidence }));
  await page.route(`http://api.test/runs/${id}/tracks`, (r) => r.fulfill({ path: fx("tracks.json") }));
  await page.route(`http://api.test/runs/${id}/video`, (r) => r.fulfill({ path: fx("tailgate-7.mp4"), contentType: "video/mp4" }));
  await page.route(`http://api.test/runs/${id}/stored/*`, (r) => r.fulfill({ status: 404, json: { detail: "not computed yet" } }));

  await page.goto("/");
  await expect(page.getByTestId("hosted-banner")).toContainText("Muse 40, SAM 6");
  await expect(page.getByTestId("gallery")).toContainText("Stop line, drone view (Novi Sad)");
  await expect(page.getByTestId(`clip-${id}`)).toHaveAttribute("href", `/?run=${id}`);
  await expect(page.getByTestId("overall")).toContainText("FAIL");  // the first demo run opens by itself
});

test("tickets panel: robustness per object and Muse Spark's defense of a ticket", async ({ page }) => {
  const id = evidence.run_id;
  await page.route(`http://api.test/runs/${id}`, (r) => r.fulfill({ json: evidence }));
  await page.route(`http://api.test/runs/${id}/tracks`, (r) => r.fulfill({ path: fx("tracks.json") }));
  await page.route(`http://api.test/runs/${id}/video`, (r) => r.fulfill({ path: fx("tailgate-7.mp4"), contentType: "video/mp4" }));
  await page.route(`http://api.test/runs/${id}/stored/*`, (r) => r.fulfill({ status: 404, json: { detail: "not computed yet" } }));
  await page.route(`http://api.test/runs/${id}/robustness`, (r) => r.fulfill({ json: [
    { object_id: 0, verdict: "PASS", status: "ROBUST", flips: [], smallest_flip: null },
    { object_id: 1, verdict: "VIOLATION", status: "DEPENDS_ON_THRESHOLD", smallest_flip: "'standing still' threshold x2 -> PASS",
      flips: [{ variant: "'standing still' threshold x2", family: "stillness", tier: "threshold", value: 2, verdict: "PASS" }] }] }));
  let posted = false;
  await page.route(`http://api.test/runs/${id}/objects/1/defense`, (r) => { posted = true; return r.fulfill({ json: {
    object_id: 1, status: "DEPENDS_ON_THRESHOLD", concede: false, concession: "", strongest: "stillness:2.0", cached: false,
    challenges: [{ id: "stillness:2.0", label: "'standing still' threshold x2", argument: "The car crawled; 'stop' is not defined as a speed.", overturns: true },
                 { id: "anchor:bottom_center", label: "measured at its bottom", argument: "The line is on the road.", overturns: false }] } }); });

  await page.goto(`/?run=${id}`);
  await expect(page.getByTestId("ticket-panel")).toContainText("1 ticket(s): 0 hold up");
  await expect(page.getByTestId("ticket-1")).toContainText("hangs on an unwritten number");
  await page.getByTestId("defend-1").click();
  await expect(page.getByTestId("defense-1")).toContainText("overturns the ticket");
  expect(posted).toBe(true);
});

test("drag the law: compare against the selected statute's Spark cell and reset", async ({ page }) => {
  // Frozen real grid; alter only the second statute's chosen indices to exercise switching.
  const grid: import("../lib/api").LawGrid = JSON.parse(readFileSync(path.join(__dirname, "../../benchmark/law/grid.json"), "utf8"));
  const first = grid.statutes[0];
  const base = first.cells.find((c) => c.min_s === first.spark_values!.min_s && c.speed === first.spark_values!.speed)!;
  const different = first.cells.find((c) => c.verdicts !== base.verdicts)!;
  const second = grid.statutes[1];
  const secondBase = second.cells.find((c) => c.verdicts !== base.verdicts && c.speed !== null)!;
  second.spark_values = { min_s: secondBase.min_s, speed: secondBase.speed! };
  await page.route("http://api.test/law/grid", (r) => r.fulfill({ json: grid }));
  await page.goto("/law");
  const count = page.getByTestId("law-changed");
  const changed = page.locator('[data-testid="law-car"][data-changed="true"]');
  await expect(count).toHaveText("0 cars changed verdict from Spark’s interpretation");
  // Label disagreement must stay distinct from a change from Spark.
  expect(base.verdicts.split("").some((v, i) => v !== grid.cars[i].truth[0] && v !== "-")).toBe(true);
  await expect(changed).toHaveCount(0);
  await expect(page.getByTestId("law-car").filter({ hasText: /^U$/ }).first()).not.toHaveClass(/ring-white/);
  await expect(page.locator('[data-testid="law-car"].ring-white').first()).toBeVisible();
  await page.getByTestId("time").fill(String(grid.times_s.indexOf(different.min_s)));
  await page.getByTestId("speed").fill(String(grid.speeds.indexOf(different.speed)));
  const flips = different.verdicts.split("").filter((v, i) => v !== base.verdicts[i]).length;
  expect(flips).toBeGreaterThan(0);
  await expect(count).toHaveText(`${flips} ${flips === 1 ? "car" : "cars"} changed verdict from Spark’s interpretation`);
  await expect(changed).toHaveCount(flips);
  await expect(changed.first()).toHaveAttribute("aria-label", /changed from Spark’s/);
  await expect(changed.first()).toHaveAttribute("title", /changed from Spark’s/);
  await expect(changed.first().locator(".bg-sky-300")).toBeVisible();
  await page.getByRole("button", { name: "Reset to Spark", exact: true }).click();
  await expect(page.getByTestId("time")).toHaveValue(String(grid.times_s.indexOf(base.min_s)));
  await expect(page.getByTestId("speed")).toHaveValue(String(grid.speeds.indexOf(base.speed)));
  await expect(count).toHaveText("0 cars changed verdict from Spark’s interpretation");
  await expect(changed).toHaveCount(0);
  await page.getByRole("button", { name: second.citation, exact: true }).click();
  await expect(page.getByTestId("time")).toHaveValue(String(grid.times_s.indexOf(secondBase.min_s)));
  await expect(page.getByTestId("speed")).toHaveValue(String(grid.speeds.indexOf(secondBase.speed)));
  await expect(count).toHaveText("0 cars changed verdict from Spark’s interpretation");
  await expect(changed).toHaveCount(0);
  await page.getByTestId("time").fill("12");
  await page.getByRole("button", { name: "Reset to Spark", exact: true }).click();
  await expect(page.getByTestId("time")).toHaveValue(String(grid.times_s.indexOf(secondBase.min_s)));
  await expect(count).toHaveText("0 cars changed verdict from Spark’s interpretation");
});

for (const missing of [null, { min_s: 99, speed: 0.05 }]) {
  test(`drag the law: ${missing ? "unavailable Spark cell" : "missing Spark values"} never reuses another statute's baseline`, async ({ page }) => {
  const grid: import("../lib/api").LawGrid = JSON.parse(readFileSync(path.join(__dirname, "../../benchmark/law/grid.json"), "utf8"));
  grid.statutes[1].spark_values = missing;
  await page.route("http://api.test/law/grid", (r) => r.fulfill({ json: grid }));
  await page.goto("/law");
  await expect(page.getByTestId("law-changed")).toContainText("0 cars changed");
  await page.getByRole("button", { name: grid.statutes[1].citation, exact: true }).click();
  await expect(page.getByTestId("law-changed")).toHaveText("Spark comparison unavailable for this statute.");
  await expect(page.getByRole("button", { name: "Reset to Spark", exact: true })).toBeDisabled();
  await expect(page.locator('[data-testid="law-car"][data-changed="true"]')).toHaveCount(0);
  });
}

test("ticket court: scoreboard, a ticket the defense beats opens first, contract block", async ({ page }) => {
  const base = { set: "s", description: "d", intended: "VIOLATION", verdict: "VIOLATION", smallest_flip: null, flipping: [],
                 rule_text: "rule", explanation: "x", anchor: "bottom_center", first_frame: 0, last_frame: 9,
                 events: [{ op: "CROSSES", target: "line", status: "TRUE", frame: 5, timestamp_ms: 500, reason: "" }],
                 defense: { chosen: [], strongest: "none", concede: true, concession: "nothing credible", strongest_overturns: false, any_overturns: false, arguments: [] } };
  await page.route("http://api.test/tickets/court", (r) => r.fulfill({ json: {
    summary: {}, cases: [
      { ...base, clip: "a.mp4", object_id: 1, run_id: "r1", correct: "right", status: "ROBUST" },
      { ...base, clip: "b.mp4", object_id: 2, run_id: "r2", correct: "right", status: "DEPENDS_ON_THRESHOLD",
        smallest_flip: "'standing still' threshold x2 -> PASS", flipping: ["stillness:2.0"],
        defense: { ...base.defense, concede: false, strongest: "stillness:2.0", strongest_overturns: true, any_overturns: true,
                   arguments: [{ id: "stillness:2.0", argument: "'Still' is never defined." }] } }],
    contract: { policy: "auto-issue only ROBUST", all_tickets: { tickets: 2, false_tickets: 1, upper_95: 0.9 },
                auto_issued: { tickets: 1, false_tickets: 0, upper_95: 0.79 }, held_for_review: { tickets: 1, false_tickets: 1, by_status: {} },
                labels_needed_error_free: { "2%": 188, "5%": 73 } } } }));
  await page.goto("/court");
  await expect(page.getByTestId("headline")).toContainText("1 of 2 hold up");
  await expect(page.getByTestId("case")).toContainText("correctly issued");
  await expect(page.getByTestId("case")).toContainText("rests on a choice nobody wrote down");
  await expect(page.getByTestId("case")).toContainText("wins");
  await expect(page.getByTestId("contract")).toContainText("188");
});

// Recorded from local lab functions on development seed 0; synthetic perfect tracks, no model call.
const rollingStopLab = JSON.parse(readFileSync(fx("lab-rolling-stop.json"), "utf8"));

test("traffic lab: rolling stop opens first, contract changes the same car, reset restores Spark", async ({ page }) => {
  const queries: string[] = [];
  await page.route("http://api.test/lab/scenes", (r) => r.fulfill({ json: rollingStopLab.scenes }));
  await page.route("http://api.test/lab/pair", (r) => r.fulfill({ json: rollingStopLab.pair }));
  await page.route("http://api.test/lab/*/0/judge?*", (r) => {
    const url = new URL(r.request().url());
    queries.push(url.pathname + url.search);
    const contract = url.searchParams.get("max_speed") === "0.01" && url.searchParams.get("any_direction") === "true";
    return r.fulfill({ json: contract ? rollingStopLab.contract : rollingStopLab.spark });
  });
  await page.route("http://api.test/lab/**/video", (r) => r.fulfill({ path: fx("tailgate-7.mp4"), contentType: "video/mp4" }));
  await page.goto("/lab");
  await expect(page.getByTestId("lab-scene")).toHaveValue("rolling_stop");
  await expect(page.getByText("Synthetic scene, perfect tracks (not SAM)", { exact: true })).toBeVisible();
  const car = page.getByTestId("lab-verdicts").locator("tbody tr").first();
  await expect(car.locator("td").nth(2)).toContainText("PASS");
  await page.getByTestId("lab-contract").click();
  await expect(page.getByTestId("lab-flip")).toContainText("Car 0: PASS → VIOLATION after changing standing-still speed.");
  await expect(car.locator("td").nth(1)).toContainText("PASS");
  await expect(car.locator("td").nth(2)).toContainText("VIOLATION");
  await page.getByRole("button", { name: "Reset to Spark", exact: true }).click();
  await expect(page.getByTestId("lab-flip")).toContainText("No car flips relative to Spark");
  await expect(car.locator("td").nth(2)).toContainText("PASS");
  expect(queries.length).toBeGreaterThanOrEqual(3);
  expect(queries.every((q) => q.startsWith("/lab/rolling_stop/0/judge?"))).toBe(true);
});
