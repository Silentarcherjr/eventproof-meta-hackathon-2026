# MEVA: findings. The study as designed does not measure rule accuracy (reported, not used as a result)

Pre-registered in `PREREGISTRATION.md` (commit 509e4aa). The data was extracted (476b4ee) before the run. The run made
2 Muse calls: Muse Spark compiled the rule, and Muse Wonder declined it as unsupported. `report.json` holds the result.

**Pre-registered result:**
- Muse Spark compiled "Every vehicle must come to a complete stop." to `DWELL(whole view, ≥ 1.0 s, ≤ 0.05 frame
  widths/s)`, measured at the bottom centre.
- Judged on the annotators' own boxes for 1,392 vehicle tracks, it agrees with the annotators' `vehicle_stops` label on
  **24 %** (Wilson 95 % 22–27 %).
- It finds 194 of the 245 annotated stops (79 %), and calls 1,004 of the other 1,147 tracks "stopped".
- No cell of the pre-registered grid beats the trivial "nothing stops" baseline (82 %). The best balanced accuracy is
  0.51.

**Why this does not measure what we meant (found after the run, by inspecting the annotations):**
- In these annotations a vehicle's track covers **only the span of the activity it was annotated for**, not the
  vehicle's whole time in view.
- A `vehicle_stops` track ends at the moment the car comes to rest, so there is almost no stillness after it. A
  `vehicle_starts` track begins with the car standing still.
- So the population we defined ("vehicle tracks that move") mixes activity fragments: arrivals, departures, turns and
  reversals. "Stood still for ≥ 1 s" is true for every departure, which explains the 1,004 "stopped" verdicts the
  annotators did not label as stops.
- A diagnostic ("moved, then stood still") also stays at or below the baseline: in a stop track the vehicle reaches
  rest only in its last frames.
- The rule shape the annotators use, "comes to a stop: moving, then at rest", is not expressible on these truncated
  tracks with the current events.

**What we keep from it:** it is a concrete case of what EventProof is about. The same words, "comes to a stop", denote
an event to the annotators and a state to the compiled rule, and on 1,392 independent labels the two disagree almost
everywhere. It is not counted in any accuracy figure in the README, and the 46 labelled real objects remain the
accuracy evidence.
