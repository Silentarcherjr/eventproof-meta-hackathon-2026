from __future__ import annotations

from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo
from eventproof.validation.line_check import crossings, match, score

INFO = VideoInfo(width=100, height=50, fps=10, frame_count=100)


def _ts(paths: dict[int, list[tuple[int, float]]]) -> TrackSet:
    """paths: track id -> [(frame, center x in px)]"""
    return TrackSet(video=INFO, source="mock", frames=[
        TrackFrame(frame_index=f, timestamp_ms=INFO.frame_to_ms(f), object_id=oid, label="package",
                   box=Box(x1=cx - 5, y1=10, x2=cx + 5, y2=20))
        for oid, pts in paths.items() for f, cx in pts])


def test_crossings_are_right_to_left_center_passages_including_jitter():
    ts = _ts({1: [(0, 60), (5, 52), (10, 48), (15, 40)],   # one crossing at frame 10
              2: [(0, 30), (10, 70)],                       # left to right: not counted
              3: [(20, 55), (21, 45), (22, 55), (23, 45)]})  # jitter: two crossings, both counted
    c = crossings(ts, 0.5)
    assert [(x["track_id"], x["frame"]) for x in c] == [(1, 10), (3, 21), (3, 23)]
    assert c[0]["t_s"] == 1.0


def test_match_is_one_to_one_order_preserving_and_within_tolerance():
    assert match([1.0, 2.0, 3.0], [1.1, 2.6, 2.9], 1.0) == [(0, 0), (1, 1), (2, 2)]
    assert match([1.0, 5.0], [1.2, 1.3, 9.0], 1.0) == [(0, 0)]  # one label cannot take two detections
    assert match([], [1.0], 1.0) == [] and match([1.0], [], 1.0) == []
    # prefers smaller total |dt| among maximal matchings
    assert match([2.0], [1.5, 2.1], 1.0) == [(0, 1)]


def test_score_counts_misses_false_crossings_and_track_ids():
    lab = {"line": {"x": 0.5}, "scored_window_s": [1.0, 9.0], "match_tolerance_s": 1.0}
    ts = _ts({1: [(9, 60), (10, 40)], 2: [(29, 60), (30, 40)], 3: [(59, 60), (60, 40)]})
    s = score({"crossings_s": [1.0, 3.0, 8.0]}, ts, lab)
    assert s["matched"] == 2 and s["missed"] == [8.0] and s["distinct_track_ids_matched"] == 2
    assert [c["t_s"] for c in s["false_crossings_in_window"]] == [6.0]


def test_committed_pexels_report_is_reproducible_from_the_cached_sam_output(monkeypatch, tmp_path):
    import json

    from eventproof.perception import sam as sam_mod
    from eventproof.validation import line_check

    monkeypatch.setattr(sam_mod, "get_client", lambda s: (_ for _ in ()).throw(AssertionError("no API calls")))
    real_dir = line_check.DIR
    fake = tmp_path / "pexels"
    fake.mkdir()
    for f in ("labels.json",):
        (fake / f).write_text((real_dir / f).read_text())
    (fake / "sam_cache").symlink_to(real_dir / "sam_cache")
    monkeypatch.setattr(line_check, "DIR", fake)
    committed = json.loads((real_dir / "report_pexels.json").read_text())
    rep = line_check.run(0)
    for k in ("code_commit", "live_sam_calls_this_run"):
        committed.pop(k)
        rep.pop(k, None)
    for c in (committed, rep):
        for clip in c["clips"].values():
            clip.pop("source_ref")
    assert json.loads(json.dumps(rep)) == committed
