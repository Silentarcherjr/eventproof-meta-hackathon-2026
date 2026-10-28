"""SAM 3.1 adapter: video + concept prompt -> `TrackSet(source="sam-3.1")`.

- `to_trackset` converts parsed wire frames into EventProof tracks (inclusive x2/y2 -> exclusive).
- `SamTracker` makes the live call (upload, Responses stream) and caches the RAW output text by
  (video sha256, model, prompt, metadata). A cache hit is still real SAM output; its `source_ref`
  says `cached` and keeps the original response id. Nothing is ever synthesized here: if there is no
  key and no cache entry, `MetaApiUnavailable` is raised (no silent fallback to mocks).
- `sam_perceiver` plugs SAM into Challenge Mode: render the scene to MP4, track, convert.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from eventproof.meta.client import MetaSettings, get_client
from eventproof.perception.sam_wire import SamFrame, SamParseError, parse_output
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo

CACHE_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "sam_cache"
METADATA = {"include_confidence": "true", "mask_encoding": "one_bit"}  # one_bit: smallest payloads


def to_trackset(frames: list[SamFrame], video: VideoInfo, concept: str, source_ref: str) -> TrackSet:
    out = []
    for f in frames:
        if f.frame >= video.frame_count:
            raise SamParseError(f"frame {f.frame} beyond video length {video.frame_count}")
        for r in f.records:
            if (r.w, r.h) != (video.width, video.height):
                raise SamParseError(f"SAM frame size {(r.w, r.h)} != video {(video.width, video.height)} "
                                    "(rotation metadata?)")
            out.append(TrackFrame(frame_index=f.frame, timestamp_ms=video.frame_to_ms(f.frame), object_id=r.object_id,
                                  label=concept, box=Box(x1=r.x1, y1=r.y1, x2=r.x2 + 1, y2=r.y2 + 1),
                                  confidence=r.confidence, mask_ref=f"f{f.frame}/o{r.object_id}" if r.mask else None))
    return TrackSet(video=video, frames=out, source="sam-3.1", source_ref=source_ref)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class SamResult:
    deltas: list[str]
    response_id: str
    model: str
    prompt: str
    video_sha256: str
    cached: bool
    latency_s: float | None

    @property
    def source_ref(self) -> str:
        return (f"{self.model}:{self.response_id}:video={self.video_sha256[:16]}:prompt={self.prompt!r}"
                + (":cached" if self.cached else ""))


class LiveCallLimit(RuntimeError):
    """Raised before uploading when a run would exceed its explicit live-call allowance (credits guard)."""


class SamTracker:
    def __init__(self, settings: MetaSettings | None = None, cache_dir: Path | None = None, max_live_calls: int = 0):
        self.settings = settings or MetaSettings.from_env()
        self.cache_dir = cache_dir or CACHE_DIR
        self.max_live_calls = max_live_calls  # 0 = cache only; every live call must be allowed explicitly
        self.live_calls = 0

    def _key(self, video_sha: str, prompt: str) -> str:
        blob = json.dumps([video_sha, self.settings.sam_model, prompt, METADATA], sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def track(self, video: Path, prompt: str) -> SamResult:
        vsha = sha256_file(video)
        cpath = self.cache_dir / f"{self._key(vsha, prompt)}.json"
        if cpath.exists():
            c = json.loads(cpath.read_text())
            return SamResult(c["deltas"], c["response_id"], c["model"], prompt, vsha, cached=True, latency_s=None)
        if self.live_calls >= self.max_live_calls:
            raise LiveCallLimit(f"not cached and live-call allowance {self.max_live_calls} is used up "
                                f"({video.name}, prompt {prompt!r})")
        client = get_client(self.settings)  # raises MetaApiUnavailable without a key
        t0 = time.monotonic()
        with video.open("rb") as fh:
            uploaded = client.files.create(file=fh, purpose="user_data")
        deltas: list[str] = []
        with client.responses.stream(
            model=self.settings.sam_model,
            input=[{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_video", "file_id": uploaded.id},
            ]}],
            metadata=METADATA,
        ) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    deltas.append(event.delta)
            final = stream.get_final_response()
        self.live_calls += 1
        res = SamResult(deltas, final.id, self.settings.sam_model, prompt, vsha, cached=False,
                        latency_s=round(time.monotonic() - t0, 2))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps({"deltas": deltas, "response_id": final.id, "model": res.model, "prompt": prompt,
                                     "video_sha256": vsha, "metadata": METADATA, "latency_s": res.latency_s}))
        return res

    def tracks(self, video: Path, prompt: str, info: VideoInfo) -> TrackSet:
        res = self.track(video, prompt)
        return to_trackset(parse_output(res.deltas), info, prompt, res.source_ref)


def sam_perceiver(tracker: SamTracker, video_dir: Path | None = None):
    """Challenge Mode perceiver backed by live (or cached) SAM 3.1. Ground truth is NOT given to SAM;
    only the rendered pixels are uploaded."""
    from eventproof.challenge.render import encode_mp4
    from eventproof.challenge.scene import SceneSpec

    vdir = video_dir or CACHE_DIR / "videos"

    def perceive(scene: SceneSpec, gt: TrackSet) -> TrackSet:
        vdir.mkdir(parents=True, exist_ok=True)
        mp4 = vdir / f"{scene.scene_hash()[:16]}.mp4"
        if not mp4.exists():
            encode_mp4(scene, mp4)
        concept = scene.objects[0].label if scene.objects else "box"
        return tracker.tracks(mp4, concept, gt.video)

    return perceive

