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
