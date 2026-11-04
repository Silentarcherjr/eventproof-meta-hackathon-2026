# Compiler with an anchor field, all frozen real sets re-run (findings)

Pre-registered in `PREREGISTRATION.md` (commit 9b87501) before any model call. The run used 6 live Muse Spark compiles
(clips that share a rule text and layout reuse one compile) and 0 new SAM calls: Muse named the same concept on every
clip. `tests/validation/test_anchor_v4.py` recomputes every verdict from the committed rules and tracks.

| set | labelled | old compiler right | new compiler right | anchor chosen |
|---|---|---|---|---|
| Novi Sad (drone view, stop line) | 8 | 8 | 8 | center |
| Wroclaw w1+w2 | 16 | 14 (2 abstained) | 14 (2 abstained) | bottom_center |
| Wroclaw w3 (footbridge view) | 6 | 5 (1 untracked) | 4 (1 untracked, **1 wrong**) | bottom_center |
| zebra + bike bridge | 8 | 7 (1 untracked) | 7 (1 untracked) | bottom_center |
| Santos (Brazil) | 8 | **0 (8 never judged)** | **5** (2 wrong, 1 untracked) | bottom_center |
| **pooled** | **46** | **34** right, 0 wrong, 2 abstained, 10 never judged | **38** right, **3 wrong**, 2 abstained, 3 never judged | |

**What the field changed:**
- Muse Spark now chooses where objects are measured.
  - On the drone view of Novi Sad it kept the box centre, and the results were unchanged.
  - Everywhere else it chose the bottom centre, where cars, people and bicycles touch the ground.
- The rule check (`engine/lint.py`) fires on none of the 10 clips. With the old compiler it fired on both Santos clips.
- Santos went from 0/8 to 5/8.

**What got worse:**
- **3 wrong verdicts**, where the old compiler had none.
- **Wroclaw w3, one car.** A silver car right behind another one crosses without stopping, labelled VIOLATION, and was
  judged PASS with the bottom point and VIOLATION with the centre. The cause is not diagnosed yet.
- **Santos toward-camera clip, two riders.** Two riders cross 1.4 s apart in opposite directions. The tracks' verdicts
  (one PASS, one VIOLATION) are exactly those of the opposite pairing. Either the hand-labelled crossing order is
  reversed, or crossing-order matching swaps them; the pre-registration named this risk. The labels and the matching
  were not changed.

**Reading.**
- The field makes the rule judge what it used to miss: never-judged objects went from 10 to 3.
- It trades zero wrong verdicts for three. For a ticketing camera that trade is not free.
- That is why the certificate checks each rule against labelled footage of its own scene, instead of trusting a
  compiler version.
- The studio now compiles new rules with this schema. Recorded runs keep the rules they were judged with.


## Erratum, 2026-11-04: label audit (`benchmark/real/santos/label_audit.json`)

The two Santos "wrong" verdicts come from our labels, not from the engine. The crossing times labelled for the first two
riders of the toward-camera clip are in the wrong order, so the matching swapped them. The tracks show both verdicts were
right. After the audit the new compiler judges **40/46 right with 1 wrong** (the Wroclaw w3 car); pre-registered, it was
38/46 with 3 wrong. Santos goes from 5/8 to 7/8.
