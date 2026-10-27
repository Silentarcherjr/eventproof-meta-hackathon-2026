"""Parser for the SAM 3.1 video output wire format (boxes; masks kept opaque).

Format (dev.meta.ai/docs/sam/segmenting and /reading-segmentation, read 2026-10-27):
- one line per frame that has detections, each sent as one `response.output_text.delta`;
- a line is `<Nf>` followed by comma-separated records; frames with no detections emit no line, so
  indices skip; never assume the k-th line is frame k;
- a record is `<object id><|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..[;c=..]|><|mask;x=..;y=..;data=H,W,<enc>payload|>`;
- box corners are source pixels, x2/y2 INCLUSIVE; w/h are the source frame size, repeated on every record;
- ids are stable within one response, not dense, not guaranteed across entry/exit/full occlusion.

Mask payloads are base85 with an unpublished alphabet, so their characters may include `|>` or `,`.
A mask token therefore ends only at a `|>` followed by end of line or by the next record
(`,<digits><|box;`). Masks are not decoded here: EventProof's rules use boxes; decoding needs the
official `meta-sam-parser` (not installed; requires participant approval).

Hand-written because the official parser was not installed; strict by default: malformed input
raises `SamParseError` with the line number instead of being silently skipped.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel, Field

FRAME_RE = re.compile(r"<(\d+)f>")
RECORD_RE = re.compile(
    r"(?P<oid>\d+)"
    r"<\|box;(?P<box>[^|]*)\|>"
    r"(?:<\|mask;x=(?P<mx>-?\d+);y=(?P<my>-?\d+);data=(?P<mh>\d+),(?P<mw>\d+),(?P<enc>.)(?P<payload>.*?)\|>"
    r"(?=$|,\d+<\|box;))?"
)
BOX_KEYS = ("x1", "y1", "x2", "y2", "w", "h")


class SamParseError(ValueError):
    def __init__(self, msg: str, line_no: int | None = None):
        super().__init__(f"line {line_no}: {msg}" if line_no is not None else msg)
        self.line_no = line_no


class SamMask(BaseModel):
    x: int
    y: int
    height: int
    width: int
    encoding: str = Field(description="'~' lossless, '!' one_bit")
    payload_chars: int


class SamRecord(BaseModel):
    object_id: int
    x1: int
    y1: int
    x2: int  # inclusive, as on the wire
    y2: int
    w: int
    h: int
    confidence: float | None = None
    mask: SamMask | None = None


class SamFrame(BaseModel):
    frame: int
    records: list[SamRecord]


def _box(body: str, line_no: int) -> dict:
    fields = {}
    for part in body.split(";"):
        k, sep, v = part.partition("=")
        if not sep:
            raise SamParseError(f"bad box field {part!r}", line_no)
        fields[k] = v
    missing = [k for k in BOX_KEYS if k not in fields]
    if missing:
        raise SamParseError(f"box missing {missing}", line_no)
    unknown = set(fields) - set(BOX_KEYS) - {"c"}
    if unknown:
        raise SamParseError(f"unknown box fields {sorted(unknown)}", line_no)
    try:
        out = {k: int(fields[k]) for k in BOX_KEYS}
        conf = float(fields["c"]) if "c" in fields else None
    except ValueError as e:
        raise SamParseError(f"non-numeric box field: {e}", line_no) from None
    if not (0 <= out["x1"] <= out["x2"] < out["w"] and 0 <= out["y1"] <= out["y2"] < out["h"]):
        raise SamParseError(f"box outside frame or inverted: {out}", line_no)
    if conf is not None and not 0 <= conf <= 1:
        raise SamParseError(f"confidence {conf} outside [0, 1]", line_no)
    return {**out, "confidence": conf}


def parse_line(line: str, line_no: int = 0) -> SamFrame:
    line = line.strip()
    m = FRAME_RE.match(line)
    if not m:
        raise SamParseError("line does not start with a <Nf> frame marker", line_no)
    pos, records, seen = m.end(), [], set()
    while True:
        r = RECORD_RE.match(line, pos)
        if not r:
            raise SamParseError(f"unparseable record at column {pos}: {line[pos:pos + 40]!r}", line_no)
        oid = int(r["oid"])
        if oid in seen:
            raise SamParseError(f"object {oid} twice on frame {m[1]}", line_no)
        seen.add(oid)
        mask = None
        if r["enc"] is not None:
            mask = SamMask(x=int(r["mx"]), y=int(r["my"]), height=int(r["mh"]), width=int(r["mw"]),
                           encoding=r["enc"], payload_chars=len(r["payload"]))
        records.append(SamRecord(object_id=oid, **_box(r["box"], line_no), mask=mask))
        pos = r.end()
        if pos == len(line):
            break
        if line[pos] != ",":
            raise SamParseError(f"expected ',' between records at column {pos}", line_no)
        pos += 1
    return SamFrame(frame=int(m[1]), records=records)


def split_deltas(deltas: Iterable[str]) -> list[str]:
    """Turn streamed `output_text` deltas into lines. Docs: one delta per frame line; tolerate deltas
    that carry newlines, several lines, or a line split across deltas (a new line starts at `<Nf>`
    only at the beginning of a delta or after a newline, never mid-payload)."""
    lines: list[str] = []
    buf = ""
    for d in deltas:
        if buf and not buf.endswith("\n") and FRAME_RE.match(d):
            lines.append(buf)
            buf = ""
        buf += d
        *done, buf = buf.split("\n")
        lines.extend(done)
    lines.append(buf)
    return [ln for ln in lines if ln.strip()]


def parse_output(deltas: Iterable[str]) -> list[SamFrame]:
    """Parse a whole response (deltas or full text lines). Frames are returned sorted; duplicate frame
    markers and inconsistent frame sizes are errors."""
    frames: dict[int, SamFrame] = {}
    size: tuple[int, int] | None = None
    for i, ln in enumerate(split_deltas(deltas), start=1):
        f = parse_line(ln, i)
        if f.frame in frames:
            raise SamParseError(f"frame {f.frame} emitted twice", i)
        for r in f.records:
            if size is None:
                size = (r.w, r.h)
            elif (r.w, r.h) != size:
                raise SamParseError(f"frame size changed from {size} to {(r.w, r.h)}", i)
        frames[f.frame] = f
    return [frames[k] for k in sorted(frames)]
