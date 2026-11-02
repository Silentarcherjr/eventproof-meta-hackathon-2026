# 3-minute demo — script (v3, 2026-11-02)

Every number on screen and in the narration is read from a committed file (table at the end). Recorded runs are
replayed from their cache and say so; nothing mock is called Meta. The video is produced by `demo/video/build.sh`
(screen capture of the real studio with Playwright, narration with a synthetic voice, cards rendered from HTML).

| # | screen | narration |
|---|---|---|
| 1 | Title card | AI can now build a video checker from one sentence. EventProof is AI-generated vision software that doesn't just claim to work: it searches for evidence that it might be wrong. |
| 2 | "Why now" card (Takoma Park, Virginia, IEEE Spectrum quote) | Cities have started writing stop-sign tickets from AI cameras. Takoma Park, Maryland, fines drivers forty dollars per citation. But what counts as a full stop is a rule someone wrote, and experts say these systems are rarely validated independently. |
| 3 | Studio, Novi Sad run: video with tracks, rule, Muse's assumptions, the van's VIOLATION | Here is real drone footage of a crossing. The rule: every car must wait one and a half seconds before the stop line. Muse Spark turns it into a typed rule, never code, and writes down how it read it: wait means standing still. SAM 3.1 tracks every car, and a deterministic engine judges each one. This van crawls through without stopping: a violation, with the exact frames. |
| 4 | Studio: the rule text is edited to "remain behind the stop line for at least 2 seconds", Check the rule, all PASS; Two readings: Spark and Wonder agree | Now a reviewer types a slightly different rule on the same clip. Muse Spark reads remain as simply being there, and so does a second Meta model, Muse Wonder. Every car passes, including the two that never stopped. Two models agreeing is not proof. |
| 5 | Certificate of that run (NOT CERTIFIED, 3/5, the two wrong verdicts) | So EventProof issues a certificate instead of trusting them. It attacks the rule with synthetic scenes, and it checks it against this clip's hand labels, frozen before any model ran. Verdict: not certified, three of five, the two cars that never stopped would have been let go. |
| 6 | Studio, demo run: Challenge Mode suite, minimal pair, repair decisions, before → after | On a warehouse version of the same rule, Challenge Mode finds 44 failures in 150 scenes and shrinks one to a minimal pair. Muse Spark proposes bounded repairs, and an independent grader keeps only those with zero regressions on 200 hidden scenes: 144 correct becomes 164. |
| 7 | Real-traffic figure, then the pooled table | But passing synthetic tests is not enough. On real footage from two cities, that repair calls crawling cars still. Across 30 labelled cars, Muse Spark's own rule gets 27 right with no wrong verdicts; the repair gets 16. And Muse Spark judging the video alone miscounts the cars in 14 of 25 runs. |
| 8 | Closing card | Build it, break it, repair it, and certify it on real video, before a camera acts on it. Every number here is recomputed in CI from committed evidence. |

## Claims → source
| claim | source |
|---|---|
| Takoma Park $40 citations, Virginia law, IEEE Spectrum quote | README "Who needs it now" (links) |
| Novi Sad rule, "wait" = standing still, van VIOLATION | `benchmark/real/novisad/runs/20261102T040830Z-37064c4a/evidence.json` |
| "remain behind the line 2 s": both models read presence; all PASS; NOT CERTIFIED 3/5 | `docs/evidence/runs/20261102T080747Z-6b0ae7d4/`, `backend/tests/test_certificate.py` |
| 44/150, minimal pair, 2/8 accepted, 0 regressions, 144 → 164 | `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/*.json` |
| 30 cars, 27 vs 16, 0 wrong verdicts, Spark alone counts wrong in 14/25 runs | `benchmark/real/POOLED_v2.json` |
| every number recomputed in CI | `backend/tests/` |

Limits stated in the README, not in the narration for time: small real set labelled by one person; synthetic voice.
