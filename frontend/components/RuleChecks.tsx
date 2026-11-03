"use client";

import { useEffect, useState } from "react";
import { getChecks, type RuleCheck } from "@/lib/api";

/** Deterministic checks of the compiled rule against this run's own tracks (shown only when one fails). */
export default function RuleChecks({ runId }: { runId: string }) {
  const [checks, setChecks] = useState<RuleCheck[]>([]);
  useEffect(() => { getChecks(runId).then(setChecks); }, [runId]);
  if (!checks.length) return null;
  return (
    <div className="mb-4 rounded-lg bg-amber-500/10 p-3 text-sm text-amber-200 ring-1 ring-amber-500/40" data-testid="rule-checks">
      <p className="font-semibold">The rule cannot see what it judges</p>
      {checks.map((c) => <p key={c.line} className="mt-1">{c.message}</p>)}
    </div>
  );
}
