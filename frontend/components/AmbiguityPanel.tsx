"use client";

import { useEffect, useState } from "react";
import { askBothModels, challengeFileUrl, getStored } from "@/lib/api";
import type { Ambiguity } from "@/lib/types";

const MODEL_NAME: Record<string, string> = { "muse-spark-1.3": "Muse Spark", "muse-wonder-1.0": "Muse Wonder" };
const SIDE = ["A", "B"] as const;

function Verdict({ v }: { v: string }) {
  const ok = v === "PASS";
  return <span className={`rounded px-1.5 py-0.5 font-mono text-xs font-bold ${ok ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"}`}>{ok ? "✓ PASS" : "✗ FAIL"}</span>;
}

export default function AmbiguityPanel({ runId, defaultText }: { runId: string; defaultText: string }) {
  const [text, setText] = useState(defaultText);
  const [res, setRes] = useState<Ambiguity | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [choice, setChoice] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    getStored<Ambiguity>(runId, "ambiguity").then((r) => { if (live && r) { setRes(r); setText(r.text); } }).catch(() => {});
    return () => { live = false; };
  }, [runId]);

  const ask = async () => {
    setBusy(true); setErr(null); setChoice(null);
    try { setRes(await askBothModels(runId, text)); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const names = (res?.models ?? []).map((m) => MODEL_NAME[m] ?? m);
  const differ = !!res?.comparison && res.comparison.disagree > 0;

  return (
    <section className="space-y-4 rounded-xl bg-zinc-900/60 p-4 ring-1 ring-teal-500/30" data-testid="ambiguity-panel">
      <div>
        <h2 className="text-lg font-bold">Two readings</h2>
        <p className="text-xs text-zinc-400">Muse Spark and Muse Wonder each turn your sentence into a rule. If the rules behave differently, you see the smallest pair of scenes that separates them, and you decide what you meant.</p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} data-testid="ambiguity-text"
                  className="flex-1 rounded bg-zinc-800 p-2 text-sm" />
        <button onClick={ask} disabled={busy || text.trim().length < 10} data-testid="ambiguity-ask"
                className="rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40">
          {busy ? "Asking both models…" : "Ask both models"}
        </button>
      </div>
      {err && <div className="rounded bg-red-500/10 p-2 text-sm text-red-300 ring-1 ring-red-500/40" data-testid="ambiguity-error">{err}</div>}

      {res && (
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            {res.readings.map((r, i) => (
              <div key={r.model} data-testid={`reading-${i}`}
                   className={`rounded-lg p-3 ring-1 ${choice === i ? "bg-teal-500/10 ring-teal-400" : "bg-zinc-900 ring-zinc-800"}`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{names[i]} <span className="text-zinc-500">(reading {SIDE[i]})</span></span>
                  {r.ok ? <span className="text-xs text-zinc-400">{r.cached ? "recorded response" : "live"}</span>
                        : <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-xs text-amber-200">declined</span>}
                </div>
                {r.ok ? (
                  <>
                    <p className="mt-2 text-sm text-zinc-100">{r.plain}</p>
                    <p className="mt-1 font-mono text-xs text-zinc-500">{r.explanation}</p>
                    <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-zinc-400">
                      {r.assumptions.slice(0, 3).map((a) => <li key={a}>{a}</li>)}
                    </ul>
                  </>
                ) : <p className="mt-2 text-xs text-amber-200">{r.refusal}</p>}
              </div>
            ))}
          </div>

          {res.comparison && (
            <p className="text-sm text-zinc-300" data-testid="ambiguity-summary">
              {differ
                ? <>The two rules give <b>different verdicts on {res.comparison.disagree} of {res.comparison.scenes}</b> synthetic scenes with known tracks ({Object.entries(res.comparison.disagree_by_family).filter(([, n]) => n).map(([f, n]) => `${f.replace("_", " ")} ${n}`).join(", ")}).</>
                : <>Both rules give the same verdict on all {res.comparison.scenes} synthetic scenes: no ambiguity found for this sentence.</>}
            </p>
          )}

          {res.pair && (
            <div className="space-y-3" data-testid="ambiguity-pair">
              <p className="text-xs text-zinc-400">Minimal pair: the same scene, {res.pair.knob} {res.pair.t_differ.toFixed(5)} vs {res.pair.t_agree.toFixed(5)}.</p>
              <div className="grid gap-3 md:grid-cols-2">
                {([["differ", "ambiguity_differ.mp4", "The readings disagree"], ["agree", "ambiguity_agree.mp4", "Nearly the same scene: they agree"]] as const).map(([k, f, title]) => (
                  <figure key={k} className="space-y-1">
                    <video src={challengeFileUrl(runId, f)} controls muted loop playsInline className="w-full rounded ring-1 ring-zinc-800" />
                    {(res.pair!.facts?.[k] ?? []).map((f) => (
                      <p key={f.object_id} className="text-xs text-zinc-400" data-testid={`facts-${k}`}>
                        box {f.object_id}: stood still {f.stood_still_s.toFixed(2)} s · inside the zone {f.in_zone_s?.toFixed(2) ?? "–"} s
                      </p>
                    ))}
                    <figcaption className="flex flex-wrap items-center gap-2 text-xs text-zinc-300">
                      <span className="font-semibold">{title}:</span>
                      {SIDE.map((s, i) => <span key={s} className="flex items-center gap-1">{names[i]} <Verdict v={res.pair![k].verdicts[s]} /></span>)}
                    </figcaption>
                  </figure>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2 rounded-lg bg-zinc-900 p-3 ring-1 ring-zinc-800">
                <span className="text-sm font-semibold">In the left clip, which verdict did you mean?</span>
                {SIDE.map((s, i) => (
                  <button key={s} onClick={() => setChoice(i)} data-testid={`choose-${s}`}
                          className={`rounded px-2 py-1 text-xs font-semibold ${choice === i ? "bg-teal-600 text-white" : "bg-zinc-800 text-zinc-200"}`}>
                    {res.pair!.differ.verdicts[s]} — {names[i]}&apos;s reading
                  </button>
                ))}
              </div>
              {choice !== null && (
                <p className="text-sm text-teal-200" data-testid="ambiguity-choice">Your rule: {res.readings[choice].plain} ({names[choice]}&apos;s reading).</p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
