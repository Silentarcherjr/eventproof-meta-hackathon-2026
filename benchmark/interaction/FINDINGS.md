# INTERACTION: the unwritten numbers change who would get ticketed

**On 1,268 real STOP-line approaches from 1,254 recording/track identities, changing
only the numeric interpretation of “stop” changes predicted tickets from 119 to
1,073 (9.38% to 84.62%; 75.24 percentage points).** This is sensitivity, not accuracy.
The separate “any motion” semantic control brings the lower bound to zero.

Preregistration: `PREREGISTRATION.md`, committed and pushed as **1d04084** before
any live model call or trajectory-outcome analysis; base main **d31abdf** (CI green).
Worktree branch **interaction-stops**. No merge, main push, video download or SAM call.

The sole live Muse Spark call compiled the **verbatim California Vehicle Code
22450(a)** in `benchmark/law/statutes.json` through the existing law-mode compiler
(`law=True`, anchor field). The validated rule is an IMPLIES/CROSSES/BEFORE/DWELL
AST, not executable model output. See `compile.json` and `cache/` for the actual
response, assumptions, request ID and token usage. **1 call of at most 2 authorized**;
no replacement compile and no use of historical rules.

## What the compiler chose

- `DWELL.min_ms = 1000`: one second, explicitly marked ASSUMED by Muse.
- `DWELL.max_speed = 0.05`: 0.05 frame widths/s in the existing engine.
- The preregistered metric frame is **100 m wide**, so that means **5 m/s = 18 km/h**.
  It is outside the numeric grid's 0.05–2.00 m/s range; evaluated separately,
  **without clamping or snapping**. Its cell is **(1.0 s, 5.0 m/s)**.
- `anchor = center`, chosen by Muse for the top-down metric boxes. No silent
  replacement with a front bumper or wheels. For this anchor, yaw/box dimensions
  do not affect the verdict; the adapter still constructs the required real-size
  rotated-box envelopes and tests their geometry.
- Muse labelled the speed QUOTED with the exact substring “shall stop”. The quote
  exists, so the existing quote validator accepts it. **Those words specify no
  numeric speed.** The speed remains an unwritten numerical assumption regardless
  of the model's provenance label. This is not a claim that California permits 18 km/h.

## Per-location and pooled results

A “ticket” below means deterministic engine VIOLATION under that cell. Denominator
is **eligible approaches**, not all vehicles in a city or the raw release. A track
can approach two STOP lines; recording/track identities are separate from approaches
and are not linked across recordings or locations. There are 14 additional
approaches beyond unique identities. All reported cells have **zero UNKNOWN**.

| Location | Input tracks | Unique included identities | Included approaches | Muse: tickets (share) | Numeric-grid min–max | Full-grid min–max |
|---|---:|---:|---:|---:|---:|---:|
| EP0 | 732 | 539 | 539 | 4 (0.74%) | 56–470 (10.39%–87.20%) | 0–470 |
| EP1 | 657 | 439 | 453 | 4 (0.88%) | 44–375 (9.71%–82.78%) | 0–375 |
| GL | 10,510 | 0 | 0 | 0 (N/A) | 0–0 (N/A–N/A) | 0–0 |
| MA | 2,982 | 276 | 276 | 2 (0.72%) | 19–228 (6.88%–82.61%) | 0–228 |
| **Pooled** | **14,881** | **1,254** | **1,268** | **10 (0.79%)** | **119–1,073 (9.38%–84.62%)** | **0–1,073** |

The strict numeric-grid extrema are **(0 s, 2 m/s)** and **(3 s, 0.05 m/s)**.
“0 s” is operationalized as **1 ms** because DWELL requires a positive duration:
any qualifying sampled observation is enough, not proof of a physical zero-duration
stop. The full-grid spread is **84.62 percentage points**, including the semantic
control; numeric-only spread is **75.24 points**. **1,073 approaches change verdict**
across the full grid. These are 197,808 approach/cell deterministic evaluations,
plus 1,268 evaluations at the compiled values; no further model calls.

## Where “stopped” becomes “rolled”

There is no human-labelled or universal separation in this dataset. The operational
boundary is the selected speed threshold and required continuous duration, measured
by the existing engine. At a fixed one-second requirement:

| “Still” threshold (m/s) | Ticketed approaches |
|---:|---:|
| 0.05 | 889 |
| 0.10 | 870 |
| 0.20 | 814 |
| 0.30 | 765 |
| 0.50 | 683 |
| 0.75 | 576 |
| 1.00 | 498 |
| 1.25 | 410 |
| 1.50 | 328 |
| 1.75 | 249 |
| 2.00 | 186 |
| Any motion (semantic control) | 0 |
| 5.00 (Muse, outside grid) | 10 |

