# Muse Glimmer on a laptop: no valid rule within the time box

Pre-registered in [`PREREGISTRATION.md`](PREREGISTRATION.md) (commit 28b8948, addendum a84e8c5), reported as is.

**Setup.** Muse Glimmer 30B, Meta open weights, Q4_K_M GGUF (sha256 `4cc57c0f…f60e`, matches the published file),
served by Ollama 0.40.6 on an Apple M1 Max (32 GB) through its OpenAI-compatible endpoint with the same law-mode
compiler, prompt and JSON schema as the Muse Spark and Muse Wonder studies. Generation ran at about 6 to 12 tokens/s.

**What happened** (server log timestamps, ET):

| Call | Statute and layout | Duration | Outcome |
|---|---|---|---|
| 1 | Maryland, first scene layout, attempt 1 | 8 min 8 s | answer rejected by the rule validator |
| 2 | same, attempt 2 (with the validation error fed back) | 8 min 31 s | rejected again: compile counted as failed |
| 3-5 | Maryland, second scene layout | 10 min each | client timeout (600 s) three times; the run stopped at 16:17 |

**Result: 0 valid rules from 1 completed compile; 0 of the 3 remaining law-arm compiles and 0 of the 6 INTERACTION
compiles ran.** Per the pre-registration, nothing was rerun and nothing was changed after seeing these outcomes.

**What this does and does not show.** It shows that this compiler cannot run on Glimmer at Q4 on a laptop through
Ollama today: each attempt takes 8 minutes or more, and the one completed compile failed validation twice. It does
not measure Glimmer's ability to compile statutes: the run stopped on the client timeout, the rejected answers were not
recorded (the study code keeps the text of a rejected answer only in its final report, which the stopped run never
wrote), and the setup differs from a fair one in three ways that could each explain the failures: 4-bit quantization,
Ollama's handling of a nested strict schema (the Meta API enforces it; the llama.cpp server, which would also enforce
it, did not start on this Mac), and laptop speed against an evaluation built for an API. A fair test needs a GPU
server with schema-enforced decoding and an 8-bit or full-precision build.

Code: `backend/eventproof/validation/glimmer_study.py` (reuses `law_study.py` and `interaction_repeats.py` unchanged).
No Meta API call; no cost beyond local compute.
