# Two Meta models, one sentence: where Muse Spark and Muse Wonder read a rule differently

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md) (19bfe76, pushed before the calls). Data:
[`report.json`](report.json); raw compiler outputs and declines in [`cache/`](cache/). CI recomputes the report from the
cache with 0 calls (`backend/tests/test_ambiguity.py`). 8 phrasings × 2 models, conveyor layout of the demo run;
differences measured on the 150-scene development suite with ground-truth tracks (interpretation only, no perception).

## Result
| phrasing ("… at least 1.5 s in the inspection zone before packing") | Muse Spark 1.3 | Muse Wonder 1.0 | verdicts differ on |
|---|---|---|---|
| stay | present (any motion) | present | 0 / 150 |
| stop | standing still | standing still | 0 / 150 |
| **wait** | **standing still** | **present** | **45 / 150** |
| pause | standing still | standing still | 0 / 150 |
| spend | present | present | 0 / 150 |
| be held | standing still | did not compile (malformed output) | – |
| be inspected | present | declined (schema limitation it stated) | – |
| **remain** | **standing still** | **present** | **45 / 150** |

"Standing still" = DWELL with `max_speed 0.05`; "present" = DWELL with no speed condition. Where both compiled (6
phrasings) the two models agreed on 4 and disagreed on 2. Rule hashes differ for all 6 (ids, explanations), so EventProof
compares behaviour, not text.

## The question EventProof asks the user (minimal pairs found automatically)
For "wait" and "remain", in the 45 scenes where the readings differ (drive-through 11, brief stop 15, occlusion 12,
canonical 7), the finder bisects one knob to the boundary:
- **Belt speed 0.11777 vs. 0.11797** (drive-through, seed 0): on one side Spark's reading says FAIL and Wonder's PASS; a
  hair faster both say FAIL. The box never stops: *"does 'wait' mean standing still, or just being there?"*
- **Stop length knob 0.24434 vs. 0.24453** (brief stop, seed 5): the same question at the edge of a short stop.
The user's answer picks the rule; no model decides it silently.

## Notes
- Agreement with the synthetic process truth (stood still ≥ 1.0 s) is in the report (119 vs 136 of 150 for the two
  readings). It is not the target here: the 1.5 s in the text and the 1.0 s process truth differ on purpose, and which
  reading is "right" is the user's call.
- Spark's readings are consistent with the rest of this repository: "stay" → present (the demo run), "wait" → standing
  still (the Novi Sad traffic run).
- Cost: 23 live calls. Cached usage is about $1.41 (Spark $0.11, Wonder $1.31). One Wonder call that ran away (≈ 388k
  characters of output, not valid JSON) is not in the cache; its cost is estimated at ≈ $2 (UNKNOWN until Billing is read).

## Addendum: the real traffic clips (pre-registered before the call)
Muse Wonder compiled the Novi Sad rule ("Every car must wait at least 1.5 seconds in the waiting zone before it crosses the
stop line"; 2 calls, request ids in [`addendum_novisad.json`](addendum_novisad.json)) and, unlike for boxes, read "wait"
as **standing still** (`max_speed 0.05`), the same as Muse Spark. On the committed SAM 3.1 tracks both readings give
identical verdicts on every object (8/8 labelled right for both, rolling van included). So the same verb is read
differently depending on the scene ("box waits at inspection" vs. "car waits at a stop line"): one more reason to check the
reading for each deployment instead of assuming it.
