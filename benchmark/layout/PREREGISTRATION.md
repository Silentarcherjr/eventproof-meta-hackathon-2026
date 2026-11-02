# Layout proposed by Muse Spark vs. hand-drawn layout (pre-registered BEFORE the evaluation calls)

Date: 2026-11-02. Code: `backend/eventproof/meta/layout_proposer.py`, `backend/eventproof/validation/layout_eval.py`.
One smoke call (Novi Sad clip a, the same request the evaluation uses; response kept in `cache/` and counted) checked the
request format before this note. Its result was seen: zone IoU 0.47, line angle off by 35° (the real stop line is diagonal).

## Question
Can Muse Spark place the zone and the line from the first frame and the rule text well enough that the verdicts on labelled
real cars are the same as with the hand-drawn layout?

## Set (fixed): all 5 labelled real traffic clips (Novi Sad a/b, Wroclaw w1/w2/w3; 30 cars), frozen labels, committed
SAM 3.1 tracks and compiled rules. 1 proposal per clip (5 calls, one already made). No prompt change after seeing output.

## Metrics: per clip zone IoU and line angle / midpoint offset vs. the hand layout; labelled cars right with the hand
layout vs. with the proposed layout (same rule logic, same tracks), totals with Wilson 95 % intervals. All reported.
