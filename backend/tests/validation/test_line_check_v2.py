from __future__ import annotations

from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo
from eventproof.validation import line_check_v2 as v2

FULL = VideoInfo(width=640, height=360, fps=10, frame_count=100)


def _f(frame: int, oid: int, x: float) -> TrackFrame:
    return TrackFrame(frame_index=frame, timestamp_ms=frame * 100.0, object_id=oid, label="package",
                      box=Box(x1=x, y1=100, x2=x + 40, y2=140))


def test_windows_cover_every_frame_with_overlap():
    w = v2.windows(203)
    assert w[0] == (0, 50) and w[-1] == (175, 203) and len(w) == 8
    assert all(b[0] < a[1] for a, b in zip(w, w[1:], strict=False))  # consecutive windows overlap
    assert v2.windows(30) == [(0, 30)]


def test_window_tracks_are_shifted_back_to_full_frame():
    x, y, w, h = v2.CROP
    ts = TrackSet(video=VideoInfo(width=w, height=h, fps=10, frame_count=50), source="sam-3.1",
                  frames=[_f(3, 0, 10.0)])
    (f,) = v2.to_full_frame(ts, 25, 10)
    assert f.frame_index == 28 and f.timestamp_ms == 2800.0 and f.box.x1 == 10.0 + x and f.box.y1 == 100 + y


def test_stitch_continues_overlapping_tracks_and_opens_new_ids():
    # window A: object moving left; window B (overlap frames 5-9): same object (local id 7) + a newcomer (local id 0)
    a = [_f(k, 3, 400 - 10 * k) for k in range(10)]
    b = [_f(k, 7, 400 - 10 * k) for k in range(5, 15)] + [_f(k, 0, 600) for k in range(8, 15)]
    ts = v2.stitch([a, b], FULL)
    ids = {f.object_id for f in ts.frames}
    assert ids == {0, 1}
    moving = [f for f in ts.frames if f.object_id == 0]
    assert sorted(f.frame_index for f in moving) == list(range(15))  # one continuous track, no duplicate frames
    assert len(ts.frames) == 15 + 7


def test_stitch_does_not_join_far_apart_boxes():
    a = [_f(k, 0, 100) for k in range(10)]
    b = [_f(k, 0, 500) for k in range(5, 15)]
    assert len({f.object_id for f in v2.stitch([a, b], FULL).frames}) == 2


def test_committed_v2_report_is_reproducible_from_cached_outputs(monkeypatch, tmp_path):
    import json

    from eventproof.perception import sam as sam_mod

    monkeypatch.setattr(sam_mod, "get_client", lambda s: (_ for _ in ()).throw(AssertionError("no API calls")))
    real = v2.DIR
    fake = tmp_path / "pexels"
    fake.mkdir()
    for f in ("labels.json", "tracking_v2.json"):
        (fake / f).write_text((real / f).read_text())
    (fake / "sam_cache").symlink_to(real / "sam_cache")
    monkeypatch.setattr(v2, "DIR", fake)
    monkeypatch.setattr(v2, "LOG", fake / "tracking_v2.json")
    committed = json.loads((real / "report_pexels_v2.json").read_text())
    rep = v2.run(0)
    for k in ("code_commit", "live_sam_calls_this_run"):
        committed.pop(k)
        rep.pop(k, None)
    assert json.loads(json.dumps(rep)) == committed
