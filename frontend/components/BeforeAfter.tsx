"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { challengeFileUrl } from "@/lib/api";
import type { BeforeAfter as BA, BeforeAfterSide, CounterStep, FinalReport, FinalSplit, HoldoutFull } from "@/lib/types";

// Series colors validated for the dark surface (CVD-separable); identity is also carried by labels and line style.
const BEFORE = "#ea580c";
const AFTER = "#0284c7";
const s2 = (ms: number) => (ms / 1000).toFixed(2);

function Verdict({ side, label, color }: { side: BeforeAfterSide; label: string; color: string }) {
  return (
    <div className="rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800" style={{ borderTop: `3px solid ${color}` }}
         data-testid={`ba-${label.toLowerCase()}`}>
      <div className="text-xs font-semibold uppercase tracking-wide text-zinc-400">{label}</div>
      <p className="mt-1 text-sm text-zinc-200">The {label === "Before" ? "original" : "repaired"} rule: {side.plain}.</p>
      <div className={`mt-3 flex items-center gap-2 text-lg font-bold ${side.correct ? "text-sky-300" : "text-orange-300"}`}>
        <span aria-hidden>{side.correct ? "✓" : "✗"}</span>
        <span>Says {side.verdict} — {side.correct ? "right" : "wrong"}</span>
      </div>
      <p className="text-xs text-zinc-500">reviewed truth: {side.intended} · rule {side.rule_hash.slice(0, 12)}</p>
    </div>
  );
}

/** The track the story is about: the one the old rule counted the most for. */
function mainTrack(b: BeforeAfterSide): string | null {
  let best: string | null = null, top = -1;
  for (const [id, s] of Object.entries(b.series)) {
    const m = Math.max(0, ...s.map((x) => x.counted_ms));
    if (m > top) { top = m; best = id; }
  }
  return best;
}

