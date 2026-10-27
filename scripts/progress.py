"""Validate .progress/tasks.json and render docs/TASKS.md, docs/STATUS.md and the table in docs/PROGRESS.md.

Usage:
    python scripts/progress.py check    # validate only (used by CI)
    python scripts/progress.py render   # validate + rewrite generated docs
    python scripts/progress.py set <ID> <STATE> [--sha SHA] [--next "..."] [--blocker "..."]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / ".progress" / "tasks.json"
STATES = {"TODO", "READY", "IN_PROGRESS", "BLOCKED", "IN_REVIEW", "DONE_VERIFIED", "FAILED", "DEFERRED"}
PRIORITIES = {"P0", "P1", "P2"}
FIELDS = [
    "id", "title", "priority", "gate", "state", "dependencies", "owner", "branch",
    "definition_of_done", "test_commands", "evidence_paths", "commit_sha", "pr_url",
    "started_at", "updated_at", "blocker", "next_action", "cost_note",
]
BEGIN, END = "<!-- BEGIN GENERATED TABLE -->", "<!-- END GENERATED TABLE -->"
PANAMA = timezone(timedelta(hours=-5))


def load() -> list[dict]:
    return json.loads(TASKS.read_text())["tasks"]


def validate(tasks: list[dict]) -> list[str]:
    errors = []
    ids = [t.get("id") for t in tasks]
    if len(ids) != len(set(ids)):
        errors.append("duplicate task ids")
    known = set(ids)
    for t in tasks:
        tid = t.get("id")
        missing = [f for f in FIELDS if f not in t]
        if missing:
            errors.append(f"{tid}: missing fields {missing}")
        if t.get("state") not in STATES:
            errors.append(f"{tid}: bad state {t.get('state')}")
        if t.get("priority") not in PRIORITIES:
            errors.append(f"{tid}: bad priority {t.get('priority')}")
        for dep in t.get("dependencies", []):
            if dep not in known:
                errors.append(f"{tid}: unknown dependency {dep}")
        if t.get("state") == "DONE_VERIFIED" and not t.get("commit_sha"):
            errors.append(f"{tid}: DONE_VERIFIED requires commit_sha")
        if t.get("state") == "BLOCKED" and not t.get("blocker"):
            errors.append(f"{tid}: BLOCKED requires blocker")
    return errors


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def counts(tasks: list[dict], prio: str) -> str:
    sel = [t for t in tasks if t["priority"] == prio]
    done = sum(t["state"] == "DONE_VERIFIED" for t in sel)
    return f"{done}/{len(sel)}"


def cell(v) -> str:
    if v is None or v == []:
        return "-"
    if isinstance(v, list):
        v = ", ".join(v)
    return str(v).replace("|", "\\|")


def table(tasks: list[dict]) -> str:
    rows = ["| ID | Pri | Gate | Deliverable | State | Owner | Depends on | Commit | Evidence |",
            "|----|-----|------|-------------|-------|-------|------------|--------|----------|"]
    for t in tasks:
        sha = (t["commit_sha"] or "")[:7] or "-"
        rows.append(f"| {t['id']} | {t['priority']} | {t['gate']} | {cell(t['title'])} | {t['state']} | "
                    f"{cell(t['owner'])} | {cell(t['dependencies'])} | {sha} | {cell(t['evidence_paths'])} |")
    return "\n".join(rows)


def render(tasks: list[dict]) -> None:
    stamp = datetime.now(PANAMA).strftime("%Y-%m-%d %H:%M")
    # TASKS.md: grouped checklist
    lines = ["# EventProof — Tasks (generated from `.progress/tasks.json`, do not edit by hand)", ""]
    for prio in ("P0", "P1", "P2"):
        lines += [f"## {prio}", ""]
        for t in tasks:
            if t["priority"] != prio:
                continue
            box = "x" if t["state"] == "DONE_VERIFIED" else " "
            lines.append(f"- [{box}] **{t['id']}** ({t['gate']}, {t['state']}) {t['title']} — DoD: {t['definition_of_done']}")
        lines.append("")
    (ROOT / "docs" / "TASKS.md").write_text("\n".join(lines))

    # STATUS.md: 60-second summary
    active = [t for t in tasks if t["state"] == "IN_PROGRESS"]
    blocked = [t for t in tasks if t["state"] == "BLOCKED"]
    status = [
        "# EventProof — STATUS (generated)", "",
        f"Updated (America/Panama): {stamp}  ",
        "Deadline: 2026-11-04 21:00 America/Panama (internal target 17:00)  ",
        f"P0 verified: {counts(tasks, 'P0')} · P1: {counts(tasks, 'P1')} · P2: {counts(tasks, 'P2')}", "",
        "## In progress", *([f"- {t['id']}: {t['title']} ({t['owner']})" for t in active] or ["- none"]), "",
        "## Blocked", *([f"- {t['id']}: {t['blocker']}" for t in blocked] or ["- none"]), "",
    ]
    (ROOT / "docs" / "STATUS.md").write_text("\n".join(status))

    # PROGRESS.md: replace generated table + counters line
    prog = ROOT / "docs" / "PROGRESS.md"
    text = prog.read_text()
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    out = []
    for line in head.splitlines():
        if line.startswith("P0 completion:"):
            line = f"P0 completion: {counts(tasks, 'P0')} verified   P1 completion: {counts(tasks, 'P1')} verified   P2: {counts(tasks, 'P2')}"
        elif line.startswith("Last updated (America/Panama):"):
            line = f"Last updated (America/Panama): {stamp}"
        out.append(line)
    prog.write_text("\n".join(out) + "\n" + BEGIN + "\n" + table(tasks) + "\n" + END + tail)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("render")
    s = sub.add_parser("set")
    s.add_argument("id")
    s.add_argument("state", choices=sorted(STATES))
    s.add_argument("--sha")
    s.add_argument("--next")
    s.add_argument("--blocker")
    s.add_argument("--evidence", action="append", default=[])
    args = ap.parse_args()

    data = json.loads(TASKS.read_text())
    tasks = data["tasks"]
    if args.cmd == "set":
        task = next((t for t in tasks if t["id"] == args.id), None)
        if task is None:
            sys.exit(f"unknown task {args.id}")
        task["state"] = args.state
        task["updated_at"] = now_utc()
        if args.state == "IN_PROGRESS" and not task["started_at"]:
            task["started_at"] = task["updated_at"]
        if args.sha:
            task["commit_sha"] = args.sha
        if args.next is not None:
            task["next_action"] = args.next
        if args.blocker is not None:
            task["blocker"] = args.blocker
        task["evidence_paths"] = sorted(set(task["evidence_paths"]) | set(args.evidence))

    errors = validate(tasks)
    if errors:
        sys.exit("tracker invalid:\n  " + "\n  ".join(errors))
    if args.cmd == "set":
        TASKS.write_text(json.dumps(data, indent=2) + "\n")
    if args.cmd in ("render", "set"):
        render(tasks)
    print(f"ok: {len(tasks)} tasks, P0 {counts(tasks, 'P0')}")


if __name__ == "__main__":
    main()
