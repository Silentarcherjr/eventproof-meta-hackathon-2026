# Recorded demo run

`showcase/` holds one complete run recorded on 2026-10-28 with live Muse Spark and SAM 3.1: the clip (synthetic, made by
the project's renderer), its evidence and ledger, Challenge and Repair outputs, and the recorded model responses
(`muse_cache/`, `sam_cache/`: response bodies and request ids only, no keys or headers). With it the studio replays the
run with no API key and no credits:

    EVENTPROOF_ARTIFACTS=./demo/showcase docker compose up --build
    open http://localhost:3000/?run=20261028T023754Z-a922b5bb

Verify it was not edited: `cd backend && uv run python -m eventproof.ledger verify ../demo/showcase/runs/20261028T023754Z-a922b5bb`
(do this before clicking around: rerunning Challenge or Repair in the studio rewrites their output files).
