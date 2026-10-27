"""Live smoke tests for Meta Model API (spends a few cents of real credits).

    cd backend && uv run python ../scripts/check_meta_api.py muse
    cd backend && uv run python ../scripts/check_meta_api.py sam --video path/to/clip.mp4 --prompt "blue box"

Exit codes: 0 ok, 1 call failed, 2 BLOCKED (no key). Prints only sanitized facts (model, latency,
request id, counts) — never headers or the key — so the output can be pasted into docs/evidence/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from eventproof.meta.client import MetaApiUnavailable, MetaSettings, get_client

ADDRESS_SCHEMA = {
    "type": "object",
    "properties": {"street": {"type": "string"}, "city": {"type": "string"}},
    "required": ["street", "city"],
    "additionalProperties": False,
}


def check_muse(s: MetaSettings) -> dict:
    client = get_client(s)
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=s.muse_model,
        messages=[{"role": "user", "content": "Format this address: 1 Hacker Wy Menlo Park CA 94025"}],
        response_format={"type": "json_schema", "json_schema": {"name": "address", "schema": ADDRESS_SCHEMA, "strict": True}},
    )
    parsed = json.loads(resp.choices[0].message.content)
    return {"model": resp.model, "request_id": resp.id, "latency_s": round(time.monotonic() - t0, 2),
            "keys": sorted(parsed), "usage": resp.usage.model_dump() if resp.usage else None}


def check_sam(s: MetaSettings, video: str, prompt: str) -> dict:
    client = get_client(s)
    t0 = time.monotonic()
    with open(video, "rb") as fh:
        uploaded = client.files.create(file=fh, purpose="user_data")
    text = []
    with client.responses.stream(
        model=s.sam_model,
        input=[{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_video", "file_id": uploaded.id},
        ]}],
        metadata={"include_confidence": "true"},
    ) as stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                text.append(event.delta)
        final = stream.get_final_response()
    lines = [ln for ln in "".join(text).splitlines() if ln.strip()]
    return {"model": s.sam_model, "response_id": final.id, "latency_s": round(time.monotonic() - t0, 2),
            "frame_lines": len(lines), "first_line_prefix": lines[0][:80] if lines else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=["muse", "sam"])
    ap.add_argument("--video")
    ap.add_argument("--prompt", default="blue box")
    args = ap.parse_args()
    s = MetaSettings.from_env()
    try:
        if args.target == "muse":
            out = check_muse(s)
        else:
            if not args.video:
                sys.exit("--video is required for sam")
            out = check_sam(s, args.video, args.prompt)
    except MetaApiUnavailable as e:
        print(json.dumps({"status": "BLOCKED", "reason": str(e)}))
        sys.exit(2)
    except Exception as e:  # report the failure class, not raw payloads
        print(json.dumps({"status": "FAILED", "error": type(e).__name__, "message": str(e)[:300]}))
        sys.exit(1)
    print(json.dumps({"status": "OK", **out}, indent=2))


if __name__ == "__main__":
    main()
