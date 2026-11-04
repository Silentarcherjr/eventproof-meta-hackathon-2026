"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  compileLab, getLabPair, getLabScenes, judgeLab, labMediaUrl,
  type LabCompiled, type LabJudgment, type LabPair, type LabScenes, type LabVerdict,
} from "@/lib/api";

const title = (name: string) => name.replaceAll("_", " ");
const card = "rounded-xl bg-zinc-900 p-4 ring-1 ring-zinc-800";
function Verdict({ value }: { value: string }) {
  const tone = value === "PASS" ? "bg-green-500/15 text-green-300" : value === "VIOLATION" ? "bg-red-500/15 text-red-300" : "bg-amber-500/15 text-amber-200";
  return <span className={`inline-block rounded px-2 py-1 text-xs font-semibold ${tone}`}>{value}</span>;
}
function Events({ verdict }: { verdict: LabVerdict }) {
  return <ul className="mt-2 space-y-1 text-xs text-zinc-400">{verdict.events.map((event, i) => (
    <li key={`${event.op}-${event.target}-${i}`}><b>{event.op}</b> {event.target}: {event.status}
      {event.frame !== null ? ` · frame ${event.frame}` : ""} — {event.reason}</li>
  ))}</ul>;
}

export default function LabPage() {
  const [data, setData] = useState<LabScenes | null>(null);
  const [pair, setPair] = useState<LabPair | null>(null);
  const [family, setFamily] = useState("full_stop");
  const [speed, setSpeed] = useState<number | null>(null);
  const [anyDirection, setAnyDirection] = useState(false);
  const [judgment, setJudgment] = useState<LabJudgment | null>(null);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [compiled, setCompiled] = useState<LabCompiled | null>(null);
  const [submitted, setSubmitted] = useState("");
  const [compiling, setCompiling] = useState(false);
  const [compileError, setCompileError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([getLabScenes(), getLabPair()]).then(([scenes, minimal]) => {
      if (!active) return;
      setData(scenes); setPair(minimal); setSpeed(scenes.defaults.max_speed);
      setAnyDirection(scenes.defaults.any_direction); setText(scenes.rule_text);
    }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!data) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      judgeLab(family, speed, anyDirection, controller.signal).then((result) => {
        if (!controller.signal.aborted) { setJudgment(result); setError(""); }
      }).catch((e: Error) => { if (!controller.signal.aborted) setError(e.message); });
    }, 120);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [data, family, speed, anyDirection]);

  async function compile() {
    setCompiling(true); setCompileError(""); setCompiled(null); setSubmitted(text.trim());
    try { setCompiled(await compileLab(text)); } catch (e) { setCompileError((e as Error).message); }
    finally { setCompiling(false); }
  }

  const fresh = judgment?.family === family && judgment.controls.max_speed === speed && judgment.controls.any_direction === anyDirection;
  const scene = data?.scenes.find((s) => s.family === family);
  return (
    <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <Link href="/" className="text-sm text-sky-300 underline">← studio</Link>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Traffic lab</h1>
      <p className="mt-1 text-sm text-zinc-400">Change a choice. Watch the same car get a different verdict.</p>
      {error ? <p role="alert" className="mt-3 rounded bg-red-500/10 p-3 text-red-200">{error}</p> : null}
      {!data ? <p role="status" className="mt-5 text-zinc-400">{error ? "Could not load Traffic lab. Reload to retry." : "Loading recorded scenes…"}</p> : <>
        <section className={`${card} mt-5 border-l-4 border-sky-500`} aria-label="Recorded sealed evaluation">
          <p data-testid="sealed-summary" className="text-lg">On <b>{data.summary.scenes}</b> sealed scenes, Spark&apos;s rule agrees with the written contract on <b>{data.summary.correct}</b>;
            {data.summary.two_choices_explain_all ? <> all <b>{data.summary.disagreements}</b> disagreements are these two open choices.</> : <> <b>{data.summary.disagreements}</b> disagree.</>}</p>
          <p className="mt-1 text-xs text-zinc-500">Recorded evaluation on perfect tracks. These controls use only eight development scenes, never the sealed scenes.</p>
        </section>
        <blockquote className="mt-5 border-l-4 border-zinc-600 pl-3 text-zinc-200">&ldquo;{data.rule_text}&rdquo;</blockquote>
        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <section className={card}>
            <label htmlFor="lab-scene" className="block text-sm font-medium">Pick a scene</label>
            <select id="lab-scene" value={family} onChange={(e) => setFamily(e.target.value)} className="mt-2 w-full rounded border border-zinc-700 bg-zinc-950 p-2 capitalize" data-testid="lab-scene">
              {data.scenes.map((s) => <option key={s.family} value={s.family}>{title(s.family)} · dev seed {s.seed}</option>)}
            </select>
            <p className="mt-3 text-xs font-semibold text-amber-200">Synthetic scene, perfect tracks (not SAM)</p>
            {scene ? <video key={scene.video_url} src={labMediaUrl(scene.video_url)} controls loop muted playsInline preload="metadata" className="mt-2 w-full rounded-lg bg-black" aria-label={`${title(family)} synthetic scene`} /> : null}
            <p className="mt-2 text-xs text-zinc-400">Gold: waiting zone · white: stop line · numbered cars · muted cross traffic. Video labels show contract truth, not the adjustable rule. Car 0 leads; car 1 follows when present.</p>
          </section>
          <section className={`${card} space-y-5`} aria-label="Your rule controls">
            <h2 className="text-lg font-semibold">Your rule</h2>
            <p className="text-sm text-zinc-400">Spark&apos;s recorded rule, with two choices you can change. Re-judging is deterministic and calls no model.</p>
            <div>
              <label htmlFor="still-speed" className="text-sm">How slow counts as standing still: <b>{speed === null ? "any motion" : `≤ ${speed.toFixed(3)} frame widths/s`}</b></label>
              <input id="still-speed" type="range" min="0.005" max="0.10" step="0.005" value={speed ?? data.defaults.max_speed ?? 0.05}
                disabled={speed === null} onChange={(e) => setSpeed(Number(e.target.value))} list="speed-markers" className="mt-2 w-full accent-sky-400" data-testid="lab-speed" />
              <datalist id="speed-markers"><option value={data.defaults.contract_max_speed} label="contract" /><option value={data.defaults.max_speed ?? undefined} label="Spark" /></datalist>
              <p className="text-xs text-zinc-400">◆ Contract: {data.defaults.contract_max_speed} · Spark: {data.defaults.max_speed ?? "any motion"}</p>
              <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={speed === null} onChange={(e) => setSpeed(e.target.checked ? null : data.defaults.max_speed)} />Any motion counts as waiting</label>
            </div>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={anyDirection} onChange={(e) => setAnyDirection(e.target.checked)} className="mt-1" data-testid="lab-direction" />
              <span>Count crossings in either direction<span className="block text-xs text-zinc-400">Contract: any direction. Spark: travel direction only (left to right).</span></span>
            </label>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => { setSpeed(data.defaults.contract_max_speed); setAnyDirection(data.defaults.contract_any_direction); }} className="rounded bg-sky-500/20 px-3 py-2 text-sm text-sky-200" data-testid="lab-contract">Use contract choices</button>
              <button onClick={() => { setSpeed(data.defaults.max_speed); setAnyDirection(data.defaults.any_direction); }} className="rounded bg-zinc-800 px-3 py-2 text-sm">Reset to Spark</button>
            </div>
            <p role="status" aria-live="polite" className="text-sm text-amber-200" data-testid="lab-flip">{fresh ? judgment.explanation : "Re-judging…"}</p>
          </section>
        </div>
        <section className={`${card} mt-5`} aria-label="Per-car verdicts">
          <h2 className="text-lg font-semibold">Same car, three readings</h2>
          <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm" data-testid="lab-verdicts">
            <thead className="text-xs text-zinc-400"><tr><th className="p-2">Car</th><th className="p-2">Contract truth</th><th className="p-2">Spark&apos;s recorded rule</th><th className="p-2">Your rule</th></tr></thead>
            <tbody>{fresh ? judgment.cars.map((car) => <tr key={car.object_id} className="border-t border-zinc-800 align-top">
              <th className="p-2">{car.object_id}</th>
              <td className="p-2"><Verdict value={car.truth.intended} /><p className="mt-2 text-xs text-zinc-400">Crossed: {car.truth.crossed_line ? "yes" : "no"} · {title(car.truth.direction)}<br />Standing still: {car.truth.standing_still_seconds.toFixed(1)} s</p></td>
              <td className="p-2"><Verdict value={car.spark.verdict} /><details className="mt-2"><summary className="cursor-pointer text-xs text-sky-300">Decisive events</summary><Events verdict={car.spark} /></details></td>
              <td className="p-2"><Verdict value={car.your.verdict} /><details className="mt-2"><summary className="cursor-pointer text-xs text-sky-300">Decisive events</summary><Events verdict={car.your} /></details></td>
            </tr>) : <tr><td colSpan={4} className="p-4 text-zinc-400">Re-judging current choices…</td></tr>}</tbody>
          </table></div>
          <details className="mt-3 text-sm text-zinc-400"><summary className="cursor-pointer">Spark&apos;s recorded assumptions</summary><ul className="mt-2 list-disc space-y-1 pl-5">{data.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></details>
          <p className="mt-3 text-xs text-zinc-500">Contract stillness uses a 333 ms speed window (four frames at 10 fps), counts consecutive qualifying samples, and measures the car center. A hidden car remains in perfect tracks. This is synthetic rule evaluation, not legal compliance or a SAM result.</p>
        </section>
        {pair ? <section className={`${card} mt-5`}>
          <h2 className="text-lg font-semibold">Minimal pair</h2>
          <p className="mt-1 text-sm text-zinc-400">The {pair.knob} knob changes by <b>{pair.motion_frame_difference} motion frame</b>. The naive rule counts residence time, even while moving.</p>
          <div className="mt-3 grid gap-4 md:grid-cols-2">{(["fail", "pass"] as const).map((side) => <div key={side}>
            <h3 className="text-sm font-medium">{side === "fail" ? "Longer crawl · fools the naive rule" : "Shorter crawl · naive rule rejects"} <span className="text-xs text-zinc-500">t={pair.sides[side].t.toFixed(4)}</span></h3>
            <video src={labMediaUrl(pair.sides[side].video_url)} controls loop muted playsInline preload="metadata" className="mt-2 w-full rounded bg-black" aria-label={`${side} boundary scene`} />
            {pair.sides[side].cars.map((c) => <p key={c.truth.object_id} className="mt-2 text-sm">Car {c.truth.object_id} · naive <Verdict value={c.naive.verdict} /> · truth <Verdict value={c.truth.intended} /></p>)}
          </div>)}</div>
        </section> : null}
        <section className={`${card} mt-5`} aria-label="Write your own rule">
          <h2 className="text-lg font-semibold">Write your own rule</h2>
          <p className="mt-1 text-sm text-zinc-400">Muse Spark compiles your sentence into validated DSL; the deterministic engine judges all eight showcase scenes on perfect tracks. No SAM call.</p>
          <form onSubmit={(e) => { e.preventDefault(); void compile(); }} className="mt-3">
            <label htmlFor="lab-rule" className="text-sm">Rule sentence</label>
            <textarea id="lab-rule" value={text} minLength={3} maxLength={2000} required disabled={compiling} onChange={(e) => { setText(e.target.value); setCompiled(null); }} rows={3} className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-950 p-3 text-sm" />
            <p className="mt-2 text-xs text-zinc-400">The prefilled sentence replays a recorded response at zero cost. New wording compiles live if the host&apos;s shared allowance permits; cached wording replays at zero cost.</p>
            <button type="submit" disabled={compiling || text.trim().length < 3} className="mt-3 rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-zinc-950 disabled:opacity-50" data-testid="lab-compile">{compiling ? "Compiling and judging…" : "Compile and judge all scenes"}</button>
          </form>
          {compileError ? <p role="alert" className="mt-3 text-sm text-red-300">{compileError}</p> : null}
          {compiled ? <div className="mt-4" data-testid="lab-compiled">
            <p className="text-sm font-semibold text-sky-200">{compiled.provenance} · {compiled.model}</p>
            <blockquote className="mt-2 border-l-2 border-zinc-700 pl-3 text-sm">{submitted}</blockquote>
            <p className="mt-2 text-sm text-amber-200">{compiled.wrong_scenes.length ? `Disagrees with contract: ${compiled.wrong_scenes.map(title).join(", ")}.` : "Agrees with the contract on every showcase scene."}</p>
            <h3 className="mt-3 text-sm font-semibold">Muse Spark&apos;s assumptions</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-zinc-400">{compiled.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            <div className="mt-3 grid gap-3 md:grid-cols-2">{compiled.scenes.map((s) => <div key={s.family} className="rounded bg-zinc-950 p-3">
              <h3 className="text-sm font-medium capitalize">{title(s.family)} <span className={s.correct ? "text-green-300" : "text-amber-200"}>{s.correct ? "· agrees" : "· disagrees"}</span></h3>
              {s.cars.map((c) => <div key={c.object_id} className="mt-2 text-xs">Car {c.object_id} · rule <Verdict value={c.your?.verdict ?? "NO VERDICT"} /> · contract <Verdict value={c.truth.intended} />
                {!c.correct ? <p className="mt-1 text-zinc-400">{c.why} Contract: {c.truth.standing_still_seconds.toFixed(1)} s still before crossing, direction {title(c.truth.direction)}.</p> : null}</div>)}
            </div>)}</div>
            <p className="mt-3 text-xs text-zinc-500">{compiled.scope}</p>
          </div> : null}
        </section>
      </>}
    </main>
  );
}
