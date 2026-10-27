"""Visual evidence for a counterexample pair: identity events, decisive frames, side-by-side replay.

Left panel: the scene that fools the detector. Right panel: the near-identical scene judged
correctly. Both show the *perceived* tracks (what the detector saw) with their track ids.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

from eventproof.challenge.minimize import Counterexample
from eventproof.challenge.render import encode_frames, ground_truth, render_frames, sha256_file
from eventproof.challenge.scene import SceneSpec
from eventproof.perception.mock import iou
from eventproof.schemas.tracks import Box, TrackSet

HEADER = 44
PALETTE = [(255, 214, 10), (0, 230, 230), (255, 90, 200), (120, 255, 120), (255, 140, 60), (180, 160, 255)]
FAIL_RED, OK_GREEN = (230, 60, 60), (60, 200, 110)


class IdentityEvent(BaseModel):
    frame: int
    kind: str  # "merged" | "lost" | "new_id" | "switch"
    detail: str


def coverage(inner: Box, outer: Box) -> float:
    """Fraction of `inner`'s area that lies inside `outer`."""
    ix = max(0.0, min(inner.x2, outer.x2) - max(inner.x1, outer.x1))
    iy = max(0.0, min(inner.y2, outer.y2) - max(inner.y1, outer.y1))
    area = (inner.x2 - inner.x1) * (inner.y2 - inner.y1)
    return ix * iy / area if area > 0 else 0.0


def identity_events(gt: TrackSet, perceived: TrackSet, min_iou: float = 0.1) -> list[IdentityEvent]:
    """Compare perceived tracks to ground truth frame by frame and report identity failures."""
    gt_by: dict[int, list] = {}
    pr_by: dict[int, list] = {}
    for f in gt.frames:
        gt_by.setdefault(f.frame_index, []).append(f)
    for f in perceived.frames:
        pr_by.setdefault(f.frame_index, []).append(f)
    owner: dict[int, int] = {}  # gt object -> perceived track id last matched
    events: list[IdentityEvent] = []
    for fi in range(gt.video.frame_count):
        visible = [g for g in gt_by.get(fi, []) if not g.occluded]
        preds = pr_by.get(fi, [])
        for p in preds:
            matches = [g for g in visible if coverage(g.box, p.box) >= 0.6]
            # heavily overlapping objects can each lie inside each other's box; it is only a merge when
            # the detector reports fewer boxes than there are visible objects
            if len(matches) > 1 and len(preds) < len(visible):
                ids = ", ".join(str(g.object_id) for g in matches)
                events.append(IdentityEvent(frame=fi, kind="merged",
                                            detail=f"track {p.object_id} covers true objects {ids}"))
        for g in visible:
            scored = [(iou(g.box, p.box), p.object_id) for p in preds]
            score, tid = max(scored, default=(0.0, None))
            tid = tid if score >= min_iou else None
            if tid is None:
                events.append(IdentityEvent(frame=fi, kind="lost", detail=f"true object {g.object_id} not detected"))
                continue
            prev = owner.get(g.object_id)
            if prev is not None and prev != tid:
                taken = any(owner.get(o) == tid for o in owner if o != g.object_id)
                events.append(IdentityEvent(frame=fi, kind="switch" if taken else "new_id",
                                            detail=f"true object {g.object_id}: track {prev} -> {tid}"))
            owner[g.object_id] = tid
    # keep the first event of each (kind, detail) so long merges do not flood the report
    seen, out = set(), []
    for e in events:
        if (e.kind, e.detail) not in seen:
            seen.add((e.kind, e.detail))
            out.append(e)
    return out


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def overlay(img: np.ndarray, tracks_at: list, title: str, color: tuple[int, int, int], frame: int, fps: float) -> np.ndarray:
    h, w, _ = img.shape
    canvas = Image.new("RGB", (w, h + HEADER), (18, 20, 24))
    canvas.paste(Image.fromarray(img), (0, HEADER))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, w, 5], fill=color)
    d.text((10, 12), title, fill=color, font=_font(16))
    d.text((w - 120, 14), f"f{frame:04d}  {frame / fps:5.2f}s", fill=(200, 200, 200), font=_font(13))
    f12 = _font(12)
    for t in tracks_at:
        c = PALETTE[t.object_id % len(PALETTE)]
        b = t.box
        d.rectangle([b.x1, b.y1 + HEADER, b.x2 - 1, b.y2 - 1 + HEADER], outline=c, width=2)
        d.text((b.x1 + 2, b.y1 + HEADER - 15), f"id {t.object_id}", fill=c, font=f12)
    return np.asarray(canvas)


def _tracks_by_frame(ts: TrackSet) -> dict[int, list]:
    out: dict[int, list] = {}
    for f in ts.frames:
        out.setdefault(f.frame_index, []).append(f)
    return out


