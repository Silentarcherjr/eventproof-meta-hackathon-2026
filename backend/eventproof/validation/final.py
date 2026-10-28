"""Final independent test set: frozen before it is ever evaluated, never used to accept or reject a repair.

Three tiers of data, each with its own job:
- DEV (seeds 0-29)               the counterexample search and the repair proposers look at it
- HOLDOUT holdout_v2 (20000-...)  the grader accepts/rejects proposals on it (so it takes part in selection)
- FINAL final_v1 (this module)    report-only: evaluated once, after every decision is recorded

final_v1 has two splits:
- in_distribution: the five Challenge families at seeds 40000-40039 (never generated before this freeze);
- shift: three families that exist ONLY here, so no rule, threshold or repair was designed against them:
    stop_and_go  a slow belt (in-zone transit 1.0-2.0 s) with a stop of 0.3-2.4 s at the station
    two_stops    two boxes: one stops 1.2-2.0 s, the other 0.3-0.9 s (the scene is a FAIL)
    fps_shift    the canonical scene re-timed to 10 or 24 fps (time must come from timestamps, not frames)

Process truth is the same as everywhere else (`challenge.truth`: a box that crosses into packing must have stood
still >= 1.0 s at the station). Nothing in this module encodes a verdict.

The grader, the proposers, the studio and the API must not import this module (tests check it).

    uv run python -m eventproof.validation.final --write ../benchmark/final/final_v1.json   # once; refuses to overwrite
    uv run python -m eventproof.validation.final                                           # verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from eventproof.challenge.families import FAMILIES, X0, X1, ZONE_WIDTH
from eventproof.challenge.scene import (
    INSPECTION,
    LANES,
    PACKING_LINE,
    SceneObject,
    SceneSpec,
    canonical_scene,
    conveyor_path,
)

FINAL_NAME = "final_v1"
FINAL_SEEDS = range(40_000, 40_040)
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "benchmark" / "final" / f"{FINAL_NAME}.json"


def stop_and_go(seed: int) -> SceneSpec:
    rng = np.random.default_rng([seed, 11])
    fps = 15.0
    transit_s = float(rng.uniform(1.0, 2.0))  # moving time inside the zone, excluding the stop
    stop_s = float(rng.uniform(0.3, 2.4))
    travel = round(transit_s * fps * (X1 - X0) / ZONE_WIDTH)
    start = int(rng.integers(0, 10))
    lane = LANES[int(rng.integers(0, len(LANES)))]
    stop = round(stop_s * fps)
    obj = SceneObject(object_id=0, color="blue", waypoints=conveyor_path(rng, start, lane, stop, travel, X0, X1))
    return SceneSpec(seed=seed, fps=fps, n_frames=max(50, start + travel + stop + 5), zones=[INSPECTION],
                     lines=[PACKING_LINE], objects=[obj], family="stop_and_go",
                     notes=f"transit_in_zone_s={transit_s:.3f} stop_s={stop_s:.3f}")


def two_stops(seed: int) -> SceneSpec:
    rng = np.random.default_rng([seed, 12])
    fps = 15.0
    lanes = rng.permutation(len(LANES))[:2]
    stops = (float(rng.uniform(1.2, 2.0)), float(rng.uniform(0.3, 0.9)))
    objs = []
    end = 0
    for oid, (lane_i, stop_s) in enumerate(zip(lanes, stops, strict=True)):
        travel = int(rng.integers(round(2.5 * fps), round(3.5 * fps)))
        start = int(rng.integers(0, 25))
        wps = conveyor_path(rng, start, LANES[int(lane_i)], round(stop_s * fps), travel)
        objs.append(SceneObject(object_id=oid, color="blue", waypoints=wps))
        end = max(end, wps[-1].frame)
    return SceneSpec(seed=seed, fps=fps, n_frames=max(50, end + 5), zones=[INSPECTION], lines=[PACKING_LINE],
                     objects=objs, family="two_stops", notes=f"stops_s={stops[0]:.3f},{stops[1]:.3f}")


def fps_shift(seed: int) -> SceneSpec:
    rng = np.random.default_rng([seed, 13])
    fps = float((10.0, 24.0)[int(rng.integers(0, 2))])
    base = canonical_scene(int(rng.integers(0, 2**31)), fps=fps, n_frames=round(8.0 * fps))
    return base.model_copy(update={"seed": seed, "family": "fps_shift", "notes": f"fps={fps:g}"})


SHIFT_FAMILIES: dict[str, Callable[[int], SceneSpec]] = {
    "stop_and_go": stop_and_go,
    "two_stops": two_stops,
    "fps_shift": fps_shift,
}
assert not set(SHIFT_FAMILIES) & set(FAMILIES), "shift families must not exist in the Challenge world"


def generator(split: str, family: str) -> Callable[[int], SceneSpec]:
    return (FAMILIES if split == "in_distribution" else SHIFT_FAMILIES)[family]


class FinalCase(BaseModel):
    split: str
    family: str
    seed: int
    scene_sha256: str


class FinalManifest(BaseModel):
    name: str
    seed_range: tuple[int, int]
    splits: dict[str, list[str]]
    cases: list[FinalCase]
    cases_sha256: str
    note: str = ("Final independent test set. Report-only: frozen before any evaluation, never used to accept, "
                 "reject, rank or tune a repair. See benchmark/final/PREREGISTRATION.md.")


class FinalDrift(RuntimeError):
    pass


def _cases_hash(cases: list[FinalCase]) -> str:
    blob = json.dumps([c.model_dump() for c in cases], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def build_manifest() -> FinalManifest:
    splits = {"in_distribution": sorted(FAMILIES), "shift": sorted(SHIFT_FAMILIES)}
    cases = [FinalCase(split=sp, family=f, seed=s, scene_sha256=generator(sp, f)(s).scene_hash())
             for sp, fams in splits.items() for f in fams for s in FINAL_SEEDS]
    return FinalManifest(name=FINAL_NAME, seed_range=(FINAL_SEEDS.start, FINAL_SEEDS.stop - 1), splits=splits,
                         cases=cases, cases_sha256=_cases_hash(cases))


def manifest_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen(path: Path = DEFAULT_PATH) -> tuple[FinalManifest, list[tuple[FinalCase, SceneSpec]]]:
    m = FinalManifest.model_validate_json(path.read_text())
    if _cases_hash(m.cases) != m.cases_sha256:
        raise FinalDrift("manifest case list does not match its own cases_sha256")
    out = []
    for c in m.cases:
        s = generator(c.split, c.family)(c.seed)
        if s.scene_hash() != c.scene_sha256:
            raise FinalDrift(f"{c.split}/{c.family}/{c.seed}: regenerated scene differs from the frozen manifest")
        out.append((c, s))
    return m, out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", type=Path, help="freeze the manifest here (refuses to overwrite)")
    ap.add_argument("--verify", type=Path, default=DEFAULT_PATH)
    args = ap.parse_args()
    if args.write:
        if args.write.exists():
            raise SystemExit(f"{args.write} exists; a frozen test set is never regenerated in place")
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(build_manifest().model_dump_json(indent=2) + "\n")
        print(json.dumps({"written": str(args.write), "sha256": manifest_sha256(args.write)}))
        return
    m, cases = load_frozen(args.verify)
    print(json.dumps({"verified": str(args.verify), "cases": len(cases), "sha256": manifest_sha256(args.verify)}))


if __name__ == "__main__":
    main()
