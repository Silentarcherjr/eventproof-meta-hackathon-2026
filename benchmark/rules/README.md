# Natural-language rules compiled by Muse Spark (live)

`nl_rules_v1.json` → `uv run python -m eventproof.meta.muse_rules ../benchmark/rules/nl_rules_v1.json --out ...`
Model `muse-spark-1.3`, structured output (`strict: true`), schema `rule-schema/2-nodes`. Geometry comes from the layout; Muse only picks operators, ids and thresholds.

| Rule | Result | AST (summary) |
|---|---|---|
| R1 "stay at least 1.5 s in inspection before packing" | compiled, 1 attempt | IMPLIES(OCCURS(CROSSES), BEFORE(DWELL 1500 ms, CROSSES)) — identical to the hand-written canonical rule (direction `to_left` = rightwards, chosen from the layout hint) |
| R2 "only into packing after it has **stopped** at inspection ≥ 1 s" | compiled | same shape, DWELL 1000 ms **max_speed 0.05** (stillness) |
| R3 "never reach packing without passing through inspection" | compiled | BEFORE(IN_ZONE min_frames 1, CROSSES) |
| R4 "after 1 s in inspection, reach packing within 6 s" | compiled | IMPLIES(OCCURS(DWELL 1000), BEFORE(DWELL 1000, CROSSES, within 6000 ms)) |
| R5 "workers must wear a yellow helmet" | **unsupported** (model refused to guess) | — |

Dev outcomes (150 synthetic scenes, **mock perception, not SAM**) are measured against ONE process intent: "stood still ≥ 1 s at the
station before packing". They are meaningful for R1 and R2, which state that intent (R1: 14 spec errors; R2: 8). R3 and R4 state
different intents, so their "spec_error" counts only show they are not the inspection rule.

Cost note: a first schema version (3 nested `$defs` levels) cost 194,990 prompt tokens per call because refs are expanded;
the node-list schema costs ~1,420. Completion tokens are 2.1k–3.8k per rule, mostly reasoning.
