import type { Layout } from "@/lib/types";

// Early recorded runs kept the form's default ids ("inspection", "packing_entry") on street footage. The evidence is
// hashed, so the ids stay; the studio only shows a readable name taken from each zone's or line's own description.
const DEFAULTS = new Set(["inspection", "packing_entry"]);
const NAMES: [RegExp, string][] = [
  [/waiting zone/i, "waiting_zone"], [/^stop line/i, "stop_line"], [/zebra crossing seen/i, "zebra_crossing"],
  [/middle of the zebra/i, "crossing_middle"], [/^the bike lane/i, "bike_lane"], [/midpoint of the bridge/i, "bridge_midpoint"],
  [/^the bike path/i, "bike_path"], [/across the bike path/i, "path_line"],
];

export function aliases(layout: Layout): Record<string, string> {
  const out: Record<string, string> = {};
  for (const { id, description } of [...layout.zones.map((z) => ({ id: z.zone.id, description: z.description })),
                                     ...layout.lines.map((l) => ({ id: l.line.id, description: l.description }))]) {
    if (!DEFAULTS.has(id) || /inspection|packing/i.test(description)) continue;
    const hit = NAMES.find(([re]) => re.test(description));
    if (hit) out[id] = hit[1];
  }
  return out;
}

export const relabel = (text: string, names: Record<string, string>) =>
  Object.entries(names).reduce((t, [id, name]) => t.replaceAll(id, name), text);

// The same readable names for a recorded case known only by its clip file (Ticket court).
const BY_CLIP: [RegExp, Record<string, string>][] = [
  [/^(novisad|wroclaw)/, { inspection: "waiting_zone", packing_entry: "stop_line" }],
  [/^crosswalk/, { inspection: "zebra_crossing", packing_entry: "crossing_middle" }],
  [/^bike_oneway/, { inspection: "bike_lane", packing_entry: "bridge_midpoint" }],
  [/^santos/, { inspection: "bike_path", packing_entry: "path_line" }],
];

export const clipNames = (clip: string) => BY_CLIP.find(([re]) => re.test(clip))?.[1] ?? {};
