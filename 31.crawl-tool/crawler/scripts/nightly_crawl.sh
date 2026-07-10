#!/usr/bin/env bash
# Nightly crawl driver — invoked by launchd (see vn.mvillage.crawl-nightly.plist).
# Runs Agoda then Trip on the project venv, keeps the Mac awake for the duration, logs each
# run to logs/, and prunes to the 30 most recent logs. Safe to run by hand too:
#     bash crawler/scripts/nightly_crawl.sh
set -u

# resolve project root from this script's location (crawler/scripts/ -> ../..)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"      # fall back if the venv moved
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOGDIR/nightly_$STAMP.log"

# single-run lock (atomic mkdir) so an overlapping trigger never double-crawls
LOCK="$LOGDIR/.nightly.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date): another nightly run holds $LOCK — skipping" >>"$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

cd "$ROOT" || exit 1
{
  echo "=== nightly crawl START $(date) ==="
  echo "root=$ROOT"
  echo "python=$PY ($("$PY" -c 'import sys;print(sys.version.split()[0])' 2>/dev/null))"

  echo "--- AGODA $(date +%H:%M:%S) ---"
  caffeinate -i "$PY" run_agoda.py
  echo "agoda exit=$?"

  echo "--- TRIP $(date +%H:%M:%S) ---"
  caffeinate -i "$PY" run_trip.py
  echo "trip exit=$?"

  echo "=== nightly crawl DONE $(date) ==="
} >>"$LOG" 2>&1

# keep only the 30 most recent nightly logs
ls -1t "$LOGDIR"/nightly_*.log 2>/dev/null | tail -n +31 | while read -r f; do rm -f "$f"; done
