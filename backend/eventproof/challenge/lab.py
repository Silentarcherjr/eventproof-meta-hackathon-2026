"""Traffic lab: eight development scenes, recorded Spark rule, deterministic re-judging.

Only seed 0 is exposed. The sealed evaluation is read as a report, never regenerated or imported
through evaluation tooling. New sentences use the caller's existing budgeted MuseRuleCompiler;
the exact prefilled sentence is replayed through that compiler class from its committed cache,
with a zero-call budget. Model output remains validated DSL data, never executable code.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

from eventproof.challenge.runner import bind_rule
from eventproof.challenge.scene import SceneSpec
from eventproof.challenge.traffic import STILL_SPEED, TRAFFIC_FAMILIES, WAIT_SECONDS, perfect_tracks, scene_truth
from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import LiveBudget, MetaSettings
from eventproof.meta.muse_rules import SCHEMA_VERSION_ANCHOR, Layout, MuseRuleCompiler
from eventproof.schemas.rules import Crosses, Dwell, VisualRule, iter_events

ROOT = Path(__file__).resolve().parents[3] / "benchmark" / "traffic_sim"
SHOWCASE = ROOT / "showcase"
REPORT = ROOT / "holdout_eval" / "report.json"
RECORDED_CACHE = ROOT / "holdout_eval" / "cache"
FAMILIES = tuple(TRAFFIC_FAMILIES)


class UnknownScene(ValueError):
    pass


def report() -> dict:
    return json.loads(REPORT.read_text())


def spark_rule() -> VisualRule:
    return VisualRule.model_validate(report()["muse_rule"])


def choices() -> dict:
    rule = spark_rule()
    dwell = next(e for e in iter_events(rule.check) if isinstance(e, Dwell))
    crossing = next(e for e in iter_events(rule.check) if isinstance(e, Crosses))
    return {"max_speed": dwell.max_speed, "any_direction": crossing.direction == "any",
            "travel_direction": crossing.direction, "contract_max_speed": STILL_SPEED,
            "contract_any_direction": True, "wait_seconds": WAIT_SECONDS}


def parse_speed(value: str) -> float | None:
    if value == "none":
        return None
    try:
        speed = float(value)
    except ValueError:
        raise ValueError("max_speed must be a number or 'none'") from None
    if not math.isfinite(speed) or not 0.005 <= speed <= 0.10:
        raise ValueError("max_speed must be between 0.005 and 0.10, or 'none'")
    return speed


def parse_direction(value: str) -> bool:
    if value not in ("true", "false"):
        raise ValueError("any_direction must be 'true' or 'false'")
    return value == "true"


def scene(family: str, seed: int) -> SceneSpec:
    if family not in FAMILIES or seed != 0:
        raise UnknownScene("only the eight showcase families with development seed 0 are available")
    index = json.loads((SHOWCASE / "index.json").read_text())
    entry = index["scenes"][family]
    result = SceneSpec.model_validate_json((SHOWCASE / entry["directory"] / "scene.json").read_text())
    if result.family != family or result.seed != seed or result.scene_hash() != entry["scene_sha256"]:
        raise ValueError("showcase scene hash drift")
    return result


def video(family: str, seed: int) -> Path:
    scene(family, seed)  # whitelist and verify identity before returning any file
    entry = json.loads((SHOWCASE / "index.json").read_text())["scenes"][family]
    return SHOWCASE / entry["directory"] / "video.mp4"


def scene_list() -> dict:
    rep, defaults = report(), choices()
    totals = rep["summary"]["muse_spark"]["total"]
    disagreements = sum(n for outcome, n in totals.items() if outcome != "correct")
    families = {f: values.get("spec_error", 0) for f, values in rep["summary"]["muse_spark"]["by_family"].items()
                if values.get("spec_error", 0)}
    return {"source": "synthetic", "rule_text": rep["rule_text"], "defaults": defaults,
            "assumptions": rep["assumptions"],
            "summary": {"scenes": rep["scenes"], "correct": totals.get("correct", 0),
                        "disagreements": disagreements, "by_family": families,
                        "two_choices_explain_all": set(families) == {"rolling_stop", "wrong_way"}
                        and sum(families.values()) == disagreements},
            "scenes": [{"family": f, "seed": 0, "truths": [t.model_dump() for t in scene_truth(scene(f, 0))],
                        "video_url": f"/lab/{f}/0/video"} for f in FAMILIES]}


def _controlled(rule: VisualRule, max_speed: float | None, any_direction: bool) -> VisualRule:
    if max_speed is not None:
        parse_speed(str(max_speed))
    direction = choices()["travel_direction"]

    def change(node):
        if isinstance(node, list):
            return [change(x) for x in node]
        if not isinstance(node, dict):
            return node
        updated = {k: change(v) for k, v in node.items()}
        if node.get("op") == "DWELL":
            updated["max_speed"] = max_speed
        if node.get("op") == "CROSSES":
            updated["direction"] = "any" if any_direction else direction
        return updated

    return VisualRule.model_validate({**rule.model_dump(), "check": change(rule.check.model_dump())})


def _verdicts(rule: VisualRule, sc: SceneSpec) -> dict:
    result = evaluate(bind_rule(rule, sc), perfect_tracks(sc))
    return {o.object_id: {"verdict": o.verdict, "events": [e.model_dump() for e in o.events],
                          "explanation": o.explanation} for o in result.objects}


def judge(family: str, seed: int, max_speed: float | None, any_direction: bool) -> dict:
    sc, spark = scene(family, seed), spark_rule()
    mine = _controlled(spark, max_speed, any_direction)
    base, own = _verdicts(spark, sc), _verdicts(mine, sc)
    speed_only = _verdicts(_controlled(spark, max_speed, choices()["any_direction"]), sc)
    direction_only = _verdicts(_controlled(spark, choices()["max_speed"], any_direction), sc)
    cars, explanations = [], []
    for truth in scene_truth(sc):
        oid = truth.object_id
        before, after = base[oid]["verdict"], own[oid]["verdict"]
        causes = []
        if before != after:
            if speed_only[oid]["verdict"] != before:
                causes.append("standing-still speed")
            if direction_only[oid]["verdict"] != before:
                causes.append("crossing direction")
            explanations.append(f"Car {oid}: {before} → {after} after changing {' and '.join(causes) or 'both choices'}.")
        cars.append({"object_id": oid, "truth": truth.model_dump(), "spark": base[oid], "your": own[oid]})
    return {"family": family, "seed": seed, "source": "synthetic", "cars": cars,
            "controls": {"max_speed": max_speed, "any_direction": any_direction},
            "explanation": " ".join(explanations) or "No car flips relative to Spark at these choices."}


def pair_video(side: str) -> Path:
    if side not in ("fail", "pass"):
        raise UnknownScene("unknown pair side")
    entry = json.loads((SHOWCASE / "index.json").read_text())["pair"][side]
    return SHOWCASE / entry["directory"] / "video.mp4"


def pair() -> dict:
    saved = json.loads((ROOT / "counterexamples" / "rolling_stop-0" / "counterexample.json").read_text())
    p = saved["pair"]
    naive = VisualRule.model_validate(saved["rule"])
    sides, scenes = {}, []
    for side, key in (("fail", "fail_scene"), ("pass", "pass_scene")):
        sc = SceneSpec.model_validate(p[key])
        scenes.append(sc)
        sides[side] = {"video_url": f"/lab/pair/{side}/video", "t": p[f"t_{side}"],
                       "cars": [{"truth": t.model_dump(), "naive": _verdicts(naive, sc)[t.object_id]}
                                for t in scene_truth(sc)]}
    frames = [sc.objects[0].waypoints[2].frame - sc.objects[0].waypoints[1].frame for sc in scenes]
    return {"knob": p["knob"], "motion_frame_difference": abs(frames[0] - frames[1]),
            "source": "synthetic", "sides": sides}


def layout() -> Layout:
    sc = scene("full_stop", 0)
    return Layout.model_validate({
        "zones": [{"zone": sc.zones[0].model_dump(),
                   "description": "waiting zone: the approach lane just before the stop line (top-down view)"}],
        "lines": [{"line": sc.lines[0].model_dump(),
                   "description": "stop line across the approach; cars travel from left to right of the frame"}]})


def compile_rule(text: str, compiler: MuseRuleCompiler) -> dict:
    text = text.strip()
    if not 3 <= len(text) <= 2000:
        raise ValueError("rule_text must be 3-2000 characters")
    lay = layout()
    if text == report()["rule_text"]:
        # This exact, committed response is always free, independent of the host's current model setting.
        paths = list(RECORDED_CACHE.glob("*.json"))
        cached = next(json.loads(p.read_text()) for p in paths if json.loads(p.read_text()).get("text") == text)
        settings = replace(MetaSettings.from_env(), muse_model=cached["model"])
        recorded = MuseRuleCompiler(settings=settings, cache_dir=RECORDED_CACHE,
                                    budget=LiveBudget("recorded traffic compile", 0), anchor_field=True)
        key = recorded._key(text, lay, SCHEMA_VERSION_ANCHOR)
        if not (RECORDED_CACHE / f"{key}.json").is_file():
            raise ValueError("recorded traffic compile does not match its layout/cache key")
        result = recorded.compile(text, lay)
    else:
        # The API supplies get_compiler(): same shared budget, cache, retries and instance allowance.
        result = compiler.compile(text, lay)
    judged = []
    for family in FAMILIES:
        sc = scene(family, 0)
        # bind_rule deliberately maps entities into synthetic worlds. Do not silently turn a
        # newly compiled pedestrian/bus rule into a car rule in the judge-facing text box.
        car_concept = result.rule.entity.concept.strip().lower() in {"car", "cars", "vehicle", "vehicles"}
        verdicts = _verdicts(result.rule, sc) if car_concept else {}
        cars = []
        for truth in scene_truth(sc):
            outcome = verdicts.get(truth.object_id)
            # A compiled rule may target a concept the perfect car tracks cannot test.
            correct = outcome is not None and outcome["verdict"] == truth.intended
            cars.append({"object_id": truth.object_id, "truth": truth.model_dump(),
                         "your": outcome, "correct": correct,
                         "why": outcome["explanation"] if outcome else
                         f"This rule targets {result.rule.entity.concept!r}; the showcase has approach-car tracks only."})
        judged.append({"family": family, "seed": 0, "cars": cars,
                       "correct": all(c["correct"] for c in cars)})
    return {"provenance": "recorded response" if result.cached else "compiled live by Muse Spark",
            "cached": result.cached, "model": result.model, "request_ids": result.request_ids,
            "assumptions": result.assumptions, "rule": result.rule.model_dump(), "scenes": judged,
            "wrong_scenes": [r["family"] for r in judged if not r["correct"]],
            "scope": "Eight development showcase scenes on perfect tracks; not a new sealed evaluation."}
