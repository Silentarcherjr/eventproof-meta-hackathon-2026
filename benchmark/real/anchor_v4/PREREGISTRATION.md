# Compiler with an anchor field: re-run every frozen real-footage set (pre-registered BEFORE any model call)

Date: 2026-11-04.

**Change under test.** The Santos field test showed that the rule compiler's schema had no field for where each object
is measured (`benchmark/real/santos/FINDINGS.md`), so every compiled rule used the box centre. Schemas 4/5
(`rule-schema/4-anchor`, `/5-with-anchor`, commit below) add a required `anchor` field (`center` | `bottom_center`). A
note in the prompt says what each point means. Nothing else changes: same events, same engine, same rule texts, same
layouts, same labels and the same matching. Recorded compiles under schemas 2/3 stay as they are.

**Sets** (labels frozen earlier, manifests unchanged): `novisad` (2 clips, 8 cars), `traffic_v2` (2, 16), `traffic_v3`
(1, 6), `domains` (3, 8), `santos` (2, 8, v1 rule text). That is 10 clips and 46 labelled objects. With the old compiler,
these sets judged **34/46** right, with 1 wrong verdict (`santos` 0/8).

**Procedure:**
- For each set: `real_video run --anchor-schema --labels <set>/labels` with outputs in `benchmark/real/anchor_v4/`.
- At most 1 live Muse compile per clip (10 in total).
- SAM tracks come from the cache when Muse names the same concept. At most 10 new SAM calls in total.

**Primary outcome:** labelled objects right, new vs old, per set and pooled; wrong verdicts; abstentions; objects never
judged.

**Secondary outcome:** the anchor chosen per clip, and whether the rule check (`engine/lint.py`) fires.

**Reporting:** reported as is, including any regression on sets that were right before. No re-run.
