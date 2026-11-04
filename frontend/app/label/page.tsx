"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";

type Obj = { description: string; crosses_packing: boolean; stood_still_s: number; intended: "PASS" | "VIOLATION";
             cross_s: number | null; cross_dir: "to_left" | "to_right" | null };
type Pt = [number, number];
type Draft = { clip: string; rule_text: string; notes: string;
               layout: { zones: { zone: { polygon: Pt[] } }[]; lines: { line: { a: Pt; b: Pt } }[] } };
type Crossing = { description: string; approx_cross_time_s: number; waited_s: number; verdict: "PASS" | "VIOLATION" };
type Clip = { draft: Draft; proposal: { crossings: Crossing[]; notes: string } | null; saved: { objects: Obj[] } | null };
type LabelSet = { set: string; frozen: boolean; writable: boolean; clips: Clip[] };

const SET = "fresh_v1";
// north clips: cars move up across a left-to-right line (to_left); south clips: down (to_right)
const dirOf = (clip: string): Obj["cross_dir"] => (clip.includes("north") ? "to_left" : "to_right");

function fromProposal(c: Clip): Obj[] {
  if (c.saved) return c.saved.objects;
  return (c.proposal?.crossings ?? []).map((x) => ({
    description: x.description, crosses_packing: true, stood_still_s: x.waited_s, intended: x.verdict,
    cross_s: x.approx_cross_time_s, cross_dir: dirOf(c.draft.clip) }));
}

const T = {
  en: { saving: "saving…", saved: "saved", notSaved: "not saved", legend: "Red: stop line. Green: waiting zone.", note: "Muse's note",
        rule: "Rule:", ruleTail: "A car that crosses without standing still ≥ 1.5 s in the zone is a VIOLATION.", crosses: "crosses",
        crossS: "cross s", now: "now", stillS: "still s", del: "delete", add: "+ car Muse missed (at current time)",
        save: "Save my labels for this clip", back: "← studio", loading: "Loading clips…",
        title: "Audit set builder: Muse Spark proposes, you decide",
        intro: "Muse Spark watched each clip and proposed which cars cross the stop line and whether they stood still first. Watch each clip (slow it down), fix or delete any wrong proposal, add the cars it missed, and save. Only your labels count as truth; they are frozen before any rule is compiled or tracked on these clips.",
        count: "clips saved", frozen: "frozen", lang: "Español" },
  es: { saving: "guardando…", saved: "guardado", notSaved: "no se guardó", legend: "Rojo: línea de detención. Verde: zona de espera.", note: "Nota de Muse",
        rule: "Regla:", ruleTail: "Un auto que cruza sin quedarse completamente quieto ≥ 1.5 s en la zona es VIOLATION (si se quedó quieto, PASS).", crosses: "cruza",
        crossS: "cruza en s", now: "ahora", stillS: "quieto s", del: "borrar", add: "+ auto que Muse no vio (en el tiempo actual)",
        save: "Guardar mis etiquetas de este clip", back: "← studio", loading: "Cargando clips…",
        title: "Constructor del set de auditoría: Muse Spark propone, tú decides",
        intro: "Muse Spark vio cada clip y propuso qué autos cruzan la línea de detención y si se quedaron quietos antes. Mira cada clip (ponlo lento), corrige o borra cualquier propuesta incorrecta, agrega los autos que no vio y guarda. Solo tus etiquetas cuentan como verdad; se congelan antes de compilar o rastrear cualquier regla en estos clips.",
        count: "clips guardados", frozen: "congelado", lang: "English" },
};
type Lang = keyof typeof T;

