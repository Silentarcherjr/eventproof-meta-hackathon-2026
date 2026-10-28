# Real-video validation protocol

A small check of EventProof on clips you record yourself with a phone. It answers one question: on real
pixels, does the pipeline (Muse Spark rule → SAM 3.1 tracks → deterministic evaluator) reach the verdict you
wrote down *before* running it?

- Results are **real-world, n = number of clips**. They are reported separately from the synthetic
  Challenge/holdout/final_v1 results and are **never used to tune** rules, thresholds, repairs or the grader.
- Process truth is the same as in the synthetic world: a box that crosses into packing must have **stood still
  ≥ 1.0 s at the inspection station** first. Boxes that never cross into packing pass.
- Code: `backend/eventproof/validation/real_video.py`. Label template: `benchmark/real/labels/TEMPLATE.json`.

## 1. Set up the scene

- A table or floor with a **taped rectangle** (inspection station) and, further along the path, a **taped line**
  (packing entry). Leave ≥ 20 cm between them. Plain, non-reflective background.
- **Coloured boxes** (e.g. blue; a second colour only if your rule names it). Boxes clearly bigger than a hand.
- **Fixed camera**: tripod or phone propped against something heavy. Top-down is best; a steep oblique view is fine.
  Do not touch the phone during recording. The tape and the whole path must be in frame.
- Good, even light; no strong shadows across the station. No people or faces in frame — push boxes with a
  stick or from outside the frame edge where possible; a hand briefly entering is acceptable.
- Record **MP4 or MOV, ≤ 20 s, 30 fps, 1080p** (SAM bills per frame, minimum 50; 60 fps doubles the cost).
  Hold the phone in the same orientation for every clip so one layout fits all.

## 2. Clips to record (2–3 minimum, all four if you can)

| clip | what happens | intended |
|---|---|---|
| `clip01_inspected` | box enters the station, **stops ≥ 2 s**, then crosses the packing line | PASS |
| `clip02_drive_through` | box moves steadily through the station and over the line, **never stops** | FAIL (VIOLATION) |
| `clip03_brief_stop` | box stops at the station **< 1 s** (a short tap-pause), then crosses | FAIL (VIOLATION) |
| `clip04_two_boxes` | box A stops ≥ 2 s and crosses; box B drives through and crosses (either order) | FAIL (B is the VIOLATION) |

Count the stop out loud ("one-thousand-one, ...") or watch a stopwatch off-camera; write the approximate
seconds down immediately. Use neutral file names (no names, places or dates).

## 3. Strip metadata (privacy)

Phone files carry location and device tags. EventProof's ingest re-encodes with `-map_metadata -1` **only when
re-encoding is needed** (rotation, HEVC, variable frame rate, ...); a clip that is already H.264/yuv420p/CFR is used
byte-for-byte, tags included. So strip before labelling, and label the stripped file:

```bash
ffmpeg -i IMG_1234.MOV -map 0:v:0 -c copy -map_metadata -1 benchmark/real/videos/clip01_inspected.mov
cd backend
uv run python -m eventproof.validation.real_video hash ../benchmark/real/videos/clip01_inspected.mov
```

`hash` prints the sha256, container, codec, size, fps, frame count, whether ingest will re-encode, and
`location_tags` — it must be `[]`. Videos stay out of git (`*.mp4`/`*.mov` are ignored); labels, the manifest and
the report are committed.

## 4. Label BLIND (before any model runs)

1. Extract the first frame exactly as SAM will see it (rotation applied) and measure the tape:
   `uv run python -m eventproof.validation.real_video frame ../benchmark/real/videos/clip01_inspected.mov /tmp/f01.png`.
   Coordinates are fractions of width/height, origin top-left (pixel x / width, pixel y / height).
2. Copy `TEMPLATE.json` to `benchmark/real/labels/<clip-stem>.json` and fill in:
   - `clip`, `clip_sha256` (from `hash`), `layout` (zone `inspection`, line `packing_entry` — keep these ids so the
     demo repair patch can apply), `rule_text`;
   - `objects`: every box, **those that cross packing first, in the order they cross**, then those that never cross;
     each with `description`, `crosses_packing`, `stood_still_s` (your estimate), `intended` (PASS/VIOLATION);
   - `expected_overall` (FAIL if any object is a VIOLATION), `labeled_by`, `labeled_at` (ISO with timezone), `notes`.
3. Validate and freeze:
   ```bash
   uv run python -m eventproof.validation.real_video check ../benchmark/real/labels --videos ../benchmark/real/videos
   uv run python -m eventproof.validation.real_video check ../benchmark/real/labels --videos ../benchmark/real/videos --freeze
   git add ../benchmark/real/labels && git commit -m "real-video labels (frozen before any model run)"
   ```
   `check` refuses a clip whose sha256 differs from its label and warns when a label disagrees with the ≥ 1.0 s
   process truth. `--freeze` writes `MANIFEST.json` (sha256 of every label file) once; it never overwrites. The commit
   timestamp is the public proof that labels predate the model outputs. Never edit a label after this point — `run`
   refuses if any label differs from the manifest.

## 5. Run

```bash
uv run python -m eventproof.validation.real_video run --labels ../benchmark/real/labels \
  --videos ../benchmark/real/videos --max-live-sam-calls 4 --max-live-muse-calls 1 \
  --out ../benchmark/real/report_real_v1.json
```

For each clip: the normal pipeline (sealed evidence under `artifacts/runs/<run_id>/`), then the verdict is compared
with the label twice — with the rule Muse compiled (**before repair**) and with that rule after the first accepted
Muse Spark repair of the recorded demo run (**after repair**; if the patch cannot apply to the clip's rule, the reason
is reported). Perceived objects are matched to labelled ones in order of crossing the packing line (non-crossing
objects by first appearance); unmatched labels are `missed`, unlabelled tracks are `extra` — both stay in the report.

Output: `report_real_v1.json` + `report_real_v1.md` with input hashes, run ids, evidence sha256, live vs cached calls,
the agreement table and the n = clips / no-tuning header. Existing reports are never overwritten.

## 6. Cost

- Each new clip = **1 SAM call** (billed per frame, ≥ 50) and at most **1 Muse compile** per distinct
  (rule text, layout) — with a fixed camera and one layout, a single compile serves all clips.
- Allowances are explicit: Muse uncached compiles are counted before anything runs; a call that would exceed either
  allowance stops the run with a clear error and no report. Completed clips stay cached.
- Re-runs on the same files are served from cache: **0 live calls, $0**. Record the calls in `docs/COSTS.md`.

## 7. Reporting rules

- Say "n = K real clips recorded by the participant"; no accuracy percentages or confidence claims beyond the counts.
- Keep real and synthetic numbers in separate tables. A disagreement is a finding, not something to fix and re-run:
  any change made after seeing these results needs new clips and new labels.
