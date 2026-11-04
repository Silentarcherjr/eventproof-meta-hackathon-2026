# Sealed traffic holdout: findings

Pre-registered in `../HOLDOUT_PREREGISTRATION.md`. 200 synthetic scenes never evaluated before, perfect tracks (not
SAM), one Muse Spark compile (recorded in `cache/`). Control: the contract's own rule gets **200/200**.

| Family (25 scenes each) | Muse Spark's rule vs the stated contract |
|---|---|
| full_stop, no_stop, brief_stop, queue, occluded, tailgate | 150/150 agree |
| rolling_stop | **0/25**: Spark chose "still" = at most 0.05 frame widths/s; the contract says 0.01. Every crawl counts as a stop for Spark and as a violation for the contract. |
| wrong_way | **0/25**: Spark read "crosses the stop line" as crossing in the travel direction (as the layout describes it); the contract counts a crossing in either direction. |

**150/200 agree; all 50 disagreements are two open choices, not engine or perception errors.** Neither sentence nor
statute writes them. This is what the approval gate asks a person to sign before a rule goes live, measured here on a
sealed set. Synthetic and perfect-track: it says nothing about perception or real-world accuracy.
