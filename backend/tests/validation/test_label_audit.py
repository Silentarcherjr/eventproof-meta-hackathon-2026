"""The Santos label audit: track 0 moves away from the camera (forbidden), track 1 toward it (allowed)."""

from __future__ import annotations

import json

from eventproof.schemas.tracks import TrackSet
from eventproof.validation.real_video import ROOT


def test_tracks_support_the_audit():
    audit = json.loads((ROOT / "benchmark/real/santos/label_audit.json").read_text())
    t = TrackSet.model_validate_json((ROOT / audit["evidence"]["run"] / "tracks.json").read_text())

    def ys(oid):
        return [f.box.y2 / t.video.height for f in sorted(t.frames, key=lambda f: f.frame_index) if f.object_id == oid]

    y0, y1 = ys(0), ys(1)
    assert y0[0] > 0.75 > min(y0)        # starts below the line (near the camera), ends above it: rides away
    assert y1[0] < 0.75 < max(y1)        # starts above the line, ends below it: rides toward the camera
