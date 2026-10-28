import type { Layout } from "./types";

// Matches the synthetic conveyor scenes (backend/eventproof/challenge/scene.py) so a rendered clip works as is.
export const DEFAULT_LAYOUT: Layout = {
  zones: [{ zone: { id: "inspection", polygon: [[0.3, 0.1], [0.5, 0.1], [0.5, 0.9], [0.3, 0.9]] },
            description: "inspection station on the conveyor" }],
  lines: [{ line: { id: "packing_entry", a: [0.75, 0.05], b: [0.75, 0.95] },
            description: "entry of the packing area; boxes travel left to right" }],
};

export const EXAMPLE_RULES = [
  "Every blue box must stay at least 1.5 seconds in the inspection zone before it crosses into packing.",
  "A blue box may only go into packing after it has stopped at the inspection station for at least one second.",
  "No blue box should ever reach packing without passing through inspection first.",
];
