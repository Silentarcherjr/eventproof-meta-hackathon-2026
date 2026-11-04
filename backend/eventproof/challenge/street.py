"""Optional street/1 presentation for traffic scenes; no measurement or rule changes.

All vehicle extents come directly from traffic.box_at. Mirrors are inside those extents;
shadows are decorative. The static drawing uses the scene's existing line and zone geometry.
A tiny fixed bitmap font and integer texture avoid machine-dependent system fonts/randomness.

Overlay labels are CONTRACT truth, not the lab's adjustable/Spark rule. Elapsed stillness is
read by asking the existing scene_truth for a prefix view of the original trajectory, never by
reimplementing a speed counter. Prefix copies are transient views and are never saved as scenes.
Crossing frames and final verdicts come directly from the full scene's unchanged traffic truth.

    uv run python -m eventproof.challenge.street --showcase ../benchmark/traffic_sim/showcase

The CLI restyles only the ten already-indexed lab videos; scene/ground-truth bytes are checked
before and after, and the frozen v1 release and evaluation/counterexample artifacts are untouched.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from eventproof.challenge.scene import SceneObject, SceneSpec
from eventproof.challenge.traffic import box_at, is_traffic, object_label, scene_truth

STYLE_VERSION = "street/1"
CAR_COLORS = ((41, 161, 190), (226, 164, 64), (197, 81, 75), (148, 130, 181), (219, 225, 218))
# Rows of a fixed 5x7 bitmap; no dependency on installed fonts or font rasterizers.
FONT = {
    "0": (14, 17, 19, 21, 25, 17, 14), "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31), "3": (30, 1, 1, 14, 1, 1, 30),
    "4": (2, 6, 10, 18, 31, 2, 2), "5": (31, 16, 16, 30, 1, 1, 30),
    "6": (14, 16, 16, 30, 17, 17, 14), "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14), "9": (14, 17, 17, 15, 1, 1, 14),
    "A": (14, 17, 17, 31, 17, 17, 17), "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (30, 17, 17, 17, 17, 17, 30), "E": (31, 16, 16, 30, 16, 16, 31),
    "H": (17, 17, 17, 31, 17, 17, 17), "I": (14, 4, 4, 4, 4, 4, 14),
    "L": (16, 16, 16, 16, 16, 16, 31), "N": (17, 25, 25, 21, 19, 19, 17),
    "O": (14, 17, 17, 17, 17, 17, 14), "P": (30, 17, 17, 30, 16, 16, 16),
    "R": (30, 17, 17, 30, 20, 18, 17), "S": (15, 16, 16, 14, 1, 1, 30),
    "T": (31, 4, 4, 4, 4, 4, 4), "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 21, 10), "Y": (17, 17, 10, 4, 4, 4, 4),
    " ": (0,) * 7, ".": (0, 0, 0, 0, 0, 12, 12),
    "/": (1, 2, 2, 4, 8, 8, 16), "#": (10, 31, 10, 10, 31, 10, 0),
}


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill, scale: int = 1) -> None:
    x, y = xy
    for char in text:
        for row, bits in enumerate(FONT[char]):
            for col in range(5):
                if bits & (1 << (4 - col)):
                    draw.rectangle((x + col * scale, y + row * scale,
                                    x + (col + 1) * scale - 1, y + (row + 1) * scale - 1), fill=fill)
        x += 6 * scale


def _px(scene: SceneSpec, x: float, y: float) -> tuple[int, int]:
    return round(x * scene.width), round(y * scene.height)


def car_rect(scene: SceneSpec, obj: SceneObject, frame: int) -> tuple[int, int, int, int] | None:
    """Exact analytic box rounded to raster edges, without any change to center/extent/trajectory."""
    box = box_at(scene, obj, frame)
    return None if box is None else (round(box.x1), round(box.y1), round(box.x2), round(box.y2))


def _background(scene: SceneSpec) -> Image.Image:
    h, w = scene.height, scene.width
    yy, xx = np.indices((h, w), dtype=np.int64)
    # Fixed integer coordinate hash: static grain, never flickering noise or global RNG state.
    grain = ((xx * 73856093 ^ yy * 19349663 ^ (scene.seed % 65536) * 83492791) % 7 - 3).astype(np.int16)
    pixels = np.empty((h, w, 3), dtype=np.uint8)
    pixels[:] = (73, 94, 77)
    ya, yb = round(0.34 * h), round(0.74 * h)
    xa, xb = round(0.77 * w), round(0.92 * w)
    sidewalk = np.zeros((h, w), dtype=bool)
    sidewalk[max(0, ya - 13):min(h, yb + 13), :] = True
    sidewalk[:, max(0, xa - 12):min(w, xb + 12)] = True
    pixels[sidewalk] = np.stack([174 + grain, 172 + grain, 163 + grain], axis=-1)[sidewalk]
    road = np.zeros((h, w), dtype=bool)
    road[ya:yb, :] = True
    road[:, xa:xb] = True
    pixels[road] = np.stack([57 + grain, 62 + grain, 65 + grain], axis=-1)[road]
    img = Image.fromarray(pixels).convert("RGBA")
    d = ImageDraw.Draw(img)
    # Concrete joints, curb highlights and edge paint; stop at the crossing street.
    for x in range(0, xa - 13, 28):
        for y in (ya - 12, yb + 1):
            d.line((x, y, x, y + 10), fill=(145, 145, 139), width=1)
    for a, b in ((0, xa - 1), (xb, w - 1)):
        for y in (ya - 1, yb):
            d.line((a, y, b, y), fill=(219, 214, 194), width=2)
        for y in (ya + 5, yb - 6):
            d.line((a, y, b, y), fill=(181, 179, 163), width=1)
    for x in (xa - 1, xb):
        for a, b in ((0, ya - 1), (yb, h - 1)):
            d.line((x, a, x, b), fill=(219, 214, 194), width=2)
    knobs = json.loads(scene.notes)
    if knobs["lanes"] == 2:
        mid = round(0.54 * h)
        for x in range(5, round(0.70 * w), 27):
            d.rectangle((x, mid - 1, x + 14, mid), fill=(213, 211, 187))
    # Dashed center divider on the cross street (away from the junction).
    for y in range(5, h - 4, 24):
        if y + 12 < ya or y > yb:
            d.rectangle(((xa + xb) // 2, y, (xa + xb) // 2 + 1, y + 11), fill=(194, 184, 136))
    # Raised planters stay off the measured roadway/zone.
    for x, y in ((round(0.15 * w), ya - 29), (round(0.50 * w), yb + 31)):
        d.rounded_rectangle((x - 15, y - 6, x + 15, y + 6), radius=3, fill=(62, 70, 61))
        for dx in (-9, 0, 9):
            d.ellipse((x + dx - 5, y - 5, x + dx + 5, y + 5), fill=(57, 84, 59))
    line = next(ln for ln in scene.lines if ln.id == "stop_line")
    stop_x, ly1 = _px(scene, *line.a)
    _, ly2 = _px(scene, *line.b)
    # Zebra immediately past the unchanged stop line; stripes run parallel to vehicle travel.
    for y in range(min(ly1, ly2) + 3, max(ly1, ly2) - 5, 12):
        d.rectangle((stop_x + 8, y, stop_x + 19, y + 6), fill=(225, 225, 212))
    d.line((*_px(scene, *line.a), *_px(scene, *line.b)), fill=(246, 245, 232), width=5)
    # Painted STOP stencil, rotated to face the approaching driver.
    stencil = Image.new("RGBA", (49, 15))
    _text(ImageDraw.Draw(stencil), (1, 0), "STOP", (218, 219, 205, 210), scale=2)
    stencil = stencil.transpose(Image.Transpose.ROTATE_90)
    lanes = (0.53,) if knobs["lanes"] == 1 else (0.45, 0.63)
    for lane in lanes:
        img.alpha_composite(stencil, (round(0.47 * w), round(lane * h) - stencil.height // 2))
    # Waiting geometry is the actual polygon, not a guessed road region.
    tint = Image.new("RGBA", img.size)
    td = ImageDraw.Draw(tint)
    for zone in scene.zones:
        pts = [_px(scene, *p) for p in zone.polygon]
        td.polygon(pts, fill=(244, 192, 68, 32))
        td.line([*pts, pts[0]], fill=(231, 186, 70, 200), width=1)
    img = Image.alpha_composite(img, tint)
    d = ImageDraw.Draw(img)
    # Roadside octagonal sign: fixed integer vertices and a tiny 3x5 STOP inscription.
    cx, cy = stop_x + 2, min(ly1, ly2) - 22
    d.line((cx, cy + 7, cx, min(ly1, ly2) - 3), fill=(110, 116, 113), width=3)
    vertices = [(cx - 4, cy - 10), (cx + 4, cy - 10), (cx + 10, cy - 4), (cx + 10, cy + 4),
                (cx + 4, cy + 10), (cx - 4, cy + 10), (cx - 10, cy + 4), (cx - 10, cy - 4)]
    d.polygon(vertices, fill=(181, 50, 46), outline=(245, 237, 220), width=2)
    tiny = {"S": (7, 4, 7, 1, 7), "T": (7, 2, 2, 2, 2), "O": (7, 5, 5, 5, 7), "P": (7, 5, 7, 4, 4)}
    for i, char in enumerate("STOP"):
        for row, bits in enumerate(tiny[char]):
            for col in range(3):
                if bits & (1 << (2 - col)):
                    d.point((cx - 7 + i * 4 + col, cy - 2 + row), fill=(255, 247, 230))
    return img


def _vehicle_patch(width: int, height: int, color: tuple[int, int, int], vertical: bool, reverse: bool) -> Image.Image:
    w, h = (height, width) if vertical else (width, height)
    patch = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(patch)
    inset = max(2, h // 8)
    # Wheels and mirrors stay INSIDE the exact annotation rectangle.
    for x in (round(w * 0.18), round(w * 0.72)):
        d.rectangle((x, 1, x + max(2, w // 7), h - 2), fill=(24, 27, 29))
    d.rounded_rectangle((0, inset, w - 1, h - inset - 1), radius=max(2, h // 4), fill=color,
                        outline=tuple(max(0, c - 35) for c in color))
    for y in (0, h - inset):
        d.rounded_rectangle((round(w * 0.60), y, round(w * 0.71), y + inset - 1), radius=1, fill=color)
    # Rear glass, roof and forward sloped windshield.
    d.polygon([(round(w * 0.19), inset + 2), (round(w * 0.32), inset + 1),
               (round(w * 0.32), h - inset - 2), (round(w * 0.19), h - inset - 3)], fill=(30, 47, 55))
    d.rounded_rectangle((round(w * 0.35), inset + 2, round(w * 0.59), h - inset - 3), radius=2,
                        fill=tuple(min(255, c + 17) for c in color))
    d.polygon([(round(w * 0.63), inset + 1), (round(w * 0.78), inset + 3),
               (round(w * 0.78), h - inset - 4), (round(w * 0.63), h - inset - 2)], fill=(36, 58, 66))
    for y in (inset + 2, h - inset - 4):
        d.line((w - 3, y, w - 2, y + 1), fill=(255, 236, 186))
        d.line((1, y, 2, y + 1), fill=(163, 48, 40))
    if reverse:
        patch = patch.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return patch.transpose(Image.Transpose.ROTATE_270) if vertical else patch


def _vehicle(img: Image.Image, scene: SceneSpec, obj: SceneObject, frame: int) -> None:
    rect = car_rect(scene, obj, frame)
    if rect is None:
        return
    x1, y1, x2, y2 = rect
    w, h = x2 - x1, y2 - y1
    if w < 8 or h < 8:
        return
    shadow = Image.new("RGBA", img.size)
    sd = ImageDraw.Draw(shadow)
    for offset, alpha in ((3, 20), (2, 34), (1, 45)):
        sd.rounded_rectangle((x1 + offset, y1 + offset, x2 + offset, y2 + offset),
                             radius=max(2, h // 4), fill=(9, 15, 18, alpha))
    img.alpha_composite(shadow)
    context = object_label(obj) != "car"
    color = (126, 144, 140) if context else CAR_COLORS[obj.object_id % len(CAR_COLORS)]
    vertical = abs(obj.waypoints[-1].y - obj.waypoints[0].y) > abs(obj.waypoints[-1].x - obj.waypoints[0].x)
    reverse = (obj.waypoints[-1].y < obj.waypoints[0].y) if vertical else (obj.waypoints[-1].x < obj.waypoints[0].x)
    img.alpha_composite(_vehicle_patch(w, h, color, vertical, reverse), (x1, y1))


def _truck(img: Image.Image, scene: SceneSpec, occ) -> None:
    x1, y1 = _px(scene, occ.x1, occ.y1)
    x2, y2 = _px(scene, occ.x2, occ.y2)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x1 + 2, y1 + 2, x2 + 2, y2 + 2), radius=3, fill=(25, 30, 30, 130))
    d.rounded_rectangle((x1, y1, x2 - 1, y2 - 1), radius=3, fill=(110, 117, 119))
    cab = x2 - max(12, (x2 - x1) // 4)
    d.rectangle((x1 + 2, y1 + 2, cab - 2, y2 - 3), fill=(220, 220, 209))
    for x in range(x1 + 5, cab - 3, 7):
        d.line((x, y1 + 4, x, y2 - 5), fill=(190, 192, 183))
    d.rounded_rectangle((cab, y1 + 2, x2 - 2, y2 - 3), radius=3, fill=(187, 192, 184))
    d.rectangle((x2 - 7, y1 + 6, x2 - 4, y2 - 7), fill=(36, 58, 66))
    for x in (x1 + 5, cab + 4):
        for y in (y1, y2 - 3):
            d.rectangle((x, y, x + 6, y + 2), fill=(29, 32, 33))


def frame_labels(scene: SceneSpec, frame: int) -> list[dict]:
    """Presentation metadata read from unchanged truth routines, with no verdict/speed calculation."""
    final = {t.object_id: t for t in scene_truth(scene)}
    # A prefix need not meet SceneSpec's >=50-frame export constraint; it is only an in-memory view.
    prefix = scene.model_copy(update={"n_frames": frame + 1})
    labels = []
    for current in scene_truth(prefix):
        full = final[current.object_id]
        crossed = full.crossing_frame is not None and frame >= full.crossing_frame
        labels.append({"object_id": current.object_id, "standing_still_seconds": current.standing_still_seconds,
                       "verdict": full.intended if crossed else None, "crossing_frame": full.crossing_frame})
    return labels


def _overlay(img: Image.Image, scene: SceneSpec, frame: int) -> None:
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((5, 5, 126, 19), radius=3, fill=(18, 25, 29, 225))
    _text(d, (10, 9), "CONTRACT / SYNTHETIC", (210, 222, 217))
    stamp = f"{frame / scene.fps:04.1f}S"
    x = scene.width - len(stamp) * 6 - 12
    d.rounded_rectangle((x - 4, 5, scene.width - 5, 19), radius=3, fill=(18, 25, 29, 225))
    _text(d, (x, 9), stamp, (221, 228, 222))
    for label in frame_labels(scene, frame):
        obj = next(o for o in scene.objects if o.object_id == label["object_id"])
        rect = car_rect(scene, obj, frame)
        if rect is None:
            continue
        text = f"#{obj.object_id} {label['standing_still_seconds']:.1f}S"
        if label["verdict"]:
            text += f" {label['verdict']}"
        color = ((239, 119, 105) if label["verdict"] == "VIOLATION" else
                 (125, 220, 164) if label["verdict"] == "PASS" else (227, 226, 195))
        width = len(text) * 6 + 7
        x = max(4, min(scene.width - width - 4, (rect[0] + rect[2] - width) // 2))
        y = max(24, rect[1] - 16 - 15 * (obj.object_id % 2))
        d.rounded_rectangle((x, y, x + width, y + 12), radius=3, fill=(18, 25, 29, 235), outline=color)
        _text(d, (x + 4, y + 3), text, color)


def render_street_frames(scene: SceneSpec, overlay: bool = False):
    if not is_traffic(scene):
        raise ValueError("street style requires a traffic scene")
    base = _background(scene)
    for frame in range(scene.n_frames):
        img = base.copy()
        for obj in scene.objects:
            _vehicle(img, scene, obj, frame)
        for occ in scene.occluders:
            if occ.active(frame):
                _truck(img, scene, occ)
        if overlay:
            _overlay(img, scene, frame)
        yield frame, np.asarray(img.convert("RGB"))


def restyle_showcase(root: Path) -> dict:
    """Only re-render indexed development/pair media, preserving every measured artifact byte."""
    from eventproof.challenge.render import render_scene, sha256_file

    if root.resolve().name != "showcase":
        raise ValueError("restyle target must be the lab showcase directory, never a frozen release")
    index = json.loads((root / "index.json").read_text())
    entries = [*index["scenes"].values(), *index["pair"].values()]
    if len(entries) != 10:
        raise ValueError("expected exactly eight scenes and two boundary videos")
    for entry in entries:
        directory = (root / entry["directory"]).resolve()
        if not directory.is_relative_to(root.resolve()):
            raise ValueError("showcase directory escaped its root")
        before = {name: (directory / name).read_bytes() for name in ("scene.json", "ground_truth.json")}
        sc = SceneSpec.model_validate_json(before["scene.json"])
        if sc.seed != 0 or sc.scene_hash() != entry["scene_sha256"]:
            raise ValueError("only existing seed-0 showcase scenes can be restyled")
        rendered = render_scene(sc, directory.parent, style="street", overlay=True)
        for name, blob in before.items():
            if (directory / name).read_bytes() != blob:
                raise ValueError(f"restyling changed measured {name}")
        if (directory / "video.mp4").stat().st_size >= 1_000_000:
            raise ValueError("showcase MP4 exceeded 1 MB")
        entry.update(frames_sha256=rendered.frames_sha256, mp4_sha256=rendered.mp4_sha256,
                     manifest_sha256=sha256_file(directory / "manifest.json"))
    index.update(render_style=STYLE_VERSION, overlay=True)
    (root / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return index


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--showcase", required=True, type=Path)
    args = ap.parse_args()
    index = restyle_showcase(args.showcase)
    print(json.dumps({"render_style": index["render_style"], "videos": 10, "overlay": index["overlay"]}))


if __name__ == "__main__":
    main()
