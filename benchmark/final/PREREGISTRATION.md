# final_v1 — pre-registration (written and committed BEFORE any evaluation on this set)

Date: 2026-10-28. Manifest `benchmark/final/final_v1.json`,
sha256 `3f955049b39526ade1129e5574fd3dfa33a0302349a0d5d9849d6110065cad28`, cases_sha256 `80ea6000761…` (in the file).
Generator code: `backend/eventproof/validation/final.py` at the commit that adds this file.

## Why a third data tier
`holdout_v2` is hidden from the proposers but the grader uses it to accept or reject proposals, so it takes part in
selection: a number measured on it after selection is optimistic. `final_v1` is never used to accept, reject, rank or
tune anything. It is evaluated only on decisions that are already recorded and hashed below.

## Data
- `in_distribution`: canonical, drive_through, brief_stop, occluded_station, tailgate at seeds 40000–40039 (200 scenes;
  these seeds were never generated before the freeze).
- `shift`: stop_and_go, two_stops, fps_shift at seeds 40000–40039 (120 scenes). These families exist only in the final
  module; no rule, threshold or repair was designed against them. Before freezing, only their process-truth class balance was
  inspected (no rule evaluated): stop_and_go 33 PASS / 7 FAIL, two_stops 40 FAIL (by design), fps_shift 9 PASS / 31 FAIL
  (23 at 10 fps, 17 at 24 fps).
- Process truth: unchanged (`challenge/truth.py`: crossing into packing requires a stop ≥ 1.0 s at the station).

## What will be evaluated (all of it, nothing selected)
1. Studio run `20261028T023754Z-a922b5bb` (rule compiled by Muse Spark): the unpatched rule and all 8 Muse Spark proposals in
   `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json` (sha256 `8031f8f4…8a10`; 2 accepted, 6 rejected).
2. Baseline proposer on the template rule (DWELL ≥ 1.5 s): the unpatched rule and every proposal in
   `benchmark/repairs/drive_through-0.json` (sha256 `d8e572ba…7378`) and `benchmark/repairs/brief_stop-5.json`
   (sha256 `792c5106…effd4`). occluded_station-1 and tailgate-0 have no proposals.

Perception: the deterministic mock tracker (primary, all 320 scenes). A live SAM 3.1 pass on a subset is optional and
needs the participant's budget approval; if run, it is reported separately and does not replace the primary result.

## Metrics and hypotheses
Per patch and split: correct / n with Wilson 95% interval; false PASS (detector PASS, truth FAIL); false alarm; abstained;
paired counts fixed vs. regressed against the unpatched rule, with a two-sided exact sign test on the discordant pairs.
- H1: every grader-ACCEPTED patch increases correct on `in_distribution` without increasing false PASS.
- H2: the same on `shift`.
- H3: the grader is informative: accepted patches gain more on final_v1 (both splits) than rejected ones.

## Reporting rules
All results are reported, including failures of H1–H3. The evaluation code may not branch on the final results. If a bug is
found after the first evaluation, the first report is kept, and the fix plus re-run is reported next to it.
`final_v1.json` is never regenerated in place; a new set gets a new name.
