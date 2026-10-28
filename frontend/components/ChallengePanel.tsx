"use client";

import { useState } from "react";
import { challengeFileUrl, confirmWithSam, runChallenge, runRepair } from "@/lib/api";
import type { ChallengeReport, RepairDecision, RepairRun, SamConfirm } from "@/lib/types";

const OUTCOMES = ["correct", "spec_error", "perception_error", "abstained"] as const;
const OUTCOME_STYLE: Record<string, string> = {
  correct: "text-green-400", spec_error: "text-red-400", perception_error: "text-orange-400", abstained: "text-amber-300",
};

function Button({ onClick, busy, children, primary, testid }: {
  onClick: () => void; busy?: boolean; children: React.ReactNode; primary?: boolean; testid: string;
}) {
  return (
    <button onClick={onClick} disabled={busy} data-testid={testid}
            className={`rounded-lg px-3 py-2 text-sm font-semibold disabled:opacity-40 ${primary ? "bg-violet-600 text-white" : "bg-zinc-800 text-zinc-200"}`}>
      {children}
    </button>
  );
}

function explain(c: NonNullable<ChallengeReport["counterexample"]>): string {
  const v = c.truths.find((t) => t.intended === "VIOLATION");
  const kind = c.outcome === "spec_error"
    ? "a specification error: with perfect tracking the rule still gives this verdict, so the rule itself is wrong"
    : "a perception error: the rule is right on perfect tracks, the (mock) tracker made it fail";
  const what = v ? `Box ${v.object_id} stood still at the station for ${(v.station_stop_ms / 1000).toFixed(2)} s` : "All boxes were inspected";
  return `${what}; the reviewed truth is ${c.intended}, your rule says ${c.detector_verdict}. This is ${kind}.`;
}

