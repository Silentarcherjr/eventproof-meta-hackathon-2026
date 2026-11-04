import type { Ambiguity, BeforeAfter, ChallengeReport, Evidence, FinalReport, Layout, RepairRun, SamConfirm, TrackSet } from "./types";

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

export interface DemoClip { run_id: string; clip: string | null; rule: string; overall: string | null }

export interface Health {
  status: string; mode: "local" | "showcase" | "hosted"; meta_api_key_configured: boolean;
  live_calls_remaining: { muse: number; sam: number }; rate_limit: string; demo_runs: string[];
  demo_clips?: DemoClip[];
}

export async function getHealth(): Promise<Health | null> {
  try { const r = await fetch(`${API_URL}/health`); return r.ok ? (r.json() as Promise<Health>) : null; } catch { return null; }
}

export async function askBothModels(runId: string, text: string): Promise<Ambiguity> {
  return json<Ambiguity>(await fetch(`${run(runId)}/ambiguity`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }),
  }));
}

export const certificateUrl = (runId: string, chosen?: "A" | "B") =>
  `${run(runId)}/certificate${chosen ? `?chosen=${chosen}` : ""}`;

/** The same video (and zones) with a new rule: a new run. */
export async function rerunWithRule(runId: string, ruleText: string, layout: Layout): Promise<Evidence> {
  return json<Evidence>(await fetch(`${run(runId)}/rule`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ rule_text: ruleText, layout }),
  }));
}

export interface LayoutProposal { layout: Layout; assumptions: string[]; model: string; request_id: string; cached: boolean }

/** Muse Spark drafts the zone and line from the video's first frame and the rule text. */
export async function proposeLayout(video: File, ruleText: string): Promise<LayoutProposal> {
  const form = new FormData();
  form.append("video", video);
  form.append("rule_text", ruleText);
  return json<LayoutProposal>(await fetch(`${API_URL}/propose-layout`, { method: "POST", body: form }));
}

export interface RuleCheck { check: string; line: string; anchor: string; other_anchor: string; other_crossers: number; message: string }

export async function getChecks(runId: string): Promise<RuleCheck[]> {
  try { const r = await fetch(`${run(runId)}/checks`); return r.ok ? (r.json() as Promise<RuleCheck[]>) : []; } catch { return []; }
}

export interface Flip { variant: string; family: string; tier: string; value: number | string; verdict: string }
export interface ObjectRobustness { object_id: number; verdict: string; status: string; flips: Flip[]; smallest_flip: string | null }
export interface Defense {
  object_id: number; status: string; concede: boolean; concession: string; strongest: string;
  challenges: { id: string; label: string; argument: string; overturns: boolean }[]; request_id?: string; cached: boolean;
}

export async function getRobustness(runId: string): Promise<ObjectRobustness[]> {
  return json<ObjectRobustness[]>(await fetch(`${run(runId)}/robustness`));
}

export async function askDefense(runId: string, objectId: number): Promise<Defense> {
  return json<Defense>(await fetch(`${run(runId)}/objects/${objectId}/defense`, { method: "POST" }));
}

export interface GridCell { min_s: number; speed: number | null; verdicts: string; tickets: number; right: number; false_tickets: number; missed: number; abstained: number; untracked: number }
export interface LawGrid {
  times_s: number[]; speeds: (number | null)[];
  cars: { clip: string; object_id: number | null; description: string; truth: string }[];
  statutes: { id: string; citation: string; text: string; spark_values: { min_s: number; speed: number } | null; cells: GridCell[] }[];
}
export async function getLawGrid(): Promise<LawGrid> { return json<LawGrid>(await fetch(`${API_URL}/law/grid`)); }

export interface CourtCase {
  set: string; clip: string; object_id: number; description: string; intended: string; verdict: string; correct: string;
  status: string; smallest_flip: string | null; flipping: string[]; run_id: string; rule_text: string; explanation: string; audited?: boolean;
  anchor: string; first_frame: number; last_frame: number;
  events: { op: string; target: string; status: string; frame: number | null; timestamp_ms: number | null; reason: string }[];
  defense: { chosen: string[]; strongest: string; concede: boolean; concession: string; strongest_overturns: boolean; any_overturns: boolean;
             arguments: { id: string; argument: string }[]; request_id?: string };
}
export interface Court {
  summary: Record<string, unknown>; cases: CourtCase[]; audit?: string;
  contract_pre_registered?: { all_tickets: { tickets: number; false_tickets: number; upper_95: number } };
  contract: { policy: string; all_tickets: { tickets: number; false_tickets: number; upper_95: number };
              auto_issued: { tickets: number; false_tickets: number; upper_95: number };
              held_for_review: { tickets: number; false_tickets: number; by_status: Record<string, number> };
              labels_needed_error_free: Record<string, number> };
}
export async function getCourt(): Promise<Court> { return json<Court>(await fetch(`${API_URL}/tickets/court`)); }
