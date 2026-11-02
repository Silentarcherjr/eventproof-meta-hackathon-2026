# final_v1 — live SAM 3.1 pass (pre-registered BEFORE any SAM call on these scenes)

Date: 2026-11-01. Budget approved by the participant: up to $5 of Meta credits.
Code: `backend/eventproof/validation/sam_pass.py` at the commit that adds this file. Primary result stays
`report_final_v1.json` (mock tracker, all 320 scenes); this pass is reported separately, as stated in `PREREGISTRATION.md`.

## Subset (fixed by seed index, not by any result)
Seeds 40000–40009 of all 8 final_v1 families: 50 `in_distribution` + 30 `shift` scenes = 80 scenes, 8,087 frames.
The mock-tracker results on these seeds are already public (report_final_v1); the subset is the first ten seeds of
every family, so it cannot be chosen to favour any outcome.

## Procedure
1. Each scene is rendered to MP4 (bit-identical renderer) and sent to `sam-3.1` once, prompt = the object concept
   (`box`). Ground truth is never sent. Raw SAM output is committed under `benchmark/final/sam_v1/sam_cache/`.
2. Live calls are capped by `--max-live-sam-calls 80`. Cost bound: all 26 earlier live calls (13 SAM ≈ 1,400 frames
   + 13 Muse) cost $0.74 in total, so SAM costs at most ≈ $0.00053/frame → ≤ $4.3 for 8,087 frames.
3. A scene whose SAM call fails or whose output does not parse is listed and excluded from both the SAM and the mock
   numbers below (it is not retried with a different prompt).
4. The report is computed from the cache with 0 live calls and is never overwritten.

## What is reported (all of it)
- Perception agreement on the unpatched Muse-run rule: per scene truth / mock verdict / SAM verdict, SAM identity
  errors against ground truth (merged, lost, new id, switch).
- The same evaluation as `PREREGISTRATION.md` (unpatched rules + all 8 Muse proposals + all baseline proposals),
  per split, with SAM tracks, and side by side with the mock tracker on exactly the same scenes.
- Questions (no thresholds tuned on the answers): S1 do the grader-accepted Muse patches still improve correct and
  not increase false PASS with SAM tracks? S2 how often do mock and SAM verdicts disagree, and in which families?
