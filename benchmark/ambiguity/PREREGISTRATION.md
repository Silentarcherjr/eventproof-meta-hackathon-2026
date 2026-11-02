# Ambiguity finder: Muse Spark vs. Muse Wonder on the same sentences (pre-registered BEFORE the calls)

Date: 2026-11-02. Within the participant's approved budget. Code: `backend/eventproof/ambiguity.py` (texts, layout,
models, suite and procedure are constants in that file at the commit that adds this note).
One smoke call (Muse Wonder, on the demo rule text with "blue box") only checked that Wonder accepts the strict schema;
it declined the rule because the DSL has no colour filter. That text is not in the set below.

## Question
Do two Meta models read the same plain-English rule the same way? Where they do not, can EventProof show the user one
concrete, minimal pair of scenes that separates the two readings, so the user decides instead of the model?

## Set (fixed now)
8 phrasings of "a box must spend 1.5 s at inspection before packing" (stay, stop, wait, pause, spend, be held,
be inspected, remain), the conveyor layout of the demo run, compiled by `muse-spark-1.3` (A) and `muse-wonder-1.0` (B)
with the product's compiler (strict JSON schema, up to 2 attempts). Up to 32 live calls.

## Procedure and metrics
- Per text: did each model compile or decline; are the two rules identical (rule hash); each model's stated assumptions.
- Where they differ: both rules on the 150-scene development suite (5 families × seeds 0–29, the seeds Challenge Mode
  already uses; never holdout or final seeds), on ground-truth tracks, so differences are interpretation only. Reported:
  scenes where the verdicts differ, by family; each reading's agreement with the process truth (stood still ≥ 1.0 s).
- For each family with a difference: a minimal pair by bisecting that family's knob (belt speed, stop length, object
  separation, occluder length) from a disagreeing scene to the nearest agreeing one.
- Summary: texts compiled by both, identical, behaving differently, with a minimal pair. All reported; nothing tuned.
Raw compiler outputs (and declines) are cached and committed; the report never overwrites.

## Addendum 2026-11-02 (written after the main report, before this call): the real traffic clips
Muse Wonder compiles the Novi Sad rule text with the Novi Sad layout (1 call, up to 2 attempts; frozen labels and SAM 3.1
tracks from `benchmark/real/novisad/` unchanged). Both readings (Muse Spark's recorded rule, Wonder's) are evaluated on
the committed tracks of both clips; reported: each reading's per-object verdicts vs. the labels and the objects where the
two readings differ. Nothing else is run; the result is reported whatever it is.
