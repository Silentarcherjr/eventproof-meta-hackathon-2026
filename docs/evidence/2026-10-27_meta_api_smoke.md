# Live Meta Model API smoke tests — 2026-10-27

Sanitized: no headers, no key, no raw payloads beyond the box prefix. Run from `backend/` with `MODEL_API_KEY` in `backend/.env`.

## SAM 3.1 (G0-04, G1-04)
- Command: `uv run python ../scripts/check_meta_api.py sam --video ../artifacts/challenge/736a7a46f42fdf5d/video.mp4 --prompt "blue box"`
- Input: synthetic canonical scene seed 0, 2 objects, 120 frames @ 15 fps, 640×360, H.264 (own work). scene sha256 `736a7a46…3d1c`, mp4 sha256 `8bfbce71…5404`.
- Response `resp_6ae1327d45ae42f0693e49df`, model `sam-3.1`, latency 8.09 s, 66 frame lines (frames 43–108), object ids {0, 1}, frame size 640×360, confidence on every record. Raw output cached under `artifacts/sam_cache/` (untracked).
- First parse FAILED (strict parser): the live mask token carries `c=` before `data=` (`<|mask;x=0;y=0;c=0.89…;data=43,44,!…|>`), which the docs' example omits. Parser fixed; 5 real lines committed as fixture `backend/tests/fixtures/sam/real_sam31_canonical0_2obj.txt`.
- SAM vs synthetic ground truth (same clip): 110/110 boxes matched (IoU ≥ 0.5), 0 missed, 0 extra; IoU median 1.000, min 0.977; box edge error ≤ 1 px; identity stable (GT 0→SAM 1, GT 1→SAM 0, no switches); confidence 0.899–0.958 (median 0.942). Rule verdict on SAM tracks = FAIL = process truth (outcome `correct`).
- Scope: one clean synthetic clip. Says nothing yet about occlusion, merges or real video.

## Muse Spark (G0-03)
- Command: `uv run python ../scripts/check_meta_api.py muse` (structured output, `response_format: json_schema`, strict).
- Request `chatcmpl-01a17fad-fba1-779f-b597-057f7f250065`, model `muse-spark-1.3`, latency 4.03 s, valid JSON with keys [city, street].
- Usage: 23 prompt tokens, 504 completion tokens of which 479 reasoning tokens (reasoning is spent even on trivial tasks — budget accordingly).

## Cost
Two live calls (1 SAM ≥ 50 frames billed, 1 Muse). Exact charge not read from the Billing page (UNKNOWN).