function ClipReview({ c, set, onSaved, t }: { c: Clip; set: LabelSet; onSaved: () => void; t: (typeof T)[Lang] }) {
  const [rows, setRows] = useState<Obj[]>(() => fromProposal(c));
  const [msg, setMsg] = useState("");
  const vid = useRef<HTMLVideoElement>(null);
  const d = c.draft;
  const zone = d.layout.zones[0].zone.polygon, line = d.layout.lines[0].line;
  const upd = (i: number, k: keyof Obj, v: Obj[keyof Obj]) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const now = () => Math.round((vid.current?.currentTime ?? 0) * 10) / 10;
  async function save() {
    setMsg(t.saving);
    const r = await fetch(`${API_URL}/label/${set.set}/${d.clip}`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objects: rows, reviewer: "participant (reviewed Muse Spark's proposals while watching the video)" }) });
    setMsg(r.ok ? t.saved : `${t.notSaved}: ${(await r.json()).detail ?? r.status}`);
    if (r.ok) onSaved();
  }
  return (
    <section className="rounded-lg bg-zinc-900 p-4 ring-1 ring-zinc-800" data-testid={`clip-${d.clip}`}>
      <h2 className="font-semibold">{d.clip} {c.saved && <span className="ml-2 rounded bg-green-500/20 px-2 text-xs text-green-300">{t.saved}</span>}</h2>
      <div className="mt-3 grid gap-4 lg:grid-cols-[360px_1fr]">
        <div className="w-full max-w-[360px]">
          <div className="relative">
          <video ref={vid} src={`${API_URL}/label/${set.set}/video/${d.clip}`} controls muted playsInline className="block w-full rounded" />
          <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="pointer-events-none absolute inset-0 h-full w-full">
            <polygon points={zone.map((p) => p.join(",")).join(" ")} fill="rgba(45,212,191,0.12)" stroke="#2dd4bf" strokeWidth={0.004} />
            <line x1={line.a[0]} y1={line.a[1]} x2={line.b[0]} y2={line.b[1]} stroke="#f87171" strokeWidth={0.012} />
          </svg>
          </div>
          <div className="mt-2 flex gap-2 text-xs">
            {[0.25, 0.5, 1].map((r) => <button key={r} className="rounded bg-zinc-800 px-2 py-1" onClick={() => { if (vid.current) vid.current.playbackRate = r; }}>{r}×</button>)}
          </div>
          <p className="mt-2 text-xs text-zinc-400">{t.legend} {c.proposal?.notes ? <>{t.note}: {c.proposal.notes}</> : null}</p>
        </div>
        <div className="min-w-0 space-y-2">
          <p className="text-xs text-zinc-400">{t.rule} {d.rule_text} {t.ruleTail}</p>
          {rows.map((r, i) => (
            <div key={i} className="grid grid-cols-2 gap-2 rounded bg-zinc-800/60 p-2 text-sm sm:grid-cols-6" data-testid="row">
              <input className="col-span-2 rounded bg-zinc-900 px-2 py-1" value={r.description} onChange={(e) => upd(i, "description", e.target.value)} />
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={r.crosses_packing}
                onChange={(e) => upd(i, "crosses_packing", e.target.checked)} />{t.crosses}</label>
              <label className="text-xs">{t.crossS} <input type="number" step="0.1" className="w-16 rounded bg-zinc-900 px-1" value={r.cross_s ?? ""}
                onChange={(e) => upd(i, "cross_s", e.target.value === "" ? null : Number(e.target.value))} />
                <button className="ml-1 text-sky-300 underline" onClick={() => upd(i, "cross_s", now())}>{t.now}</button></label>
              <label className="text-xs">{t.stillS} <input type="number" step="0.1" min="0" className="w-14 rounded bg-zinc-900 px-1" value={r.stood_still_s}
                onChange={(e) => upd(i, "stood_still_s", Number(e.target.value))} /></label>
              <div className="flex items-center gap-1">
                <select className="rounded bg-zinc-900 px-1 text-xs" value={r.intended} onChange={(e) => upd(i, "intended", e.target.value as Obj["intended"])}>
                  <option>PASS</option><option>VIOLATION</option>
                </select>
                <button className="text-xs text-red-300" onClick={() => setRows(rows.filter((_, j) => j !== i))}>{t.del}</button>
              </div>
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-2">
            <button className="rounded bg-zinc-800 px-3 py-1 text-sm" data-testid="add"
                    onClick={() => setRows([...rows, { description: "", crosses_packing: true, stood_still_s: 0, intended: "VIOLATION", cross_s: now(), cross_dir: dirOf(d.clip) }])}>{t.add}</button>
            <button className="rounded bg-teal-600 px-3 py-1 text-sm font-semibold text-white disabled:opacity-40" disabled={!set.writable || set.frozen}
                    onClick={save} data-testid="save">{t.save}</button>
            <span className="text-xs text-zinc-400">{msg}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function LabelPage() {
  const [set, setSet] = useState<LabelSet | null>(null);
  const [lang, setLang] = useState<Lang>("en");
  useEffect(() => { if (new URLSearchParams(window.location.search).get("lang") === "es") setLang("es"); }, []);
  const t = T[lang];
  const load = () => fetch(`${API_URL}/label/${SET}`).then((r) => r.json()).then(setSet).catch(() => setSet(null));
  useEffect(() => { load(); }, []);
  if (!set) return <main className="mx-auto max-w-6xl px-4 py-6 text-zinc-400">{t.loading}</main>;
  const saved = set.clips.filter((c) => c.saved).length;
  return (
    <main className="mx-auto max-w-6xl space-y-4 px-4 py-6 lg:px-8">
      <div className="flex items-center justify-between"><Link href="/" className="text-sm text-sky-300 underline">{t.back}</Link>
        <button className="rounded bg-zinc-800 px-2 py-1 text-xs" onClick={() => setLang(lang === "en" ? "es" : "en")} data-testid="lang">{t.lang}</button></div>
      <h1 className="text-2xl font-bold tracking-tight">{t.title}</h1>
      <p className="max-w-3xl text-sm text-zinc-400">{t.intro} {saved}/{set.clips.length} {t.count}{set.frozen ? ` · ${t.frozen}` : ""}.</p>
      {set.clips.map((c) => <ClipReview key={c.draft.clip} c={c} set={set} onSaved={load} t={t} />)}
    </main>
  );
}
