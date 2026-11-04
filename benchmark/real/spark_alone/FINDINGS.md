# Muse Spark alone vs. EventProof on the same real clips

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md) (62822d3, pushed before the calls). Data:
[`report.json`](report.json), raw responses in [`cache/`](cache/) (10 live `muse-spark-1.3` calls, 26.7k input /
42.6k output tokens, about $0.21). CI recomputes every metric from the committed answers (`test_spark_alone.py`).
Clips, rule text, layout and labels are exactly those of [`../novisad/`](../novisad/FINDINGS.md); n is small (2 clips).

## Pre-registered metrics
| | Muse Spark alone (5 runs per clip) | EventProof (Muse rule → SAM 3.1 → engine) |
|---|---|---|
| overall clip verdict agrees with the label | **10/10** runs (Wilson 95 % 0.72–1.00) | 2/2 clips |
| crossings and violations both counted right | **5/10** runs: clip b 5/5, **clip a (the rolling van) 0/5** | both clips; 8/8 labelled objects |
| run-to-run spread on clip a | 3 or 4 crossings reported (truth 3), 1 or 3 violations (truth 2) | deterministic given the tracks |

## What the answers show (read after the run; not a pre-registered metric)
- The obvious case is easy: every run flags the red car that drives straight through, so the overall FAIL is always right.
- The rolling van (crosses at ~17.4 s, never stands still) is called a VIOLATION in **1 of 5** runs; the other runs call it
  PASS ("waited 6.0 s"), confuse it with a queued car, or omit it.
- In **3 of 5** runs Muse Spark reports cars that wait in the other lane for the whole clip as crossing ("white car
  waiting in middle lane … 15.0 s, PASS"): crossings that never happen.
- With no typed rule there is no stated interpretation to inspect, no per-frame evidence, and a different answer per run.

## Takeaway
Asking a strong multimodal model directly gets the headline verdict right here but not the per-object facts that a QA or
safety reviewer needs; EventProof's split (model proposes the rule, SAM 3.1 measures, code decides) produced the right
per-object verdicts on these clips, with evidence. Two clips are not a benchmark: this is a concrete, reproducible
illustration, not an accuracy claim.
