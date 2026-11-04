# What counts as "stopped"? EventProof against independent human annotators (MEVA) — pre-registered BEFORE any model call

Date: 2026-11-04.

**Data.** MEVA, Multiview Extended Video with Activities (Kitware Inc. and IARPA), licensed under CC BY 4.0
(https://mevadata.org/). We use the official Kitware activity annotations for the ground cameras hospital.G436,
school.G336, school.G424, school.G328, school.G339 and bus.G340 (237 five-minute clips, from meva-data-repo,
`annotation/DIVA-phase-2/MEVA/kitware`):
- per-frame actor boxes (`*.geom.yml`);
- actor types (`*.types.yml`);
- `vehicle_stops` activity intervals (`*.activities.yml`).

We did not write these labels.

**Citation.** Corona et al., "MEVA: A Large-Scale Multiview, Multimodal Video Dataset for Activity Detection",
WACV 2021.

**Population.** Every vehicle actor, defined deterministically from the annotators' boxes alone, before any model call:
- its track lasts at least 1 s;
- the bottom centre of its box moves by at least 5 % of the frame width over the track (this excludes parked vehicles
  that never move).

**Truth.** The vehicle "stopped" if the annotators gave it at least one `vehicle_stops` activity; otherwise it did not
stop.

**What is judged.**
- Rule text: "Every vehicle must come to a complete stop."
- Layout: one zone covering the whole camera view.
- Muse Spark (law-mode schema with provenance and anchor) compiles it once. Muse Wonder compiles it once more as a
  second reading.
- At most 4 live calls, including retries.
- The compiled rule is judged by the unchanged engine on the annotators' own boxes. No SAM call is made in this part,
  so perception is held fixed and only the rule is measured.
- A VIOLATION verdict means "never stopped", and PASS means "stopped".

**Outcomes, reported as they come:**
- agreement with the annotators, with Wilson 95 % intervals;
- false "stopped" verdicts and missed stops, per camera and in total;
- the same counts over the pre-registered grid of `benchmark/law` (stop time 0–3 s in 0.25 s steps × "still" speed
  0.01–0.20 in 0.01 steps, plus any motion), with the region that best matches the humans.

No threshold is tuned on this data before reporting.

**Disclosed before the run:**
- The population size and the base rate of stoppers are computed beforehand (no model involved): 5,041 vehicle actors
  and 731 annotated as stopping, before the "moves" filter.
- The camera speed unit (frame widths/s) ignores perspective.
