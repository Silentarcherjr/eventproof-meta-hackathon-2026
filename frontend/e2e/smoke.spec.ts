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

test("API errors are shown, not swallowed", async ({ page }) => {
  await page.route("http://api.test/runs", (r) => r.fulfill({ status: 503, json: { detail: "live-call allowance 0 is used up" } }));
  await page.goto("/");
  await page.getByTestId("video-input").setInputFiles(fx("tailgate-7.mp4"));
  await page.getByTestId("run").click();
  await expect(page.getByTestId("error")).toContainText("allowance");
});
