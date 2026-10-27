"""Frozen hidden holdout: scenes generated from a separate seed range, hashed, committed before any repair.

Seed ranges are disjoint by construction:
- DEV_SEEDS (0-29)            challenge cases; the counterexample search and the repairer may look at them
- HOLDOUT_SEEDS (20000-20039) hidden; only the grader in `eventproof.repair.grader` loads them

The committed manifest (`benchmark/holdout/holdout_v1.json`) lists every case with its scene hash.
`load_frozen` regenerates each scene and refuses to grade if any hash drifted (a generator change
would silently turn the holdout into a different test set).

    uv run python -m eventproof.challenge.holdout --write ../benchmark/holdout/holdout_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.runner import DEV_SEEDS  # noqa: F401  re-exported next to HOLDOUT_SEEDS
from eventproof.challenge.scene import SceneSpec

HOLDOUT_SEEDS = range(20_000, 20_040)  # 10000-10039 were touched by a design scan; not used
HOLDOUT_NAME = "holdout_v1"
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "benchmark" / "holdout" / f"{HOLDOUT_NAME}.json"


class HoldoutCase(BaseModel):
    family: str
    seed: int
    scene_sha256: str


class HoldoutManifest(BaseModel):
    name: str
    seed_range: tuple[int, int]
    families: list[str]
    cases: list[HoldoutCase]
    cases_sha256: str
    note: str = "Hidden holdout. Never passed to a repair proposer; graded only after a proposal is fixed."


class HoldoutDrift(RuntimeError):
    pass


def _cases_hash(cases: list[HoldoutCase]) -> str:
    blob = json.dumps([c.model_dump() for c in cases], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def build_manifest() -> HoldoutManifest:
    fams = sorted(FAMILIES)
    cases = [HoldoutCase(family=f, seed=s, scene_sha256=FAMILIES[f](s).scene_hash()) for f in fams for s in HOLDOUT_SEEDS]
    return HoldoutManifest(name=HOLDOUT_NAME, seed_range=(HOLDOUT_SEEDS.start, HOLDOUT_SEEDS.stop - 1),
                           families=fams, cases=cases, cases_sha256=_cases_hash(cases))


def manifest_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen(path: Path = DEFAULT_PATH) -> tuple[HoldoutManifest, list[SceneSpec]]:
    """Load the committed manifest and regenerate its scenes, verifying every hash."""
    m = HoldoutManifest.model_validate_json(path.read_text())
    if _cases_hash(m.cases) != m.cases_sha256:
        raise HoldoutDrift("manifest case list does not match its own cases_sha256")
    scenes = []
    for c in m.cases:
        s = FAMILIES[c.family](c.seed)
        if s.scene_hash() != c.scene_sha256:
            raise HoldoutDrift(f"{c.family}/{c.seed}: regenerated scene hash differs from the frozen manifest")
        scenes.append(s)
    return m, scenes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", type=Path, help="freeze a new manifest here (refuses to overwrite)")
    ap.add_argument("--verify", type=Path, default=DEFAULT_PATH)
    args = ap.parse_args()
    if args.write:
        if args.write.exists():
            raise SystemExit(f"{args.write} exists; a frozen holdout is never regenerated in place")
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(build_manifest().model_dump_json(indent=2) + "\n")
        print(json.dumps({"written": str(args.write), "sha256": manifest_sha256(args.write)}))
        return
    m, scenes = load_frozen(args.verify)
    print(json.dumps({"verified": str(args.verify), "cases": len(scenes), "sha256": manifest_sha256(args.verify)}))


if __name__ == "__main__":
    main()