def _pad(frames: list[np.ndarray], n: int) -> list[np.ndarray]:
    return frames + [frames[-1]] * (n - len(frames))


def perception_divergence(a: TrackSet, b: TrackSet) -> int | None:
    """First frame where the detector sees a different number of objects or different track ids."""
    ba, bb = _tracks_by_frame(a), _tracks_by_frame(b)
    for fi in range(max(a.video.frame_count, b.video.frame_count)):
        ids_a = sorted(f.object_id for f in ba.get(fi, []))
        ids_b = sorted(f.object_id for f in bb.get(fi, []))
        if ids_a != ids_b:
            return fi
    return None


def pixel_difference(a: SceneSpec, b: SceneSpec) -> dict:
    fa = [img for _, img in render_frames(a)]
    fb = [img for _, img in render_frames(b)]
    n = max(len(fa), len(fb))
    fa, fb = _pad(fa, n), _pad(fb, n)
    diff = [int(np.any(x != y, axis=2).sum()) for x, y in zip(fa, fb, strict=True)]
    changed = [i for i, d in enumerate(diff) if d]
    return {"frames_compared": n, "frames_differing": len(changed),
            "first_differing_frame": changed[0] if changed else None,
            "max_pixels_differing_in_a_frame": max(diff) if diff else 0}


def export_pair(cx: Counterexample, out_dir: Path, video: bool = True) -> dict:
    from eventproof.challenge.runner import mock_perceiver

    pair = cx.pair
    assert pair is not None
    fail_s, pass_s = pair.fail_scene, pair.pass_scene
    gt_f, gt_p = ground_truth(fail_s), ground_truth(pass_s)
    pr_f, pr_p = mock_perceiver(fail_s, gt_f), mock_perceiver(pass_s, gt_p)
    ev_f, ev_p = identity_events(gt_f, pr_f), identity_events(gt_p, pr_p)
    by_f, by_p = _tracks_by_frame(pr_f), _tracks_by_frame(pr_p)

    tf = (f"FOOLED  detector {pair.fail.detector_verdict} / truth {pair.fail.intended}"
          f"  [{pair.fail.outcome}, {pr_f.source}]")
    tp = f"CORRECT  detector {pair.passing.detector_verdict} / truth {pair.passing.intended}  [{pr_p.source}]"
    frames_f = [overlay(img, by_f.get(i, []), tf, FAIL_RED, i, fail_s.fps) for i, img in render_frames(fail_s)]
    frames_p = [overlay(img, by_p.get(i, []), tp, OK_GREEN, i, pass_s.fps) for i, img in render_frames(pass_s)]
    n = max(len(frames_f), len(frames_p))
    frames_f, frames_p = _pad(frames_f, n), _pad(frames_p, n)
    sep = np.full((frames_f[0].shape[0], 6, 3), 255, dtype=np.uint8)
    combo = [np.hstack([a, sep, b]) for a, b in zip(frames_f, frames_p, strict=True)]

    divergence = perception_divergence(pr_f, pr_p)
    decisive = sorted({e.frame for e in ev_f[:2]} | ({divergence} if divergence is not None else set()))
    if not decisive:  # spec errors: perception is fine, so show where the rule's events fire
        decisive = sorted(set(_rule_event_frames(cx, fail_s)))[:3]
    pngs = []
    for fr in decisive:
        p = out_dir / f"decisive_f{fr:04d}.png"
        Image.fromarray(combo[min(fr, n - 1)]).save(p)
        pngs.append(p.name)
    result = {"identity_events_fail": [e.model_dump() for e in ev_f],
              "identity_events_pass": [e.model_dump() for e in ev_p],
              "perception_divergence_frame": divergence,
              "decisive_frames": decisive, "decisive_pngs": pngs,
              "scene_difference": pixel_difference(fail_s, pass_s),
              "fail_scene_sha256": fail_s.scene_hash(), "pass_scene_sha256": pass_s.scene_hash()}
    if video:
        mp4 = out_dir / "side_by_side.mp4"
        h, w, _ = combo[0].shape
        result["frames_sha256"] = encode_frames(combo, w, h, fail_s.fps, mp4)
        result["side_by_side_mp4"] = mp4.name
        result["mp4_sha256"] = sha256_file(mp4)
    else:
        result["frames_sha256"] = hashlib.sha256(b"".join(c.tobytes() for c in combo)).hexdigest()
    (out_dir / "replay.json").write_text(json.dumps(result, indent=2))
    return result


def _rule_event_frames(cx: Counterexample, scene: SceneSpec) -> list[int]:
    from eventproof.challenge.runner import inspection_rule, mock_perceiver
    from eventproof.engine.evaluator import evaluate

    rep = evaluate(inspection_rule(scene, cx.dwell_ms), mock_perceiver(scene, ground_truth(scene)))
    return [e.frame for o in rep.objects for e in o.events if e.status == "TRUE" and e.frame is not None]
