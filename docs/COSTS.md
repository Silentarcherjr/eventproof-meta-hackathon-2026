# Costs and credits

Only confirmed numbers go in "confirmed" columns. Estimates are labelled. AI-assistant credit balance is never inferred from chat; if no dashboard value is available it is UNKNOWN.

| fecha (Panamá) | plataforma | sesión/tarea | tipo de crédito | saldo confirmado | consumo confirmado | estimado | límite acordado | alerta | fuente |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-27 | Meta Model API | G0 | hackathon $150 | NOT_CLAIMED | $0 | - | $150 total; backend guard `META_BUDGET_USD=40` per environment | Spend Limit notification to be set by participant | participant (no credits yet) |
| 2026-10-27 | Meta Model API | G1-04 | hackathon $150 | CLAIMED per participant; balance UNKNOWN (no dashboard read) | $0 (no live call yet) | - | $150 total; live SAM calls need explicit `--max-live-calls` | - | participant message |
| 2026-10-27 | AI coding assistant (local session) | G0 bootstrap | participant plan | UNKNOWN | UNKNOWN | - | - | - | no dashboard read |
| 2026-10-27 | Baseten / Modal / Fireworks | - | partner credits | NOT_REQUESTED | $0 | - | - | - | - |

## Pricing notes
- SAM 3.1 bills a minimum of 50 frames per request (dev.meta.ai/docs/sam/segmenting, 2026-10-27). Cache results by (video sha256, model, prompt).
- Muse Spark pricing: not yet read from the account's Billing page — fill in once credits are active.
