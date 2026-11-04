"use client";

import { useEffect, useState } from "react";
import { askDefense, getRobustness, type Defense, type ObjectRobustness } from "@/lib/api";

const STYLE: Record<string, string> = {
  ROBUST: "bg-green-500/15 text-green-300 ring-green-500/40",
  FRAGILE: "bg-red-500/15 text-red-300 ring-red-500/40",
  DEPENDS_ON_THRESHOLD: "bg-amber-500/15 text-amber-200 ring-amber-500/40",
  DEPENDS_ON_MEANING: "bg-amber-500/15 text-amber-200 ring-amber-500/40",
  UNSTABLE: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/40",
};
const WORDS: Record<string, string> = {
  ROBUST: "holds up", FRAGILE: "fragile: a measurement detail flips it",
  DEPENDS_ON_THRESHOLD: "hangs on an unwritten number", DEPENDS_ON_MEANING: "hangs on what the sentence means",
  UNSTABLE: "becomes undecidable",
};

/** Would each verdict hold up? Deterministic re-judging under a typed menu; Muse Spark can argue the defense of a ticket. */
export default function TicketPanel({ runId }: { runId: string }) {
  const [rows, setRows] = useState<ObjectRobustness[] | null>(null);
  const [def, setDef] = useState<Record<number, Defense | string>>({});
  useEffect(() => { getRobustness(runId).then(setRows).catch(() => setRows([])); }, [runId]);
  if (!rows?.length) return null;
  const tickets = rows.filter((r) => r.verdict === "VIOLATION");
  const defend = async (id: number) => {
    setDef((d) => ({ ...d, [id]: "Muse Spark is preparing the defense…" }));
    try { const r = await askDefense(runId, id); setDef((d) => ({ ...d, [id]: r })); }
    catch (e) { setDef((d) => ({ ...d, [id]: e instanceof Error ? e.message : String(e) })); }
  };
  return (
    <section className="rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800" data-testid="ticket-panel">
      <h2 className="text-lg font-semibold">Would these tickets hold up?</h2>
      <p className="mb-3 text-sm text-zinc-400">
        Every verdict re-judged with the line drawn a few pixels away, the object measured at another point, the
        thresholds moved ±20 %, half the frames, and another meaning of &ldquo;stop&rdquo;. No model decides this.
        {` ${tickets.length} ticket(s): ${tickets.filter((t) => t.status === "ROBUST").length} hold up.`}
      </p>
      <ul className="space-y-2">
        {rows.map((r) => {
          const d = def[r.object_id];
          return (
            <li key={r.object_id} className="text-sm" data-testid={`ticket-${r.object_id}`}>
              <span className="font-mono text-zinc-400">#{r.object_id}</span> {r.verdict}{" "}
              <span className={`ml-1 rounded px-1.5 py-0.5 text-xs ring-1 ${STYLE[r.status] ?? ""}`}>{WORDS[r.status] ?? r.status}</span>
              {r.smallest_flip && <span className="ml-2 text-zinc-400">smallest change: {r.smallest_flip}</span>}
              {r.verdict === "VIOLATION" && !d && (
                <button onClick={() => defend(r.object_id)} className="ml-2 rounded bg-zinc-800 px-2 py-0.5 text-xs hover:bg-zinc-700"
                        data-testid={`defend-${r.object_id}`}>Ask Muse Spark to defend</button>
              )}
              {typeof d === "string" && <p className="mt-1 text-zinc-400">{d}</p>}
              {d && typeof d !== "string" && (
                <div className="mt-1 rounded bg-zinc-950 p-2 ring-1 ring-zinc-800" data-testid={`defense-${r.object_id}`}>
                  {d.concede ? <p className="text-zinc-300">The defense concedes: {d.concession}</p> : (
                    <ul className="space-y-1">
                      {d.challenges.map((c) => (
                        <li key={c.id}>
                          <span className={c.overturns ? "text-red-300" : "text-zinc-400"}>{c.overturns ? "overturns the ticket" : "does not change it"}</span>
                          {" — "}<span className="text-zinc-200">{c.label}</span>: <span className="text-zinc-400">{c.argument}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
