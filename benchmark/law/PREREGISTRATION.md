# Compile the law as written (pre-registered BEFORE any model call for it)

Date: 2026-11-04.

**Inputs:**
- **Statutes:** `statutes.json`, verbatim operative clauses copied from the official legislature pages:
  - Md. Code, Transportation § 21-707(a): the Maryland statute; Takoma Park's automated stop-sign citations are issued
    in Maryland.
  - Cal. Vehicle Code § 22450(a).
  - Neither states a stop duration or a speed for "stop".
- **Law mode of the compiler** (`rule-schema/6-law`, `muse_rules.py`): the statute text is the rule text, unchanged.
  - Every concrete value in the rule needs a provenance entry, either QUOTED (exact words of the statute) or ASSUMED
    (with a reason).
  - A deterministic check rejects any QUOTED entry that is not a verbatim substring of the statute, with one retry; a
    second failure counts as compile failed.
- **Models:** muse-spark-1.3 and muse-wonder-1.0.
- **Scenes:** the two traffic layouts (Novi Sad; Wroclaw w1/w2/w3), so 2 statutes × 2 models × 2 layouts = 8 compiles,
  at most 12 live calls with retries.
- **Cars:** the 30 labelled cars of `novisad`, `traffic_v2` and `traffic_v3`, judged on their committed SAM 3.1 tracks
  (anchor_v4 runs).
- **Truth under these statutes:** VIOLATION if the car crossed the stop line without stopping (labelled
  stood_still_s = 0), else PASS. On these clips this equals the frozen labels: every car that stopped stood for at
  least 4 s.

**Outcomes, reported as they come:**
- per statute × model:
  - compiled / 2;
  - cars right, wrong and abstained;
  - QUOTED vs ASSUMED counts;
- **cars whose verdict flips when a value the model marked ASSUMED is varied**, using the same variant menu as
  `benchmark/tickets` (time ±20 %, stillness speed ×0.5/×2 or meaning, measured point, line ±1–3 %);
- Spark vs Wonder verdict splits.

No statute text, layout or label is changed after this commit.
