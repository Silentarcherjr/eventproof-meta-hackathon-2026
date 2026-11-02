# Real traffic v3 (Wroclaw, one more window) and the updated pooled result

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md) (45ba9ba, labels + manifest pushed before any call).
Data: [`report_wroclaw_w3.json`](report_wroclaw_w3.json), [`runs/`](runs/), [`spark_alone_wroclaw_w3.json`](spark_alone_wroclaw_w3.json),
pooled numbers [`../POOLED_v2.json`](../POOLED_v2.json) (the first pooled result, [`../POOLED.json`](../POOLED.json), stays).
Live calls: SAM 3.1 1 (91 frames), Muse Spark 5 video calls; the rule compile came from cache (same text and layout).

## wroclaw_w3 (green light, 6 labelled cars, none stops)
| reading | right | notes |
|---|---|---|
| Muse Spark's rule | 5/6 | the 6th car (grey-green SUV, crosses at ~5.8 s) **never got a SAM 3.1 track**: no verdict at all |
| + repair accepted on synthetic data | 3/6 | passes two cars that never stopped (same perspective effect as w2) |
| Muse Spark alone (5 runs) | clip verdict 5/5 | crossings and violations counted exactly in 0/5 runs |

## Pooled: 5 real traffic clips, 30 labelled cars (Novi Sad a/b + Wroclaw w1/w2/w3)
| detector | labelled cars right | notes |
|---|---|---|
| Muse Spark's rule → SAM 3.1 → engine | **27/30** (Wilson 95 % 0.74–0.97) | 2 abstained, **1 not tracked**, 0 wrong verdicts |
| Muse Wonder's rule | 27/30 | same reading as Spark for this scene |
| + repair accepted on synthetic data | **16/30** (0.36–0.70) | |
| Muse Spark alone from video | – | clip verdict 25/25 runs; counts exact 11/25 (0.27–0.63) |

The certificate now separates the two kinds of miss: a wrong verdict makes a rule NOT CERTIFIED; an object perception
never tracked makes it CONDITIONAL (the rule cannot judge what it cannot see). For this rule the status is
**CONDITIONAL: PERCEPTION GAPS** because of that one SUV.
