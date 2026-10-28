"use client";

import type { Evidence } from "@/lib/types";

const OVERALL: Record<string, string> = {
  PASS: "bg-green-500/15 text-green-300 ring-green-500/40",
  FAIL: "bg-red-500/15 text-red-300 ring-red-500/40",
  UNKNOWN: "bg-amber-500/15 text-amber-300 ring-amber-500/40",
  NO_OBJECTS: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/40",
};

const short = (s: string | null | undefined, n = 12) => (s ? `${s.slice(0, n)}…` : "—");

export default function Results({ ev, onSeek }: { ev: Evidence; onSeek: (f: number) => void }) {
  const r = ev.result;
  return (
    <div className="space-y-5" data-testid="results">
      {ev.status !== "completed" ? (
        <div className="rounded-lg bg-amber-500/10 p-4 text-amber-200 ring-1 ring-amber-500/40" data-testid="run-status">
          <div className="font-semibold">{ev.status.replace("_", " ")}</div>
          <div className="text-sm">{ev.rule.error ?? ev.perception?.error}</div>
        </div>
      ) : r && (
        <div className={`rounded-lg p-4 ring-1 ${OVERALL[r.overall]}`} data-testid="overall">
          <div className="text-xs uppercase tracking-wide opacity-80">Overall verdict</div>
          <div className="text-3xl font-bold">{r.overall}</div>
          <div className="text-sm opacity-80">{r.objects.length} tracked object(s) · rule {r.rule_id} v{r.rule_version}</div>
        </div>
      )}

      {r && (
        <ul className="space-y-2" data-testid="objects">
          {r.objects.map((o) => (
            <li key={o.object_id} className="rounded-lg bg-zinc-900 p-3 ring-1 ring-zinc-800">
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm">object #{o.object_id}</span>
                <span className={`text-sm font-semibold ${o.verdict === "PASS" ? "text-green-400" : o.verdict === "VIOLATION" ? "text-red-400" : "text-amber-400"}`}>{o.verdict}</span>
              </div>
              <ul className="mt-2 space-y-1 text-sm text-zinc-300">
                {o.events.map((e) => (
                  <li key={`${e.op}-${e.target}`} className="flex items-start gap-2">
                    <span className="font-mono text-xs text-zinc-500">{e.op}</span>
                    <span className="flex-1">{e.reason}</span>
                    {e.frame != null && (
                      <button className="rounded bg-zinc-800 px-1.5 font-mono text-xs text-sky-300 hover:bg-zinc-700"
                              onClick={() => onSeek(e.frame!)}>f{e.frame}</button>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {ev.rule.assumptions.length > 0 && (
        <div data-testid="assumptions">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">How Muse Spark read the rule</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">
            {ev.rule.assumptions.map((a) => <li key={a}>{a}</li>)}
          </ul>
        </div>
      )}

      {ev.rule.compiled_rule && (
        <details className="rounded-lg bg-zinc-900 p-3 ring-1 ring-zinc-800">
          <summary className="cursor-pointer text-sm text-zinc-300">Compiled rule (DSL)</summary>
          <pre className="mt-2 max-h-80 overflow-auto text-xs text-zinc-400">{JSON.stringify(ev.rule.compiled_rule.check, null, 2)}</pre>
        </details>
      )}

      <div data-testid="provenance">
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">Provenance</h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-xs text-zinc-400">
          <dt>rule</dt><dd>{ev.rule.model} · {ev.rule.request_ids.map((x) => short(x, 18)).join(", ") || "—"}{ev.rule.cached ? " · cached" : ""}</dd>
          {ev.perception && <><dt>tracks</dt><dd>{ev.perception.model} · prompt “{ev.perception.prompt}” · {ev.perception.boxes} boxes{ev.perception.cached ? " · cached" : ""}</dd></>}
          <dt>video</dt><dd>{ev.video.filename} · {ev.video.info.width}×{ev.video.info.height} · {ev.video.info.fps} fps · {short(ev.video.sha256)}{ev.video.reencoded ? ` · re-encoded (${ev.video.reencode_reasons.join("; ")})` : ""}</dd>
          <dt>evidence</dt><dd>{ev.run_id} · sha256 {short(ev.evidence_sha256)}</dd>
        </dl>
      </div>
    </div>
  );
}
