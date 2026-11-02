# Costs and credits

## Current summary (2026-11-01)
- Meta Model API: $150 hackathon credits. **Balance $149.26 → spent $0.74** (read by the participant from the Billing page, 2026-11-01).
- Live calls made so far (from the rows below): SAM 3.1 = 13 (1 smoke, 10 SAM-vs-mock, 1 E2E, 1 studio confirm);
  Muse Spark ≈ 13 (1 smoke, 6 rule compiles incl. one of 194,990 prompt tokens, ~6 repair rounds). Everything since is cached.
- 2026-11-01: **80 live SAM 3.1 calls** (final_v1 SAM pass, P1-07; 8,087 frames; participant approved up to $5).
  Upper bound ≈ $4.3 (from $0.74 for the 26 earlier calls); exact charge UNKNOWN until the Billing page is read again.
  SAM 3.1 total so far: 104 live calls (+1 Pexels v1, 203 frames; +8 Pexels v2 windows, ≤ 400 billed frames; +2 Novi Sad clips, 387 frames).
  Muse Spark: +1 live compile (Novi Sad rule), 2026-11-01.
- 2026-10-28 work (before/after view, final_v1, ledger, showcase deploy, real-video flow): **0 live calls**.
- Hosting: $0 (nothing deployed). AI coding assistant: UNKNOWN (no dashboard read).

## Log
Only confirmed numbers go in "confirmed" columns. Estimates are labelled. AI-assistant credit balance is never inferred from chat; if no dashboard value is available it is UNKNOWN.