function Counter({ before, after, tb, ta, fps, nFrames, t, onSeek }: {
  before: CounterStep[]; after: CounterStep[]; tb: number; ta: number; fps: number; nFrames: number; t: number;
  onSeek: (s: number) => void;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 560, H = 230, L = 50, R = 10, T = 14, B = 70; // B leaves room for the two state bands
  const dur = nFrames / fps;
  const yMax = Math.max(2, tb, ta, ...before.map((x) => x.counted_ms / 1000), ...after.map((x) => x.counted_ms / 1000)) * 1.1;
  const x = (s: number) => L + (s / dur) * (W - L - R);
  const y = (sec: number) => T + (1 - sec / yMax) * (H - T - B);
  const path = (steps: CounterStep[]) => steps.map((p, i) => `${i ? "L" : "M"}${x(p.frame / fps).toFixed(1)},${y(p.counted_ms / 1000).toFixed(1)}`).join("");
  const at = (steps: CounterStep[], s: number) => [...steps].reverse().find((p) => p.frame / fps <= s);
  const hs = hover ?? t;
  const hb = at(before, hs), ha = at(after, hs);
  const bandY = H - B + 24;
  const band = (key: "in_zone" | "still", row: number, color: string) => before.map((p, i) => {
    const on = key === "still" ? after[i]?.still : p.in_zone;
    return on ? <rect key={`${key}${i}`} x={x(p.frame / fps)} y={bandY + row * 16} width={Math.max(1, (W - L - R) / nFrames)} height={10} fill={color} /> : null;
  });
  const ticks = Array.from({ length: Math.floor(dur) + 1 }, (_, i) => i);
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full select-none" role="img" data-testid="counter-chart"
           aria-label="Seconds counted toward the inspection requirement, before and after the repair"
           onMouseMove={(e) => {
             const r = e.currentTarget.getBoundingClientRect();
             const s = (((e.clientX - r.left) / r.width) * W - L) / (W - L - R) * dur;
             setHover(s >= 0 && s <= dur ? s : null);
           }}
           onMouseLeave={() => setHover(null)} onClick={() => hover !== null && onSeek(hover)}>
        {[0, 1, 2].filter((v) => v < yMax).map((v) => (
          <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="#27272a" />
            <text x={L - 6} y={y(v) + 4} textAnchor="end" className="fill-zinc-500 text-[12px]">{v} s</text></g>
        ))}
        {ticks.map((s) => <text key={s} x={x(s)} y={H - B + 13} textAnchor="middle" className="fill-zinc-500 text-[12px]">{s}s</text>)}
        <text x={L - 6} y={bandY + 9} textAnchor="end" className="fill-zinc-400 text-[12px]">in zone</text>
        <text x={L - 6} y={bandY + 25} textAnchor="end" className="fill-zinc-400 text-[12px]">still</text>
        {band("in_zone", 0, "#a16207")}
        {band("still", 1, "#3f3f46")}
        <line x1={L} x2={W - R} y1={bandY + 26} y2={bandY + 26} stroke="#27272a" />
        {/* the requirement of each rule */}
        <line x1={L} x2={W - R} y1={y(tb)} y2={y(tb)} stroke={BEFORE} strokeDasharray="2 4" strokeWidth={1} opacity={0.8} />
        <text x={W - R - 2} y={y(tb) - 4} textAnchor="end" className="text-[12px]" fill={BEFORE}>before needs {tb.toFixed(2)} s</text>
        <line x1={L} x2={W - R} y1={y(ta)} y2={y(ta)} stroke={AFTER} strokeDasharray="2 4" strokeWidth={1} opacity={0.8} />
        <text x={W - R - 2} y={y(ta) - 4} textAnchor="end" className="text-[12px]" fill={AFTER}>after needs {ta.toFixed(2)} s</text>
        <path d={path(before)} fill="none" stroke={BEFORE} strokeWidth={2} strokeDasharray="6 3" />
        <path d={path(after)} fill="none" stroke={AFTER} strokeWidth={2} />
        <line x1={x(hs)} x2={x(hs)} y1={T} y2={H - B} stroke="#e4e4e7" strokeWidth={1} />
      </svg>
      {hb && (
        <div className="pointer-events-none absolute right-2 top-1 rounded bg-zinc-950/90 px-2 py-1 font-mono text-[11px] text-zinc-300 ring-1 ring-zinc-700">
          t = {hs.toFixed(2)} s · in zone {hb.in_zone ? "yes" : "no"} · still {ha?.still ? "yes" : "no"}<br />
          <span style={{ color: BEFORE }}>■</span> before counted {s2(hb.counted_ms)} s · <span style={{ color: AFTER }}>■</span> after {s2(ha?.counted_ms ?? 0)} s
        </div>
      )}
    </div>
  );
}

function Bars({ label, before, after, n }: { label: string; before: number; after: number; n: number }) {
  return (
    <div className="space-y-1">
      <div className="text-xs text-zinc-400">{label}</div>
      {([["before", before, BEFORE], ["after", after, AFTER]] as const).map(([k, v, c]) => (
        <div key={k} className="flex items-center gap-2 text-xs">
          <span className="w-10 text-zinc-500">{k}</span>
          <div className="h-3 flex-1 rounded-sm bg-zinc-800"><div className="h-3 rounded-sm" style={{ width: `${(100 * v) / n}%`, background: c }} /></div>
          <span className="w-16 text-right font-mono text-zinc-200">{v}/{n}</span>
        </div>
      ))}
    </div>
  );
}

function FamilyTable({ b, a }: { b: HoldoutFull; a: HoldoutFull }) {
  const fams = Object.keys(b.by_family).sort();
  return (
    <table className="w-full text-xs" data-testid="ba-families">
      <thead><tr className="text-left text-zinc-500"><th className="py-1">family</th><th>correct before → after</th></tr></thead>
      <tbody>{fams.map((f) => {
        const cb = b.by_family[f].correct ?? 0, ca = a.by_family[f]?.correct ?? 0;
        const n = Object.values(b.by_family[f]).reduce((x, y) => x + y, 0);
        return <tr key={f} className="border-t border-zinc-800"><td className="py-1 font-mono text-zinc-300">{f}</td>
          <td className={ca > cb ? "text-sky-300" : ca < cb ? "text-orange-300" : "text-zinc-400"}>{cb} → {ca} / {n}</td></tr>;
      })}</tbody>
    </table>
  );
}

