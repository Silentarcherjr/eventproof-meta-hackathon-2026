"""Evaluate recorded repair decisions on the frozen final test set (report-only), as pre-registered in
`benchmark/final/PREREGISTRATION.md`.

Inputs are decision files that already exist and are hashed in the pre-registration; every proposal in them is
evaluated (accepted and rejected), nothing is selected or tuned here. The report records the sha256 of each input,
of the manifest, and the git commit, and refuses to overwrite an earlier report.

    uv run python -m eventproof.validation.evaluate --out ../benchmark/final/report_final_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from eventproof.challenge.runner import CaseResult, Perceiver, mock_perceiver, run_case
from eventproof.repair.patch import RulePatch
from eventproof.repair.proposer import DetectorConfig
from eventproof.schemas.rules import VisualRule
from eventproof.validation.final import DEFAULT_PATH, FinalCase, load_frozen, manifest_sha256

ROOT = Path(__file__).resolve().parents[3]
MUSE_RUN = "docs/evidence/runs/20261028T023754Z-a922b5bb"
SOURCES = (  # (label, decision file, detector) exactly as pre-registered
    ("muse-studio-run", f"{MUSE_RUN}/challenge/repair_muse.json", "run-rule"),
    ("baseline-drive_through-0", "benchmark/repairs/drive_through-0.json", "template"),
    ("baseline-brief_stop-5", "benchmark/repairs/brief_stop-5.json", "template"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 4), round(c + h, 4))


def sign_test(fixed: int, regressed: int) -> float:
    """Two-sided exact binomial test on the discordant pairs (p = 0.5)."""
    n = fixed + regressed
    if n == 0:
        return 1.0
    k = min(fixed, regressed)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return round(min(1.0, 2 * tail), 6)


class SplitMetrics(BaseModel):
    n: int
    correct: int
    accuracy_ci95: tuple[float, float]
    false_pass: int
    false_alarm: int
    abstained: int
    by_family: dict[str, dict[str, int]]


class PatchResult(BaseModel):
    source: str
    proposal_id: str
    proposer: str
    patch_description: str
    grader_accepted: bool
    holdout_v2: str  # the grader's own before -> after, copied from the decision file
    splits: dict[str, SplitMetrics]
    fixed: dict[str, int]
    regressed: dict[str, int]
    sign_test_p: dict[str, float]
    regressed_cases: list[str]


def split_metrics(results: list[CaseResult]) -> SplitMetrics:
    fam: dict[str, Counter] = {}
    for r in results:
        fam.setdefault(r.family, Counter())[r.outcome] += 1
    k = sum(r.outcome == "correct" for r in results)
    return SplitMetrics(n=len(results), correct=k, accuracy_ci95=wilson(k, len(results)),
                        false_pass=sum(r.detector_verdict == "PASS" and r.intended == "FAIL" for r in results),
                        false_alarm=sum(r.detector_verdict == "FAIL" and r.intended == "PASS" for r in results),
                        abstained=sum(r.outcome == "abstained" for r in results),
                        by_family={f: dict(c) for f, c in sorted(fam.items())})


def _detector(kind: str, decisions_file: dict) -> DetectorConfig:
    if kind == "run-rule":
        ev = json.loads((ROOT / MUSE_RUN / "evidence.json").read_text())
        return DetectorConfig(rule=VisualRule.model_validate(ev["rule"]["compiled_rule"]))
    return DetectorConfig(**decisions_file["detector_before"])


def _run(det: DetectorConfig, cases: list[tuple[FinalCase, object]], patch: RulePatch | None,
         perceiver: Perceiver) -> dict[str, list[CaseResult]]:
    out: dict[str, list[CaseResult]] = {}
    for c, scene in cases:
        out.setdefault(c.split, []).append(run_case(scene, det.rule_for(scene, patch), perceiver))
    return out


def evaluate(manifest_path: Path = DEFAULT_PATH, perceiver: Perceiver = mock_perceiver) -> dict:
    manifest, cases = load_frozen(manifest_path)
    report: dict = {"final_set": manifest.name, "manifest_sha256": manifest_sha256(manifest_path),
                    "perception": "mock (NOT SAM)", "inputs": {}, "baselines": {}, "patches": []}
    for label, rel, kind in SOURCES:
        path = ROOT / rel
        data = json.loads(path.read_text())
        report["inputs"][label] = {"file": rel, "sha256": sha256(path), "proposals": len(data["decisions"])}
        det = _detector(kind, data)
        before = _run(det, cases, None, perceiver)
        report["baselines"][label] = {sp: split_metrics(rs).model_dump() for sp, rs in before.items()}
        for d in data["decisions"]:
            patch = RulePatch.model_validate(d["proposal"]["patch"])
            after = _run(det, cases, patch, perceiver)
            fixed, regressed, p, reg_cases = {}, {}, {}, []
            for sp in before:
                pairs = list(zip(before[sp], after[sp], strict=True))
                fixed[sp] = sum(a.outcome == "correct" and b.outcome != "correct" for b, a in pairs)
                regressed[sp] = sum(b.outcome == "correct" and a.outcome != "correct" for b, a in pairs)
                reg_cases += [f"{sp}/{b.family}/{b.seed}" for b, a in pairs
                              if b.outcome == "correct" and a.outcome != "correct"]
                p[sp] = sign_test(fixed[sp], regressed[sp])
            hb, ha = d["holdout_before"], d.get("holdout_after")
            report["patches"].append(PatchResult(
                source=label, proposal_id=d["proposal"]["proposal_id"], proposer=d["proposal"]["proposer"],
                patch_description=d["patch_description"], grader_accepted=d["accepted"],
                holdout_v2=f"{hb['correct']}/{hb['n']} -> {ha['correct']}/{ha['n']}" if ha else "not graded (unsafe)",
                splits={sp: split_metrics(rs) for sp, rs in after.items()}, fixed=fixed, regressed=regressed,
                sign_test_p=p, regressed_cases=reg_cases[:40]).model_dump())
    return report


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; the first final report is kept (see PREREGISTRATION.md)")
    report = evaluate()
    report["code_commit"] = _git_head()
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"written": str(args.out), "patches": len(report["patches"])}))


if __name__ == "__main__":
    main()
