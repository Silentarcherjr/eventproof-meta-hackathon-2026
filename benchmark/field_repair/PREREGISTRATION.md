# Field repair: repair from real failures, prove on another city and on the synthetic holdout (pre-registered)

Date: 2026-11-02. Code: `backend/eventproof/validation/field_repair.py` at the commit that adds this note.
Disclosed before running: while building the grader I dry-ran it on the first 3 grid patches (max_speed 0.03 with
min_ms 800 / 1000 / 1200). Seen: 0.03/800 accepted (real holdout 9 -> 19/22, synthetic 164 -> 166/200), the other two
rejected for synthetic regressions. No Muse Spark call has been made. Nothing below changes after seeing any output.

- Start rule R0 (per clip): Muse Spark's compiled rule + the repair accepted on synthetic data (r3-0, DWELL >= 0.8 s while
  speed <= 0.08/s). On the 5 real clips it gets 16/30; on the Wroclaw holdout 9/22.
- Dev (shown to proposers): Novi Sad a/b, 8 labelled cars, with the engine's measurements on the committed SAM tracks.
- Real holdout (never shown): Wroclaw w1/w2/w3, 22 labelled cars. Synthetic holdout: holdout_v2, 200 scenes, warehouse
  rule of the demo run + r3-0 (164/200 before).
- Acceptance (all): dev fully right; real holdout strictly better with 0 regressions; synthetic holdout 0 regressions and
  no new false PASS.
- Proposers: Muse Spark (2 calls: proposals, then one revision with dev-only feedback; ops limited to DWELL min_ms and
  max_speed) and a 16-patch grid (max_speed 0.03-0.06 × min_ms 0.8-1.5 s). Every proposal is graded and reported; the
  headline is Muse Spark's first accepted proposal in its own order, never the best holdout score.
