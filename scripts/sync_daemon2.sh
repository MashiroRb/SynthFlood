#!/bin/bash
# Daemon v2: every 5 minutes run one guaranteed sync cycle (commit-first,
# rebase, retry push). Replaces sync_daemon.sh (which deadlocked when local
# changes existed at pull time).
ROOT=${SYNTHFLOOD_ROOT:-/root/synthflood}
while true; do
  bash "$ROOT/code/scripts/sync_now.sh"
  sleep 300
done
