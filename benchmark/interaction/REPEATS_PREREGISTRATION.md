# INTERACTION: does the compiler pick the same unwritten numbers twice? (pre-registered)

Registered 2026-11-04, before any of the calls below and before any outcome of them is seen. Addendum to
`PREREGISTRATION.md` (unchanged). Population, data and engine are exactly those of the main study: the 1,268 eligible
STOP-line approaches in `derived.json.gz`, bound per approach as in `interaction.py`.

## Question

The statutes write "shall stop" and no number. The main study compiled California's once. Here: across independent
compilations of the same verbatim statute, with the same layout and the same compiler, how much do the stop time, the
"still" speed, the measured point and the rule's structure vary, and how many of the 1,268 approaches would each
compiled rule ticket? This measures stability of a model's silent choices, not accuracy: there are no human
violation labels.

## Design

- Statutes, verbatim from `benchmark/law/statutes.json`: `ca-veh-22450a` and `md-tr-21-707a`.
- Models: `muse-spark-1.3` and `muse-wonder-1.0`. 10 independent compilations per model and statute: 40 runs.
- Compiler: the existing law-mode compiler (`law=True`, anchor field, escalation to the WITH schema as usual,
  `max_attempts=2`), the main study's `compilation_layout()` unchanged (it states that the frame is 100 m wide and
  the zone is the last 10 m before the line). API default sampling; no temperature is set.
- Each run has its own cache folder, so each run is a fresh call; the responses are recorded and committed, and
  everything below recomputes from them with zero calls.
- A transport error (HTTP/timeout, no model answer) is retried at most twice and reported; it is not a model outcome.
  A compile that fails validation after its attempts, a refusal, or a rule without DWELL is a reported outcome.
- Live-call cap for the whole study: 160 (40 runs x at most 4 calls). Nothing else is called.

## Evaluation

Each successful rule is bound to each approach (zone = mapped approach polygon, line = the STOP line) and judged by the
deterministic engine with its own compiled values: no clamping, no snapping, no grid. Rules without DWELL are judged as
compiled and flagged.

Reported per model x statute and overall: runs, successes, failures by kind; every compiled stop time, "still" speed
(frame widths/s and the m/s it means at 100 m), anchor and event structure; tickets and share of the 1,268 approaches
per run (min, median, max); the number of distinct verdict strings; approaches whose verdict changes across the
successful rules. The main study's single compile is shown beside them, not counted among the 40.

No rerun, replacement call or change of design after seeing results. Every run is reported.
