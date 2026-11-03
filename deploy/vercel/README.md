# Private hosted studio on Vercel

One Vercel project (`eventproof-studio`, team HACKS) with two services:
- **studio:** the Next.js app in `frontend/`.
- **api:** the FastAPI backend as a container (`Dockerfile.api`, with ffmpeg).

`/api/*` goes to the API (it also accepts the prefix: `EVENTPROOF_PATH_PREFIX=/api`), and everything else goes to the
studio.

**Access.** Vercel Authentication is on for all deployments, so only members of the team can open the studio. Scripted
checks use the project's protection-bypass secret in the `x-vercel-protection-bypass` header. The secret is kept
outside the repo.

**What a visitor can do.** `EVENTPROOF_MODE=hosted`: the studio opens with a gallery of real clips
(`EVENTPROOF_DEMO_RUNS`). A visitor picks one, edits the rule and runs it.
- Muse Spark compiles the new sentence live.
- SAM 3.1 tracks come from the cache unless the rule names a new concept.
- Challenge Mode, the baseline repair and the certificate run on the server for free.
- The live-call caps are per container instance (`EVENTPROOF_MAX_LIVE_MUSE_CALLS=40`,
  `EVENTPROOF_MAX_LIVE_SAM_CALLS=6`). There is a per-IP rate limit, and one heavy job runs at a time.
- `MODEL_API_KEY` is set by the participant in the Vercel dashboard and never stored in the repo.
- New runs live on the instance's disk and disappear when it is recycled. Recorded runs are baked into the image.

**Deploy.** The recorded runs and their Pexels clips are not in git, because the repo does not redistribute them. So
the deployment is uploaded from a staging folder:

    sh deploy/vercel/stage.sh /tmp/ep-stage
    cd /tmp/ep-stage && vercel link --project eventproof-studio --scope hacks10 && vercel deploy

Git pushes are ignored by the project (`commandForIgnoringBuildStep`: build only when `.vercel-staged`, a file that
only the staging folder has, is present).
