# Traffic lab browser verification

Verified locally in the in-app browser against this worktree, using the production Next build.
The participant selected alternate ports to preserve the already-running main checkout:
studio `http://localhost:3001/lab`, backend `http://127.0.0.1:8001`, `EVENTPROOF_MODE=local`.
Both live model allowances were explicitly zero, with no API key configured.

- Studio's Traffic lab nav link opened `/lab`; summary loaded from the recorded report.
- Rolling stop at Spark's defaults: contract VIOLATION, Spark PASS, your rule PASS.
- Moved the speed slider to 0.01: your verdict became VIOLATION; the explanation identified standing-still speed.
- Wrong way with travel-direction-only: contract VIOLATION, Spark/your rule PASS.
  Enabled either direction: your verdict became VIOLATION; the explanation identified crossing direction.
- Enabled any motion, then restored contract choices: verdicts updated without a model call.
- Submitted the prefilled sentence: rendered `recorded response`, original assumptions and all eight scene results;
  rolling stop and wrong way were identified as disagreements. No new sealed evaluation was run.
- Main and pair videos loaded with `readyState=4`, 480-pixel width and no media error.
  Main playback advanced with `paused=false`; durations were 8.3 s / 8.2 s / 8.2 s for the observed clips.
- Browser warning/error log was empty. Backend returned 200 for scene, judge, pair and recorded-compile requests, and 206 for video range requests.

`lab-browser.png` captures the rolling-stop flip, three verdict columns, minimal pair and recorded compilation.
New-wording live compilation was verified with a fake compiler and a zero-budget test, never a paid model call.