function finalFor(rep: FinalReport | null, ba: BA) {
  if (!rep || !ba.decision) return null;
  const src = Object.entries(rep.inputs).find(([, v]) => v.file.includes(ba.run_id))?.[0];
  const p = src && rep.patches.find((x) => x.source === src && x.patch_description === ba.decision!.patch_description);
  return p && src ? { p, base: rep.baselines[src], rep } : null;
}

function FinalSplitRow({ name, base, after, fixed, regressed }: { name: string; base: FinalSplit; after: FinalSplit; fixed: number; regressed: number }) {
  return (
    <div className="space-y-1">
      <Bars label={name} before={base.correct} after={after.correct} n={base.n} />
      <p className="font-mono text-[11px] text-zinc-500">
        95% CI after {after.accuracy_ci95[0].toFixed(2)}–{after.accuracy_ci95[1].toFixed(2)} · fixed {fixed} · regressed {regressed} · false PASS {base.false_pass} → {after.false_pass}
      </p>
    </div>
  );
}

export default function BeforeAfter({ ba, final }: { ba: BA; final: FinalReport | null }) {
  const vid = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0);
  const track = useMemo(() => mainTrack(ba.before), [ba]);
  useEffect(() => {
    const v = vid.current;
    if (!v) return;
    let id = 0;
    const tick = () => { setT(v.currentTime); id = requestAnimationFrame(tick); };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, []);
  if (!ba.after || !ba.decision || !track) {
    return <p className="text-sm text-amber-200" data-testid="ba-none">No accepted repair to compare ({ba.proposals} proposals, none passed the holdout).</p>;
  }
  const d = ba.decision, hb = d.holdout_before, ha = d.holdout_after!;
  const v = ba.truths.find((x) => x.intended === "VIOLATION");
  const maxB = Math.max(...ba.before.series[track].map((x) => x.counted_ms));
  const maxA = Math.max(0, ...(ba.after.series[track] ?? []).map((x) => x.counted_ms));
  const fin = finalFor(final, ba);
  const frame = Math.round(t * ba.scene.fps);
  const boxes = ba.boxes.filter((b) => b.frame_index === frame);
  const z = ba.scene.zones[0], ln = ba.scene.lines[0];
  const W = ba.scene.width, H = ba.scene.height;

  return (
    <section className="space-y-5 rounded-xl bg-zinc-950 p-5 ring-1 ring-sky-500/30" data-testid="before-after">
      <div>
        <h2 className="text-xl font-bold">Before → after the repair</h2>
        <p className="text-sm text-zinc-400">
          The case that broke the rule ({ba.scene.family} #{ba.scene.seed}), judged by the original rule and by the repair
          {ba.proposer.startsWith("muse") ? " Muse Spark proposed" : " the baseline found"}. Shown: {ba.choice} ({ba.accepted} of {ba.proposals} accepted).
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Verdict side={ba.before} label="Before" color={BEFORE} />
        <Verdict side={ba.after} label="After" color={AFTER} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="relative self-start">
          <video ref={vid} src={challengeFileUrl(ba.run_id, "counterexample.mp4")} controls loop muted playsInline
                 className="w-full rounded-lg bg-black" data-testid="ba-video" />
          <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="pointer-events-none absolute inset-0 h-full w-full">
            <polygon points={z.polygon.map((p) => p.join(",")).join(" ")} fill="rgba(250,204,21,0.10)" stroke="#facc15" strokeWidth={0.004} />
            <line x1={ln.a[0]} y1={ln.a[1]} x2={ln.b[0]} y2={ln.b[1]} stroke="#38bdf8" strokeWidth={0.004} strokeDasharray="0.01 0.01" />
            {boxes.map((b) => <rect key={b.object_id} x={b.box.x1 / W} y={b.box.y1 / H} width={(b.box.x2 - b.box.x1) / W}
                                    height={(b.box.y2 - b.box.y1) / H} fill="none" stroke="#f4f4f5" strokeWidth={0.004} />)}
          </svg>
        </div>
        <div className="space-y-2">
          <Counter before={ba.before.series[track]} after={ba.after.series[track] ?? []}
                   tb={(ba.before.threshold_ms ?? 0) / 1000} ta={(ba.after.threshold_ms ?? 0) / 1000} fps={ba.scene.fps}
                   nFrames={ba.scene.n_frames} t={t} onSeek={(s) => { if (vid.current) vid.current.currentTime = s; }} />
          <div className="flex flex-wrap gap-4 text-xs text-zinc-400">
            <span><span style={{ color: BEFORE }}>- - -</span> before: seconds counted (needs {s2(ba.before.threshold_ms ?? 0)} s)</span>
            <span><span style={{ color: AFTER }}>———</span> after: seconds counted (needs {s2(ba.after.threshold_ms ?? 0)} s)</span>
          </div>
          <p className="text-sm text-zinc-200" data-testid="ba-story">
            {v ? `The box never stood still long enough (${s2(v.station_stop_ms)} s at the station), so it was not inspected. ` : ""}
            The original rule counted <b style={{ color: BEFORE }}>{s2(maxB)} s</b> of time in the zone, moving included, and said {ba.before.verdict}.
            The repaired rule counts only standing still: <b style={{ color: AFTER }}>{s2(maxA)} s</b>, so it says {ba.after.verdict}.
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800" data-testid="ba-holdout">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Does it hold on cases it never saw?</div>
            <p className="text-xs text-zinc-500">Hidden holdout ({d.holdout_name}, {hb.n} synthetic scenes). Muse never saw it; the grader used it to accept or reject.</p>
          </div>
          <Bars label="judged correctly" before={hb.correct} after={ha.correct} n={hb.n} />
          <p className="text-xs text-zinc-300">dangerous false PASS {hb.false_pass} → {ha.false_pass} · regressions <b>{d.regressions.length}</b> · fixed {d.fixed_cases.length}</p>
          <FamilyTable b={hb} a={ha} />
        </div>
        <div className="space-y-3 rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800" data-testid="ba-final">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Independent final test</div>
            <p className="text-xs text-zinc-500">
              {fin ? `${fin.rep.final_set}: pre-registered, frozen before evaluation, never used to accept or reject. Includes 3 scene families no rule was designed for.`
                   : "This repair is not part of the pre-registered final test (only the recorded demo run is). See benchmark/final/."}
            </p>
          </div>
          {fin && (<>
            <FinalSplitRow name="same kinds of scenes (200)" base={fin.base.in_distribution} after={fin.p.splits.in_distribution}
                           fixed={fin.p.fixed.in_distribution} regressed={fin.p.regressed.in_distribution} />
            <FinalSplitRow name="new kinds of scenes (120)" base={fin.base.shift} after={fin.p.splits.shift}
                           fixed={fin.p.fixed.shift} regressed={fin.p.regressed.shift} />
            <p className="text-[11px] text-zinc-500">Perception in all synthetic tests: {fin.rep.perception}.</p>
          </>)}
        </div>
      </div>

      <p className="break-all font-mono text-[12px] text-zinc-600" data-testid="ba-hashes">
        rule {d.previous_rule_hash.slice(0, 16)} → {d.patched_rule_hash?.slice(0, 16)} · holdout {d.holdout_manifest_sha256.slice(0, 16)}
        · scene {ba.scene.scene_sha256.slice(0, 16)}{fin ? ` · final manifest ${fin.rep.manifest_sha256.slice(0, 16)} · eval commit ${fin.rep.code_commit.slice(0, 7)}` : ""}
        · search perception {ba.perception}
      </p>
    </section>
  );
}
