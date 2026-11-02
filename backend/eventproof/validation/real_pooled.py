"""Pooled real-traffic results (pre-registered in `benchmark/real/traffic_v2/PREREGISTRATION.md`): every labelled car of the
Novi Sad and Wroclaw clips, judged on the committed SAM 3.1 tracks by three readings of the same sentence (Muse Spark's
compiled rule, the same rule + the synthetic-accepted repair, Muse Wonder's rule), next to Muse Spark judging from the
video alone. Recomputed from committed files only (no video, no API):

    uv run python -m eventproof.validation.real_pooled > ../benchmark/real/POOLED.json
"""

from __future__ import annotations

import json
import sys

from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import MetaSettings
from eventproof.meta.muse_rules import MuseRuleCompiler
from eventproof.repair.patch import apply_patch
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.evaluate import ROOT, wilson
from eventproof.validation.real_video import load_labels, load_repair

SETS = (  # (folder, real_video report, spark-alone report)
    ("benchmark/real/novisad", "report_novisad.json", "../spark_alone/report.json"),
    ("benchmark/real/traffic_v2", "report_wroclaw.json", "spark_alone_wroclaw.json"),
)
WONDER_CACHE = ROOT / "benchmark" / "ambiguity" / "cache" / "muse-wonder-1.0"


def _wonder_rule(text: str, layout) -> VisualRule:
    import dataclasses

    s = dataclasses.replace(MetaSettings.from_env(), muse_model="muse-wonder-1.0", api_key=None)
    return MuseRuleCompiler(s, cache_dir=WONDER_CACHE).compile(text, layout).rule  # cache only (no key)


def pooled() -> dict:
    repair = load_repair()
    readers = ("muse_spark_rule", "muse_spark_rule_plus_synthetic_repair", "muse_wonder_rule")
    tally = {k: {"objects_right": 0, "clips_right": 0, "abstained": 0} for k in readers}
    n_obj = n_clips = 0
    spark_alone = {"runs": 0, "overall_right": 0, "counts_exact": 0}
    clips = []
    for folder, rep_name, sa_name in SETS:
        d = ROOT / folder
        labels = {lb.clip: lb for _, lb in load_labels(d / "labels")}
        rep = json.loads((d / rep_name).read_text())
        for c in rep["clips"]:
            lab = labels[c["clip"]]
            run = d / "runs" / c["run_id"]
            muse = VisualRule.model_validate(json.loads((run / "evidence.json").read_text())["rule"]["compiled_rule"])
            tracks = TrackSet.model_validate_json((run / "tracks.json").read_text())
            rules = {readers[0]: muse, readers[1]: apply_patch(muse, repair.patch),
                     readers[2]: _wonder_rule(lab.rule_text, lab.layout)}
            row = {"clip": c["clip"], "labelled": len(c["objects"]["labeled"]), "expected": lab.expected_overall}
            for k, rule in rules.items():
                r = evaluate(rule, tracks)
                v = {o.object_id: o.verdict for o in r.objects}
                right = sum(v.get(o["matched_object_id"]) == o["intended"] for o in c["objects"]["labeled"])
                unk = sum(v.get(o["matched_object_id"]) == "UNKNOWN" for o in c["objects"]["labeled"])
                tally[k]["objects_right"] += right
                tally[k]["abstained"] += unk
                tally[k]["clips_right"] += r.overall == lab.expected_overall
                row[k] = {"objects_right": right, "abstained": unk, "overall": r.overall}
            n_obj += row["labelled"]
            n_clips += 1
            clips.append(row)
        sa = json.loads((d / sa_name).read_text())
        for c in sa["clips"]:
            for r in c["runs"]:
                spark_alone["runs"] += 1
                spark_alone["overall_right"] += bool(r.get("overall_agrees"))
                spark_alone["counts_exact"] += bool(r.get("valid") and r["crossings_reported"] == r["crossings_true"]
                                                    and r["violations_reported"] == r["violations_true"])
    for k in readers:
        tally[k]["objects_ci95"] = wilson(tally[k]["objects_right"], n_obj)
    spark_alone["counts_exact_ci95"] = wilson(spark_alone["counts_exact"], spark_alone["runs"])
    return {"schema": "eventproof-real-pooled/1", "clips": n_clips, "labelled_cars": n_obj, "readings": tally,
            "muse_spark_alone_from_video": spark_alone, "per_clip": clips,
            "note": "Per-object scores need tracks, so they exist only for the three rule readings; Muse Spark alone is "
                    "scored per run on its overall verdict and on whether it counted crossings and violations exactly."}


def main() -> None:
    json.dump(pooled(), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
