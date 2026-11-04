# Traffic Challenge world — synthetic, offline

Status: implemented on `traffic-sim`; merge requires separate review. No Meta calls, secrets,
external video, datasets, or paid services. Existing conveyor generators and frozen hashes are preserved.

Eight pure `seed -> SceneSpec` families: `full_stop`, `rolling_stop`, `no_stop`, `brief_stop`,
`queue`, `occluded`, `wrong_way`, `tailgate`. Seed knobs vary speed, stop duration/distance,
lane count/selection, optional cross traffic, perspective box scaling and symmetric box jitter.
The truck is a static, timed occluder. Rectangles and linear waypoints are deliberately simple.

## Truth contract (`traffic-gen/1`, `traffic-truth/1`)

Car **centers** cross a finite vertical stop line at x=0.72. Waiting zone:
x=[0.54,0.70], y=[0.36,0.72]. The longest consecutive in-zone low-speed run **before** the
first crossing must last >=1.5 s; separate stops are not summed. No crossing means vacuous PASS.
Direction is `forward` / `wrong_way` / `none`; this waiting rule adds no separate direction ban.
Cross traffic is context, excluded from the approach-car rule.

Low speed means <=0.01 normalized frame units/s, measured over the preceding ceil(0.333*fps)
frames (four at 10 fps), or since track start. Each qualifying sample counts 1/fps seconds.
`standing_still_seconds` is this sampled, smoothed operational measure;
`stationary_seconds` separately reports exact zero-speed waypoint time. In particular, a physical
1.5 s rest may not satisfy 1.5 s of **windowed** stillness after fast arrival. This benchmark
measures that stated contract, not legal compliance or exact continuous-time bumper stopping.

Truth reads waypoints independently of engine, renderer and perception. `tracks.json` contains
complete analytic perfect boxes, including hidden cars, with `source: "synthetic"`; use
`TrafficTracks.model_validate_json` to load this challenge-local provenance extension.
`ground_truth.json` retains visibility/occlusion flags. Box jitter changes extents, never centers.
Perfect-track results must always be reported **separately from SAM results**. Mocks say `mock`.

## Reproduce (from `backend/`, with the existing environment and ffmpeg)

```sh
uv run python -m eventproof.challenge.runner --world traffic --perception perfect --seeds 0-39
uv run python -m eventproof.challenge.minimize --world traffic --family rolling_stop --seed 0 \
  --perfect --naive-traffic --out ../benchmark/traffic_sim/counterexamples
uv run python -m eventproof.challenge.traffic_export freeze --out ../benchmark/traffic_sim/regenerated_v1
uv run python -m eventproof.challenge.traffic_export verify --out ../benchmark/traffic_sim/v1
# A fresh checkout intentionally lacks generated MP4s; verify all tracked JSON instead:
uv run python -m eventproof.challenge.traffic_export verify --out ../benchmark/traffic_sim/v1 --allow-missing-video
uv run pytest -q
uv run ruff check .
```

Frozen release `v1`: development seeds 0–39 x 8 = 320 scenes; holdout seeds
100000–100024 x 8 = 200 scenes. Search and suite entry points reject these holdout seeds.
Holdout export computes geometry labels without running a detector; tests only verify its bytes.
Never tune on the holdout or regenerate a frozen folder in place: export into a **new** directory.

Every scene exports MP4, `scene.json`, perfect `tracks.json`, visibility-aware `ground_truth.json`,
`labels.json`, and a manifest with file SHA-256 and raw RGB frame SHA-256. Split and release manifests
seal the case lists. MP4s stay locally under this folder, ignored by the existing repo policy;
JSON, labels and hashes are committed. MP4 bytes can differ with ffmpeg versions; raw-frame hashes
are the portable pixel contract. Re-encoding is not evidence of identical MP4 bytes across machines.

## Validation and limits

Development tests cover all families/car verdicts, manual 1.4/1.5 s sampled boundaries, slow drift,
separate and post-crossing stops, line contact, no crossing, occlusion, pixel/box alignment,
identity-at-zero knobs, replayable minimization and deterministic MP4 exports. The rolling-stop
counterexample varies only crawl time; its boundary scenes differ by one motion frame.

Works through the existing backend runner/minimizer with `--world traffic`; the studio UI has not
been changed. This is not a traffic dynamics or collision simulator. Perspective changes box size,
not a calibrated projection. Occlusion is scripted, and perfect tracks do not measure perception.
Generated approach cars cross at most once and do not park on the line; the shared DSL uses first
event occurrences, so this is not a benchmark of arbitrary repeated crossings or long line contact.
No holdout score or SAM score is claimed. No real-world performance or human annotation is claimed.

Implementation validation: `uv run pytest -q -p no:cacheprovider`: **336 passed, 2 skipped**
(one skip is the not-yet-frozen release check); `uv run ruff check . --no-cache`: passed.
The CLI replay was rendered with `source: synthetic`, 31 evaluations, a one-frame crawl change,
and a real PASS→FAIL detector flip while both truth labels remain VIOLATION.
Release generation/validation is recorded separately below. No merge performed.
