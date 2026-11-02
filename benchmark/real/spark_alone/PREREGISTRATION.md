# Baseline: Muse Spark judging the rule straight from video (pre-registered BEFORE any call on these clips)

Date: 2026-11-02. Within the participant's approved budget. Code: `backend/eventproof/validation/spark_alone.py`.
A 1-call smoke test on the synthetic demo clip (not one of these clips) checked the request format only.

## Question
Does EventProof's pipeline (Muse Spark → typed rule; SAM 3.1 → tracks; deterministic engine) beat simply asking Muse
Spark to judge the rule from the video, on the same real clips, rule text, layout and frozen labels?

## Inputs (unchanged, frozen in 45bde5e)
`benchmark/real/novisad/labels/*.json` and the two prepared clips (sha256 in the labels). Rule text, zone/line
descriptions and coordinates are passed to Muse Spark exactly as EventProof receives them. The prompt asks for every car
that crosses the line, its crossing time, how long it *waited* in the zone (neutral wording, as in the rule), a per-car
PASS/VIOLATION and an overall verdict, as strict JSON (Responses API, `input_video`, `muse-spark-1.3`).

## Runs and metrics
5 independent calls per clip (10 calls). Reported per call and in total: overall verdict agrees with the label (Wilson 95 %
interval), crossings reported vs. labelled (a: 3, b: 1), violations reported vs. labelled (a: 2, b: 0), and the run-to-run
spread. Compared with EventProof's recorded result on the same clips (2/2 clip verdicts, 8/8 objects with Muse's rule).
Every response is cached raw and committed; the report never overwrites. The prompt is not changed after seeing output.
