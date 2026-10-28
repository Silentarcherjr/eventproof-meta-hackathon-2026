import type { Evidence, Layout, TrackSet } from "./types";

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
