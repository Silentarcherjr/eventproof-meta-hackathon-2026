"""Video ingestion: validate with ffprobe, normalize only when needed.

Accepted input: an MP4/MOV file with one video stream, <= MAX_SECONDS, <= MAX_BYTES, <= MAX_SIDE px.
A file that is already H.264 yuv420p, constant frame rate and unrotated is used byte-for-byte (its hash,
and therefore the SAM cache key, does not change). Anything else is re-encoded to that form, because:
- SAM frame indices are decoded-frame indices and EventProof derives timestamps as index / fps, which is
  only right at a constant frame rate;
- SAM reports w/h after rotation; re-encoding applies the rotation so tracks and pixels agree.

Never executes or trusts anything in the file beyond what ffprobe reports; ffmpeg runs with fixed args.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from pydantic import BaseModel

from eventproof.schemas.tracks import VideoInfo

MAX_SECONDS = 20.0
MAX_BYTES = 100 * 1024 * 1024
MAX_SIDE = 3840
MIN_FRAMES = 2
CONTAINERS = ("mp4", "mov")


class VideoRejected(ValueError):
    pass


class IngestedVideo(BaseModel):
    path: Path
    sha256: str
    original_sha256: str
    info: VideoInfo
    duration_s: float
    codec: str
    reencoded: bool
    reencode_reasons: list[str]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise RuntimeError(f"{name} not found on PATH")
    return p


def probe(path: Path) -> dict:
    cmd = [_tool("ffprobe"), "-v", "error", "-count_frames", "-show_entries",
           "stream=codec_name,codec_type,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,pix_fmt"
           ":stream_side_data=rotation:format=format_name,duration", "-of", "json", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise VideoRejected(f"not a readable video ({r.stderr.strip()[:200] or 'ffprobe failed'})")
    return json.loads(r.stdout)


def _rate(s: str | None) -> Fraction:
    try:
        return Fraction(s or "0")
    except (ValueError, ZeroDivisionError):
        return Fraction(0)


def inspect(path: Path) -> tuple[dict, list[str]]:
    """Validate; return the video stream facts and the reasons a re-encode is needed (empty = use as is)."""
    if path.stat().st_size > MAX_BYTES:
        raise VideoRejected(f"file larger than {MAX_BYTES // (1024 * 1024)} MB")
    data = probe(path)
    fmt = data.get("format", {}).get("format_name", "")
    if not any(c in fmt.split(",") for c in CONTAINERS):
        raise VideoRejected(f"container '{fmt}' not accepted (MP4/MOV only)")
    vids = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if len(vids) != 1:
        raise VideoRejected(f"expected exactly one video stream, found {len(vids)}")
    v = vids[0]
    duration = float(data["format"].get("duration") or 0)
    if not 0 < duration <= MAX_SECONDS:
        raise VideoRejected(f"duration {duration:.1f}s outside (0, {MAX_SECONDS:.0f}] s")
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    if not (0 < w <= MAX_SIDE and 0 < h <= MAX_SIDE):
        raise VideoRejected(f"frame size {w}x{h} not accepted")
    if int(v.get("nb_read_frames") or 0) < MIN_FRAMES:
        raise VideoRejected("video has no decodable frames")
    reasons = []
    if v.get("codec_name") != "h264":
        reasons.append(f"codec {v.get('codec_name')} -> h264")
    if v.get("pix_fmt") != "yuv420p":
        reasons.append(f"pixel format {v.get('pix_fmt')} -> yuv420p")
    if _rate(v.get("r_frame_rate")) != _rate(v.get("avg_frame_rate")):
        reasons.append("variable frame rate -> constant")
    rotation = next((sd.get("rotation") for sd in v.get("side_data_list", []) if "rotation" in sd), None)
    if rotation not in (None, 0):
        reasons.append(f"rotation {rotation} applied to pixels")
    if w % 2 or h % 2:
        reasons.append("odd frame size -> even (yuv420p)")
    return v, reasons


def _reencode(src: Path, dst: Path, fps: Fraction) -> None:
    fps = fps if fps > 0 else Fraction(30)
    cmd = [_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
           "-map", "0:v:0", "-an", "-vf", f"fps={fps.numerator}/{fps.denominator},scale=trunc(iw/2)*2:trunc(ih/2)*2",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-map_metadata", "-1", "-movflags", "+faststart", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise VideoRejected(f"re-encode failed: {r.stderr.strip()[:200]}")


def ingest(src: Path, work_dir: Path) -> IngestedVideo:
    original_sha = sha256_file(src)
    v, reasons = inspect(src)
    work_dir.mkdir(parents=True, exist_ok=True)
    if reasons:
        dst = work_dir / f"{original_sha[:16]}.normalized.mp4"
        if not dst.exists():
            _reencode(src, dst, _rate(v.get("avg_frame_rate")) or _rate(v.get("r_frame_rate")))
        v2, again = inspect(dst)
        if again:
            raise VideoRejected(f"normalization incomplete: {again}")
        v, path = v2, dst
    else:
        path = src
    data = probe(path)
    fps = _rate(v.get("avg_frame_rate"))
    info = VideoInfo(width=int(v["width"]), height=int(v["height"]), fps=float(fps), frame_count=int(v["nb_read_frames"]))
    return IngestedVideo(path=path, sha256=sha256_file(path) if reasons else original_sha, original_sha256=original_sha,
                         info=info, duration_s=float(data["format"]["duration"]), codec=v["codec_name"],
                         reencoded=bool(reasons), reencode_reasons=reasons)
