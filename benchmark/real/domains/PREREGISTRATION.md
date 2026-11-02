# New domains on real footage: one-way rules for pedestrians and cyclists (pre-registered BEFORE any model call)

Date: 2026-11-02. 109 Pexels clips in 9 categories were screened (camera fixed? both outcomes present? objects large
enough?); 7 were usable. Two are used here because their rules fit the label format (objects that cross a line, each
with an intended verdict); the others needed rules about objects that never cross (e.g. a bus staying too long) or had
ambiguous truth (store entrance), and are not used.

| clip | source | rule | labelled |
|---|---|---|---|
| `crosswalk_oneway.mp4` | Pexels 37247586, top view of a zebra crossing, 13.7 s | "Everyone must cross the middle of the zebra crossing only from left to right." | 6: 2 walk right→left (VIOLATION), 2 cyclists + 1 woman left→right (PASS), 1 person who never crosses (PASS) |
| `bike_oneway_a.mp4` / `_b.mp4` | Pexels 15928375, bike lane on a bridge, t 0–19 s / 8.5–27.5 s | "Cyclists may ride past the midpoint of the bike lane only from left to right." | a: 1 cyclist left→right (PASS); b: 1 cyclist right→left (VIOLATION) |

Hashes in `labels/*.json`, frozen in `labels/MANIFEST.json`. Procedure: `real_video run` (Muse Spark compiles each rule
text once, SAM 3.1 tracks each clip once; ≤ 2 Muse + 3 SAM calls). The "after" column applies the warehouse repair
r3-0, which only touches DWELL; for rules without DWELL it is reported as not applicable. Reported as is.
