"""Render a `SceneSpec` to raw frames, H.264 MP4 and an oracle ground-truth `TrackSet`.

Determinism: frames are produced with integer numpy drawing only, so `frames_sha256` is identical on
every machine. The MP4 is encoded single-threaded with bitexact flags; its hash is recorded but the
raw-frame hash is the reproducibility contract (encoder builds may differ across platforms).

    uv run python -m eventproof.challenge.render --seed 7 --out ../artifacts/challenge
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from eventproof.challenge.scene import COLORS, SceneSpec, canonical_scene
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo

BG = (34, 37, 43)
BELT = (52, 56, 64)
INSPECTION_TINT = (240, 200, 60)
PACKING_TINT = (70, 200, 120)
OCCLUDER = (128, 128, 132)


def _px(scene: SceneSpec, x: float, y: float) -> tuple[int, int]:
    return round(x * scene.width), round(y * scene.height)


def box_pixels(scene: SceneSpec, cx: float, cy: float, size: tuple[float, float]) -> tuple[int, int, int, int] | None:
    """Integer pixel rect [x1, x2) × [y1, y2) clipped to the frame; None when fully outside."""
    w, h = size
    x1, y1 = _px(scene, cx - w / 2, cy - h / 2)
    x2, y2 = _px(scene, cx + w / 2, cy + h / 2)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(scene.width, x2), min(scene.height, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _blend(img: np.ndarray, x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], alpha_num: int) -> None:
    """Integer alpha blend (alpha = alpha_num/256) so results are bit-identical everywhere."""
    region = img[y1:y2, x1:x2].astype(np.uint16)
    c = np.array(color, dtype=np.uint16)
    img[y1:y2, x1:x2] = ((region * (256 - alpha_num) + c * alpha_num) >> 8).astype(np.uint8)


def _static_layer(scene: SceneSpec) -> np.ndarray:
    img = np.empty((scene.height, scene.width, 3), dtype=np.uint8)
    img[:] = BG
    for lane_y in sorted({round(o.waypoints[0].y, 3) for o in scene.objects}):
        _, y = _px(scene, 0, lane_y)
        half = round(0.09 * scene.height)
        img[max(0, y - half):y + half, :] = BELT
    for z in scene.zones:  # zones are drawn as their bounding boxes (rectangular in all generators)
        xs, ys = [p[0] for p in z.polygon], [p[1] for p in z.polygon]
        x1, y1 = _px(scene, min(xs), min(ys))
        x2, y2 = _px(scene, max(xs), max(ys))
        _blend(img, x1, y1, x2, y2, INSPECTION_TINT, 56)
    for ln in scene.lines:
        (xa, ya), (xb, yb) = _px(scene, *ln.a), _px(scene, *ln.b)
        if xa == xb:  # vertical line (all current generators)
            _blend(img, xa, min(ya, yb), scene.width, max(ya, yb), PACKING_TINT, 36)
            img[min(ya, yb):max(ya, yb), max(0, xa - 1):xa + 2] = (235, 235, 235)
    return img


def render_frames(scene: SceneSpec):
    """Yield (frame_index, HxWx3 uint8 frame, visible boxes) for each frame."""
    base = _static_layer(scene)
    for f in range(scene.n_frames):
        img = base.copy()
        for obj in scene.objects:
            c = obj.center_at(f)
            rect = c and box_pixels(scene, c[0], c[1], obj.size)
            if not rect:
                continue
            x1, y1, x2, y2 = rect
            color = np.array(COLORS[obj.color], dtype=np.int16)
            img[y1:y2, x1:x2] = np.clip(color - 45, 0, 255).astype(np.uint8)  # border
            if x2 - x1 > 4 and y2 - y1 > 4:
                img[y1 + 2:y2 - 2, x1 + 2:x2 - 2] = color.astype(np.uint8)
                band = max(1, (y2 - y1) // 6)
                img[y1 + 2:y1 + 2 + band, x1 + 2:x2 - 2] = np.clip(color + 40, 0, 255).astype(np.uint8)  # lid
                mid = (x1 + x2) // 2
                img[y1 + 2:y2 - 2, mid:mid + 2] = (200, 185, 140)  # tape
        for occ in scene.occluders:
            if occ.active(f):
                x1, y1 = _px(scene, occ.x1, occ.y1)
                x2, y2 = _px(scene, occ.x2, occ.y2)
                img[y1:y2, x1:x2] = OCCLUDER
        yield f, img


def ground_truth(scene: SceneSpec) -> TrackSet:
    """Oracle tracks: true identity and true box for every frame the object is in view.

    Occlusion does not hide anything from the oracle; `occluded` marks frames where an occluder
    covers the box center so perception failures can be analysed later.
    """
    frames = []
    for f in range(scene.n_frames):
        for obj in scene.objects:
            c = obj.center_at(f)
            rect = c and box_pixels(scene, c[0], c[1], obj.size)
            if not rect:
                continue
            x1, y1, x2, y2 = rect
            hidden = any(o.active(f) and o.x1 <= c[0] <= o.x2 and o.y1 <= c[1] <= o.y2 for o in scene.occluders)
            frames.append(TrackFrame(frame_index=f, timestamp_ms=f * 1000.0 / scene.fps, object_id=obj.object_id,
                                     label=obj.label, box=Box(x1=x1, y1=y1, x2=x2, y2=y2), confidence=1.0,
                                     occluded=hidden))
    return TrackSet(video=VideoInfo(width=scene.width, height=scene.height, fps=scene.fps, frame_count=scene.n_frames),
                    frames=frames, source="synthetic_ground_truth", source_ref=f"scene:{scene.scene_hash()}")


def oracle_view(gt: TrackSet) -> TrackSet:
    """Ground truth with occlusion flags cleared: what really happened, used to derive expected labels."""
    return gt.model_copy(update={"frames": [f.model_copy(update={"occluded": False}) for f in gt.frames]})


@dataclass(frozen=True)
class RenderResult:
    directory: Path
    scene_hash: str
    frames_sha256: str
    mp4_sha256: str | None


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg not found on PATH")
    return path


def encode_mp4(scene: SceneSpec, out: Path) -> str:
    """Pipe frames to ffmpeg (H.264 yuv420p, single thread, bitexact). Returns sha256 of raw frames."""
    cmd = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{scene.width}x{scene.height}", "-r", str(scene.fps), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "1",
           "-x264-params", "threads=1:sliced-threads=0", "-map_metadata", "-1", "-fflags", "+bitexact",
           "-flags:v", "+bitexact", "-movflags", "+faststart", str(out)]
    h = hashlib.sha256()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for _, img in render_frames(scene):
            buf = img.tobytes()
            h.update(buf)
            proc.stdin.write(buf)
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed with code {proc.returncode}")
    return h.hexdigest()


def frames_digest(scene: SceneSpec) -> str:
    h = hashlib.sha256()
    for _, img in render_frames(scene):
        h.update(img.tobytes())
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render_scene(scene: SceneSpec, out_root: Path, encode: bool = True) -> RenderResult:
    """Write scene.json, ground_truth.json, video.mp4 and manifest.json under out_root/<scene_hash[:16]>/."""
    sh = scene.scene_hash()
    d = out_root / sh[:16]
    d.mkdir(parents=True, exist_ok=True)
    (d / "scene.json").write_text(scene.model_dump_json(indent=2))
    gt = ground_truth(scene)
    (d / "ground_truth.json").write_text(gt.model_dump_json())
    mp4_hash = None
    if encode:
        frames_hash = encode_mp4(scene, d / "video.mp4")
        mp4_hash = sha256_file(d / "video.mp4")
    else:
        frames_hash = frames_digest(scene)
    manifest = {"scene_sha256": sh, "frames_sha256": frames_hash, "mp4_sha256": mp4_hash,
                "generator": scene.generator, "seed": scene.seed, "family": scene.family,
                "n_frames": scene.n_frames, "fps": scene.fps, "size": [scene.width, scene.height],
                "objects": len(scene.objects), "ground_truth_frames": len(gt.frames), "origin": "synthetic, own work"}
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return RenderResult(d, sh, frames_hash, mp4_hash)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--objects", type=int)
    ap.add_argument("--out", type=Path, default=Path("../artifacts/challenge"))
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()
    res = render_scene(canonical_scene(args.seed, args.objects), args.out, encode=not args.no_video)
    print(json.dumps({"dir": str(res.directory), "scene_sha256": res.scene_hash,
                      "frames_sha256": res.frames_sha256, "mp4_sha256": res.mp4_sha256}, indent=2))


if __name__ == "__main__":
    main()
