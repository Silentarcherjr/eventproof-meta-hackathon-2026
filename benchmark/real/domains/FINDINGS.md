# New domains on real footage: one-way rules for pedestrians and cyclists

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md) (labels + manifest pushed before any call). Data:
[`report_domains.json`](report_domains.json) / [`.md`](report_domains.md), run evidence and SAM 3.1 tracks in
[`runs/`](runs/). Live calls: Muse Spark 2 (one compile per rule text), SAM 3.1 3.

| clip | rule (typed in plain English) | Muse Spark's rule | labelled objects right |
|---|---|---|---|
| zebra crossing, top view | "Everyone must cross the middle of the zebra crossing only from left to right." | NOT OCCURS(CROSSES to_right) — it mapped "left to right" through the line's own orientation and wrote that down | **5/6**: both people walking the wrong way → VIOLATION, both cyclists and the woman → PASS; the person who never crosses got no matching track (SAM gave one extra track that crosses at 10.1 s, judged PASS) |
| bike lane, clip a | "Cyclists may ride past the midpoint of the bike lane only from left to right." | same form | **1/1** PASS |
| bike lane, clip b | same | same | **1/1** VIOLATION (rides the wrong way) |

0 wrong verdicts. The same engine, compiler and tracker that check "stop before the line" for cars check a direction rule
for pedestrians and cyclists, with no code change: only the sentence and the drawn zone/line differ. n is tiny (8
objects); this shows breadth, not accuracy. The warehouse repair (a DWELL patch) does not apply to these rules and is
reported as not applicable.
