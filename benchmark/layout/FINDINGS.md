# Muse Spark proposes the zone and line from the first frame: results

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md). Data: [`report.json`](report.json), raw proposals in
[`cache/`](cache/) (5 calls). CI recomputes the scores from the cache and the committed tracks (`test_layout_eval.py`).

| clip | zone IoU vs hand | line angle off | labelled cars right: hand layout | proposed layout |
|---|---|---|---|---|
| Novi Sad a | 0.47 | 35° | 5/5 | **5/5** |
| Novi Sad b | 0.45 | 30° | 3/3 | **3/3** |
| Wroclaw w1 | 0.00 | 0° (30 % lower) | 6/6 | **0/6** (3 cars no longer cross the proposed line) |
| Wroclaw w2 | 0.00 | 0° (33 % lower) | 8/10 + 2 abstained | 8/10 + 2 abstained |
| Wroclaw w3 | 0.24 | 0° | 5/6 | 4/6 (and it read the travel direction backwards) |
| **total** | median 0.24 | | **27/30** | **20/30** |

What happened: on the drone view (painted stop line visible) the proposal gives the same verdicts as the hand layout even
though the polygons differ. On the footbridge view there is no painted stop line inside the crop; Muse said so in its
assumptions ("no painted stop line is visible, so a proxy stop line was placed…") and put the line elsewhere, and in one
clip it inferred the wrong travel direction from lane arrows.

Product consequence: the proposal is shown as a draft with Muse's assumptions next to it, and the user confirms or redraws
it before the rule runs; the certificate records which layout was used. It is not trusted silently.
