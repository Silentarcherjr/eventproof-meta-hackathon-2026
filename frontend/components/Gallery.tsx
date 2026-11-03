import type { DemoClip } from "@/lib/api";

const NAMES: Record<string, string> = {
  novisad_approach_a: "Stop line, drone view (Novi Sad)", novisad_approach_b: "Stop line, drone view (Novi Sad), clip 2",
  wroclaw_w1: "Queue at a light (Wroclaw)", wroclaw_w2: "Green light (Wroclaw)", wroclaw_w3: "Footbridge view (Wroclaw)",
  crosswalk_oneway: "Zebra crossing from above", bike_oneway_a: "Bike lane on a bridge", bike_oneway_b: "Bike lane, other direction",
  umbrella_crossing: "Rainy crossing: umbrellas", santos_away: "Bike path, Santos (Brazil)",
  santos_toward: "Bike path, Santos, other end", "tailgate-7": "Warehouse belt (synthetic)",
};

/** Real clips a visitor can open and write their own rule over (hosted mode). */
export default function Gallery({ clips, current }: { clips: DemoClip[]; current?: string }) {
  return (
    <section className="mb-4" data-testid="gallery">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-400">Real clips: open one, then write your own rule</h2>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {clips.map((c) => {
          const key = (c.clip ?? "").replace(/\.mp4$/, "");
          return (
            <a key={c.run_id} href={`/?run=${c.run_id}`} data-testid={`clip-${c.run_id}`}
               className={`rounded-lg bg-zinc-900 p-3 ring-1 hover:ring-zinc-500 ${c.run_id === current ? "ring-sky-500" : "ring-zinc-800"}`}>
              <span className="block text-sm font-medium text-zinc-100">{NAMES[key] ?? key}</span>
              <span className="mt-1 block text-xs leading-snug text-zinc-400">&ldquo;{c.rule}&rdquo;</span>
              {c.overall && <span className="mt-1 block text-xs text-zinc-500">recorded verdict: {c.overall}</span>}
            </a>
          );
        })}
      </div>
    </section>
  );
}
