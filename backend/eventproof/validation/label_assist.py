"""Label assistance: Muse Spark proposes labels for a clip, a person confirms or corrects them, and only the person's
labels count as truth (pre-registered in `benchmark/real/fresh_v1/PREREGISTRATION.md`).

    uv run python -m eventproof.validation.label_assist propose --set ../benchmark/real/fresh_v1 --max-live-calls 6
    uv run python -m eventproof.validation.label_assist compare --set ../benchmark/real/fresh_v1

`propose` reads each draft (`drafts/*.json`: rule, layout, clip hash; no objects) and writes `proposals/<clip>.json`.
Raw responses are cached by (clip sha256, prompt, model) and committed, so proposals recompute with 0 calls.
`compare` matches the proposals to the person's frozen labels (`labels/*.json`) by crossing time and reports how many
were accepted unchanged, corrected, deleted or missed.
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

from eventproof.meta.client import MetaSettings
from eventproof.validation.real_video import sha256_file
from eventproof.validation.spark_alone import SparkAlone

MATCH_S = 1.0  # a proposal and a label are the same car if their crossing times differ by at most this


def prompt(draft: dict, duration_s: float, fps: float, size: tuple[int, int]) -> str:
    lay = draft["layout"]
    zones = "\n".join(f"- zone '{z['zone']['id']}': {z['description']}; polygon (x, y as fractions of width, height, "
                      f"origin top-left): {z['zone']['polygon']}" for z in lay["zones"])
    lines = "\n".join(f"- line '{ln['line']['id']}': {ln['description']}; from {ln['line']['a']} to {ln['line']['b']}"
                      for ln in lay["lines"])
    return (f"You are helping a person label a video for an audit ({size[0]}x{size[1]} px, {fps:g} fps, "
            f"{duration_s:.1f} s). Rule being audited: {draft['rule_text']}\nLayout:\n{zones}\n{lines}\n"
            f"Watch the whole video. List every car that crosses the line '{draft['packing_line']}' during the video, "
            "in crossing order: a short visual description (colour, type, lane), the approximate crossing time in "
            "seconds, how long it stood completely still in the zone before crossing (waited_s, 0 if it never stopped), "
            "and PASS or VIOLATION under the rule. Cars that never cross do not need to be listed. overall is FAIL if "
            "any listed car is a VIOLATION, else PASS. A person will check every entry. Answer in JSON only.")


def _video_facts(video: Path) -> tuple[float, float, tuple[int, int]]:
    from eventproof.video.ingest import probe

    data = probe(video)
    v = next(s for s in data["streams"] if s.get("codec_type") == "video")
    return float(data["format"]["duration"]), float(Fraction(v["avg_frame_rate"])), (v["width"], v["height"])


def propose(set_dir: Path, judge: SparkAlone) -> list[dict]:
    out_dir = set_dir / "proposals"
    out_dir.mkdir(exist_ok=True)
    rows = []
    for p in sorted((set_dir / "drafts").glob("*.json")):
        draft = json.loads(p.read_text())
        video = set_dir / "videos" / draft["clip"]
        if sha256_file(video) != draft["clip_sha256"]:
            raise SystemExit(f"{video} does not match its draft")
        rec = judge.judge(video, prompt(draft, *_video_facts(video)), 0)
        prop = {"schema": "eventproof-label-proposal/1", "clip": draft["clip"], "clip_sha256": draft["clip_sha256"],
                "model": rec["model"], "response_id": rec["response_id"], "error": rec["error"],
                "crossings": (rec["parsed"] or {}).get("crossings", []), "notes": (rec["parsed"] or {}).get("notes", "")}
        (out_dir / p.name).write_text(json.dumps(prop, indent=1) + "\n")
        rows.append({"clip": draft["clip"], "cached": rec["cached"], "proposed": len(prop["crossings"])})
    return rows


def _cross_s(obj: dict) -> float | None:
    return obj.get("cross_s", obj.get("approx_cross_time_s"))


def compare(set_dir: Path) -> dict:
    clips, tot = [], {"proposed": 0, "labelled": 0, "accepted": 0, "corrected": 0, "deleted": 0, "missed": 0}
    for p in sorted((set_dir / "labels").glob("*.json")):
        if p.name == "MANIFEST.json":
            continue
        lab = json.loads(p.read_text())
        prop = json.loads((set_dir / "proposals" / p.name).read_text())
        truth = [o for o in lab["objects"] if o.get("crosses_packing")]
        free = list(range(len(truth)))
        acc = cor = 0
        for c in prop["crossings"]:
            best = min(free, key=lambda i: abs(_cross_s(truth[i]) - c["approx_cross_time_s"]), default=None)
            if best is None or abs(_cross_s(truth[best]) - c["approx_cross_time_s"]) > MATCH_S:
                continue
            free.remove(best)
            if truth[best]["intended"] == c["verdict"]:
                acc += 1
            else:
                cor += 1
        row = {"clip": lab["clip"], "proposed": len(prop["crossings"]), "labelled": len(truth), "accepted": acc,
               "corrected": cor, "deleted": len(prop["crossings"]) - acc - cor, "missed": len(free)}
        clips.append(row)
        for k in tot:
            tot[k] += row[k]
    return {"schema": "eventproof-label-assist/1", "preregistration": "benchmark/real/fresh_v1/PREREGISTRATION.md",
            "match_window_s": MATCH_S, "total": tot, "clips": clips}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--set", type=Path, required=True)
    p.add_argument("--max-live-calls", type=int, default=0)
    c = sub.add_parser("compare")
    c.add_argument("--set", type=Path, required=True)
    c.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.cmd == "propose":
        judge = SparkAlone(MetaSettings.from_env(), cache_dir=a.set / "proposals" / "cache", max_live_calls=a.max_live_calls)
        print(json.dumps(propose(a.set, judge), indent=1))
    else:
        rep = compare(a.set)
        if a.out:
            a.out.write_text(json.dumps(rep, indent=1) + "\n")
        print(json.dumps(rep["total"]))


if __name__ == "__main__":
    main()
