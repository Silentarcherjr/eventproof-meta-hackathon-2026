#!/bin/sh
# Build the folder that `vercel deploy` uploads: tracked code + the data the hosted studio serves.
#   sh deploy/vercel/stage.sh <out_dir>
# Recorded runs (with their videos) and model caches come from the local artifacts/ folder; the public clips are
# Pexels footage that the repo does not redistribute, so they reach the private deployment only through this folder.
# Never copies backend/.env, private/ or raw downloads.
set -eu
cd "$(dirname "$0")/../.."
OUT=${1:?out dir}
test ! -e "$OUT" || { echo "$OUT exists" >&2; exit 1; }
mkdir -p "$OUT"
git ls-files -z backend frontend benchmark/holdout benchmark/final/report_final_v1.json benchmark/ambiguity/cache benchmark/real \
  | grep -zv -e '^backend/tests/' -e '^frontend/e2e/' | xargs -0 -I{} sh -c 'mkdir -p "$1/$(dirname "$2")" && cp "$2" "$1/$2"' _ "$OUT" {}
mkdir -p "$OUT/artifacts/runs"
for c in muse_cache sam_cache muse_layout_cache; do test -d "artifacts/$c" && cp -R "artifacts/$c" "$OUT/artifacts/"; done
cp -R artifacts/runs/. "$OUT/artifacts/runs/"
for r in benchmark/real/*/runs/*/; do cp -R "${r%/}" "$OUT/artifacts/runs/"; done
for r in docs/evidence/runs/*/; do test -e "$OUT/artifacts/runs/$(basename "$r")" || cp -R "${r%/}" "$OUT/artifacts/runs/"; done

cp deploy/vercel/Dockerfile.api "$OUT/Dockerfile"
cp deploy/vercel/vercel.json "$OUT/vercel.json"
touch "$OUT/.vercel-staged"
printf ".env*\n" > "$OUT/.vercelignore"
test ! -e "$OUT/backend/.env" || { echo "refusing: .env in stage" >&2; exit 1; }
echo "$OUT: $(du -sh "$OUT" | cut -f1), runs: $(ls "$OUT/artifacts/runs" | wc -l | tr -d ' ')"
