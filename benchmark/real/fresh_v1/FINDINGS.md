# Fresh camera view: findings

Pre-registered in `PREREGISTRATION.md` (and addendum 1) before any model call. Footage: Pexels video 35172060, a static
top-down drone view never used before in this repository; two approaches x three windows = 6 clips.

## Pre-registered result (labels as frozen)

| | |
|---|---|
| Clips whose overall verdict matches the labels | **5/6** |
| Labelled objects judged right by the rule Muse Spark compiled (SAM 3.1 tracks, deterministic engine) | **7/10** (1 abstained, 2 not matched: the labelled crossing times were more than 1.0 s from the tracked crossing) |
| Wrong verdicts | 0 among matched objects |

## Label audit (side view; the pre-registered figures above are kept)

After the run, SAM 3.1 + the engine and Muse Wonder's blind proposals both showed crossings in `drone_south_1` that the
labels lacked. The participant re-watched the clip: **five** southbound cars cross the line without stopping; the labels
had one (`label_audit.json`). With the audit, the four added cars are all judged VIOLATION by the engine, correctly:
**11/14** labelled objects right.

## Muse as a labelling assistant

| | Muse Spark (shown to the reviewer) | Muse Wonder (never shown; blind) |
|---|---|---|
| Crossings proposed that match an audited crossing | 9 of 13 | 12 of 13 |
| Missed | 4 (all in `drone_south_1`) | 1 |
| Extra entries | 0 | 1 (a car already halfway across in the first frame) |

The reviewer accepted all of Spark's proposals unchanged, including the clip where it missed four of five cars. One model
proposing and one person confirming was not enough; a second, independent reading (Wonder) and the tracked evidence
(SAM 3.1 + engine) were. EventProof keeps a person as the source of truth and uses disagreement between independent
readings to say where that person should look again.

## Limits

Small: 6 clips, 10 labelled objects as frozen (14 audited). The intersection has traffic lights the camera cannot see;
labels judge the rule as written, not the law. Crossing times proposed by Muse are approximate, which broke time-based
matching for two cars.
