# Session handoff

Written: 2026-10-27 (end of session 1, local). Overwrite at the end of every session, after push.

## State
- Gate G0. Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). Tag `hackathon-start-2026-10-27` = ec8e2f9. Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com> (repo-local git config; set it again in fresh cloud clones).
- Backend: DSL + tri-state evaluator + `/evaluate` API, 21 tests passing locally. CI workflow added (verify it is green on GitHub).
- Live Meta: BLOCKED until the participant claims credits and provides `MODEL_API_KEY` in `backend/.env` (or cloud secret).

## Next exact task
1. (done) CI green; G0-02, G0-05, G1-02 DONE_VERIFIED at ec8e2f9.
2. G2-01: `backend/eventproof/challenge/renderer.py` — deterministic 2D renderer (OpenCV or Pillow + ffmpeg pipe) that writes MP4 (H.264, ≥50 frames) + `ground_truth` TrackSet (`source="synthetic_ground_truth"`) from a seed. Same seed ⇒ same sha256. This clip also unblocks G0-04 (SAM smoke test).
3. G1-04: SAM adapter. Ask the participant before installing `meta-sam-parser`; otherwise write a documented fallback parser for the `<Nf>id<|box;…|>` wire format with fixtures.

## Human actions pending
- C-03: claim $150 Meta credits (form in guide §5), add card, set Spend Limit alert, then put key in `backend/.env`.
- C-02: ask in #questions: private repo during build OK? disclose AI coding assistants? license required? video exactly 3:00?
