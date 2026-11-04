# Umbrella pilot: a two-object rule on real footage (findings)

Pre-registered in `PREREGISTRATION.md` (commit 90a2cab) before any model call. Run once:
`with_pilot run --max-muse 2 --max-sam 2`, 2 Muse Spark calls + 2 SAM 3.1 requests. `report.json` recomputes from
the recorded run with 0 API calls (`with_pilot report`, tested in CI).

**What happened:**
- **Muse Spark escalated the schema.** It first refused the base schema, which cannot express a second object. It then
  compiled the sentence with the WITH schema: `IMPLIES(IN_ZONE crossing, WITH(umbrella, on_top, min_ms 0))`, with the
  entity "pedestrian".
- **SAM 3.1 tracked both concepts:** 16 pedestrian tracks, plus 7 umbrella tracks from a separate request.
- **The overall verdict was FAIL, as labelled.**

| labelled person | truth | verdict | outcome |
|---|---|---|---|
| man in white cap, no umbrella | VIOLATION | VIOLATION | right |
| person under a tartan umbrella | PASS | PASS | right |
| white-haired man, no umbrella | VIOLATION | PASS | **wrong** |
| person under a clear umbrella, entering at the bottom corner | PASS | no track | not tracked |

**2/4 right, 1 wrong, 1 not tracked.** Both failures are specific:

- **Wrong verdict.** The bare-headed man walks right next to the person with the tartan umbrella. For 5 frames (0.4 s)
  the edge of that umbrella's box overlaps the top of his box by about 1 % of the frame width. Muse Spark chose
  `min_ms: 0` because the sentence gives no duration, so a single frame of overlap counts as "holding an umbrella".
  - With a minimum hold of 0.5 s, the verdict would have been VIOLATION.
  - We did not re-run with that change. Changing the rule after seeing the output would be tuning.
  - This is the kind of case the two-readings check is meant to surface: the sentence says nothing about duration,
    and a model filled the gap silently.
- **Not tracked.** SAM tracked the clear umbrella but not the person under it. Seen from above, the person is almost
  hidden, so the rule had nobody to check.

**Limits:**
- This is one clip with 4 people, a demonstration and not an accuracy figure.
- The `on_top` test was changed (box overlap instead of centre) after looking at this footage and before any model
  output existed. This is disclosed in the pre-registration.
- Challenge Mode and two-readings do not yet handle WITH rules: the synthetic world has no second object. The studio
  says so instead of running them.