| fecha (Panamá) | plataforma | sesión/tarea | tipo de crédito | saldo confirmado | consumo confirmado | estimado | límite acordado | alerta | fuente |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-02 | Meta Model API | Ambiguity finder, Spark vs Wonder (P1-11) | hackathon $150 | UNKNOWN | 1 Wonder smoke + 23 live compiles (8 Spark, 15 Wonder incl. retries) | cached usage ≈ $1.41 + one uncached Wonder runaway ≈ $2 (estimate) | within the $60 approval | - | benchmark/ambiguity/FINDINGS.md |
| 2026-11-02 | Meta Model API | Muse Spark-alone video baseline (P1-10) | hackathon $150 | UNKNOWN | 1 smoke + 10 live muse-spark-1.3 video calls (26.7k in / 42.6k out tokens) | ≈ $0.23 at list price | within the $60 approval | - | benchmark/real/spark_alone/report.json |
| 2026-11-02 | Meta Model API | budget approval (real-footage set v2 + Spark-alone baseline) | hackathon $150 | UNKNOWN | - | - | participant approved up to $60 more | - | participant message |
| 2026-11-01 | Meta Model API | Novi Sad real traffic loop (P1-09) | hackathon $150 | UNKNOWN | 2 live SAM calls (190 + 197 frames) + 1 live Muse compile | ≤ $0.21 SAM (bound) + 1 Muse compile | participant approved | - | benchmark/real/novisad/report_novisad.json |
| 2026-11-01 | Meta Model API | Pexels check v2 (P1-08) | hackathon $150 | UNKNOWN | 8 live SAM calls (50-frame windows) | ≤ $0.21 (bound) | participant approved | - | benchmark/real/pexels/report_pexels_v2.json |
| 2026-11-01 | Meta Model API | Pexels real-footage check (P1-08) | hackathon $150 | UNKNOWN | 1 live SAM call (203 frames) | ≤ $0.11 (bound) | participant approved | - | benchmark/real/pexels/report_pexels.json |
| 2026-11-01 | Meta Model API | final_v1 SAM pass (P1-07) | hackathon $150 | UNKNOWN (Billing not re-read) | 80 live SAM calls (8,087 frames, 2 trial + 78) | ≤ $4.3 (bound) | participant approved ≤ $5 | - | benchmark/final/sam_v1/tracking.json |
| 2026-11-01 | Meta Model API | balance read (C-03) | hackathon $150 | $149.26 remaining | $0.74 total to date (all live calls since 2026-10-27) | - | $150 | - | participant, Billing page |
| 2026-10-27 | Meta Model API | G0 (superseded: credits claimed later that day) | hackathon $150 | NOT_CLAIMED | $0 | - | $150 total; backend guard `META_BUDGET_USD=40` per environment | Spend Limit notification to be set by participant | participant (no credits yet) |
| 2026-10-27 | Meta Model API | G1-04 | hackathon $150 | CLAIMED per participant; balance UNKNOWN (no dashboard read) | $0 (no live call yet) | - | $150 total; live SAM calls need explicit `--max-live-calls` | - | participant message |
| 2026-10-27 | Meta Model API | G0-03/G0-04 smoke | hackathon $150 | UNKNOWN (Billing not read) | 2 live calls: 1 SAM (120-frame clip, min 50 billed), 1 Muse (23 in / 504 out tokens) | - | live SAM calls need explicit `--max-live-calls` | - | docs/evidence/2026-10-27_meta_api_smoke.md |
| 2026-10-27 | Meta Model API | SAM vs mock comparison | hackathon $150 | UNKNOWN (Billing not read) | 10 live SAM calls (96–120 frames each) | - | participant approved max 10 | - | benchmark/reports/2026-10-27_sam_vs_mock.json |
| 2026-10-27 | Meta Model API | G1-03 Muse rule compiler | hackathon $150 | UNKNOWN (Billing not read) | 6 Muse calls: 1 × 194,990 prompt tokens (first schema, fixed), 5 × ~1,420; 2.1k–3.8k completion each | - | - | the 195k-token call is the largest single spend so far | benchmark/rules/2026-10-27_muse_compile_report.json |
| 2026-10-27 | Meta Model API | G1-01 E2E run | hackathon $150 | UNKNOWN (Billing not read) | 1 live SAM call (102 frames); Muse cached | - | - | - | docs/evidence/2026-10-27_e2e_run.md |
| 2026-10-27 | Meta Model API | Challenge+Repair (G2-03/G4-01) | hackathon $150 | UNKNOWN (Billing not read) | about 6 Muse repair calls (1–3k prompt, 2–8k completion tokens each) + 1 live SAM call (studio confirm) | - | - | - | docs/evidence/2026-10-27_studio_challenge_repair.md |
| 2026-10-28 | Meta Model API | Docker compose verification (G5-02) | hackathon $150 | $0 | 0 calls (cached inputs, key forced empty, 0 live SAM allowed) | - | - | - | docs/evidence/2026-10-28_docker_compose.md |
| 2026-10-28 | Meta Model API | before/after, final_v1, ledger, showcase, real-video flow | hackathon $150 | UNKNOWN | 0 calls | - | - | - | CI 40717424645 |
| 2026-10-28 | Hosting | Deploy proposal (G6-01) | - | $0 (nothing deployed) | options $6–14/month, see docs/DEPLOY_PROPOSAL.md | - | - | - | docs/DEPLOY_PROPOSAL.md |
| 2026-10-27 | AI coding assistant (local session) | G0 bootstrap | participant plan | UNKNOWN | UNKNOWN | - | - | - | no dashboard read |
| 2026-10-27 | Baseten / Modal / Fireworks | - | partner credits | NOT_REQUESTED | $0 | - | - | - | - |

## Pricing notes
- SAM 3.1 bills a minimum of 50 frames per request (dev.meta.ai/docs/sam/segmenting, 2026-10-27). Cache results by (video sha256, model, prompt).
- Official prices read 2026-11-02 (dev.meta.ai/docs/pricing-rate-limits): SAM 3.1 video $0.20 per 1,000 frames (min 50
  per request), images $2.50 per 1,000; Muse Spark 1.3 $1.25 / $4.25 per 1M input / output tokens (cached input $0.15);
  Muse Wonder 1.0 $4 / $20. Earlier "≤ $X (bound)" entries used a cost-per-frame bound derived from the $0.74 total and
  overstate SAM spend: at list price all ~10,500 SAM frames so far cost about $2.1.
- Muse Spark pricing: not yet read from the account's Billing page — fill in once credits are active.
