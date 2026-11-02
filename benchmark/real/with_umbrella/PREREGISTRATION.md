# Two-concept rule on real footage: umbrellas on a crossing (pre-registered BEFORE any model call)

Date: 2026-11-02. 99 Pexels clips were screened for two-object rules (hard hats, forklift proximity, cyclist and
motorcycle helmets, umbrellas, dogs near people). The camera had to be fixed and both outcomes had to be visible. One
clip passed: Pexels 39488108, a rainy zebra crossing filmed from a fixed high camera. Most hard-hat, forklift and
helmet clips pan with the subject or show only compliant people.

- **Clip:** `videos/umbrella_crossing.mp4` = source t 1.5–4.5 s, 10 fps, metadata stripped, sha256 in `labels.json`.
- **Rule text:** "Every pedestrian in the crossing zone must hold an umbrella over their head."
- **Zone:** the lower half of the crossing (y ≥ 0.55), given as the layout.
- **Labels (`labels.json`, sha256 `02df873a1d82e31ef556b7fdf99dceeed883cd1509298773f03e87c766b59865`):**
  4 people whose feet enter the zone. Two have no umbrella (VIOLATION) and two do (PASS), so the expected overall
  verdict is FAIL. Each person has a feet point at t = 2.9 s.
- **Procedure:** `python -m eventproof.validation.with_pilot run --max-muse 2 --max-sam 2`.
  - Muse Spark compiles the text. It is expected to refuse the base schema and escalate to the WITH schema, so up to
    2 calls.
  - SAM 3.1 tracks the entity concept and the context concept, so 2 requests.
  - Labelled people are matched to entity tracks by feet position (≤ 0.12 of the frame, ±0.3 s, one-to-one).
- **Reported as is:** right / wrong / abstained / not tracked per person, and the overall verdict. No re-run or
  re-labelling after seeing the output.

## Engine change made before the run (disclosed)

While labelling, the first frames showed that from a high camera an umbrella sits up and to the side of the walker. Its
centre falls above the person's box, outside the old `on_top` test (centre inside the head band). `on_top` now means
"the other box overlaps the head band": from 15 % of the box height above the top to 35 % into the box. The band
itself is unchanged.

This was decided from the footage alone, before any Muse or SAM output for it existed. The existing WITH tests still
pass, and a top-down umbrella test was added. It is still a change informed by the evaluation clip, so treat this
pilot as one demonstration on 4 people, not as a measured accuracy.
