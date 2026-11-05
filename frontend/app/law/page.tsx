"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getLawGrid, type LawGrid } from "@/lib/api";

const COLOR: Record<string, string> = { V: "bg-red-500/80", P: "bg-green-500/70", U: "bg-zinc-500", "-": "bg-zinc-800" };

export default function LawPage() {
  const [g, setG] = useState<LawGrid | null>(null);
  const [s, setS] = useState(0);
  const [ti, setTi] = useState(4);
  const [vi, setVi] = useState(4);
  useEffect(() => {
    getLawGrid().then((x) => {
      // start on the values Muse Spark chose for the first statute
      const sv = x.statutes[0]?.spark_values;
      setTi(Math.max(0, sv ? x.times_s.indexOf(sv.min_s) : 0));
      setVi(Math.max(0, sv ? x.speeds.indexOf(sv.speed) : 0));
      setG(x);
    }).catch(() => setG(null));
  }, []);
  const st = g?.statutes[s];
  const cell = useMemo(() => st?.cells.find((c) => c.min_s === g!.times_s[ti] && c.speed === g!.speeds[vi]), [st, g, ti, vi]);
  if (!g || !st || !cell) return <main className="mx-auto max-w-7xl px-4 py-6 text-zinc-400">Loading…</main>;
  const sv = st.spark_values;
  const sparkTi = sv ? g.times_s.indexOf(sv.min_s) : -1;
  const sparkVi = sv ? g.speeds.indexOf(sv.speed) : -1;
  const baseline = sv ? st.cells.find((c) => c.min_s === sv.min_s && c.speed === sv.speed) : undefined;
  const comparable = baseline && baseline.verdicts.length === g.cars.length && cell.verdicts.length === g.cars.length;
  const changed = g.cars.map((_, i) => Boolean(comparable && cell.verdicts[i] !== baseline.verdicts[i]));
  const changedCount = changed.filter(Boolean).length;
  const canReset = sparkTi >= 0 && sparkVi >= 0 && Boolean(baseline);
  function resetToSpark() {
    if (canReset) { setTi(sparkTi); setVi(sparkVi); }
  }
  const speed = g.speeds[vi];
  const violators = g.cars.filter((c) => c.truth === "VIOLATION").length;
  const clips = [...new Set(g.cars.map((c) => c.clip))];
  return (
    <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <Link href="/" className="text-sm text-sky-300 underline">← studio</Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Drag the law: the numbers the statute never wrote</h1>
      <div className="mt-3 flex gap-2">
        {g.statutes.map((x, i) => (
          <button key={x.id} onClick={() => {
            setS(i);
            setTi(Math.max(0, x.spark_values ? g.times_s.indexOf(x.spark_values.min_s) : 0));
            setVi(Math.max(0, x.spark_values ? g.speeds.indexOf(x.spark_values.speed) : 0));
          }} className={`rounded px-3 py-1 text-sm ring-1 ${i === s ? "bg-zinc-800 ring-sky-500" : "ring-zinc-700"}`}>{x.citation}</button>
        ))}
      </div>
      <blockquote className="mt-3 max-w-3xl border-l-4 border-zinc-600 pl-3 text-zinc-200" data-testid="statute">&ldquo;{st.text}&rdquo;</blockquote>
      <p className="mt-1 text-sm text-zinc-400">Verbatim. It contains no number: not how long a stop lasts, not how slow counts as stopped. A camera rule needs both.{" "}
        {sv ? <>Muse Spark chose <b>{sv.min_s} s at ≤ {sv.speed} frame widths/s</b> (marked ◆).</> : "No recorded Spark choices are available for this statute."}</p>
      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="space-y-4">
          <label className="block text-sm">How long the car must stand still: <b>{g.times_s[ti]} s</b>{sv && g.times_s[ti] === sv.min_s && " ◆"}
            <input type="range" min={0} max={g.times_s.length - 1} value={ti} onChange={(e) => setTi(+e.target.value)} className="w-full" data-testid="time" />
          </label>
          <label className="block text-sm">What counts as standing still: <b>{speed === null ? "any motion" : `≤ ${speed} frame widths/s`}</b>{sv && speed === sv.speed && " ◆"}
            <input type="range" min={0} max={g.speeds.length - 1} value={vi} onChange={(e) => setVi(+e.target.value)} className="w-full" data-testid="speed" />
          </label>
          <button onClick={resetToSpark} disabled={!canReset} className="rounded bg-zinc-800 px-3 py-2 text-sm disabled:opacity-50">Reset to Spark</button>
          <p role="status" aria-live="polite" className="text-sm text-sky-200" data-testid="law-changed">
            {comparable ? `${changedCount} ${changedCount === 1 ? "car" : "cars"} changed verdict from Spark’s interpretation` : "Spark comparison unavailable for this statute."}
          </p>
          <div className="grid grid-cols-3 gap-2 text-center" data-testid="counters">
            <div className="rounded-lg bg-zinc-900 p-3 ring-1 ring-zinc-800"><p className="text-3xl font-bold">{cell.tickets}</p><p className="text-xs text-zinc-400">tickets issued</p></div>
            <div className="rounded-lg bg-zinc-900 p-3 ring-1 ring-zinc-800"><p className="text-3xl font-bold text-red-300">{cell.false_tickets}</p><p className="text-xs text-zinc-400">to drivers who stopped</p></div>
            <div className="rounded-lg bg-zinc-900 p-3 ring-1 ring-zinc-800"><p className="text-3xl font-bold text-amber-300">{cell.missed}</p><p className="text-xs text-zinc-400">of {violators} who never stopped, let go</p></div>
          </div>
          <p className="text-sm text-zinc-400">{cell.right} of {g.cars.length} labelled cars judged right · same law, same footage, same model.</p>
          <div>
            <p className="mb-1 text-xs text-zinc-500">Tickets issued at every combination (rows: stop time; columns: still speed)</p>
            <div className="grid gap-px" style={{ gridTemplateColumns: `repeat(${g.speeds.length}, minmax(0, 1fr))` }}>
              {g.times_s.flatMap((t, r) => g.speeds.map((v, c) => {
                const x = st.cells.find((y) => y.min_s === t && y.speed === v)!;
                const on = r === ti && c === vi;
                return <button key={`${r}-${c}`} onClick={() => { setTi(r); setVi(c); }} title={`${t} s, ${v ?? "any"}: ${x.tickets} tickets, ${x.right} right`}
                               className={`h-4 ${on ? "outline outline-2 outline-sky-400" : ""}`} style={{ background: `rgba(239,68,68,${0.1 + 0.9 * x.tickets / 17})` }} />;
              }))}
            </div>
          </div>
        </div>
        <div className="space-y-3" data-testid="cars">
          {clips.map((clip) => (
            <div key={clip}>
              <p className="text-xs font-semibold text-zinc-400">{clip.replace(".mp4", "")}</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {g.cars.map((c, i) => c.clip !== clip ? null : (
                  <span key={i} role="img" data-testid="law-car" data-changed={changed[i]}
                        aria-label={`${c.description} — verdict ${cell.verdicts[i]}, truth ${c.truth}${changed[i] ? `; changed from Spark’s ${baseline!.verdicts[i]}` : ""}`}
                        title={`${c.description} — truth ${c.truth}${changed[i] ? `; changed from Spark’s ${baseline!.verdicts[i]} to ${cell.verdicts[i]}` : ""}`}
                        className={`relative inline-flex h-8 w-8 items-center justify-center rounded text-[10px] font-bold text-white ${COLOR[cell.verdicts[i]]} ${cell.verdicts[i] !== c.truth[0] && cell.verdicts[i] !== "-" && cell.verdicts[i] !== "U" ? "ring-2 ring-white" : ""}`}>
                    {cell.verdicts[i]}
                    {changed[i] ? <span aria-hidden="true" className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-sky-300" /> : null}
                  </span>
                ))}
              </div>
            </div>
          ))}
          <p className="text-xs text-zinc-500">Red: ticket · green: pass · sky dot: changed from Spark’s interpretation · white ring: judged wrong against the frozen label · grey: abstains or untracked. Muse Spark&apos;s compiled rule, the real SAM 3.1 tracks, the engine re-run for every cell; no model is called on this page.</p>
        </div>
      </div>
    </main>
  );
}
