"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Layout, ObjectVerdict, Pt, TrackFrame, VideoInfo } from "@/lib/types";

export type Tool = "none" | "zone" | "line";

const VERDICT_COLOR: Record<string, string> = { PASS: "#22c55e", VIOLATION: "#ef4444", UNKNOWN: "#f59e0b" };

interface Props {
  src: string | null;
  layout: Layout;
  onLayoutChange?: (l: Layout) => void;
  tool: Tool;
  tracksByFrame?: Map<number, TrackFrame[]>;
  info?: VideoInfo;
  verdicts?: Map<number, ObjectVerdict>;
  onFrame?: (frame: number) => void;
  seekFrame?: number | null;
}

const clamp = (v: number) => Math.min(1, Math.max(0, v));

/** Video with an SVG overlay in normalized coordinates: layout (zones/lines, editable) + perceived tracks. */
export default function VideoStage({ src, layout, onLayoutChange, tool, tracksByFrame, info, verdicts, onFrame, seekFrame }: Props) {
  const video = useRef<HTMLVideoElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const [frame, setFrame] = useState(0);
  const [aspect, setAspect] = useState(16 / 9);
  const [drag, setDrag] = useState<{ start: Pt; end: Pt } | null>(null);

  // frame clock: index = floor(t * fps), the same convention the backend uses for timestamps
  useEffect(() => {
    const v = video.current;
    if (!v || !info) return;
    let handle = 0;
    const tick = () => {
      const f = Math.min(info.frame_count - 1, Math.floor(v.currentTime * info.fps + 1e-6));
      setFrame(f);
      onFrame?.(f);
      handle = requestAnimationFrame(tick);
    };
    handle = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(handle);
  }, [info, onFrame, src]);

  useEffect(() => {
    if (seekFrame == null || !video.current || !info) return;
    video.current.pause();
    video.current.currentTime = (seekFrame + 0.5) / info.fps;
  }, [seekFrame, info]);

  const toNorm = useCallback((e: React.PointerEvent): Pt => {
    const r = svg.current!.getBoundingClientRect();
    return [clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height)];
  }, []);

  const commit = (start: Pt, end: Pt) => {
    if (!onLayoutChange) return;
    const r = (n: number) => Math.round(n * 1000) / 1000;
    if (tool === "zone") {
      const [x1, x2] = [Math.min(start[0], end[0]), Math.max(start[0], end[0])].map(r);
      const [y1, y2] = [Math.min(start[1], end[1]), Math.max(start[1], end[1])].map(r);
      if (x2 - x1 < 0.01 || y2 - y1 < 0.01) return;
      const zones = [...layout.zones];
      zones[0] = { ...zones[0], zone: { ...zones[0].zone, polygon: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]] } };
      onLayoutChange({ ...layout, zones });
    } else if (tool === "line") {
      if (Math.hypot(end[0] - start[0], end[1] - start[1]) < 0.01) return;
      const lines = [...layout.lines];
      lines[0] = { ...lines[0], line: { ...lines[0].line, a: [r(start[0]), r(start[1])], b: [r(end[0]), r(end[1])] } };
      onLayoutChange({ ...layout, lines });
    }
  };

  const tracks = tracksByFrame?.get(frame) ?? [];
  const W = info?.width ?? 1, H = info?.height ?? 1;

  return (
    <div className="relative w-full overflow-hidden rounded-lg bg-black" style={{ aspectRatio: aspect }}>
      {src ? (
        <video ref={video} src={src} controls={tool === "none"} playsInline muted data-testid="video"
               className="absolute inset-0 h-full w-full"
               onLoadedMetadata={(e) => setAspect(e.currentTarget.videoWidth / e.currentTarget.videoHeight || 16 / 9)} />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-sm text-zinc-500">No video yet</div>
      )}
      <svg ref={svg} viewBox="0 0 1 1" preserveAspectRatio="none" data-testid="overlay"
           className={`absolute inset-0 h-full w-full ${tool === "none" ? "pointer-events-none" : "cursor-crosshair"}`}
           onPointerDown={(e) => { if (tool !== "none") { const p = toNorm(e); setDrag({ start: p, end: p }); e.currentTarget.setPointerCapture(e.pointerId); } }}
           onPointerMove={(e) => drag && setDrag({ ...drag, end: toNorm(e) })}
           onPointerUp={() => { if (drag) commit(drag.start, drag.end); setDrag(null); }}>
        {layout.zones.map(({ zone }) => (
          <g key={zone.id}>
            <polygon points={zone.polygon.map((p) => p.join(",")).join(" ")} fill="rgba(250,204,21,0.15)"
                     stroke="#facc15" strokeWidth={0.004} vectorEffect="non-scaling-stroke" />
            <text x={zone.polygon[0][0] + 0.005} y={zone.polygon[0][1] + 0.04} fontSize={0.035} fill="#facc15">{zone.id}</text>
          </g>
        ))}
        {layout.lines.map(({ line }) => (
          <g key={line.id}>
            <line x1={line.a[0]} y1={line.a[1]} x2={line.b[0]} y2={line.b[1]} stroke="#38bdf8" strokeWidth={3}
                  vectorEffect="non-scaling-stroke" strokeDasharray="6 4" />
            <text x={line.a[0] + 0.008} y={line.a[1] + 0.04} fontSize={0.035} fill="#38bdf8">{line.id}</text>
          </g>
        ))}
        {drag && tool === "zone" && (
          <rect x={Math.min(drag.start[0], drag.end[0])} y={Math.min(drag.start[1], drag.end[1])}
                width={Math.abs(drag.end[0] - drag.start[0])} height={Math.abs(drag.end[1] - drag.start[1])}
                fill="none" stroke="#fff" strokeWidth={2} vectorEffect="non-scaling-stroke" />
        )}
        {drag && tool === "line" && (
          <line x1={drag.start[0]} y1={drag.start[1]} x2={drag.end[0]} y2={drag.end[1]} stroke="#fff" strokeWidth={2}
                vectorEffect="non-scaling-stroke" />
        )}
        {tracks.map((t) => {
          const c = VERDICT_COLOR[verdicts?.get(t.object_id)?.verdict ?? "UNKNOWN"];
          return (
            <g key={t.object_id} data-testid={`track-box-${t.object_id}`}>
              <rect x={t.box.x1 / W} y={t.box.y1 / H} width={(t.box.x2 - t.box.x1) / W} height={(t.box.y2 - t.box.y1) / H}
                    fill="none" stroke={c} strokeWidth={2.5} vectorEffect="non-scaling-stroke" />
              {/* odd ids label below the box so labels of overlapping objects stay readable */}
              <text x={t.box.x1 / W} y={t.object_id % 2 ? t.box.y2 / H + 0.04 : t.box.y1 / H - 0.01} fontSize={0.035} fill={c}>
                #{t.object_id}{t.confidence != null ? ` ${(t.confidence * 100).toFixed(0)}%` : ""}
              </text>
            </g>
          );
        })}
      </svg>
      {info && <div className="pointer-events-none absolute right-2 top-2 rounded bg-black/60 px-2 py-0.5 font-mono text-xs text-zinc-200"
                    data-testid="frame-counter">f{frame} · {(frame / info.fps).toFixed(2)}s</div>}
    </div>
  );
}
