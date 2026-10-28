"use client";

import type { ObjectVerdict } from "@/lib/types";

const BAR: Record<string, string> = { PASS: "bg-green-500/40", VIOLATION: "bg-red-500/50", UNKNOWN: "bg-amber-500/40" };
const MARK: Record<string, string> = { TRUE: "bg-white", FALSE: "bg-zinc-500", UNKNOWN: "bg-amber-400" };

/** One row per tracked object: lifetime bar, event markers (click to seek), shared playhead. */
export default function Timeline({ objects, frameCount, fps, frame, onSeek }: {
  objects: ObjectVerdict[]; frameCount: number; fps: number; frame: number; onSeek: (f: number) => void;
}) {
  const pct = (f: number) => `${(100 * f) / Math.max(1, frameCount - 1)}%`;
  return (
    <div className="space-y-2" data-testid="timeline">
      {objects.map((o) => (
        <div key={o.object_id} className="flex items-center gap-3">
          <div className="w-24 shrink-0 font-mono text-xs text-zinc-300">#{o.object_id} {o.verdict}</div>
          <div className="relative h-6 flex-1 cursor-pointer rounded bg-zinc-800"
               onClick={(e) => {
                 const r = e.currentTarget.getBoundingClientRect();
                 onSeek(Math.round(((e.clientX - r.left) / r.width) * (frameCount - 1)));
               }}>
            <div className={`absolute inset-y-1 rounded ${BAR[o.verdict]}`}
                 style={{ left: pct(o.first_frame), width: `calc(${pct(o.last_frame)} - ${pct(o.first_frame)})` }} />
            {o.events.filter((e) => e.frame != null).map((e) => (
              <button key={`${e.op}-${e.target}`} title={`${e.op} ${e.target}: ${e.reason}`}
                      className={`absolute top-0 h-6 w-1.5 -translate-x-1/2 rounded ${MARK[e.status]}`}
                      style={{ left: pct(e.frame!) }}
                      onClick={(ev) => { ev.stopPropagation(); onSeek(e.frame!); }} />
            ))}
            <div className="pointer-events-none absolute inset-y-0 w-px bg-sky-400" style={{ left: pct(frame) }} />
          </div>
        </div>
      ))}
      <div className="flex justify-between pl-27 font-mono text-[10px] text-zinc-500">
        <span>0 s</span><span>{((frameCount - 1) / fps).toFixed(1)} s</span>
      </div>
    </div>
  );
}
