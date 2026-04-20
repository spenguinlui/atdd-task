#!/bin/bash
# Archive Claude Code telemetry logs with date range filename
# Usage: archive.sh

LOG_FILE="$HOME/claude-telemetry/logs.json"
# ARCHIVE_DIR can be overridden via env var (e.g. to a Google Drive synced path).
# Default: ~/claude-telemetry/archive
ARCHIVE_DIR="${CLAUDE_TELEMETRY_ARCHIVE_DIR:-$HOME/claude-telemetry/archive}"

if [ ! -f "$LOG_FILE" ]; then
  echo "ERROR: $LOG_FILE not found"
  exit 1
fi

if [ ! -s "$LOG_FILE" ]; then
  echo "ERROR: $LOG_FILE is empty, nothing to archive"
  exit 1
fi

mkdir -p "$ARCHIVE_DIR"

# Extract first and last timestamps from log
DATE_RANGE=$(python3 -c "
import json, sys

dates = []
with open('$LOG_FILE') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            # Check resourceLogs
            for rl in obj.get('resourceLogs', []):
                for sl in rl.get('scopeLogs', []):
                    for lr in sl.get('logRecords', []):
                        for a in lr.get('attributes', []):
                            if a['key'] == 'event.timestamp':
                                ts = a['value'].get('stringValue', '')
                                if ts:
                                    dates.append(ts[:10])
            # Check resourceMetrics
            for rm in obj.get('resourceMetrics', []):
                for sm in rm.get('scopeMetrics', []):
                    for m in sm.get('metrics', []):
                        for dp in m.get('sum', {}).get('dataPoints', []) + m.get('gauge', {}).get('dataPoints', []):
                            ts = dp.get('timeUnixNano', '')
                            if ts:
                                from datetime import datetime
                                d = datetime.utcfromtimestamp(int(ts) / 1e9).strftime('%Y-%m-%d')
                                dates.append(d)
        except:
            continue

if dates:
    dates.sort()
    print(f'{dates[0]}~{dates[-1]}')
else:
    from datetime import date
    print(f'{date.today().isoformat()}~{date.today().isoformat()}')
")

if [ -z "$DATE_RANGE" ]; then
  echo "ERROR: Could not determine date range"
  exit 1
fi

ARCHIVE_FILE="$ARCHIVE_DIR/${DATE_RANGE}.json"

# Handle duplicate filename
if [ -f "$ARCHIVE_FILE" ]; then
  i=1
  while [ -f "$ARCHIVE_DIR/${DATE_RANGE}_${i}.json" ]; do
    i=$((i + 1))
  done
  ARCHIVE_FILE="$ARCHIVE_DIR/${DATE_RANGE}_${i}.json"
fi

# Copy then truncate in place to preserve inode.
# The otelcol file exporter holds an open fd on logs.json; using `mv` would
# leave the collector writing to the archived file. Truncating preserves the
# inode so the collector keeps writing to the (now empty) logs.json.
cp "$LOG_FILE" "$ARCHIVE_FILE"
: > "$LOG_FILE"

LINE_COUNT=$(wc -l < "$ARCHIVE_FILE" | tr -d ' ')
FILE_SIZE=$(du -h "$ARCHIVE_FILE" | cut -f1 | tr -d ' ')

echo "OK|$ARCHIVE_FILE|$LINE_COUNT|$FILE_SIZE"
