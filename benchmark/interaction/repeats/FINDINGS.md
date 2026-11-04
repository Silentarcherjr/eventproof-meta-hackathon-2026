# Same statute, compiled 40 times: the silent numbers are stable, and that is the problem

Pre-registered in [`../REPEATS_PREREGISTRATION.md`](../REPEATS_PREREGISTRATION.md) (commit 9cc0a6b, pushed before any
call). 40 runs, each a fresh call: Muse Spark 1.3 and Muse Wonder 1.0, 10 each, on the verbatim California
(Veh. Code § 22450(a)) and Maryland (Transp. § 21-707(a)) stop statutes, same layout as the main study (it states the
frame is 100 m wide and the zone is the last 10 m before the line). 61 live calls in all (cap 160). Every rule judged on
the same 1,268 real STOP approaches with its own compiled values. Recomputed with zero calls by
`backend/tests/validation/test_interaction_repeats.py`.

## Result

| Model x statute | Valid rules | Stop time chosen | "Still" speed chosen | Tickets of 1,268 |
|---|---:|---|---|---|
| Spark, California | 10/10 | 1.0 s (9 runs), 0.5 s (1) | 0.05 frame widths/s every time (= 5 m/s) | 10 (9 runs), 3 (1) |
| Spark, Maryland | 10/10 | 1.0 s (9 runs), 0.5 s (1) | 0.05 every time | 10 (9 runs), 3 (1) |
| Wonder, California | 3/10 | 1.0 s | 0.05 every time | 10 |
| Wonder, Maryland | 5/10 | 1.0 s | 0.05 every time | 10 |

- **Every one of the 28 valid rules wrote the same "still" speed, 0.05 frame widths/s,** although the layout said the
  frame is 100 m wide, so it means 5 m/s (18 km/h). The stop time moved only between 1.0 s and 0.5 s. Anchor: always
  the box centre. Structure: "a crossing requires a still dwell before it" (one Wonder rule dropped the outer
  IMPLIES; same verdicts).
- **Tickets: 3 to 10 of 1,268 (0.2 % to 0.8 %).** Only 7 approaches ever change verdict across the 28 rules.
- **Wonder failed 12 of 20 compiles** after its two attempts: 8 malformed rule graphs (unused or mis-wired nodes), 2 with
  a required field missing, one answer of about 390,000 characters that was not JSON, one provenance quote not found in
  the statute. Spark failed none. Recorded as outcomes, not retried.
- The main study's single compile (Spark, California: 1.0 s, 0.05) is the modal answer here.

## Reading

The model is not noisy; it is consistent. It has a default, and it applies it to statutes that contain no number. On
this population that default tickets under 1 % of approaches, while the preregistered grid of plausible values spans
9 % to 85 % ([main study](../FINDINGS.md)). For scale, not as a pre-registered test: the definition used by Minnesota
DOT's human coders (motionless for 10+ frames, about 0.7 s; MnDOT report 2020-17, Table 3.9) sits closest to the grid
cell 0.75 s at <= 0.1 m/s, where 838 of 1,268 approaches (66 %) are not full stops. So a stable model choice is still
an unapproved enforcement policy, and a very lenient one here: repeating the compile does not surface it, only putting
the numbers in front of a person does. This is the open choice EventProof's approval gate withholds until it is signed.

## Limits

No human violation labels: this measures stability and its consequence, not accuracy. Trajectories measured by the
INTERACTION authors (CC BY 4.0), not SAM; no video. "0.05 frame widths/s" is a unit the schema asks for; a schema in
metres might change the answer, which this study does not test. Failed compiles kept no response text when the
validator rejected them (only the error), so their token use is not recorded; billed dollars are read from the
Billing page, not estimated here. `code_commit` in `compiles.json` is the preregistration commit; the module
(`interaction_repeats.py`) was committed right after the run; only its import formatting changed after launch.
