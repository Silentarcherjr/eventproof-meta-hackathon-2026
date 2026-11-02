"""Muse Spark proposes the scene layout (one zone + one line) from the first video frame and the rule text, so a user can
go from "a sentence over a video" to a checkable rule without drawing anything; the user still confirms or redraws.

- Input: the first frame as a PNG (base64 data URL, image input of the Chat Completions API) and the rule text.
- Output (strict JSON schema): the zone polygon (3-8 points) and the line (two points), as fractions of width/height,
  each with a short description, plus the model's stated assumptions. Ids are fixed by EventProof ("inspection" for the
  zone, "packing_entry" for the line) so every downstream stage (rule compiler, Challenge Mode world) works unchanged;
  the descriptions carry the scene's own words.
- The model output is data: coordinates are clipped to [0, 1] and re-validated through the same `Layout` schema as a
  hand-drawn layout. Invalid output is rejected (no silent fallback).
- Responses are cached by (frame sha256, rule text, model, schema version).
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

from pydantic import ValidationError

from eventproof.meta.client import LiveBudget, LiveCallLimit, MetaSettings, get_client
from eventproof.meta.muse_rules import Layout, RuleCompileError

SCHEMA_VERSION = "layout-proposal/1"
CACHE_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "muse_layout_cache"
ZONE_ID, LINE_ID = "inspection", "packing_entry"

_PT = {"type": "array", "items": {"type": "number"}, "description": "[x, y] as fractions of width, height; origin top-left"}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["zone_polygon", "zone_description", "line_a", "line_b", "line_description", "travel_direction",
                 "assumptions"],
    "properties": {
        "zone_polygon": {"type": "array", "items": _PT, "description": "3-8 points, in order around the zone"},
        "zone_description": {"type": "string",
                             "description": "what the zone is in this scene, e.g. 'waiting area before the stop line'"},
        "line_a": _PT, "line_b": _PT,
        "line_description": {"type": "string",
                             "description": "what the line is, e.g. 'stop line at the edge of the crosswalk'"},
        "travel_direction": {"type": "string", "description": "how the objects move across the line, in image terms"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
}
SYSTEM = """You look at the first frame of a fixed-camera video and a rule about it, and place the geometry the rule needs:
one ZONE (the area where objects must stay, wait or be checked) and one LINE (the boundary whose crossing the rule is about,
e.g. a stop line, the entry of an area). Coordinates are fractions of the image width and height, origin top-left.
The zone should cover the area right before the line on the side objects come from, touching the line.
Draw the line across the full width of the lanes or belt it applies to. Output only the JSON the schema allows,
and list every placement choice you made in assumptions."""


def first_frame_png(video: Path) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "f0.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-frames:v", "1", str(out)], check=True)
        return out.read_bytes()


def _clip01(p: list[float]) -> tuple[float, float]:
    if len(p) != 2:
        raise RuleCompileError(f"point {p} is not [x, y]")
    return (min(1.0, max(0.0, float(p[0]))), min(1.0, max(0.0, float(p[1]))))


def to_layout(out: dict) -> Layout:
    poly = [_clip01(p) for p in out["zone_polygon"]]
    if not 3 <= len(poly) <= 8:
        raise RuleCompileError(f"zone polygon has {len(poly)} points (3-8 required)")
    try:
        return Layout.model_validate({
            "zones": [{"zone": {"id": ZONE_ID, "polygon": poly}, "description": out["zone_description"][:200]}],
            "lines": [{"line": {"id": LINE_ID, "a": _clip01(out["line_a"]), "b": _clip01(out["line_b"])},
                       "description": f"{out['line_description'][:160]}; {out['travel_direction'][:120]}"}]})
    except ValidationError as e:
        raise RuleCompileError(f"proposed layout is invalid: {e.errors()[:2]}") from None


class LayoutProposer:
    def __init__(self, settings: MetaSettings | None = None, cache_dir: Path | None = None,
                 budget: LiveBudget | None = None, max_live_calls: int | None = None):
        self.settings = settings or MetaSettings.from_env()
        self.cache_dir = cache_dir or CACHE_DIR
        self.budget, self.max_live_calls, self.live_calls = budget, max_live_calls, 0

    def _key(self, png: bytes, text: str) -> str:
        return hashlib.sha256(json.dumps([hashlib.sha256(png).hexdigest(), text.strip(), self.settings.muse_model,
                                          SCHEMA_VERSION]).encode()).hexdigest()

    def propose(self, png: bytes, text: str) -> dict:
        cpath = self.cache_dir / f"{self._key(png, text)}.json"
        if cpath.exists():
            c = json.loads(cpath.read_text())
            return {"layout": to_layout(c["raw_output"]), "assumptions": c["raw_output"]["assumptions"],
                    "request_id": c["request_id"], "model": c["model"], "cached": True}
        if self.max_live_calls is not None and self.live_calls >= self.max_live_calls:
            raise LiveCallLimit(f"layout proposal: allowance {self.max_live_calls} used up")
        client = get_client(self.settings)
        if self.budget:
            self.budget.take("layout proposal")
        t0 = time.monotonic()
        url = "data:image/png;base64," + base64.b64encode(png).decode()
        resp = client.chat.completions.create(
            model=self.settings.muse_model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": [{"type": "text", "text": f"Rule:\n{text.strip()}"},
                                                   {"type": "image_url", "image_url": {"url": url}}]}],
            response_format={"type": "json_schema", "json_schema": {"name": "layout", "schema": SCHEMA, "strict": True}})
        self.live_calls += 1
        try:
            out = json.loads(resp.choices[0].message.content or "")
        except json.JSONDecodeError as e:
            raise RuleCompileError(f"model returned non-JSON content: {e}") from None
        layout = to_layout(out)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps({"raw_output": out, "request_id": resp.id, "model": self.settings.muse_model,
                                     "text": text, "usage": resp.usage.model_dump() if resp.usage else {},
                                     "latency_s": round(time.monotonic() - t0, 2)}, indent=2))
        return {"layout": layout, "assumptions": out["assumptions"], "request_id": resp.id,
                "model": self.settings.muse_model, "cached": False}


# ---- agreement with a hand-drawn layout ---------------------------------------------------------------------------

def polygon_iou(a: list[tuple[float, float]], b: list[tuple[float, float]], n: int = 400) -> float:
    """IoU of two polygons in unit coordinates, by rasterising both on an n x n grid (even-odd rule)."""
    import numpy as np

    ys, xs = np.mgrid[0:n, 0:n]
    px, py = (xs + 0.5) / n, (ys + 0.5) / n

    def mask(poly):
        m = np.zeros((n, n), bool)
        j = len(poly) - 1
        for i in range(len(poly)):
            (xi, yi), (xj, yj) = poly[i], poly[j]
            cond = (yi > py) != (yj > py)
            with np.errstate(divide="ignore", invalid="ignore"):
                xint = (xj - xi) * (py - yi) / (yj - yi) + xi
            m ^= cond & (px < xint)
            j = i
        return m

    ma, mb = mask(a), mask(b)
    union = (ma | mb).sum()
    return float((ma & mb).sum() / union) if union else 0.0


def line_agreement(a: tuple, b: tuple) -> dict:
    """Angle between two lines (degrees, 0-90) and distance between their midpoints (fraction of the frame)."""
    import math

    def ang(l):  # noqa: E741
        return math.degrees(math.atan2(l[1][1] - l[0][1], l[1][0] - l[0][0])) % 180

    d = abs(ang(a) - ang(b))
    mid = lambda l: ((l[0][0] + l[1][0]) / 2, (l[0][1] + l[1][1]) / 2)  # noqa: E731,E741
    (ax, ay), (bx, by) = mid(a), mid(b)
    return {"angle_deg": round(min(d, 180 - d), 1), "midpoint_dist": round(math.hypot(ax - bx, ay - by), 3)}
