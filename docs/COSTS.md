# Costs and credits

## Current summary (2026-10-28)
- Meta Model API: $150 hackathon credits claimed by the participant. **Balance and spend: UNKNOWN** (Billing page not read yet, C-03).
- Live calls made so far (from the rows below): SAM 3.1 = 13 (1 smoke, 10 SAM-vs-mock, 1 E2E, 1 studio confirm);
  Muse Spark ≈ 13 (1 smoke, 6 rule compiles incl. one of 194,990 prompt tokens, ~6 repair rounds). Everything since is cached.
- 2026-10-28 work (before/after view, final_v1, ledger, showcase deploy, real-video flow): **0 live calls**.
- Hosting: $0 (nothing deployed). AI coding assistant: UNKNOWN (no dashboard read).

## Log
Only confirmed numbers go in "confirmed" columns. Estimates are labelled. AI-assistant credit balance is never inferred from chat; if no dashboard value is available it is UNKNOWN.

| fecha (Panamá) | plataforma | sesión/tarea | tipo de crédito | saldo confirmado | consumo confirmado | estimado | límite acordado | alerta | fuente |
|---|---|---|---|---|---|---|---|---|---|
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
- Muse Spark pricing: not yet read from the account's Billing page — fill in once credits are active.
