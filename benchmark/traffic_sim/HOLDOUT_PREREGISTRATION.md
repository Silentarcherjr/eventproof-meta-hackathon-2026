# Sealed traffic holdout: the rule Muse Spark compiles, judged against the stated contract (pre-registered)

Date: 2026-11-04. Written before the compile call and before any run on the holdout.

**Set.** `benchmark/traffic_sim/v1/holdout/`: 200 synthetic scenes (8 families x 25 seeds, 100000-100024), frozen by
release hash `fd9f6567...036bb7b` and never evaluated before. Perfect synthetic tracks (`source: "synthetic"`): this
measures the **rule**, not perception. No SAM call.

**Rule.** Muse Spark 1.3 (anchor schema, as used on real footage) compiles *"Every car must wait at least 1.5 seconds
in the waiting zone before it crosses the stop line."* once, with the holdout layout: zone `waiting`, line `stop_line`
(cars travel left to right). One live call, recorded in `holdout_eval/cache/`.

**Truth.** The generator's stated contract (`README.md`): >= 1.5 s of windowed stillness (<= 0.01 frame units/s) in the
zone before the first crossing.

**Outcome.** Per family: scenes where Spark's rule matches the contract, spec errors (the rule decides differently from
the contract on perfect tracks), abstentions. Also the same 200 scenes with the contract's own rule (`traffic_rule`) as
a control, which must be 200/200. Reported as is; no change to the rule after seeing results.

**Reading.** A disagreement here is not Spark being "wrong" about the law: the law never wrote these numbers. It shows,
on 200 sealed scenes, how far one model's silent choice sits from one written contract, which is the open choice the
approval gate asks a person to sign.