Holding speed at 0.50 m/s, increasing duration from the 1 ms operational floor to
3 s changes tickets from **611 to 921**; at 1 s it yields **683**. Thus both
unwritten numbers matter, even without changing the geometry or trajectories.

`report.json` stores all 156 per-vehicle verdict strings and the longest continuous
qualifying dwell for each vehicle at every speed, in the same order as `vehicle_ids`.
That dwell counter includes the engine's one-sample interval and must be read with
the compiled BEFORE condition: completing dwell at the crossing frame does not
satisfy “before”. It is not an independent “rolling stop” ground-truth label.

## Exactly which STOP lines and lanelets

`maps.json` is the full map audit: original `.osm` and `.osm_xy` hashes; regulatory
IDs; sign IDs; finite reference-line geometry; source lanelet polygon; local bases;
clipped zone polygons; and excluded relations. Coordinates are authors' metres.
The map schema differs from the simplified task description: STOP is encoded by
`all_way_stop` yield lanelets or `right_of_way` yield lanelets explicitly referring
to `traffic_sign/usR1-1`. Bare stop markings, unsigned yield relations and roundabout
locations were excluded. `ref_line` IDs repeat, so pairs are deduplicated and each
lanelet uses its nearest reference line. The table lists **all 26 selected pairs**,
including those contributing no complete track. STOP-sign lists for an all-way
relation are relation-wide, not an asserted one-to-one sign/lanelet pairing.

| Location | STOP line | Yield lanelet | Regulatory relation(s) | Kind | Eligible approaches |
|---|---|---|---|---|---:|
| EP0 | 10070 | 30057 | 50003 | right_of_way | 0 |
| EP0 | 10072 | 30041 | 50001 | all_way_stop | 147 |
| EP0 | 10072 | 30046 | 50001 | all_way_stop | 92 |
| EP0 | 10074 | 30048 | 50001 | all_way_stop | 124 |
| EP0 | 10076 | 30028 | 50001 | all_way_stop | 176 |
| EP0 | 10105 | 30056 | 50002 | right_of_way | 0 |
| EP1 | 10006 | 30069 | 50002 | right_of_way | 19 |
| EP1 | 10026 | 30068 | 50003 | right_of_way | 17 |
| EP1 | 10066 | 30024 | 50001 | all_way_stop | 143 |
| EP1 | 10086 | 30030 | 50001 | all_way_stop | 79 |
| EP1 | 10086 | 30031 | 50001 | all_way_stop | 94 |
| EP1 | 10110 | 30067 | 50001 | all_way_stop | 96 |
| EP1 | 10139 | 30071 | 50004 | right_of_way | 5 |
| GL | 10060 | 30039 | 50002, 50008 | right_of_way | 0 |
| GL | 10070 | 30081 | 50003, 50007, 50009 | right_of_way | 0 |
| GL | 10143 | 30057 | 50005 | right_of_way | 0 |
| GL | 10143 | 30069 | 50001 | right_of_way | 0 |
| MA | 10035 | 30046 | 50001 | all_way_stop | 276 |
| MA | 10036 | 30039 | 50001 | all_way_stop | 0 |
| MA | 10036 | 30055 | 50001 | all_way_stop | 0 |
| MA | 10036 | 30062 | 50001 | all_way_stop | 0 |
| MA | 10038 | 30056 | 50001 | all_way_stop | 0 |
| MA | 10038 | 30057 | 50001 | all_way_stop | 0 |
| MA | 10040 | 30010 | 50001 | all_way_stop | 0 |
| MA | 10040 | 30013 | 50001 | all_way_stop | 0 |
| MA | 10065 | 30014 | 50002 | right_of_way | 0 |

EP0 contributes its central all-way STOP approaches. EP1 contributes its central
all-way STOP plus explicitly signed lateral approaches. MA contributes only the
long-enough lanelet 30046 at STOP line 10035. Other MA mapped yield lanelets are
shorter than the required 10 m, or have no eligible observed crossing. EP0 lateral
pairs also have zero eligible crossings under the frozen rules.

**GL contributes zero, not a fabricated rate.** Its four mapped yield lanelets end
about 3 m before their stop lines. The required continuous lanelet membership to
the crossing therefore rejects those approaches. No corridor extension or relaxed
inclusion was introduced after seeing the population. This and MA's short lanelets
create substantial selection bias: the pooled result represents these eligible
approaches, not all four intersections or all STOP traffic in INTERACTION.

`population.json` records input hashes and counts for every track/lanelet candidate.
These exclusion counts are **candidate-pair counts**, not disjoint vehicle counts;
one car is tested against multiple lanelets. The final track/line unit is deduplicated,
choosing the smallest eligible numeric lanelet ID.

## Data, conversion and limitations

