#!/bin/bash
# Finalizer: the moment an experiment queue prints its DONE marker, force a
# full results upload (retried until GitHub accepts). Also leaves a marker.
QUEUE_LOG="$1"; MARK="$2"
while true; do
  [ -f "$MARK" ] && exit 0
  if grep -q "DONE" "$QUEUE_LOG" 2>/dev/null; then
    for i in 1 2 3 4 5 6 8; do
      bash /root/synthflood/code/scripts/sync_now.sh
      if tail -20 /root/sync_now.log 2>/dev/null | grep -q PUSH_OK; then
        touch "$MARK"
        echo "finalized $(date -u +%FT%TZ)" >> /root/sync_now.log
        exit 0
      fi
      sleep 30
    done
    exit 1
  fi
  sleep 60
done
