"""README figure for the real traffic footage (benchmark/real/novisad). Reads the committed rule + SAM 3.1 tracks; the
background frame comes from the local prepared clip (videos are not committed).

    uv run --project backend --with matplotlib python scripts/figure_novisad.py
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from math import hypot
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.image import imread  # noqa: E402

from eventproof.engine.evaluator import SPEED_WINDOW_MS, build_tracks  # noqa: E402
from eventproof.schemas.rules import VisualRule  # noqa: E402
from eventproof.schemas.tracks import TrackSet  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "benchmark" / "real" / "novisad"
REPORT = json.loads((DIR / "report_novisad.json").read_text())
CLIP = REPORT["clips"][0]  # clip a: the stopping sedan and the rolling van
OUT = ROOT / "docs" / "media" / "real_traffic.png"
STOP, ROLL = "#0284c7", "#ea580c"  # validated pair (light surface); identity also carried by direct labels
INK, MUTED, GRID = "#1f2328", "#59636e", "#d8dee4"


def speeds(t) -> tuple[list[float], list[float]]:
    xs, ys, j = [], [], 0
    for o in t.obs:
        while j + 1 < len(t.obs) and o.ts - t.obs[j + 1].ts >= SPEED_WINDOW_MS:
            j += 1
        ref = t.obs[j]
        dt = (o.ts - ref.ts) / 1000.0
        if dt > 0:
            xs.append(o.ts / 1000.0)
            ys.append(hypot(o.pt[0] - ref.pt[0], o.pt[1] - ref.pt[1]) / dt)
    return xs, ys


def main() -> None:
    run = DIR / "runs" / CLIP["run_id"]
    rule = VisualRule.model_validate(json.loads((run / "evidence.json").read_text())["rule"]["compiled_rule"])
    tracks = TrackSet.model_validate_json((run / "tracks.json").read_text())
    rows = {r["label_index"]: r for r in CLIP["objects"]["labeled"]}
    sedan_id, van_id = rows[1]["matched_object_id"], rows[2]["matched_object_id"]
    by = {t.object_id: t for t in build_tracks(rule, tracks)}
    w, h = tracks.video.width, tracks.video.height

    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "f.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "9.0", "-i", str(DIR / "videos" / CLIP["clip"]),
                        "-frames:v", "1", str(png)], check=True)
        frame = imread(png)

    fig = plt.figure(figsize=(11, 5.2), dpi=160, facecolor="white")
    ax0 = fig.add_axes([0.02, 0.08, 0.27, 0.84])
    ax1 = fig.add_axes([0.37, 0.14, 0.60, 0.74])

    ax0.imshow(frame, extent=(0, w, h, 0))
    zone = rule.zones[0].polygon
    ax0.fill([p[0] * w for p in zone], [p[1] * h for p in zone], color="white", alpha=0.12, lw=0)
    ax0.plot([p[0] * w for p in zone] + [zone[0][0] * w], [p[1] * h for p in zone] + [zone[0][1] * h],
             color="white", lw=1, ls="--")
    ln = rule.lines[0]
    ax0.plot([ln.a[0] * w, ln.b[0] * w], [ln.a[1] * h, ln.b[1] * h], color="white", lw=2.5)
    ax0.text(ln.b[0] * w + 4, ln.b[1] * h - 6, "stop line", color="white", fontsize=8, fontweight="bold")
    for oid, color in ((sedan_id, STOP), (van_id, ROLL)):
        obs = by[oid].obs[::5]  # one dot every 0.5 s: dots pile up where the car stands still
        ax0.plot([o.pt[0] * w for o in obs], [o.pt[1] * h for o in obs], color=color, lw=2, marker="o", ms=4,
                 mec="white", mew=0.8)
    ax0.set_xlim(0, w)
    ax0.set_ylim(h, 0)
    ax0.axis("off")
    ax0.set_title("Real footage (Pexels, Novi Sad), dots every 0.5 s", fontsize=8.5, color=MUTED, loc="left")

    labels = {sedan_id: ("sedan: stands still ~4 s,\nthen crosses (truth PASS)", 6.6, (0.3, 0.185)),
              van_id: ("van: crawls, never stops\n(truth VIOLATION)", 12.6, (15.0, 0.315))}
    for oid, color in ((sedan_id, STOP), (van_id, ROLL)):
        xs, ys = speeds(by[oid])
        ax1.plot(xs, ys, color=color, lw=2, solid_capstyle="round")
        text, at, xy = labels[oid]
        i = min(range(len(xs)), key=lambda k: abs(xs[k] - at))
        ax1.annotate(text, (xs[i], ys[i]), xytext=xy, fontsize=8.5, color=INK, va="center",
                     arrowprops={"arrowstyle": "-", "color": color, "lw": 1})
    for y, txt in ((0.05, "0.05: Muse Spark's \"still\""), (0.08, "0.08: repair's \"still\"")):
        ax1.axhline(y, color=MUTED, lw=1, ls=(0, (4, 3)))
        ax1.text(0.2, y + 0.005, txt, fontsize=8, color=MUTED)
    ax1.text(0.2, 0.33, "The van, judged by\n  Muse Spark's rule (speed ≤ 0.05 for 1.5 s):  VIOLATION  ✓\n"
             "  repair accepted on synthetic data (≤ 0.08 for 0.8 s):  PASS  ✗",
             fontsize=8.5, color=INK, va="top", linespacing=1.5)
    ax1.set_xlim(0, 19)
    ax1.set_ylim(0, 0.36)
    ax1.set_xlabel("time in clip (s)", fontsize=9, color=MUTED)
    ax1.set_ylabel("speed (frame widths / s, over 1/3 s)", fontsize=9, color=MUTED)
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax1.spines[s].set_color(GRID)
    ax1.tick_params(colors=MUTED, labelsize=8)
    ax1.grid(axis="y", color=GRID, lw=0.6)
    ax1.set_title("Same SAM 3.1 tracks, two readings of \"wait\": the synthetic-tuned repair passes a real rolling stop",
                  fontsize=10, color=INK, loc="left")
    fig.savefig(OUT, facecolor="white")
    print(OUT)


if __name__ == "__main__":
    main()
