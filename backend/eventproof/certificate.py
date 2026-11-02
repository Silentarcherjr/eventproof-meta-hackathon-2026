"""Rule certificate: one page that says what a rule means, how hard it was attacked, whether a repair held, and how it did
on labelled real footage, with every model request id and file hash needed to re-check it.

Built only from files that already exist for a run (evidence, Challenge/Repair results, the two-readings check, the
pre-registered final test, real-footage reports whose labels use the same rule text) plus the run's ledger. Nothing is
recomputed or called; a section with no data says so. The status is a fixed function of those results:

- NOT CERTIFIED     Challenge Mode found failures and no repair passed the hidden holdout, or the field check has a
                    wrong verdict.
- REPAIR CERTIFIED (synthetic) / CONDITIONAL  the accepted repair passed the hidden holdout, but no labelled footage of a
                    deployment scene checked it yet, or footage checked it and it failed there (then: REJECTED IN THE FIELD).
- CERTIFIED FOR CHECKED SCENES  labelled real footage of this rule text exists and the rule made no wrong verdict on it.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from eventproof import ledger, studio
from eventproof.pipeline import RUNS_DIR, Evidence

ROOT = Path(__file__).resolve().parents[2]
REAL_DIR = ROOT / "benchmark" / "real"
FINAL_REPORT = ROOT / "benchmark" / "final" / "report_final_v1.json"


def _wilson(k: int, n: int) -> tuple[float, float]:
    from eventproof.validation.evaluate import wilson

    return wilson(k, n)


def field_checks(rule_text: str, real_dir: Path = REAL_DIR) -> list[dict]:
    """Real-video reports (labels frozen before any model call) whose clips were labelled with this exact rule text."""
    out = []
    for rep_path in sorted(real_dir.glob("*/report_*.json")):
        rep = json.loads(rep_path.read_text())
        if rep.get("schema_version") != "eventproof-real-report/1":
            continue
        for c in rep["clips"]:
            label_path = rep_path.parent / "labels" / c["label_file"]
            if not label_path.is_file() or json.loads(label_path.read_text())["rule_text"].strip() != rule_text.strip():
                continue
            rows = (c.get("objects") or {}).get("labeled", [])
            out.append({
                "set": rep_path.parent.name, "report": str(rep_path.relative_to(ROOT)), "clip": c["clip"],
                "clip_sha256": c["clip_sha256"], "labelled": len(rows),
                "rule": {"right": sum(r["agree_before"] for r in rows),
                         "abstained": sum(r["before"] == "UNKNOWN" for r in rows),
                         "not_tracked": sum(r["matched_object_id"] is None for r in rows),
                         "overall_agrees": c["before"]["agrees_overall"]},
                "repair": {"proposal_id": rep["repair"]["proposal_id"], "source_run": rep["repair"]["run_id"],
                           "right": sum(r["agree_after"] for r in rows),
                           "overall_agrees": c["after"]["agrees_overall"]},
            })
    return out


def build(run_id: str, runs_dir: Path | None = None, chosen: str | None = None) -> dict:
    run_dir = (runs_dir or RUNS_DIR) / run_id
    ev = Evidence.model_validate_json((run_dir / "evidence.json").read_text())
    st = lambda k: studio.stored(run_id, k, runs_dir)  # noqa: E731
    ch, rep, amb, ba = st("challenge"), st("repair-muse"), st("ambiguity"), st("before-after-muse")
    led = ledger.build(run_dir)
    cert: dict = {
        "schema": "eventproof-certificate/1", "run_id": run_id, "created_at": ev.created_at,
        "rule": {"text": ev.rule.text, "model": ev.rule.model, "request_ids": ev.rule.request_ids,
                 "cached": ev.rule.cached, "assumptions": ev.rule.assumptions, "rule_hash": ev.rule.rule_hash,
                 "explanation": (ev.rule.compiled_rule or {}).get("normalized_explanation")},
        "readings": None, "challenge": None, "repair": None, "final_test": None, "field": [],
        "hashes": {"evidence_sha256": ev.evidence_sha256, "ledger_sha256": led["ledger_sha256"],
                   "video_sha256": ev.video.sha256, "files": len(led["files"])},
    }
    if amb and amb.get("text", "").strip() == ev.rule.text.strip():
        cert["readings"] = {"models": amb["models"], "plain": [r.get("plain") for r in amb["readings"]],
                            "ok": [r["ok"] for r in amb["readings"]], "comparison": amb["comparison"],
                            "pair": amb["pair"] and {k: amb["pair"][k] for k in ("family", "knob", "t_differ", "t_agree",
                                                                                    "differ", "agree")},
                            "chosen": chosen if chosen in ("A", "B") else None}
    if ch:
        cx = ch.get("counterexample")
        cert["challenge"] = {"world": ch["world"], "perception": ch["perception"],
                             "scenes": ch["suite_cases"],
                             "failures": ch["failures"],
                             "counterexample": cx and {k: cx.get(k) for k in (
                                 "family", "seed", "outcome", "detector_verdict",
                                                                              "intended", "knob", "t_fail", "t_pass")}}
    if rep:
        dec = rep["decisions"]
        acc = [d for d in dec if d["accepted"]]
        first = acc[0] if acc else None
        cert["repair"] = {"proposer": rep["proposer"], "proposals": len(dec), "accepted": len(acc),
                          "first_accepted": first and {
                              "proposal_id": first["proposal"]["proposal_id"], "patch": first["patch_description"],
                              "holdout": first["holdout_name"], "holdout_manifest_sha256": first["holdout_manifest_sha256"],
                              "before": first["holdout_before"], "after": first["holdout_after"],
                              "regressions": len(first["regressions"]),
                              "plain_after": (ba or {}).get("after", {}).get("plain")}}
        if FINAL_REPORT.is_file() and first:
            fr = json.loads(FINAL_REPORT.read_text())
            p = next((p for p in fr["patches"] if p["proposal_id"] == first["proposal"]["proposal_id"]
                      and p["source"] == "muse-studio-run"), None)
            if p and fr["baselines"].get("muse-studio-run"):
                base = fr["baselines"]["muse-studio-run"]
                cert["final_test"] = {sp: {"n": m["n"], "before": base[sp]["correct"], "after": m["correct"],
                                           "regressed": p["regressed"][sp]} for sp, m in p["splits"].items()}
    cert["field"] = field_checks(ev.rule.text)
    cert["status"] = status(cert)
    return cert


def status(c: dict) -> dict:
    f = c["field"]
    n = sum(x["labelled"] for x in f)
    right = sum(x["rule"]["right"] for x in f)
    abst = sum(x["rule"]["abstained"] for x in f)
    missed = sum(x["rule"].get("not_tracked", 0) for x in f)
    wrong = n - right - abst - missed
    reasons, rep = [], c["repair"]
    if f:
        reasons.append(f"labelled real footage: {right}/{n} objects right, {abst} abstained, {missed} not tracked, "
                       f"{wrong} wrong verdicts "
                       f"({len(f)} clip(s); Wilson 95 % {_wilson(right, n)})")
        rep_right = sum(x["repair"]["right"] for x in f)
        reasons.append(f"repair {f[0]['repair']['proposal_id']} from run {f[0]['repair']['source_run']} "
                       "on the same footage: "
                       f"{rep_right}/{n} right" + (" - do not deploy it for these scenes" if rep_right < right else ""))
        if wrong:
            return {"label": "NOT CERTIFIED", "reasons": reasons}
        if missed:
            reasons.append(f"{missed} labelled object(s) never got a track: the rule cannot judge what perception misses; "
                           "fix the camera view or crop before certifying those scenes")
            return {"label": "CONDITIONAL: PERCEPTION GAPS", "reasons": reasons}
        return {"label": "CERTIFIED FOR CHECKED SCENES", "reasons": reasons}
    if c["challenge"] and c["challenge"]["failures"]:
        reasons.append(f"Challenge Mode: {c['challenge']['failures']}/{c['challenge']['scenes']} synthetic scenes fail "
                       "with the rule as written")
        first = rep and rep["first_accepted"]
        if first:
            reasons.append(f"accepted repair {first['proposal_id']}: hidden holdout {first['before']['correct']}/"
                           f"{first['before']['n']} -> {first['after']['correct']}/{first['after']['n']}, "
                           f"{first['regressions']} regressions")
            reasons.append("no labelled footage of a deployment scene yet: certify the repair only after a field check")
            return {"label": "REPAIR CONDITIONAL", "reasons": reasons}
        return {"label": "NOT CERTIFIED", "reasons": reasons}
    reasons.append("not challenged yet and no field check")
    return {"label": "NOT CERTIFIED", "reasons": reasons}


# ---- HTML (one printable page) -----------------------------------------------------------------------------------------

def _e(x) -> str:
    return html.escape(str(x))


def render_html(c: dict) -> str:
    s = c["status"]
    colour = {"CERTIFIED FOR CHECKED SCENES": "#15803d", "REPAIR CONDITIONAL": "#b45309",
              "CONDITIONAL: PERCEPTION GAPS": "#b45309"}.get(s["label"], "#b91c1c")
    rows = []

    def section(title: str, body: str) -> None:
        rows.append(f"<section><h2>{_e(title)}</h2>{body}</section>")

    r = c["rule"]
    section("1 · The rule", f"<p class='rule'>“{_e(r['text'])}”</p><p>{_e(r['explanation'] or '')}</p>"
            f"<p class='k'>How {_e(r['model'])} read it</p><ul>" + "".join(f"<li>{_e(a)}</li>" for a in r["assumptions"])
            + "</ul>")
    rd = c["readings"]
    if rd:
        cmp = rd["comparison"]
        body = "<ul>" + "".join(f"<li><b>{_e(m)}</b>: {_e(p or 'declined')}</li>"
                                for m, p in zip(rd["models"], rd["plain"], strict=True)) + "</ul>"
        if cmp:
            body += (f"<p>The two readings give different verdicts on <b>{cmp['disagree']}/{cmp['scenes']}</b> synthetic "
                     "scenes with known tracks.</p>")
        if rd["pair"]:
            p = rd["pair"]
            body += (f"<p>Minimal pair ({_e(p['family'])}, {_e(p['knob'])} {p['t_differ']:.5f} vs {p['t_agree']:.5f}): "
                     f"verdicts {p['differ']['verdicts']} vs {p['agree']['verdicts']}.</p>")
        body += f"<p class='k'>Reading chosen by the reviewer: {_e(rd['chosen'] or 'not recorded')}</p>"
        section("2 · Two independent readings", body)
    else:
        section("2 · Two independent readings", "<p class='muted'>Not run for this rule.</p>")
    chx = c["challenge"]
    if chx:
        cx = chx["counterexample"] or {}
        section("3 · Attack (Challenge Mode)",
                f"<p>{chx['scenes']} synthetic scenes with known truth ({_e(chx['world'])}; "
                f"perception {_e(chx['perception'])}): "
                f"<b>{chx['failures']} failures</b>.</p>"
                + (f"<p>Clearest: {_e(cx.get('family'))} #{_e(cx.get('seed'))}, rule says {_e(cx.get('detector_verdict'))}, "
                   f"truth {_e(cx.get('intended'))} ({_e(cx.get('outcome'))}); minimal pair on {_e(cx.get('knob'))} "
                   f"{cx.get('t_fail'):.4f} vs {cx.get('t_pass'):.4f}.</p>" if cx.get("knob") else ""))
    else:
        section("3 · Attack (Challenge Mode)", "<p class='muted'>Not run for this rule.</p>")
    rp = c["repair"]
    if rp and rp["first_accepted"]:
        f = rp["first_accepted"]
        body = (f"<p>{rp['proposals']} proposals by {_e(rp['proposer'])}, <b>{rp['accepted']} accepted</b>. First accepted: "
                f"<code>{_e(f['patch'])}</code>.</p><p>{_e(f['plain_after'] or '')}</p>"
                f"<p>Hidden holdout {_e(f['holdout'])} (manifest {_e(f['holdout_manifest_sha256'][:12])}…): "
                f"<b>{f['before']['correct']}/{f['before']['n']} → {f['after']['correct']}/{f['after']['n']}</b>, "
                f"false PASS {f['before']['false_pass']} → {f['after']['false_pass']}, {f['regressions']} regressions.</p>")
        if c["final_test"]:
            body += "<p>Pre-registered final test (evaluated once): " + ", ".join(
                f"{_e(sp)} {v['before']} → {v['after']}/{v['n']} ({v['regressed']} regressed)"
                for sp, v in c["final_test"].items()) + ".</p>"
        section("4 · Repair, graded on scenes it never saw", body)
    elif rp:
        section("4 · Repair", f"<p>{rp['proposals']} proposals, none accepted.</p>")
    else:
        section("4 · Repair", "<p class='muted'>Not run for this rule.</p>")
    if c["field"]:
        tr = "".join(
            f"<tr><td>{_e(x['set'])} / {_e(x['clip'])}</td><td>{x['labelled']}</td><td>{x['rule']['right']}"
            f"{' (' + str(x['rule']['abstained']) + ' abstained)' if x['rule']['abstained'] else ''}"
            f"{' (' + str(x['rule'].get('not_tracked', 0)) + ' not tracked)' if x['rule'].get('not_tracked') else ''}</td>"
            f"<td>{x['repair']['right']}</td></tr>" for x in c["field"])
        section("5 · Field check on labelled real footage (labels frozen before any model call)",
                "<table><tr><th>clip</th><th>labelled</th><th>this rule right</th><th>with repair "
                f"{_e(c['field'][0]['repair']['proposal_id'])}</th></tr>{tr}</table>")
    else:
        section("5 · Field check on labelled real footage",
                "<p class='muted'>No labelled footage for this rule text yet.</p>")
    h = c["hashes"]
    section("6 · Re-verify", f"<p class='mono'>run {_e(c['run_id'])} · evidence {_e(h['evidence_sha256'][:16])}… · ledger "
            f"{_e(h['ledger_sha256'][:16])}… ({h['files']} files) · video {_e(h['video_sha256'][:16])}… · rule "
            f"{_e(r['rule_hash'][:16])}… · request ids {_e(', '.join(r['request_ids']))}"
            f"{' (recorded response)' if r['cached'] else ''}"
            "</p><p class='muted'>`uv run python -m eventproof.ledger verify &lt;run folder&gt;` re-hashes every file.</p>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Rule certificate · {_e(c['run_id'])}</title>
<style>
body{{font:15px/1.45 -apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;color:#18181b;max-width:860px;
margin:32px auto;padding:0 24px}}
h1{{font-size:26px;margin:0}} h2{{font-size:16px;margin:18px 0 6px;border-bottom:1px solid #e4e4e7;padding-bottom:4px}}
.status{{display:inline-block;margin:10px 0;padding:6px 12px;border-radius:6px;color:white;font-weight:700;
background:{colour}}}
.rule{{font-size:18px;font-weight:600}} .k{{font-weight:600}} .muted{{color:#71717a}}
.mono,code{{font:12px ui-monospace,Menlo,monospace}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid #e4e4e7;padding:4px 6px;text-align:left}}
ul{{margin:4px 0;padding-left:20px}} @media print{{body{{margin:0}}}}</style></head><body>
<h1>Rule certificate</h1>
<div class="muted">EventProof · run {_e(c['run_id'])} · created {_e(c['created_at'])}</div>
<div class="status">{_e(s['label'])}</div><ul>{''.join(f'<li>{_e(x)}</li>' for x in s['reasons'])}</ul>
{''.join(rows)}
<p class="muted">Built only from recorded results of this run and committed reports; no model was called to write it.</p>
</body></html>"""
