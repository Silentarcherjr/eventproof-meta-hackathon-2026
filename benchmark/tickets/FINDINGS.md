# Would these tickets hold up? Findings

Pre-registered in `PREREGISTRATION.md` (commit 243dfa6). Part 1 (robustness) was explored on these same objects before
the tier split, as disclosed there. Part 2 made 20 live Muse Spark calls. `report.json` recomputes from the cache with
0 calls (`tests/validation/test_ticket_study.py`).

**Robustness of the 43 tracked labelled verdicts (no model):**

| status | right | wrong | abstained |
|---|---|---|---|
| ROBUST, nothing in the menu flips it | 23 | **1** | |
| FRAGILE, a measurement detail flips it | 2 | **2** | |
| DEPENDS_ON_THRESHOLD, the unwritten "stopped" speed or time flips it | 11 | | |
| DEPENDS_ON_MEANING, "any motion counts as stopping" flips it | 2 | | |
| UNSTABLE, it only becomes undecidable | | | 2 |

- 2 of the 3 wrong verdicts are flagged as not robust, and both are the measured-point cases.
- The third is a ROBUST wrong verdict: one of the two Santos riders swapped by crossing-order matching. It is a label or
  matching problem that no rule-side doubt can catch.

**The 20 real tickets (VIOLATION verdicts):**
- **Only 4 survive every challenge.**
- 11 depend on the speed that counts as "stopped" (0.05 frame widths/s, a number no statute writes).
- 2 depend on what "stop" means.
- 3 fall to the measured point.

**Muse Spark as the defense:**
- **It found an overturning argument for 8 of the 16 beatable tickets.** Its strongest pick overturned 7 of them.
- **It conceded 3 of the 4 tickets nothing can overturn.**
- **It conceded the one wrongly issued ticket**, a Santos rider ticketed although she rode the allowed way. The
  deterministic menu overturns that ticket by measuring the rider at the box centre.
- So the model argues well but misses the case that mattered most. The engine's full sweep, not the model, is what
  protects that resident.
- Muse picks only from the closed menu: no choice outside it was returned, and every win is decided by the engine.

**Limits:**
- There are 43 tracked objects and 20 tickets.
- The menu is fixed and finite: "holds up" means against these changes, not every possible objection.
- The defense sees text evidence (events and frames), not the video.
