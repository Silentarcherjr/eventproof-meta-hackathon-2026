"""Evidence ledger: one exportable manifest that lets a reviewer re-check everything a run claims.

For a run folder it records the sha256 and size of every file (video, tracks, rule, evidence, Challenge and
Repair outputs), the model ids and request/response ids behind each model output (and whether each was live
or cached), the hidden-holdout manifest each repair decision was graded on, and the sealed evidence hash.
`ledger_sha256` covers the rest of the ledger (canonical JSON).

    uv run python -m eventproof.ledger build <run_id>             # writes <run>/ledger.json
    uv run python -m eventproof.ledger verify <run folder>         # re-hashes every file; exit 1 on any mismatch
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from eventproof import __version__
from eventproof.pipeline import RUNS_DIR, Evidence, verify_evidence_file

LEDGER_SCHEMA = "eventproof-ledger/1"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _canon_sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _load(p: Path) -> dict | None:
    return json.loads(p.read_text()) if p.is_file() else None


def build(run_dir: Path) -> dict:
    ev = Evidence.model_validate_json((run_dir / "evidence.json").read_text())
    files = {str(p.relative_to(run_dir)): {"sha256": _sha(p), "bytes": p.stat().st_size}
             for p in sorted(run_dir.rglob("*")) if p.is_file() and p.name != "ledger.json"}
    models = [{"stage": "rule", "model": ev.rule.model, "request_ids": ev.rule.request_ids, "cached": ev.rule.cached,
               "usage": ev.rule.usage}]
    if ev.perception:
        models.append({"stage": "perception", "model": ev.perception.model, "source_ref": ev.perception.source_ref,
                       "cached": ev.perception.cached, "tracks_sha256": ev.perception.tracks_sha256})
    ch = run_dir / "challenge"
    repairs = {}
    for who in ("muse", "baseline"):
        r = _load(ch / f"repair_{who}.json")
        if not r:
            continue
        repairs[who] = {
            "proposer": r["proposer"],
            "holdout": sorted({(d["holdout_name"], d["holdout_manifest_sha256"]) for d in r["decisions"]}),
            "decisions": [{"proposal_id": d["proposal"]["proposal_id"], "patch": d["patch_description"],
                           "accepted": d["accepted"], "previous_rule_hash": d["previous_rule_hash"],
                           "patched_rule_hash": d["patched_rule_hash"]} for d in r["decisions"]],
        }
        for t in r.get("trace", {}).get("rounds", []):
            models.append({"stage": f"repair round {t['round']}", "model": r["proposer"], "request_ids": [t["request_id"]],
                           "cached": t["cached"]})
    sam = _load(ch / "sam_confirm.json")
    challenge = _load(ch / "challenge.json")
    ledger = {
        "schema": LEDGER_SCHEMA, "eventproof_version": __version__, "run_id": ev.run_id, "created_at": ev.created_at,
        "status": ev.status, "evidence_sha256": ev.evidence_sha256,
        "evidence_seal_valid": verify_evidence_file(run_dir / "evidence.json"),
        "inputs": {"video_sha256": ev.video.sha256, "video_original_sha256": ev.video.original_sha256,
                   "rule_text_sha256": ev.rule.text_sha256, "rule_hash": ev.rule.rule_hash},
        "verdict": ev.result.overall if ev.result else None,
        "models": models,
        "challenge": None if not challenge else {
            "perception": challenge["perception"], "suite_cases": challenge["suite_cases"],
            "failures": challenge["failures"],
            "counterexample": challenge["counterexample"] and {k: challenge["counterexample"][k]
                                                               for k in ("family", "seed", "outcome")},
            "sam_confirm": sam and {"scene_sha256": sam["scene_sha256"], "still_fails_with_sam": sam["still_fails_with_sam"],
                                    "live_sam_calls": sam["live_sam_calls"]}},
        "repairs": repairs,
        "files": files,
    }
    ledger["ledger_sha256"] = _canon_sha(ledger)
    return ledger


def verify(run_dir: Path, ledger: dict | None = None) -> list[str]:
    """Problems found (empty = everything matches): ledger hash, evidence seal, and every listed file."""
    led = ledger or json.loads((run_dir / "ledger.json").read_text())
    body = {k: v for k, v in led.items() if k != "ledger_sha256"}
    problems = [] if _canon_sha(body) == led.get("ledger_sha256") else ["ledger_sha256 does not match its content"]
    if not verify_evidence_file(run_dir / "evidence.json"):
        problems.append("evidence.json seal is broken")
    for name, f in led["files"].items():
        p = run_dir / name
        if not p.is_file():
            problems.append(f"missing: {name}")
        elif _sha(p) != f["sha256"]:
            problems.append(f"changed: {name}")
    return problems


def write(run_id: str, runs_dir: Path | None = None) -> dict:
    run_dir = (runs_dir or RUNS_DIR) / run_id
    led = build(run_dir)
    (run_dir / "ledger.json").write_text(json.dumps(led, indent=2) + "\n")
    return led


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("run_id")
    v = sub.add_parser("verify")
    v.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    if args.cmd == "build":
        led = write(args.run_id)
        print(json.dumps({"ledger_sha256": led["ledger_sha256"], "files": len(led["files"])}))
        return
    problems = verify(args.run_dir)
    print(json.dumps({"run_dir": str(args.run_dir), "ok": not problems, "problems": problems}, indent=2))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
