"use client";

import { useEffect, useState } from "react";
import { API_URL, certificateUrl, getStored } from "@/lib/api";
import type { ChallengeReport, Evidence, RepairRun } from "@/lib/types";

interface Cert { status: { label: string; reasons: string[] } }

type State = "done" | "warn" | "todo";
const DOT: Record<State, string> = { done: "bg-green-500", warn: "bg-amber-400", todo: "bg-zinc-600" };

function Step({ n, title, detail, state, href }: { n: number; title: string; detail: string; state: State; href: string }) {
  return (
    <a href={href} className="flex min-w-0 flex-1 items-start gap-2 rounded-lg bg-zinc-900 p-3 ring-1 ring-zinc-800 hover:ring-zinc-600"
       data-testid={`step-${n}`}>
      <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${DOT[state]}`} />
      <span className="min-w-0">
        <span className="block text-xs font-semibold uppercase tracking-wide text-zinc-400">{n} · {title}</span>
        <span className="block text-sm leading-snug text-zinc-100">{detail}</span>
      </span>
    </a>
  );
}

/** Where this rule stands in Build → Break → Repair → Certify, from results already stored for the run. */
export default function Stepper({ ev }: { ev: Evidence }) {
  const [ch, setCh] = useState<ChallengeReport | null>(null);
  const [rep, setRep] = useState<RepairRun | null>(null);
  const [cert, setCert] = useState<Cert | null>(null);

  useEffect(() => {
    let live = true;
    const load = async () => {
      const [c, r, ce] = await Promise.all([
        getStored<ChallengeReport>(ev.run_id, "challenge").catch(() => null),
        getStored<RepairRun>(ev.run_id, "repair-muse").catch(() => null),
        fetch(`${API_URL}/runs/${encodeURIComponent(ev.run_id)}/certificate?format=json`).then((x) => (x.ok ? x.json() : null)).catch(() => null),
      ]);
      if (live) { setCh(c); setRep(r); setCert(ce); }
    };
    load();
    const t = setInterval(load, 5000);
    return () => { live = false; clearInterval(t); };
  }, [ev.run_id]);

  const v = ev.result?.overall;
  const acc = rep?.decisions.filter((d) => d.accepted).length ?? 0;
  const label = cert?.status.label ?? "";
  return (
    <nav className="mb-4 flex flex-col gap-2 sm:flex-row" data-testid="stepper">
      <Step n={1} title="Build" href="#results" state={v ? "done" : "todo"}
            detail={v ? `verdict ${v} · ${ev.result?.objects.length ?? 0} objects` : "check a rule on a video"} />
      <Step n={2} title="Break" href="#challenge" state={ch ? (ch.failures ? "warn" : "done") : "todo"}
            detail={ch ? `${ch.failures}/${ch.suite_cases} test scenes fool it` : "not attacked yet"} />
      <Step n={3} title="Repair" href="#challenge" state={rep ? (acc ? "done" : "warn") : "todo"}
            detail={rep ? `${acc}/${rep.decisions.length} repairs hold on hidden scenes` : "no repair yet"} />
      <Step n={4} title="Certify" href={certificateUrl(ev.run_id)}
            state={label.startsWith("CERTIFIED") ? "done" : label ? "warn" : "todo"}
            detail={label ? label.toLowerCase() : "certificate"} />
    </nav>
  );
}
