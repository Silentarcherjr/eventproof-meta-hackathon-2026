# INTERACTION stop-law sensitivity — preregistration v1

Registered 2026-11-04 before model calls and before trajectory outcome analysis.
Base: origin/main 5fc1310ee737c501c88ffa364b49888aa74bc278.
Deadline: 2026-11-04 13:30 America/Panama. Branch: interaction-stops; no merge.

## Data and map-only selection

Use INTERACTION-Dataset-DR-v1_1.rar from the author-approved Hugging Face
INTERACTION-dataset/INTERACTION-dataset release (CC BY 4.0). Raw material stays
outside Git. Cite Zhan et al., arXiv:1910.03088; keep ATTRIBUTION.md.
Use all vehicle CSV recordings at DR_USA_Intersection_EP0, EP1, GL and MA.
Roundabout-named locations are outside this intersection-only population.

The maps actually encode regulatory_element/all_way_stop and right_of_way
referencing traffic_sign/usR1-1 ways, rather than a uniform traffic_sign/stop
relation. Accept all_way_stop yield lanelets, and right_of_way yield lanelets
only when the relation refers to an explicit usR1-1 STOP sign and has ref_line.
Do not equate an unsigned yield or a bare stop_line marking with STOP. Deduplicate
regulatory references and stop-line/lanelet pairs. Select the nearest ref_line
to the yield lanelet endpoint, not positional pairing (maps repeat ref_line IDs).
Save relation/sign/line/lanelet IDs, map hashes, coordinates and selection reasons.

## Population (no outcome-based sampling)

Every car track in every vehicle CSV at the four locations is eligible. Unit:
vehicle/recording/STOP-line approach; repeated observations in different recordings
are separate vehicles, not linked identities. A vehicle may approach multiple lines;
report approach count and distinct recording/track count separately.
Require positive, finite length/width/yaw/coordinates/timestamps, strictly increasing
100 ms samples without missing frames in the analyzed segment. No gap interpolation.
Require observed crossing of the finite STOP line in the inbound direction, using
the vehicle centre for selection (independent of the model-selected evaluation
anchor). Require an observed centre at least N=10 m upstream, with lateral position
within the line span and inside the associated approach lanelet. Require the last
10 m of the approach through centre crossing to remain in that lanelet until the
line (line/map numerical tolerance 0.25 m); otherwise record exclusion. No selection
by speed, stop duration, model verdict or conformity to California law. Deduplicate
same track/line across lanelets; choose smallest numeric eligible lanelet ID.
Analyze from first qualifying >=10 m upstream observation until first observed
centre crossing plus one second when available. No minimum downstream duration.
Record exclusions, ambiguous map relations, input hashes and all included identities.

## Geometry, units, waiting zone, temporal semantics

Map .osm topology and matching .osm_xy metric coordinates supplied by authors are
used together. For each approach: origin = midpoint of ref_line endpoints; local x
is along the line, local y is its perpendicular oriented from upstream lanelet
towards crossing. A square local frame is W=100 m wide and high; origin maps to
(0.5,0.6). Positions: x_norm=0.5+x_m/100, y_norm=0.6+y_m/100.
Use 10000 x 10000 virtual pixels (100 px/m), no video rendered or claimed.
Thus DWELL.max_speed * 100 = m/s; 0.01 frame widths/s = 1 m/s. Transform
length/width/yaw into the local frame and take the axis-aligned envelope of the
four rotated vehicle corners. Preserve CSV timestamps, offset to segment start;
10 fps. Keep the actual car dimensions, no fixed boxes. Source is exactly
"dataset trajectory (INTERACTION, drone)", never SAM or human_annotation.

Waiting zone = associated approach lanelet polygon intersected with the fixed
longitudinal strip -10 <= local y_m <= 0. The line remains its finite mapped span.
The generic compilation layout is a 10 m wide x 10 m long approach zone ending
at a limit line at y=0.6; known mapped geometry replaces only the generic zone/line
coordinates per approach. Model chooses center or bottom_center anchor, retained
in all evaluations; bottom_center is the downstream edge of the top-down AABB,
not wheels or a true yaw-aware front bumper. Report that limitation explicitly.
Engine speed uses anchor displacement over its existing 333 ms window, not CSV
vx/vy. Dwell includes the engine's one-sample interval convention; 100 ms resolution
and measured trajectory noise limit interpretation of exact zero motion.

## Live compilation, frozen grid, outcomes

AFTER this file is committed, compile verbatim ca-veh-22450a from
benchmark/law/statutes.json with existing MuseRuleCompiler law=True and anchor
field, muse-spark-1.3, total process LiveBudget <=2 calls including retry/escalation.
Load the locally configured key into the process environment without copying it.
If unavailable or compilation unsupported/invalid within budget, stop and report;
never substitute another statute, cached historical rule, hand-written rule or mock.
Record new response/cache, usage, request IDs and actual assumptions. Extract actual
DWELL min_ms and max_speed; report conversion to seconds and m/s. If compiled
values fall outside the grid, evaluate them separately without snapping. If there
is no DWELL, report inability to perform this preregistered dwell study and stop.

Grid: times [0,0.25,...,3] s (13); speeds [0.05,0.10,0.20,0.30,0.50,0.75,1.00,
1.25,1.50,1.75,2.00] m/s plus None = any motion (12): 156 cells.
Zero seconds is operationalized as 1 ms because the DSL requires positive dwell;
it means any qualifying observed sample, NOT proof of a physical full stop.
Any-motion removes the stillness condition; it is a semantic control, reported
separately from the numeric speed grid. Change only DWELL.min_ms and max_speed.
Run deterministic evaluate for every included approach and cell. Never infer
human violation truth from a threshold. Keep PASS, VIOLATION, UNKNOWN separately.

Report pooled, per-location and per-approach: denominators; count and share ticketed
(VIOLATION/all included); UNKNOWN; full-grid and numeric-only min/max and spread;
compiled-rule result; per-cell verdicts. Also report unique vehicles so repeated
approaches cannot masquerade as extra people. Report the time/speed boundary via
per-vehicle longest continuous qualifying dwell at each grid speed (engine counters),
not a single universal cutoff. Record number whose verdict changes across cells.

## Reproduction and honest claims

Commit small derived local trajectories (lossless numeric values), selected map
geometry and provenance, not raw archive or raw CSVs. Tests recompute report.json
from these committed derivatives with zero model calls and test unit conversion,
map STOP selection, crossing direction, missing/incomplete tracks, box rotation,
deduplication and exact grid regeneration. Full pytest and Ruff before EVERY commit.
Interpret results as sensitivity to unwritten parameters, NOT enforcement accuracy:
no human violation labels, no video, no SAM; trajectories measured by dataset authors.
California statute applied counterfactually to this population; no legal judgment
on drivers at these mapped locations. No post-outcome tuning of inclusion/grid.
