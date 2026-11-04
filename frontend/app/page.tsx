"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import BeforeAfterView from "@/components/BeforeAfter";
import AmbiguityPanel from "@/components/AmbiguityPanel";
import ChallengePanel from "@/components/ChallengePanel";
import Results from "@/components/Results";
import Stepper from "@/components/Stepper";
import Timeline from "@/components/Timeline";
import VideoStage, { type Tool } from "@/components/VideoStage";
import Gallery from "@/components/Gallery";
import RuleChecks from "@/components/RuleChecks";
import TicketPanel from "@/components/TicketPanel";
import { certificateUrl, createRun, getFinalReport, type LayoutProposal, proposeLayout, rerunWithRule, getHealth, getRun, getTracks, type Health, videoUrl } from "@/lib/api";
import { DEFAULT_LAYOUT, EXAMPLE_RULES } from "@/lib/defaults";
import type { BeforeAfter, Evidence, FinalReport, Layout, ObjectVerdict, TrackFrame, TrackSet } from "@/lib/types";

export default function Studio() {
  const [file, setFile] = useState<File | null>(null);
  const [localUrl, setLocalUrl] = useState<string | null>(null);
  const [layout, setLayout] = useState<Layout>(DEFAULT_LAYOUT);
  const [rule, setRule] = useState(EXAMPLE_RULES[0]);
  const [tool, setTool] = useState<Tool>("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ev, setEv] = useState<Evidence | null>(null);
  const [tracks, setTracks] = useState<TrackSet | null>(null);
  const [frame, setFrame] = useState(0);
  const [seek, setSeek] = useState<number | null>(null);
  const [ba, setBa] = useState<BeforeAfter | null>(null);
  const [finalReport, setFinalReport] = useState<FinalReport | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const showcase = health?.mode === "showcase";

  useEffect(() => () => { if (localUrl) URL.revokeObjectURL(localUrl); }, [localUrl]);

  // ?run=<id> reopens a recorded run (evidence, tracks and any Challenge/Repair results stored with it)
  useEffect(() => {
    getFinalReport().then(setFinalReport).catch(() => setFinalReport(null));
    (async () => {
      const h = await getHealth();
      setHealth(h);
      // a showcase or hosted server opens its first recorded run when no run is asked for
      const id = new URLSearchParams(window.location.search).get("run")
        ?? (h?.mode === "showcase" || h?.mode === "hosted" ? h.demo_runs[0] ?? null : null);
      if (!id) return;
      try {
        const e = await getRun(id);
        setRule(e.rule.text);
        setLayout(e.rule.layout);
        setEv(e);
        setTracks(e.status === "completed" ? await getTracks(e.run_id) : null);
      } catch (err) {
        setError(`could not open run ${id}: ${err instanceof Error ? err.message : String(err)}`);
      }
    })();
  }, []);

  const [proposal, setProposal] = useState<LayoutProposal | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const suggest = async () => {
    if (!file) return;
    setSuggesting(true);
    setError(null);
    try {
      const p = await proposeLayout(file, rule);
      setLayout(p.layout);
      setProposal(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSuggesting(false);
    }
  };

  const pick = (f: File | null) => {
    setFile(f);
    setEv(null);
    setBa(null);
    setTracks(null);
    setError(null);
    setLocalUrl(f ? URL.createObjectURL(f) : null);
  };

  const run = async () => {
    if (!file && !ev) return;
    setBusy(true);
    setError(null);
    setTool("none");
    try {
      // a new file starts a new run; otherwise the open run's video is checked against the edited rule and zones
      const e = file ? await createRun(file, rule, layout) : await rerunWithRule(ev!.run_id, rule, layout);
      setBa(null);
      setEv(e);
      setTracks(e.status === "completed" ? await getTracks(e.run_id) : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const tracksByFrame = useMemo(() => {
    const m = new Map<number, TrackFrame[]>();
    tracks?.frames.forEach((f) => m.set(f.frame_index, [...(m.get(f.frame_index) ?? []), f]));
    return m;
  }, [tracks]);
  const verdicts = useMemo(() => new Map<number, ObjectVerdict>((ev?.result?.objects ?? []).map((o) => [o.object_id, o])), [ev]);
  const onSeek = useCallback((f: number) => setSeek(f + Math.random() * 1e-6), []); // re-trigger on same frame
  const info = ev?.video.info;
  // the shown verdict belongs to the inputs of that run; say so as soon as the user edits them
  const stale = !!ev && (ev.rule.text !== rule || JSON.stringify(ev.rule.layout) !== JSON.stringify(layout));

  const setZone = (k: "id" | "description", v: string) => {
    const zones = [...layout.zones];
    zones[0] = k === "id" ? { ...zones[0], zone: { ...zones[0].zone, id: v } } : { ...zones[0], description: v };
    setLayout({ ...layout, zones });
  };
  const setLine = (k: "id" | "description", v: string) => {
    const lines = [...layout.lines];
    lines[0] = k === "id" ? { ...lines[0], line: { ...lines[0].line, id: v } } : { ...lines[0], description: v };
    setLayout({ ...layout, lines });
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">EventProof Studio</h1>
          <nav className="mt-1 flex gap-4 text-sm"><Link href="/court" className="text-sky-300 underline" data-testid="nav-court">Ticket court: would 20 real tickets hold up?</Link><Link href="/law" className="text-sky-300 underline" data-testid="nav-law">Drag the law</Link></nav>
          <p className="text-sm text-zinc-400">Describe a visual rule in plain language. Muse Spark turns it into a checkable rule, SAM 3.1 tracks the objects, and every verdict comes with its frames.</p>
        </div>
      </header>
      {showcase && (
        <div className="mb-4 rounded-lg bg-sky-500/10 p-3 text-sm text-sky-200 ring-1 ring-sky-500/40" data-testid="showcase-banner">
          Showcase server: it replays recorded runs (real Muse Spark and SAM 3.1 outputs, served from their cache) and makes no
          live model calls, so uploads are off. Challenge Mode and the baseline repair run live; they are free and deterministic.
          {health && health.demo_runs.length > 1 && (
            <span> Recorded runs: {health.demo_runs.map((r) => <a key={r} href={`/?run=${r}`} className="mx-1 underline">{r.slice(-8)}</a>)}</span>
          )}
        </div>
      )}

      {health?.mode === "hosted" && (
        <div className="mb-4 rounded-lg bg-sky-500/10 p-3 text-sm text-sky-200 ring-1 ring-sky-500/40" data-testid="hosted-banner">
          Live studio: open a real clip below, change the rule text (or write a new one) and press the check button. Muse Spark
          compiles your sentence live and the engine judges every tracked object; SAM 3.1 is called again only when your rule
          names a new kind of object. Live Meta calls on this server are capped
          (left: Muse {health.live_calls_remaining.muse}, SAM {health.live_calls_remaining.sam}).
        </div>
      )}
      {health?.mode === "hosted" && !!health.demo_clips?.length && <Gallery clips={health.demo_clips} current={ev?.run_id} />}

      {ev?.status === "completed" && !stale && <Stepper key={`st-${ev.run_id}`} ev={ev} />}
      {ev?.status === "completed" && !stale && <RuleChecks key={`rc-${ev.run_id}`} runId={ev.run_id} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section className="space-y-4">
          <VideoStage src={ev ? videoUrl(ev.run_id) : localUrl} layout={layout} onLayoutChange={setLayout} tool={tool}
                      tracksByFrame={tracksByFrame} info={info} verdicts={verdicts} onFrame={setFrame} seekFrame={seek} />
          {ev?.result && info && (
            <Timeline objects={ev.result.objects} frameCount={info.frame_count} fps={info.fps} frame={frame} onSeek={onSeek} />
          )}
          {ev?.status === "completed" && !stale && <TicketPanel key={`tp-${ev.run_id}`} runId={ev.run_id} />}
          {ev?.status === "completed" && !stale && <ChallengePanel key={ev.run_id} runId={ev.run_id} onBeforeAfter={setBa} />}
          {ev?.status === "completed" && !stale && <AmbiguityPanel key={`amb-${ev.run_id}`} runId={ev.run_id} defaultText={ev.rule.text} />}
        </section>

        <section className="space-y-5">
          <div className="space-y-2 rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800">
            <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-400" htmlFor="video">1 · Video (MP4/MOV, ≤ 20 s)</label>
            <input id="video" data-testid="video-input" type="file" accept="video/mp4,video/quicktime,.mp4,.mov" disabled={showcase}
                   onChange={(e) => pick(e.target.files?.[0] ?? null)}
                   className="block w-full text-sm text-zinc-300 file:mr-3 file:rounded file:border-0 file:bg-zinc-700 file:px-3 file:py-1.5 file:text-zinc-100" />
          </div>

          <div className="space-y-2 rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-400">2 · Zone and line</span>
              <div className="flex gap-1 text-xs">
                {(["none", "zone", "line"] as Tool[]).map((t) => (
                  <button key={t} onClick={() => setTool(t)} data-testid={`tool-${t}`}
                          className={`rounded px-2 py-1 ${tool === t ? "bg-sky-600 text-white" : "bg-zinc-800 text-zinc-300"}`}>
                    {t === "none" ? "view" : `draw ${t}`}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-[auto_1fr] items-center gap-2 text-sm">
              <span className="text-yellow-400">zone</span>
              <div className="flex gap-2">
                <input className="w-32 rounded bg-zinc-800 px-2 py-1 font-mono" value={layout.zones[0].zone.id} onChange={(e) => setZone("id", e.target.value)} />
                <input className="flex-1 rounded bg-zinc-800 px-2 py-1" value={layout.zones[0].description} onChange={(e) => setZone("description", e.target.value)} />
              </div>
              <span className="text-sky-400">line</span>
              <div className="flex gap-2">
                <input className="w-32 rounded bg-zinc-800 px-2 py-1 font-mono" value={layout.lines[0].line.id} onChange={(e) => setLine("id", e.target.value)} />
                <input className="flex-1 rounded bg-zinc-800 px-2 py-1" value={layout.lines[0].description} onChange={(e) => setLine("description", e.target.value)} />
              </div>
            </div>
            <p className="text-xs text-zinc-500">Drag on the video to redraw. Ids must be lowercase (a–z, 0–9, _).</p>
            <button onClick={suggest} disabled={!file || suggesting || rule.trim().length < 3} data-testid="suggest-layout"
                    className="w-full rounded bg-zinc-800 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-700 disabled:opacity-40">
              {suggesting ? "Muse Spark is reading the first frame…" : "Suggest zone and line with Muse Spark (from the rule and the first frame)"}
            </button>
            {proposal && (
              <div className="rounded bg-amber-500/10 p-2 text-xs text-amber-100 ring-1 ring-amber-500/40" data-testid="layout-proposal">
                <b>Draft from {proposal.model}{proposal.cached ? " (recorded response)" : ""}: check it on the video and redraw if needed.</b>
                <ul className="mt-1 list-disc pl-4">{proposal.assumptions.slice(0, 4).map((a) => <li key={a}>{a}</li>)}</ul>
              </div>
            )}
          </div>

          <div className="space-y-2 rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800">
            <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-400" htmlFor="rule">3 · Rule</label>
            <textarea id="rule" data-testid="rule-input" rows={3} value={rule} onChange={(e) => setRule(e.target.value)}
                      className="w-full rounded bg-zinc-800 p-2 text-sm" />
            <div className="flex flex-wrap gap-1">
              {EXAMPLE_RULES.map((r, i) => (
                <button key={r} onClick={() => setRule(r)} className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400 hover:text-zinc-200">example {i + 1}</button>
              ))}
            </div>
          </div>

          <button onClick={run} disabled={(!file && !(ev && stale)) || busy || rule.trim().length < 3} data-testid="run"
                  className="w-full rounded-lg bg-sky-600 py-2.5 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">
            {busy ? "Running Muse Spark + SAM 3.1…" : "Check the rule"}
          </button>
          {error && <div className="rounded bg-red-500/10 p-3 text-sm text-red-300 ring-1 ring-red-500/40" data-testid="error">{error}</div>}
          {stale && (
            <div className="rounded bg-amber-500/10 p-3 text-sm text-amber-200 ring-1 ring-amber-500/40" data-testid="stale">
              Rule or layout changed since this run — the results below are for the previous inputs. Run again to check.
            </div>
          )}
          {ev?.status === "completed" && !stale && (
            <a href={certificateUrl(ev.run_id)} target="_blank" rel="noreferrer" data-testid="certificate-link"
               className="block w-full rounded-lg bg-zinc-100 py-2 text-center text-sm font-semibold text-zinc-900 hover:bg-white">
              Rule certificate (one page, printable)
            </a>
          )}
          <div id="results">{ev && <Results ev={ev} onSeek={onSeek} />}</div>
        </section>
      </div>
      {ba && ev?.run_id === ba.run_id && !stale && <div className="mt-6"><BeforeAfterView ba={ba} final={finalReport} /></div>}
    </main>
  );
}
