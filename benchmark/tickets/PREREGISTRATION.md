# Would these tickets hold up? (pre-registered BEFORE any Muse call for it)

Date: 2026-11-04. Objects: the 46 labelled real objects of `benchmark/real/anchor_v4` (10 clips; compiled rules and
SAM 3.1 tracks committed).

**Part 1: robustness (deterministic, no model). Not blind: disclosed.** `review/robustness.py` re-judges every object
under a fixed, typed menu of variants, sorted by size:
- measurement: geometry moved ±1/2/3 % of the frame along the line normal; centre ↔ bottom point; every other frame
  dropped;
- threshold: DWELL time ±20 %; the "standing still" speed ×0.5 / ×2;
- meaning: "any motion counts" ↔ "only while still".

Each object is labelled FRAGILE (a measurement variant flips it), DEPENDS_ON_THRESHOLD, DEPENDS_ON_MEANING, ROBUST or
UNSTABLE (variants only make it undecidable). The tiers were set after one exploratory pass on these same 46 objects:
that pass showed the "any motion" variant flips every never-stopping car, so it was moved out of the measurement tier.
The exploratory counts were: ROBUST 23 right + 1 wrong; FRAGILE 13 right + 2 wrong (after the tier split); 2
abstained; 3 untracked. The final counts are reported, and the exploratory pass is part of this disclosure.

**Part 2: Muse Spark as the defense (pre-registered here, run after this commit).**
- For every ticket (a labelled object judged VIOLATION), `meta/muse_defense.py` sends Muse Spark the sentence, the rule
  it ran, the object's decisive events and the same variant menu as Part 1 (ids and plain labels; no robustness
  results).
- Muse picks up to 4 challenges and the strongest one, or concedes.
- The engine then says which of its challenges overturn the ticket.
- At most 1 live call per ticket (about 22), strict schema. Choices outside the menu are rejected.

**Outcomes, reported as they come:**
- tickets the menu can overturn (from Part 1);
- tickets where Muse's strongest or any chosen challenge overturns it;
- concessions on tickets nothing can overturn;
- whether the wrong tickets are overturned by the defense.
