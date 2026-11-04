"""Offline traffic benchmark export. Frozen directories are never overwritten.

    uv run python -m eventproof.challenge.traffic_export freeze --out ../benchmark/traffic_sim/v1
    uv run python -m eventproof.challenge.traffic_export verify --out ../benchmark/traffic_sim/v1

Export computes geometry labels, NOT engine scores; holdout videos/labels are produced without
feeding any holdout scene to a detector, minimizer, or repairer. Verification checks file hashes
without evaluating rules. Raw RGB hashes, not MP4 hashes across encoder versions, are the portable
pixel contract inherited from the existing renderer. An interrupted export leaves an incomplete
new directory, which must be investigated; the command will not overwrite it on a retry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from eventproof.challenge.render import render_scene, sha256_file
from eventproof.challenge.traffic import (
    DEV_SEEDS,
    HOLDOUT_SEEDS,
    TRAFFIC_FAMILIES,
    TRAFFIC_GENERATOR,
    perfect_tracks,
    scene_truth,
)


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def _digest(value) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def _export_case(scene, root: Path, encode: bool) -> dict:
    rendered = render_scene(scene, root, encode=encode)
    directory = rendered.directory
    # Visibility-aware ground_truth.json is retained alongside the complete oracle tracks.
    (directory / "tracks.json").write_text(perfect_tracks(scene).model_dump_json() + "\n")
    labels = {"source": "synthetic", "scene_sha256": scene.scene_hash(),
              "rule": "Every car must wait at least 1.5 seconds in the waiting zone before crossing the stop line.",
              "truth_version": "traffic-truth/1", "cars": [t.model_dump() for t in scene_truth(scene)]}
    (directory / "labels.json").write_text(_json(labels))
    files = ["scene.json", "ground_truth.json", "tracks.json", "labels.json"]
    if encode:
        files.append("video.mp4")
    hashes = {name: sha256_file(directory / name) for name in files}
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest.update(source="synthetic", files_sha256=hashes, truth_version="traffic-truth/1")
    (directory / "manifest.json").write_text(_json(manifest))
    return {"family": scene.family, "seed": scene.seed, "scene_sha256": scene.scene_hash(),
            "directory": directory.name, "manifest_sha256": sha256_file(directory / "manifest.json")}


def freeze(out: Path, encode: bool = True, *, dev_seeds=DEV_SEEDS, holdout_seeds=HOLDOUT_SEEDS,
           families=None) -> dict:
    """Create a new immutable release; optional small seed ranges are for exporter tests only."""
    dev_seeds, holdout_seeds = tuple(dev_seeds), tuple(holdout_seeds)
    if set(dev_seeds) & set(holdout_seeds):
        raise ValueError("development and holdout seeds overlap")
    families = sorted(TRAFFIC_FAMILIES if families is None else families)
    if not families or not dev_seeds or not holdout_seeds:
        raise ValueError("both splits and at least one family are required")
    if any(f not in TRAFFIC_FAMILIES for f in families):
        raise ValueError("unknown traffic family")
    # Validate before creating anything; mkdir without exist_ok also protects against races.
    out.mkdir(parents=True, exist_ok=False)
    release = {"generator": TRAFFIC_GENERATOR, "source": "synthetic", "engine_evaluation": "not run",
               "encoded_video": encode, "splits": {}}
    for split, seeds in (("dev", dev_seeds), ("holdout", holdout_seeds)):
        root = out / split
        root.mkdir()
        cases = [_export_case(TRAFFIC_FAMILIES[family](seed), root, encode)
                 for family in families for seed in seeds]
        manifest = {"name": f"traffic_sim_v1_{split}", "source": "synthetic", "families": families,
                    "seeds": list(seeds), "cases": cases, "cases_sha256": _digest(cases),
                    "usage": "development" if split == "dev" else "frozen; never used for development"}
        (root / "manifest.json").write_text(_json(manifest))
        release["splits"][split] = {"cases": len(cases), "manifest_sha256": sha256_file(root / "manifest.json")}
    (out / "manifest.json").write_text(_json(release))
    return release


def verify(out: Path, require_video: bool = True) -> dict:
    """Check hashes of the frozen bytes, no trajectory generation and no detector execution."""
    release = json.loads((out / "manifest.json").read_text())
    if release["source"] != "synthetic" or release["generator"] != TRAFFIC_GENERATOR:
        raise ValueError("not a traffic synthetic release")
    seeds_by_split = {}
    for split in ("dev", "holdout"):
        root = out / split
        if sha256_file(root / "manifest.json") != release["splits"][split]["manifest_sha256"]:
            raise ValueError(f"{split} manifest hash drift")
        manifest = json.loads((root / "manifest.json").read_text())
        seeds_by_split[split] = set(manifest["seeds"])
        if _digest(manifest["cases"]) != manifest["cases_sha256"]:
            raise ValueError(f"{split} case-list hash drift")
        if len(manifest["cases"]) != release["splits"][split]["cases"]:
            raise ValueError(f"{split} case count drift")
        for case in manifest["cases"]:
            # Directory identifiers are hashes, not arbitrary paths supplied by a manifest.
            dirname = case["directory"]
            if len(dirname) != 16 or any(c not in "0123456789abcdef" for c in dirname):
                raise ValueError("invalid case directory")
            directory = root / dirname
            if sha256_file(directory / "manifest.json") != case["manifest_sha256"]:
                raise ValueError(f"{split}/{dirname} manifest hash drift")
            cm = json.loads((directory / "manifest.json").read_text())
            if cm["scene_sha256"] != case["scene_sha256"]:
                raise ValueError("scene hash does not match split manifest")
            for name, expected in cm["files_sha256"].items():
                if name not in {"scene.json", "ground_truth.json", "tracks.json", "labels.json", "video.mp4"}:
                    raise ValueError("unexpected artifact name")
                path = directory / name
                if name == "video.mp4" and not require_video and not path.exists():
                    continue  # MP4s are local generated artifacts; JSON and hashes are tracked.
                if sha256_file(path) != expected:
                    raise ValueError(f"{split}/{dirname}/{name} hash drift")
    if seeds_by_split["dev"] & seeds_by_split["holdout"]:
        raise ValueError("frozen splits overlap")
    return release


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["freeze", "verify"])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--allow-missing-video", action="store_true", help="verify tracked JSON without local MP4s")
    args = ap.parse_args()
    result = freeze(args.out) if args.command == "freeze" else verify(args.out, not args.allow_missing_video)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
