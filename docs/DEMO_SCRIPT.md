# 3-minute demo — script and shot list (draft for the participant)

Rule for this video: **every number on screen is read from a committed file** (table at the end). Nothing is animated
from made-up data, nothing mock is called Meta, and recorded runs are said to be recorded.

Recording setup: local stack with no key (`MODEL_API_KEY= EVENTPROOF_MAX_LIVE_SAM_CALLS=0 uv run uvicorn …` + `npm run dev`,
or the showcase compose). Browser at 1920×1080, zoom 110 %, dark theme. Open
`http://localhost:3000/?run=20261028T023754Z-a922b5bb` — the run recorded on 2026-10-28 with live Muse Spark and SAM 3.1;
its outputs are replayed from cache (the evidence says `cached`, with the original request ids). Costs 0 credits.
Optional section 5b only if the participant has recorded and run real clips (`docs/REAL_VIDEO_PROTOCOL.md`).

| time | screen | narration (English, ~150 wpm) | on-screen text |
|---|---|---|---|
| 0:00–0:12 | Title card over the studio | "AI can now build a visual checker from one sentence. The question nobody asks: who checks the checker?" | **EventProof** — AI builds visual apps. Then tries to break them. |
| 0:12–0:40 | Studio: rule text, compiled rule, assumptions, video with tracks, timeline | "I describe a rule in plain English. Muse Spark turns it into a typed rule — never code — and writes down its assumptions. SAM 3.1 tracks every box. Box 1 tailgated into packing without inspection: FAIL, with the exact frames." | Muse Spark → typed DSL · SAM 3.1 → tracks · verdict FAIL (frame 88) |
| 0:40–0:52 | Zoom on the assumptions list | "Look at one assumption: Muse read 'stay 1.5 seconds' as *any* time inside the zone — moving or not. Is that what we meant?" | highlight: "any motion allowed … not requiring stopped" |
| 0:52–1:22 | Challenge Mode: suite table, counterexample card, side-by-side replay | "Challenge Mode attacks the rule with 150 synthetic scenes whose truth we know. 44 fail. The clearest one: a box that never stopped — zero seconds — but crawled through the zone in 1.8 seconds. The rule says PASS. It then finds the minimal pair: two clips that differ only in belt speed, one fools the rule, one doesn't." | 150 scenes · 44 failures · spec error · belt speed 0.1178 vs 0.1180 |
| 1:22–1:35 | Click "Confirm with SAM 3.1" result | "Is this just our simulator? Real SAM 3.1 tracks on the same scene: still PASS. The rule is wrong, not the perception." | SAM 3.1: still fails → specification error |
| 1:35–2:05 | Repair panel: round diagnoses, 8 proposals, accepted/rejected with reasons | "Muse Spark diagnoses it: 'stay' must mean standing still. It proposes bounded patches — no free-form code. An independent grader tests every proposal on 200 hidden cases Muse never saw. Its first idea was too strict: 26 regressions, rejected. Three rounds later, 2 of 8 proposals pass: zero regressions." | 8 proposals · 2 accepted · 6 rejected (reasons shown) |
| 2:05–2:30 | Before → after view: verdict cards, video + counter chart (scrub), holdout bars | "Same case, both rules. The old rule counted 1.53 seconds of *moving* time and passed it. The repaired rule counts only standing still: zero. FAIL — correct. On the hidden cases: 144 → 164 of 200 right, dangerous false passes 40 → 21, no regressions." | before 1.53 s ✗ · after 0.00 s ✓ · 144 → 164 / 200 |
| 2:30–2:48 | Final-test card (zoom) | "But the grader picked among proposals on those cases, so we froze a third test set *before* evaluating anything, with three kinds of scenes no rule was designed for. Evaluated once: 141 → 158 of 200, and 109 → 117 of 120 on the new kinds. Zero regressions." | pre-registered final test · 141 → 158 / 200 · 109 → 117 / 120 |
| 2:48–3:00 | Ledger / hashes footer, then closing card | "Every verdict comes with hashes, model request ids and a ledger anyone can verify. EventProof: build, break, repair — and prove it." | 221 tests · evidence ledger verified · github link (after approval) |

## 5b (optional, only with real results) — replaces 2:30–2:48 if the real-video report exists
"On clips I recorded with my phone, labelled blind before any model ran: X of N verdicts agree before the repair, Y after."
Numbers only from `benchmark/real/report_*.md`. If they are worse than synthetic, say so — that is the honest result.

## Visual direction
- One idea per shot; zoom into the element being talked about (the assumption line, the counter chart, the bars).
- The before/after chart is the hero shot: scrub the video so the playhead runs while the orange line climbs past
  "needs 1.50 s" and the blue line stays at 0.
- Orange = before, blue = after everywhere (validated color pair; ✓/✗ always next to the color).
- No stock footage, no fake UI, no numbers that are not on the screen of the real app.

## Claims → source (check before recording)
| claim | source |
|---|---|
| rule text, Muse assumptions, request id, verdict FAIL frame 88 | `docs/evidence/runs/20261028T023754Z-a922b5bb/evidence.json` |
| 150 scenes, 44 failures, drive_through spec error, 0 s still / 1.835 s transit, belt speed pair | `…/challenge/challenge.json`, round diagnoses in `…/challenge/repair_muse.json` |
| SAM 3.1 confirms (spec error with real tracks) | `…/challenge/sam_confirm.json` |
| 8 proposals, 2 accepted, first one 26 regressions, 144 → 164 / 166 | `…/challenge/repair_muse.json` |
| 1.53 s vs 0.00 s, false PASS 40 → 21 | studio before/after view (`before_after_muse.json`, computed by the evaluator) |
| 141 → 158 / 200, 109 → 117 / 120, 0 regressions, pre-registered | `benchmark/final/REPORT_final_v1.md`, `report_final_v1.json`, `PREREGISTRATION.md` |
| 221 tests | CI run on the commit used for recording (update the number if it changed) |
| ledger verified | `uv run python -m eventproof.ledger verify artifacts/runs/20261028T023754Z-a922b5bb` |

Limitations to keep honest in narration or captions: synthetic scenes; Challenge/holdout/final scoring uses a mock tracker
(SAM 3.1 confirms the counterexample); n is small; the baseline patch did slightly better than Muse's on one new family
(stop_and_go).
