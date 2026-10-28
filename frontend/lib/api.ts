import type { BeforeAfter, ChallengeReport, Evidence, FinalReport, Layout, RepairRun, SamConfirm, TrackSet } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function createRun(video: File, ruleText: string, layout: Layout): Promise<Evidence> {
  const form = new FormData();
  form.append("video", video);
  form.append("rule_text", ruleText);
  form.append("layout", JSON.stringify(layout));
  return json<Evidence>(await fetch(`${API_URL}/runs`, { method: "POST", body: form }));
}

export async function getTracks(runId: string): Promise<TrackSet> {
  return json<TrackSet>(await fetch(`${API_URL}/runs/${encodeURIComponent(runId)}/tracks`));
}

export const videoUrl = (runId: string) => `${API_URL}/runs/${encodeURIComponent(runId)}/video`;

const run = (id: string) => `${API_URL}/runs/${encodeURIComponent(id)}`;

export async function runChallenge(runId: string): Promise<ChallengeReport> {
  return json<ChallengeReport>(await fetch(`${run(runId)}/challenge`, { method: "POST" }));
}

export async function confirmWithSam(runId: string): Promise<SamConfirm> {
  return json<SamConfirm>(await fetch(`${run(runId)}/challenge/sam-confirm`, { method: "POST" }));
}

export async function runRepair(runId: string, proposer: "muse" | "baseline"): Promise<RepairRun> {
  return json<RepairRun>(await fetch(`${run(runId)}/repair`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ proposer }) }));
}

export const challengeFileUrl = (runId: string, name: string) => `${run(runId)}/challenge/files/${encodeURIComponent(name)}`;

export async function getRun(runId: string): Promise<Evidence> {
  return json<Evidence>(await fetch(run(runId)));
}

export async function beforeAfter(runId: string, proposer: "muse" | "baseline"): Promise<BeforeAfter> {
  return json<BeforeAfter>(await fetch(`${run(runId)}/before-after`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ proposer }),
  }));
}

/** A result computed earlier for this run, or null if it was never computed. */
export async function getStored<T>(runId: string, key: string): Promise<T | null> {
  const res = await fetch(`${run(runId)}/stored/${key}`);
  return res.status === 404 ? null : json<T>(res);
}

export async function getFinalReport(): Promise<FinalReport | null> {
  const res = await fetch(`${API_URL}/final-report`);
  return res.ok ? (res.json() as Promise<FinalReport>) : null;
}
