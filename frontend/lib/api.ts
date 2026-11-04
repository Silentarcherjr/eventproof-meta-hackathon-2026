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
  approvable?: Record<string, string>;
  gates?: Record<string, Gate>;
}
export interface Gate {
  approved: string[]; decision: "WITHHELD" | "DEPLOYABLE"; reason: string; tickets: number;
  missing: { family: string; label: string; tickets: number }[];
  auto_issued: { tickets: number; false_tickets: number };
  held_for_review: { tickets: number; false_tickets: number; because: string[] };
}
export async function getCourt(): Promise<Court> { return json<Court>(await fetch(`${API_URL}/tickets/court`)); }

export interface LabTruth {
  object_id: number; crossed_line: boolean; crossing_frame: number | null; direction: string;
  standing_still_seconds: number; stationary_seconds: number; intended: string;
}
export interface LabVerdict {
  verdict: string; explanation: string;
  events: { op: string; target: string; status: string; frame: number | null; timestamp_ms: number | null; reason: string }[];
}
export interface LabCar { object_id: number; truth: LabTruth; spark: LabVerdict; your: LabVerdict }
export interface LabScenes {
  source: string; rule_text: string; assumptions: string[];
  defaults: { max_speed: number | null; any_direction: boolean; travel_direction: string;
              contract_max_speed: number; contract_any_direction: boolean; wait_seconds: number };
  summary: { scenes: number; correct: number; disagreements: number; two_choices_explain_all: boolean;
             by_family: Record<string, number> };
  scenes: { family: string; seed: number; truths: LabTruth[]; video_url: string }[];
}
export interface LabJudgment {
  family: string; seed: number; source: string; cars: LabCar[]; explanation: string;
  controls: { max_speed: number | null; any_direction: boolean };
}
export interface LabPair {
  knob: string; motion_frame_difference: number; source: string;
  sides: Record<"fail" | "pass", { video_url: string; t: number; cars: { truth: LabTruth; naive: LabVerdict }[] }>;
}
export interface LabCompiled {
  provenance: string; cached: boolean; model: string; request_ids: string[]; assumptions: string[];
  wrong_scenes: string[]; scope: string;
  scenes: { family: string; seed: number; correct: boolean;
            cars: { object_id: number; truth: LabTruth; your: LabVerdict | null; correct: boolean; why: string }[] }[];
}
export const labMediaUrl = (path: string) => `${API_URL}${path}`;
export async function getLabScenes(): Promise<LabScenes> { return json<LabScenes>(await fetch(`${API_URL}/lab/scenes`)); }
export async function getLabPair(): Promise<LabPair> { return json<LabPair>(await fetch(`${API_URL}/lab/pair`)); }
export async function judgeLab(family: string, speed: number | null, direction: boolean, signal?: AbortSignal): Promise<LabJudgment> {
  const query = new URLSearchParams({ max_speed: speed === null ? "none" : String(speed), any_direction: String(direction) });
  return json<LabJudgment>(await fetch(`${API_URL}/lab/${encodeURIComponent(family)}/0/judge?${query}`, { signal }));
}
export async function compileLab(ruleText: string): Promise<LabCompiled> {
  return json<LabCompiled>(await fetch(`${API_URL}/lab/compile`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ rule_text: ruleText }),
  }));
}
