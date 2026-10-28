#!/bin/sh
# Package the recorded runs (and the cached model outputs they were produced with) for a showcase server.
# Usage: deploy/export_showcase.sh [run_id ...]   ->   showcase-data.tgz
# Never includes backend/.env or anything outside artifacts/.
set -eu
cd "$(dirname "$0")/.."
RUNS=${*:-20261028T023754Z-a922b5bb}
for r in $RUNS; do
  test -f "artifacts/runs/$r/evidence.json" || { echo "missing artifacts/runs/$r" >&2; exit 1; }
done
paths=""
for r in $RUNS; do paths="$paths runs/$r"; done
tar -czf showcase-data.tgz -C artifacts $paths muse_cache sam_cache
echo "showcase-data.tgz: $(du -h showcase-data.tgz | cut -f1) — runs: $RUNS"
echo "on the server: mkdir -p showcase-data && tar -xzf showcase-data.tgz -C showcase-data"
