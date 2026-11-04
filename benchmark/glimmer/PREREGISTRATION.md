# Muse Glimmer on a laptop: the same statutes, compiled with Meta's open weights (pre-registered)

Registered 2026-11-04 15:25 ET, before the model is started and before any compile below.

## Question

Can a city compile the statute on its own hardware, with no API, and what does the open model choose for the numbers
the law never wrote? Same compiler, prompts, schema and evaluation as the Muse Spark and Muse Wonder studies; only the
model changes.

## Model and hardware

`meta-models/Muse-Glimmer-30B-GGUF`, file `Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf` (Apache 2.0), served by
llama.cpp `llama-server` (build 11960) on the author's laptop (Apple M1 Max, 32 GB), OpenAI-compatible endpoint, the
schema enforced through `response_format` (`json_schema`) as for the Meta API. Server defaults for sampling; no
temperature is set. Model name recorded as `muse-glimmer-30b-q4km (local)`. No Meta API call in this study.

## Arms

1. **30 labelled real cars** (`law_study.py`, unchanged): the verbatim Maryland (Transp. § 21-707(a)) and California
   (Veh. Code § 22450(a)) statutes, compiled once per scene layout (Novi Sad, Wroclaw), law mode. Reported exactly as
   the Spark/Wonder rows in `benchmark/law/report.json`: compiled, right, wrong, verdicts that hang on an unwritten
   number, QUOTED vs ASSUMED.
2. **1,268 INTERACTION approaches** (`interaction_repeats.py`, unchanged): each statute compiled 3 times with the main
   study's layout; every valid rule judged with its own compiled values; the stop time and "still" speed it picks.

Every compile is recorded and committed; reports recompute from the recordings with zero model calls.

## Rules

- At most 2 attempts per compile (as for the API models). A failed compile is an outcome, reported.
- Time box: compiles still running at 17:00 ET are stopped and reported as not run. No rerun, no prompt or schema
  change after seeing any output.
- This measures the rule the open model writes, not perception (tracks are the committed SAM 3.1 tracks and the
  INTERACTION trajectories).
