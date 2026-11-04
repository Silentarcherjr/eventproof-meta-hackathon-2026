"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getCourt, type Court, type CourtCase } from "@/lib/api";

const TONE: Record<string, string> = {
  ROBUST: "ring-green-500/50 bg-green-500/10", FRAGILE: "ring-red-500/50 bg-red-500/10",
  DEPENDS_ON_THRESHOLD: "ring-amber-500/50 bg-amber-500/10", DEPENDS_ON_MEANING: "ring-amber-500/50 bg-amber-500/10",
  UNSTABLE: "ring-zinc-500/50 bg-zinc-500/10",
};
const WORDS: Record<string, string> = {
  ROBUST: "holds up", FRAGILE: "falls to a measurement detail", DEPENDS_ON_THRESHOLD: "hangs on an unwritten number",
  DEPENDS_ON_MEANING: "hangs on what 'stop' means", UNSTABLE: "becomes undecidable",
};
const pct = (x: number) => `${Math.round(x * 100)} %`;

function Case({ c }: { c: CourtCase }) {
  const d = c.defense;
  return (
    <div className="grid gap-3 lg:grid-cols-3" data-testid="case">
      <div className="rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">1 · Prosecution</h3>
        <p className="text-sm text-zinc-200">&ldquo;{c.rule_text}&rdquo;</p>
        <p className="mt-2 text-sm text-zinc-400">{c.explanation}</p>
        <p className="mt-2 text-sm text-zinc-400">Measured at the object&apos;s {c.anchor.replace("_", " ")}. SAM 3.1 track #{c.object_id}, frames {c.first_frame}–{c.last_frame}.</p>
        <ul className="mt-2 space-y-1 text-xs text-zinc-300">
          {c.events.map((e, i) => <li key={i}><span className="font-mono">{e.op}</span> {e.target}: {e.status}{e.frame != null ? ` at frame ${e.frame}` : ""}</li>)}
        </ul>
        <p className="mt-3 text-sm"><span className="rounded bg-red-500/20 px-2 py-0.5 text-red-200">Ticket: {c.verdict}</span></p>
        <a href={`/?run=${c.run_id}`} className="mt-2 inline-block text-xs text-sky-300 underline">open this clip in the studio</a>
      </div>
      <div className="rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">2 · Defense (Muse Spark)</h3>
        {d.concede ? <p className="text-sm text-zinc-300">The defense <b>concedes</b>: {d.concession}</p> : (
          <ul className="space-y-2 text-sm">
            {d.arguments.map((a) => (
              <li key={a.id}>
                <span className={c.flipping.includes(a.id) ? "text-red-300" : "text-zinc-500"}>{c.flipping.includes(a.id) ? "wins" : "does not change it"}</span>
                {" · "}<span className="font-mono text-xs text-zinc-400">{a.id}</span>
                <p className="text-zinc-300">{a.argument}</p>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-zinc-500">Muse picks only from a closed menu of challenges; the engine decides which ones win.</p>
      </div>
      <div className="rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">3 · Ruling (deterministic sweep)</h3>
        <p className="text-sm text-zinc-200">This ticket <b>{WORDS[c.status] ?? c.status}</b>.</p>
        {c.smallest_flip && <p className="mt-1 text-sm text-zinc-400">Smallest change that overturns it: {c.smallest_flip}</p>}
        <p className="mt-2 text-sm text-zinc-400">{c.flipping.length} of the challenges in the menu overturn it.</p>
        <p className="mt-3 text-sm">Frozen label (truth): <b>{c.intended}</b> — the ticket was <b className={c.correct === "wrong" ? "text-red-300" : "text-green-300"}>{c.correct === "wrong" ? "wrongly issued" : "correctly issued"}</b>.</p>
        <p className="mt-1 text-sm text-zinc-400">Policy: {c.status === "ROBUST" ? "auto-issue" : "hold for a human reviewer"}.</p>
      </div>
    </div>
  );
}

export default function CourtPage() {
  const [court, setCourt] = useState<Court | null>(null);
  const [sel, setSel] = useState<number>(-1);
  useEffect(() => { getCourt().then((c) => { setCourt(c); setSel(Math.max(0, c.cases.findIndex((x) => x.correct === "wrong"))); }).catch(() => setCourt(null)); }, []);
  if (!court) return <main className="mx-auto max-w-7xl px-4 py-6 text-zinc-400">Loading the 20 real tickets…</main>;
  const k = court.contract;
  const robust = court.cases.filter((c) => c.status === "ROBUST").length;
  return (
    <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <Link href="/" className="text-sm text-sky-300 underline">← studio</Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Ticket court: would these 20 real tickets hold up?</h1>
      <p className="mt-1 max-w-3xl text-sm text-zinc-400">Every ticket a compiled rule issued on labelled real footage. Each one is attacked by Muse Spark acting as the
        defense, and by a deterministic sweep (the line a few pixels away, another measured point, thresholds ±20 %, another meaning of &ldquo;stop&rdquo;).</p>
      <p className="mt-4 text-4xl font-bold" data-testid="headline">{robust} of {court.cases.length} hold up.</p>
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5 lg:grid-cols-10" data-testid="scoreboard">
        {court.cases.map((c, i) => (
          <button key={`${c.run_id}-${c.object_id}`} onClick={() => setSel(i)}
                  className={`rounded-lg p-2 text-left text-xs ring-1 ${TONE[c.status] ?? ""} ${i === sel ? "outline outline-2 outline-sky-400" : ""}`}>
            <span className="block font-semibold text-zinc-100">{c.clip.replace(".mp4", "")} #{c.object_id}</span>
            <span className="block text-zinc-300">{WORDS[c.status]}</span>
            {c.correct === "wrong" && <span className="block text-red-300">wrongly issued</span>}
          </button>
        ))}
      </div>
      {sel >= 0 && <div className="mt-6"><Case c={court.cases[sel]} /></div>}
      <section className="mt-8 rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800" data-testid="contract">
        <h2 className="text-lg font-semibold">Contract acceptance block</h2>
        <p className="mt-1 text-sm text-zinc-400">What a city could write into a camera vendor&apos;s contract, filled in from these labelled tickets. It states what the evidence supports; it is not a certification.</p>
        <ul className="mt-2 space-y-1 text-sm text-zinc-200">
          <li><b>Policy:</b> {k.policy}.</li>
          <li><b>All tickets:</b> {k.all_tickets.false_tickets} wrong of {k.all_tickets.tickets} (95 % upper bound {pct(k.all_tickets.upper_95)}).</li>
          <li><b>Auto-issued under the policy:</b> {k.auto_issued.tickets}, {k.auto_issued.false_tickets} wrong (upper bound {pct(k.auto_issued.upper_95)}: too few to promise anything yet).</li>
          <li><b>Held for review:</b> {k.held_for_review.tickets}, including the {k.held_for_review.false_tickets} wrongly issued one.</li>
          <li><b>To promise ≤ 2 % false tickets:</b> {k.labels_needed_error_free["2%"]} labelled error-free tickets; ≤ 5 %: {k.labels_needed_error_free["5%"]}.</li>
        </ul>
      </section>
    </main>
  );
}