Source: [INTERACTION author release](https://huggingface.co/datasets/INTERACTION-dataset/INTERACTION-dataset),
**CC BY 4.0**, [Zhan et al., arXiv:1910.03088](https://arxiv.org/abs/1910.03088).
See `ATTRIBUTION.md` for authors, license, citation and changes. Archive SHA-256:
`a43e04dcbbc9961e5fce7b898386b4946c65f3f66274f4b821bc92c84e8e1388`.
Raw archive and CSVs are outside Git at `/private/tmp/interaction/` on the authoring
machine. Only small derived geometry/trajectories and measured results are committed.
The 3.2 MiB deterministic gzip stores local coordinates, timestamps, yaw, dimensions
and provenance; original source CSV/track/frame IDs remain auditable via hashes.

Every accepted track is `agent_type=car`, with positive dimensions, finite values,
complete >=10 m approach, inbound finite-line crossing and contiguous 100 ms samples.
The waiting polygon is the **mapped lanelet clipped to -10 <= y_m <= 0**, not an
unbounded rectangle. Origin is the line midpoint; local +y is downstream; a square
100 m frame maps to 10000 virtual pixels. Coordinates map as x/100+0.5, y/100+0.6.
CSV yaw and length/width produce the four-corner AABB envelope. TrackSet source is
exactly **`dataset trajectory (INTERACTION, drone)`**, never SAM.

- **No human violation labels:** this is sensitivity, not accuracy, false-positive
  rate, proof of wrongdoing or a measured enforcement error. The California rule
  is applied counterfactually; locations need not be in that jurisdiction.
- **No video and no SAM:** trajectories were measured/processed by dataset authors;
  this does not evaluate perception. We did not review video to validate positions,
  signs, queues, police direction, stop reasons or apparent full stops.
- Speed is anchor displacement over the existing **333 ms window** (at 10 Hz usually
  a 400 ms baseline), not CSV vx/vy. The engine includes one 100 ms sample in dwell.
  Noise, quantization and 100 ms sampling limit any “exactly still” interpretation.
- The 10 m zone accepts a stop anywhere in that strip. It does not test whether
  the front bumper stopped precisely at the legal limit line. Selection uses
  centre crossing and Muse independently chose centre for evaluation.
- Full-scale frame width is a preregistered engineering choice. The model's normalized
  speed assumption inherits that scale: changing it would change its physical meaning.
  We froze the scale and report the resulting 5 m/s rather than silently correcting it.
- Tracks/recordings are not an independent random sample. Queue effects and repeated
  locations prevent causal or population-wide enforcement claims. No bootstrap CI
  or hypothesis test is asserted. No outcomes were used to change the frozen grid.

## Reproduce without a model or raw download

From the branch checkout:

```sh
cd backend
uv sync
uv run pytest -q tests/validation/test_interaction.py
uv run pytest -q
uv run ruff check .
```

`test_report_recomputes_every_cell_zero_calls` loads committed `derived.json.gz` and
`compile.json`, runs the deterministic engine for every cell and compiled value,
and requires exact equality with committed `report.json`. The suite blocks live
Meta clients. No API key or raw archive is required. Other tests independently
check selection, STOP-vs-yield extraction, map/reference deduplication, incomplete
approaches, gaps, direction, yaw-aware box envelopes and physical speed mapping.

The module CLI `derive --raw` is the initial extraction entrypoint and refuses to
overwrite the frozen derivative; `report` and `compile` also preserve first evidence.
For a fresh raw audit without touching committed files, use the Python entrypoint
with `interaction.BENCH` set to a scratch directory (as the extraction unit test does).
`maps --raw` audits geometry only. Download/extract outside Git:

```sh
mkdir -p /private/tmp/interaction
curl -fL 'https://huggingface.co/datasets/INTERACTION-dataset/INTERACTION-dataset/resolve/main/INTERACTION-Dataset-DR-v1_1.rar' -o /private/tmp/interaction/INTERACTION-Dataset-DR-v1_1.rar
bsdtar -xf /private/tmp/interaction/INTERACTION-Dataset-DR-v1_1.rar -C /private/tmp/interaction
```

Do not rerun `compile` to reproduce this study: it was one recorded live call, with
1,967 prompt + 6,395 completion tokens (8,362 total). Actual billed dollars are
**unknown**; using the historical rates recorded in `docs/COSTS.md` gives an estimate
of **$0.0296**. No second call, SAM expense, deployment, merge or raw-data commit.

## Verification and branch handoff

Implementation: `backend/eventproof/validation/interaction.py`; tests:
`backend/tests/validation/test_interaction.py`. Source schema has one new explicit
trajectory provenance value. The law compiler and deterministic engine are unchanged.
Final test counts and push verification are recorded in the session handoff and chat;
tracker remains **IN_REVIEW**, because no reviewed merged SHA is claimed.