function Decision({ d }: { d: RepairDecision }) {
  const b = d.holdout_before, a = d.holdout_after;
  return (
    <li className={`rounded-lg p-3 ring-1 ${d.accepted ? "bg-green-500/10 ring-green-500/40" : "bg-zinc-900 ring-zinc-800"}`}
        data-testid={d.accepted ? "decision-accepted" : "decision-rejected"}>
      <div className="flex items-start justify-between gap-2">
        <div className="font-mono text-xs text-zinc-200">{d.patch_description}</div>
        <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-bold ${d.accepted ? "bg-green-600 text-white" : "bg-red-500/20 text-red-300"}`}>
          {d.accepted ? "ACCEPTED" : "REJECTED"}
        </span>
      </div>
      {d.proposal.rationale && <p className="mt-1 text-xs text-zinc-400">{d.proposal.rationale}</p>}
      <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-xs text-zinc-400">
        {d.proposal.expected_effect.dev_screen && (
          <span>visible dev: {d.proposal.expected_effect.dev_screen.dev_regressions} regressions{d.proposal.expected_effect.round ? ` · round ${d.proposal.expected_effect.round}` : ""}</span>
        )}
        {a && <span>unseen holdout: {b.correct}/{b.n} → {a.correct}/{a.n}</span>}
      </div>
      <p className={`mt-1 text-xs ${d.accepted ? "text-green-300" : "text-red-300"}`}>{d.reasons.join("; ")}</p>
    </li>
  );
}

export default function ChallengePanel({ runId }: { runId: string }) {
  const [ch, setCh] = useState<ChallengeReport | null>(null);
  const [sam, setSam] = useState<SamConfirm | null>(null);
  const [rep, setRep] = useState<Record<string, RepairRun>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const act = async (key: string, f: () => Promise<void>) => {
    setBusy(key); setErr(null);
    try { await f(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  };
  const c = ch?.counterexample;
  const best = Object.values(rep).flatMap((r) => r.decisions).filter((d) => d.accepted)
    .sort((x, y) => (y.holdout_after?.correct ?? 0) - (x.holdout_after?.correct ?? 0))[0];

  return (
    <section className="space-y-4 rounded-xl bg-zinc-900/60 p-4 ring-1 ring-violet-500/30" data-testid="challenge-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold">Challenge Mode</h2>
          <p className="text-xs text-zinc-400">Try to break the rule on synthetic scenes with known truth, then repair it and verify on unseen cases.</p>
        </div>
        <Button primary testid="challenge" busy={busy !== null}
                onClick={() => act("challenge", async () => { setSam(null); setRep({}); setCh(await runChallenge(runId)); })}>
          {busy === "challenge" ? "Searching…" : ch ? "Search again" : "Challenge this rule"}
        </Button>
      </div>
      {err && <div className="rounded bg-red-500/10 p-2 text-sm text-red-300 ring-1 ring-red-500/40" data-testid="challenge-error">{err}</div>}

      {ch && (
        <div className="space-y-4">
          <div className="overflow-x-auto">
            <table className="w-full text-xs" data-testid="suite">
              <thead><tr className="text-left text-zinc-500"><th className="py-1">family ({ch.suite_cases} scenes)</th>{OUTCOMES.map((o) => <th key={o} className={OUTCOME_STYLE[o]}>{o.replace("_", " ")}</th>)}</tr></thead>
              <tbody>
                {Object.entries(ch.suite).map(([fam, counts]) => (
                  <tr key={fam} className="border-t border-zinc-800">
                    <td className="py-1 font-mono text-zinc-300">{fam}</td>
                    {OUTCOMES.map((o) => <td key={o} className={counts[o] ? OUTCOME_STYLE[o] : "text-zinc-700"}>{counts[o] ?? 0}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-[11px] text-zinc-500">World: {ch.world}. Search perception: {ch.perception}.</p>
          </div>

          {!c ? (
            <p className="text-sm text-green-300" data-testid="no-counterexample">No failing case found on {ch.suite_cases} scenes.</p>
          ) : (
            <div className="space-y-3" data-testid="counterexample">
              <div className="rounded-lg bg-red-500/10 p-3 ring-1 ring-red-500/40">
                <div className="text-xs font-semibold uppercase tracking-wide text-red-300">Counterexample · {c.family} #{c.seed}</div>
                <p className="mt-1 text-sm text-zinc-200">{explain(c)}</p>
                {c.knob && (
                  <p className="mt-1 text-xs text-zinc-400">
                    Minimal pair on <b>{c.knob}</b>: t = {c.t_fail?.toFixed(4)} fools the rule, t = {c.t_pass?.toFixed(4)} is judged correctly
                    {c.scene_difference ? ` — the two clips differ in at most ${c.scene_difference.max_pixels_differing_in_a_frame} pixels per frame` : ""}. Local minimum, not global.
                  </p>
                )}
              </div>
              {ch.files.includes("side_by_side.mp4") && (
                <video src={challengeFileUrl(runId, "side_by_side.mp4")} controls loop muted playsInline data-testid="side-by-side"
                       className="w-full rounded-lg bg-black" />
              )}
              <div className="flex flex-wrap items-center gap-2">
                <Button testid="sam-confirm" busy={busy !== null} onClick={() => act("sam", async () => setSam(await confirmWithSam(runId)))}>
                  {busy === "sam" ? "Asking SAM 3.1…" : "Confirm with SAM 3.1 (1 call)"}
                </Button>
                {sam && (
                  <span className={`text-sm ${sam.still_fails_with_sam ? "text-red-300" : "text-green-300"}`} data-testid="sam-result">
                    {sam.still_fails_with_sam
                      ? `With real SAM 3.1 tracks the rule still says ${sam.sam.detector_verdict} (truth ${sam.sam.intended}): ${sam.sam.outcome.replace("_", " ")}.`
                      : `With real SAM 3.1 tracks the verdict is ${sam.sam.outcome} — this failure came from the mock tracker.`}
                  </span>
                )}
              </div>

              <div className="space-y-2 border-t border-zinc-800 pt-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Button primary testid="repair-muse" busy={busy !== null} onClick={() => act("muse", async () => {
                    const r = await runRepair(runId, "muse"); setRep((p) => ({ ...p, muse: r }));
                  })}>{busy === "muse" ? "Muse Spark is proposing…" : "Repair with Muse Spark"}</Button>
                  <Button testid="repair-baseline" busy={busy !== null} onClick={() => act("baseline", async () => {
                    const r = await runRepair(runId, "baseline"); setRep((p) => ({ ...p, baseline: r }));
                  })}>{busy === "baseline" ? "Searching…" : "Baseline (grid search)"}</Button>
                </div>
                {Object.keys(rep).length > 0 && (
                  <div className={`rounded-lg p-3 text-sm font-semibold ring-1 ${best ? "bg-green-500/10 text-green-300 ring-green-500/40" : "bg-amber-500/10 text-amber-200 ring-amber-500/40"}`}
                       data-testid="repair-headline">
                    {best && best.holdout_after
                      ? `Repair verified on unseen cases: ${best.holdout_before.correct}/${best.holdout_before.n} → ${best.holdout_after.correct}/${best.holdout_after.n}, 0 regressions`
                      : "Repair did not generalize — no proposal passed the hidden holdout"}
                  </div>
                )}
                {Object.entries(rep).map(([who, r]) => (
                  <div key={who} className="space-y-2" data-testid={`repair-${who}-result`}>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                      {who === "muse" ? `Proposals by ${r.proposer}` : "Deterministic baseline (not a model)"}
                    </h3>
                    {r.trace.rounds?.map((t) => (
                      <p key={t.round} className="text-xs text-zinc-400"><b>Round {t.round} diagnosis:</b> {t.diagnosis}</p>
                    ))}
                    <ul className="space-y-2">{r.decisions.map((d) => <Decision key={d.proposal.proposal_id} d={d} />)}</ul>
                    <p className="text-[11px] text-zinc-500">{r.holdout_note}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
